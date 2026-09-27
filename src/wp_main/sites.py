import re
import secrets
from pathlib import Path

import typer

from .config import DEFAULT_DASHBOARD_PORT, MAIN_DIR, TEMPLATES_DIR, Site
from .runner import DevEnvError, Runner

PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
SECRET_PLACEHOLDER = "change-me"


def template_vars(site: Site) -> dict[str, str]:
    return {
        "SITE_ID": site.id,
        "DIR_NAME": site.dir_name,
        "WP_IMAGE": site.image,
        "DEBUG_PORT": str(site.debug_port),
        "DOMAIN": site.domain,
        "TITLE": site.title,
    }


def render_text(text: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            raise DevEnvError(f"テンプレート変数 {key} が未定義です")
        return variables[key]

    return PLACEHOLDER.sub(replace, text)


def render_site(site: Site, dest: Path, templates_dir: Path = TEMPLATES_DIR) -> list[Path]:
    variables = template_vars(site)
    written = []
    for src in sorted(templates_dir.rglob("*")):
        if src.is_dir():
            continue
        target = dest / src.relative_to(templates_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_text(src.read_text(), variables))
        written.append(target)
    return written


def is_empty_dir(path: Path) -> bool:
    return path.is_dir() and not any(path.iterdir())


def ensure_site_repo(runner: Runner, site: Site, root: Path) -> str:
    """戻り値は実施内容（"exists" / "cloned" / "scaffolded"）。"""
    path = root / site.dir_name
    if path.exists() and not is_empty_dir(path):
        if (path / ".git").exists():
            origin = runner.run(
                ["git", "-C", str(path), "remote", "get-url", "origin"], check=False, mutate=False
            ).stdout.strip()
            if origin == site.remote:
                return "exists"
        raise DevEnvError(
            f"{path} は既に存在し、{site.remote} の clone ではありません。"
            "中身を確認して移動または削除してから再実行してください。"
        )

    if is_empty_dir(path) and not runner.dry_run:
        path.rmdir()
    runner.run(["git", "clone", site.remote, str(path)])
    if runner.dry_run:
        return "cloned"

    if runner.ok(["git", "-C", str(path), "rev-parse", "--verify", "HEAD"]):
        return "cloned"

    typer.echo(f"  {site.remote} は空のため、テンプレートから初期化します")
    render_site(site, path)
    runner.run(["git", "-C", str(path), "add", "-A"])
    runner.run(
        ["git", "-C", str(path), "commit", "-m", f"chore: {site.dir_name} を wp-main テンプレートから初期化"]
    )
    return "scaffolded"


def parse_env(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def fill_secrets(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}={secrets.token_urlsafe(18)}"

    return re.sub(
        rf"^([A-Z0-9_]+)={re.escape(SECRET_PLACEHOLDER)}$", replace, text, flags=re.MULTILINE
    )


def ensure_env(runner: Runner, directory: Path) -> bool:
    env = directory / ".env"
    example = directory / ".env.example"
    if env.exists():
        return False
    if not example.exists():
        if runner.dry_run:
            typer.echo(f"[dry-run] {env} を生成")
            return True
        raise DevEnvError(f"{example} がありません")
    if runner.dry_run:
        typer.echo(f"[dry-run] {example} から {env} を生成")
        return True
    env.write_text(fill_secrets(example.read_text()))
    env.chmod(0o600)
    return True


def read_env(directory: Path) -> dict[str, str]:
    env = directory / ".env"
    return parse_env(env.read_text()) if env.exists() else {}


def dashboard_port(main_dir: Path = MAIN_DIR) -> int:
    value = read_env(main_dir).get("DASHBOARD_PORT", "")
    try:
        return int(value) if value else DEFAULT_DASHBOARD_PORT
    except ValueError as error:
        raise DevEnvError(f"{main_dir / '.env'} の DASHBOARD_PORT が数値ではありません: {value}") from error


def proxy_is_public(main_dir: Path = MAIN_DIR) -> bool:
    # docker-compose.yml の既定値と同じく、未設定はループバックとみなす
    return read_env(main_dir).get("PROXY_BIND_ADDRESS", "127.0.0.1") not in ("127.0.0.1", "")
