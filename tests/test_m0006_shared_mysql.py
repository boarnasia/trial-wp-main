from pathlib import Path

import pytest

from wp_main import versioning
from wp_main.devenv.migrations import m0006_shared_mysql
from wp_main.runner import DevEnvError
from wp_main.sites import parse_env
from wp_main.versioning import MigrationContext


@pytest.fixture
def dirs(tmp_path: Path, monkeypatch):
    main = tmp_path / "wp-main"
    main.mkdir()
    (main / ".env").write_text("WP1_DOMAIN=local.wp1.yamashita109.com\n")
    for site_id in ("wp1", "wp2"):
        (tmp_path / f"wp-{site_id}").mkdir()
        (tmp_path / f"wp-{site_id}" / ".env").write_text(
            "MYSQL_DATABASE=wordpress\nMYSQL_ROOT_PASSWORD=old-root-secret\n"
        )
    monkeypatch.setattr(m0006_shared_mysql, "wait_for", lambda check, what, timeout: check())
    return tmp_path, main


def legacy(*, volumes=("wp1-db-data",), source=None, copied=None, existing=None):
    """旧 DB と共有 MySQL の問い合わせに答える。source / copied / existing はテーブルごとの行数。"""
    source = {"wp_posts": 3, "wp_options": 10} if source is None else source
    copied = source if copied is None else copied
    imported = {"done": False}

    def rows(counts: dict[str, int], sql: str) -> str:
        if "information_schema" in sql:
            return "".join(f"{name}\n" for name in sorted(counts))
        return "".join(f"{name}\t{count}\n" for name, count in counts.items())

    def respond(args):
        if args[:3] == ["docker", "volume", "inspect"]:
            return (0 if args[3] in volumes else 1), ""
        if args[:3] == ["docker", "container", "inspect"]:
            return 1, ""
        if args[0] == "bash":
            imported["done"] = True
            return 0, ""
        if args[:2] == ["docker", "exec"] and "mysql" in args:
            container, sql = args[4], args[args.index("-e", 5) + 1]
            if container.endswith("-db-migrate"):
                return 0, rows(source, sql)
            counts = copied if imported["done"] else (existing or {})
            return 0, rows(counts, sql)
        return 0, ""

    return respond


def run(fake_runner, dirs, **kwargs):
    root, main = dirs
    runner = fake_runner(legacy(**kwargs))
    m0006_shared_mysql.up(MigrationContext(runner, root, main, ()))
    return runner


def test_is_auto_runnable():
    assert not m0006_shared_mysql.REQUIRES_SUDO and not m0006_shared_mysql.DESTRUCTIVE
    assert m0006_shared_mysql in versioning.discover()


def test_copies_verifies_then_removes_volume(fake_runner, dirs):
    runner = run(fake_runner, dirs)
    [pipe] = runner.mutating(["bash"])
    assert "mysqldump" in pipe[-1] and "wp1-db-migrate" in pipe[-1] and "mysql -uroot wp1" in pipe[-1]
    assert runner.mutating(["docker", "volume", "rm"]) == [["docker", "volume", "rm", "wp1-db-data"]]
    assert ["docker", "rm", "-f", "wp1-db-migrate"] in runner.calls
    # wp2 はボリュームがないので何もしない
    assert not [call for call in runner.calls if "wp2-db-migrate" in call]


def test_passwords_never_on_command_line(fake_runner, dirs):
    root, main = dirs
    runner = run(fake_runner, dirs)
    new_password = parse_env((main / ".env").read_text())["DB_ROOT_PASSWORD"]
    for call in runner.calls:
        assert "old-root-secret" not in " ".join(call) and new_password not in " ".join(call)
    assert {"OLD_PASSWORD": "old-root-secret", "NEW_PASSWORD": new_password} in runner.envs


def test_mismatch_keeps_volume(fake_runner, dirs):
    with pytest.raises(DevEnvError, match="wp_posts（旧 3 / 新 2）.*wp1-db-data は残しています"):
        run(fake_runner, dirs, copied={"wp_posts": 2, "wp_options": 10})


def test_mismatch_removes_temp_container_but_not_volume(fake_runner, dirs):
    root, main = dirs
    runner = fake_runner(legacy(copied={"wp_posts": 2, "wp_options": 10}))
    with pytest.raises(DevEnvError):
        m0006_shared_mysql.up(MigrationContext(runner, root, main, ()))
    assert ["docker", "rm", "-f", "wp1-db-migrate"] in runner.calls
    assert not runner.mutating(["docker", "volume", "rm"])


def test_existing_tables_are_not_overwritten(fake_runner, dirs):
    root, main = dirs
    runner = fake_runner(legacy(existing={"wp_posts": 1}))
    with pytest.raises(DevEnvError, match="既にテーブルがある"):
        m0006_shared_mysql.up(MigrationContext(runner, root, main, ()))
    assert not runner.mutating(["bash"]) and not runner.mutating(["docker", "volume", "rm"])


def test_rerun_without_volumes_changes_nothing(fake_runner, dirs):
    runner = run(fake_runner, dirs, volumes=())
    assert not runner.mutating(["bash"]) and not runner.mutating(["docker", "volume", "rm"])
    assert runner.mutating(["docker", "compose", "up"])


def test_db_settings_are_added_once(fake_runner, dirs):
    root, main = dirs
    run(fake_runner, dirs, volumes=())
    first = parse_env((main / ".env").read_text())
    assert first["DB_USER"] == "wordpress" and first["DB_PASSWORD"] and first["DB_ROOT_PASSWORD"]
    run(fake_runner, dirs, volumes=())
    assert parse_env((main / ".env").read_text()) == first


def test_sites_stay_stopped_after_migration(fake_runner, dirs):
    runner = run(fake_runner, dirs)
    ups = runner.mutating(["docker", "compose", "up"])
    assert ups == [["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "120", "caddy", "mysql"]]
    # 開発セッションの外なので、起動した共有インフラも止める
    assert runner.mutating(["docker", "compose", "down"]) == [["docker", "compose", "down", "--remove-orphans"]]


def test_infra_stays_in_session(fake_runner, dirs, monkeypatch):
    from wp_main import session

    monkeypatch.setattr(session, "is_running", lambda path=None: True)
    runner = run(fake_runner, dirs)
    assert not runner.mutating(["docker", "compose", "down"])


def test_infra_stops_even_when_migration_fails(fake_runner, dirs):
    root, main = dirs
    runner = fake_runner(legacy(copied={"wp_posts": 2, "wp_options": 10}))
    with pytest.raises(DevEnvError):
        m0006_shared_mysql.up(MigrationContext(runner, root, main, ()))
    assert runner.mutating(["docker", "compose", "down"])
