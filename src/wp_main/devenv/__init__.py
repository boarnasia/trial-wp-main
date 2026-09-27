import shutil
from collections.abc import Callable
from pathlib import Path

import typer
from django.core.management import call_command

from .. import health, hosts, power, versioning
from ..config import (
    CA_CERT_FILE,
    CADDY_IMAGE,
    CADDY_VOLUMES,
    DASHBOARD_DOMAIN,
    DB_NETWORK,
    LEGACY_DASHBOARD_CONTAINER,
    LEGACY_DASHBOARD_IMAGE,
    LEGACY_DASHBOARD_VOLUME,
    LOCAL_DIR,
    MAIN_DIR,
    MYSQL_IMAGE,
    MYSQL_VOLUME,
    NETWORK,
    PROXY_PORTS,
    SITES,
    STATE_FILE,
    WP_CLI_IMAGE,
    Site,
)
from ..docker import check_ports, compose, ensure_network, wait_for
from ..runner import DevEnvError, Runner
from ..sites import dashboard_port, ensure_env, ensure_site_repo, read_env
from ..trust import SYSTEM_KEYCHAIN, load_state, trust_caddy_ca, untrust


def step(title: str) -> None:
    typer.secho(f"==> {title}", fg=typer.colors.CYAN, bold=True)


def install_wordpress(runner: Runner, site: Site, root: Path) -> None:
    env = read_env(root / site.dir_name)
    wait_for(
        lambda: compose(
            runner, "exec", "-T", site.wordpress_service, "test", "-f", "/var/www/html/wp-config.php",
            check=False, mutate=False,
        ).returncode
        == 0,
        f"{site.wordpress_service} の wp-config.php 生成",
    )
    installed = compose(
        runner, "run", "--rm", "-T", "--quiet-pull", site.cli_service, "wp", "core", "is-installed",
        check=False, mutate=False,
    )
    if installed.returncode == 0:
        typer.echo(f"  {site.domain}: インストール済み")
        return
    compose(
        runner, "run", "--rm", "-T", "--quiet-pull", site.cli_service, "wp", "core", "install",
        f"--url=https://{site.domain}",
        f"--title={env.get('WP_TITLE', site.title)}",
        f"--admin_user={env.get('WP_ADMIN_USER', 'admin')}",
        f"--admin_password={env['WP_ADMIN_PASSWORD']}",
        f"--admin_email={env.get('WP_ADMIN_EMAIL', 'admin@example.com')}",
        "--skip-email",
    )


SERVE_COMMAND = "uv run manage.py serve --site=all"


def prepare_db(runner: Runner) -> None:
    if runner.dry_run:
        typer.echo("[dry-run] manage.py migrate")
        return
    call_command("migrate", verbosity=0, interactive=False)
    typer.echo("  最新のスキーマです")


def db_files() -> list[Path]:
    # テストで MAIN_DIR を差し替えたときに、実際の DB を消さないよう呼び出し時に求める
    db = MAIN_DIR / ".local" / "db.sqlite3"
    return [db, db.with_name("db.sqlite3-wal"), db.with_name("db.sqlite3-shm")]


def dashboard_running() -> bool:
    try:
        return health.probe_dashboard(dashboard_port(MAIN_DIR)) is None
    except DevEnvError:
        return False


def hosts_domains() -> list[str]:
    return [*(site.domain for site in SITES), DASHBOARD_DOMAIN]


HOOKS_PATH = ".githooks"


def git_hooks_path(runner: Runner) -> str:
    return runner.run(
        ["git", "-C", str(MAIN_DIR), "config", "--local", "--get", "core.hooksPath"], check=False, mutate=False
    ).stdout.strip()


def enable_hooks(runner: Runner) -> None:
    current = git_hooks_path(runner)
    if current == HOOKS_PATH:
        typer.echo("  設定済み")
        return
    if current:
        typer.secho(
            f"  core.hooksPath は {current} に設定されているため変更しません。"
            f"{MAIN_DIR / HOOKS_PATH} の post-merge と post-rewrite を {current} から呼び出してください",
            fg=typer.colors.YELLOW,
        )
        return
    runner.run(["git", "-C", str(MAIN_DIR), "config", "--local", "core.hooksPath", HOOKS_PATH])


def disable_hooks(runner: Runner) -> None:
    if git_hooks_path(runner) == HOOKS_PATH:
        runner.run(["git", "-C", str(MAIN_DIR), "config", "--local", "--unset", "core.hooksPath"])


def finish_version(runner: Runner, root: Path, fresh: bool) -> None:
    if runner.dry_run:
        return
    if fresh:
        versioning.record_latest()
        return
    message = versioning.outdated_message(root)
    if message:
        typer.secho(message, fg=typer.colors.YELLOW)


def install(runner: Runner, root: Path, *, start: bool, trust: bool) -> None:
    # 既存の環境に最新のバージョンを記録すると、未適用の migration が永久に実行されなくなる
    fresh = versioning.installed_version(root) is None

    step(f"サイトリポジトリを準備 (root: {root})")
    for site in SITES:
        result = ensure_site_repo(runner, site, root)
        typer.echo(f"  {site.dir_name}: {result}")

    step(".env を生成")
    for directory in (MAIN_DIR, *(root / site.dir_name for site in SITES)):
        created = ensure_env(runner, directory)
        typer.echo(f"  {directory / '.env'}: {'生成' if created else '既存のため維持'}")

    step("ダッシュボードの DB（django:migration）")
    prepare_db(runner)

    step(f"Docker ネットワーク {NETWORK}")
    typer.echo("  作成" if ensure_network(runner) else "  既存")

    step(f"wp-main の git フック（core.hooksPath = {HOOKS_PATH}）")
    enable_hooks(runner)

    step("/etc/hosts にエントリを登録（sudo）")
    new_hosts = hosts.with_block(hosts.HOSTS_FILE.read_text(), hosts_domains())
    typer.echo("  更新" if hosts.write_hosts(runner, new_hosts) else "  変更なし")

    if not start:
        finish_version(runner, root, fresh)
        typer.echo("--no-start のため起動・WordPress の初期セットアップ・CA 登録を省略しました")
        typer.echo(f"開発は別の端末で始めてください: {SERVE_COMMAND}")
        return

    step("共有インフラ（プロキシ・MySQL）を起動")
    check_ports(runner, PROXY_PORTS)
    power.start_infra(runner, MAIN_DIR)

    if runner.dry_run:
        typer.echo("[dry-run] WordPress の初期セットアップと CA 登録は省略")
        return

    step("WordPress の初期セットアップ")
    for site in SITES:
        # サイトは開発セッションの外では動かさないので、セットアップの間だけ起動する
        power.start(runner, site, root, MAIN_DIR)
        try:
            install_wordpress(runner, site, root)
        finally:
            power.stop(runner, site, root, MAIN_DIR)

    step("Caddy ローカル CA を System キーチェーンに登録（sudo）")
    if trust:
        typer.echo(f"  SHA-1: {trust_caddy_ca(runner)}")
    else:
        typer.echo(
            "  --skip-trust のため省略しました。手動で登録する場合:\n"
            f"    docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt {CA_CERT_FILE}\n"
            f"    sudo security add-trusted-cert -d -r trustRoot -k {SYSTEM_KEYCHAIN} {CA_CERT_FILE}"
        )

    finish_version(runner, root, fresh)
    typer.secho("\n完了しました。", fg=typer.colors.GREEN, bold=True)
    for site in SITES:
        env = read_env(root / site.dir_name)
        typer.echo(
            f"  https://{site.domain}/  (管理者: {env.get('WP_ADMIN_USER')} / パスワードは {root / site.dir_name / '.env'})"
        )
    typer.echo(f"\n開発セッション（サイトとダッシュボード https://{DASHBOARD_DOMAIN}/）は別の端末で始めてください:\n  {SERVE_COMMAND}")


def unsaved_changes(runner: Runner, path: Path) -> list[str]:
    if not (path / ".git").exists():
        return []
    problems = []
    status = runner.run(["git", "-C", str(path), "status", "--porcelain"], mutate=False, check=False)
    if status.stdout.strip():
        problems.append("未コミットの変更")
    unpushed = runner.run(
        ["git", "-C", str(path), "log", "--branches", "--not", "--remotes", "--oneline"],
        mutate=False, check=False,
    )
    if unpushed.stdout.strip():
        problems.append(f"未 push のコミット {len(unpushed.stdout.strip().splitlines())} 件")
    return problems


def uninstall(runner: Runner, root: Path, *, assume_yes: bool) -> None:
    site_dirs = [root / site.dir_name for site in SITES]
    state = load_state()

    typer.echo("次のリソースを削除します:")
    for path in site_dirs:
        typer.echo(f"  - {path}")
    typer.echo(f"  - コンテナ・ボリューム（共有 MySQL のデータ {MYSQL_VOLUME} を含む）・イメージ、ネットワーク {NETWORK}・{DB_NETWORK}")
    typer.echo("  - /etc/hosts の wp-dev-env ブロック")
    if state.get("ca_sha1"):
        typer.echo(f"  - System キーチェーンの Caddy ローカル CA ({state['ca_sha1']})")

    typer.echo(f"  - ダッシュボードの DB（{db_files()[0]}）")
    if dashboard_running():
        typer.secho("警告: uv run manage.py serve が動いています。先に Ctrl-C で止めてください。", fg=typer.colors.YELLOW)

    for path in site_dirs:
        for problem in unsaved_changes(runner, path):
            typer.secho(f"警告: {path} に{problem}があります。削除すると失われます。", fg=typer.colors.YELLOW)

    if not assume_yes and not typer.confirm("削除を実行しますか？", default=False):
        typer.echo("中止しました。")
        raise typer.Exit(1)

    failures: list[str] = []

    def attempt(title: str, action: Callable[[], None]) -> None:
        step(title)
        try:
            action()
        except (DevEnvError, OSError) as error:
            typer.secho(f"  失敗: {error}", fg=typer.colors.RED)
            failures.append(title)

    def stop_containers() -> None:
        compose(runner, "down", "--volumes", "--remove-orphans", check=False)
        # 旧構成（コンテナのダッシュボード、サイトごとの DB）の環境では、compose の定義から外れて残る
        legacy = [LEGACY_DASHBOARD_CONTAINER, *(site.legacy_db_container for site in SITES)]
        for name in legacy:
            if runner.ok(["docker", "container", "inspect", name]):
                runner.run(["docker", "rm", "-f", name])

    def remove_volumes() -> None:
        names = [*CADDY_VOLUMES, MYSQL_VOLUME, LEGACY_DASHBOARD_VOLUME, *(volume for site in SITES for volume in site.volumes)]
        existing = [name for name in names if runner.ok(["docker", "volume", "inspect", name])]
        if existing:
            runner.run(["docker", "volume", "rm", *existing])

    def remove_images() -> None:
        images = {CADDY_IMAGE, MYSQL_IMAGE, WP_CLI_IMAGE, LEGACY_DASHBOARD_IMAGE}
        for site, path in zip(SITES, site_dirs):
            images.add(read_env(path).get("WP_IMAGE", site.image))
        for image in sorted(images):
            if runner.ok(["docker", "image", "inspect", image]):
                result = runner.run(["docker", "image", "rm", image], check=False, capture=True)
                if result.returncode != 0:
                    typer.echo(f"  {image} は使用中のため残します")

    def remove_network() -> None:
        for name in (NETWORK, DB_NETWORK):
            if runner.ok(["docker", "network", "inspect", name]):
                runner.run(["docker", "network", "rm", name])

    def remove_ca() -> None:
        if state.get("ca_sha1"):
            untrust(runner, state["ca_sha1"])

    def remove_hosts() -> None:
        hosts.write_hosts(runner, hosts.strip_block(hosts.HOSTS_FILE.read_text()))

    def remove_dirs() -> None:
        for path in site_dirs:
            if path.exists():
                typer.echo(f"  rm -rf {path}")
                if not runner.dry_run:
                    shutil.rmtree(path)

    def remove_local_files() -> None:
        for path in (STATE_FILE, CA_CERT_FILE, MAIN_DIR / ".env", *db_files()):
            if path.exists():
                typer.echo(f"  rm {path}")
                if not runner.dry_run:
                    path.unlink()
        locks = MAIN_DIR / ".local" / "locks"
        if locks.exists():
            typer.echo(f"  rm -rf {locks}")
            if not runner.dry_run:
                shutil.rmtree(locks)

    attempt("コンテナを停止・削除", stop_containers)
    attempt("ボリュームを削除", remove_volumes)
    attempt("イメージを削除", remove_images)
    attempt(f"ネットワーク {NETWORK}・{DB_NETWORK} を削除", remove_network)
    attempt("Caddy ローカル CA の信頼を解除（sudo）", remove_ca)
    attempt("/etc/hosts のエントリを削除（sudo）", remove_hosts)
    attempt("wp-main の git フックの設定を解除", lambda: disable_hooks(runner))
    attempt("サイトディレクトリを削除", remove_dirs)
    attempt(f"{LOCAL_DIR} の状態ファイルと .env を削除", remove_local_files)

    if hosts.BACKUP_FILE.exists():
        typer.echo(
            f"\n{hosts.BACKUP_FILE} は復旧用に残しています。"
            f"/etc/hosts に問題がなければ削除してください:\n  sudo rm {hosts.BACKUP_FILE}"
        )

    if failures:
        typer.secho(f"\n失敗したステップ: {', '.join(failures)}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    typer.secho("\nアンインストールが完了しました。", fg=typer.colors.GREEN, bold=True)
