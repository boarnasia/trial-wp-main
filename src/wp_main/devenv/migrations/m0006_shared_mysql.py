import typer

from ... import power
from ...config import MYSQL_CONTAINER, MYSQL_IMAGE, SITES, Site
from ...docker import wait_for
from ...runner import DevEnvError
from ...sites import parse_env, read_env
from ._env import add_secret

VERSION = 6
DESCRIPTION = "サイトごとの MySQL を共有 MySQL（1 台、サイトごとの schema）に移し、旧 DB のコンテナとボリュームを片付ける"
REQUIRES_SUDO = False
# 旧ボリュームは、写したテーブルと行数が一致したときだけ消すので、データは失われない
DESTRUCTIVE = False
LOSES = ""
DB_USER_DEFAULT = "wordpress"
START_TIMEOUT_SECONDS = 120


def add_setting(ctx, key: str, value: str) -> None:
    env = ctx.main_dir / ".env"
    if not env.exists() or parse_env(env.read_text()).get(key):
        return
    if ctx.runner.dry_run:
        typer.echo(f"[dry-run] {env} に {key} を追加")
        return
    text = env.read_text()
    separator = "" if not text or text.endswith("\n") else "\n"
    env.write_text(f"{text}{separator}{key}={value}\n")
    typer.echo(f"  {key}: 追加")


def query(ctx, container: str, password: str, sql: str, database: str | None = None) -> list[list[str]]:
    # パスワードはコマンドラインに出さず、docker exec -e で環境変数から渡す
    args = ["docker", "exec", "-e", "MYSQL_PWD", container, "mysql", "-uroot", "-N", "-B", "-e", sql]
    result = ctx.runner.run([*args, *([database] if database else [])], mutate=False, env={"MYSQL_PWD": password})
    return [line.split("\t") for line in result.stdout.splitlines() if line]


def table_rows(ctx, container: str, password: str, database: str) -> dict[str, int]:
    tables = [row[0] for row in query(
        ctx, container, password,
        "SELECT table_name FROM information_schema.tables "
        f"WHERE table_schema = '{database}' AND table_type = 'BASE TABLE' ORDER BY table_name",
    )]
    if not tables:
        return {}
    counts = " UNION ALL ".join(f"SELECT '{table}', COUNT(*) FROM `{table}`" for table in tables)
    return {name: int(count) for name, count in query(ctx, container, password, counts, database)}


def differences(source: dict[str, int], copied: dict[str, int]) -> list[str]:
    return [
        f"{table}（旧 {source.get(table, 'なし')} / 新 {copied.get(table, 'なし')}）"
        for table in sorted(source.keys() | copied.keys())
        if source.get(table) != copied.get(table)
    ]


def migrate_site(ctx, site: Site, root_password: str) -> None:
    runner = ctx.runner
    volume = site.legacy_db_volume
    if not runner.ok(["docker", "volume", "inspect", volume]):
        typer.echo(f"  {site.id}: {volume} がないため、写すものはありません")
        return
    old_env = read_env(ctx.root / site.dir_name)
    old_password = old_env.get("MYSQL_ROOT_PASSWORD", "")
    old_database = old_env.get("MYSQL_DATABASE", "wordpress")
    if not old_password:
        raise DevEnvError(f"{ctx.root / site.dir_name / '.env'} に MYSQL_ROOT_PASSWORD がないため、{volume} を読めません")
    if not power.SCHEMA_NAME.match(old_database):
        raise DevEnvError(f"{ctx.root / site.dir_name / '.env'} の MYSQL_DATABASE に使えない文字があります: {old_database}")
    schema = power.schema_name(site, ctx.root)
    if runner.dry_run:
        typer.echo(f"[dry-run] {volume} の {old_database} を共有 MySQL の {schema} に写し、確認してから {volume} を削除")
        return

    if table_rows(ctx, MYSQL_CONTAINER, root_password, schema):
        raise DevEnvError(f"共有 MySQL の {schema} に既にテーブルがあるため、上書きしません。{volume} は残しています")

    temp = f"{site.id}-db-migrate"
    runner.run(["docker", "rm", "-f", temp], check=False, capture=True)
    # 初期化済みのデータディレクトリなので、root のパスワードを渡さなくても起動する
    runner.run(["docker", "run", "-d", "--name", temp, "-v", f"{volume}:/var/lib/mysql", MYSQL_IMAGE], capture=True)
    try:
        wait_for(
            lambda: runner.ok(["docker", "exec", temp, "mysqladmin", "ping", "-h", "127.0.0.1", "--silent"]),
            f"{volume} の旧 DB の起動", timeout=START_TIMEOUT_SECONDS,
        )
        power.ensure_schema(runner, site, ctx.root)
        runner.run(
            ["bash", "-o", "pipefail", "-c",
             f'MYSQL_PWD="$OLD_PASSWORD" docker exec -e MYSQL_PWD {temp} '
             f"mysqldump -uroot --single-transaction --routines --triggers --no-tablespaces {old_database} "
             f'| MYSQL_PWD="$NEW_PASSWORD" docker exec -i -e MYSQL_PWD {MYSQL_CONTAINER} mysql -uroot {schema}'],
            capture=True, env={"OLD_PASSWORD": old_password, "NEW_PASSWORD": root_password},
        )
        source = table_rows(ctx, temp, old_password, old_database)
        copied = table_rows(ctx, MYSQL_CONTAINER, root_password, schema)
    finally:
        runner.run(["docker", "rm", "-f", temp], check=False, capture=True)
    mismatched = differences(source, copied)
    if mismatched:
        raise DevEnvError(f"{site.id} の写した内容が一致しません: {', '.join(mismatched)}。{volume} は残しています")
    runner.run(["docker", "volume", "rm", volume])
    typer.echo(f"  {site.id}: {len(source)} テーブルを {schema} に写しました")


def up(ctx) -> None:
    runner = ctx.runner
    add_setting(ctx, "DB_USER", DB_USER_DEFAULT)
    add_secret(ctx, "DB_PASSWORD")
    add_secret(ctx, "DB_ROOT_PASSWORD")

    # 旧構成のコンテナは restart: unless-stopped を持ち、旧 DB に接続する設定のまま残るので作り直させる
    for site in SITES:
        for name in (site.wordpress_service, site.legacy_db_container):
            if runner.ok(["docker", "container", "inspect", name]):
                runner.run(["docker", "rm", "-f", name])

    power.start_infra(runner, ctx.main_dir)
    root_password = read_env(ctx.main_dir).get("DB_ROOT_PASSWORD", "")
    for site in SITES:
        migrate_site(ctx, site, root_password)
    typer.secho("  開発セッションは別の端末で始めてください: uv run manage.py serve --site=all", fg=typer.colors.CYAN)
