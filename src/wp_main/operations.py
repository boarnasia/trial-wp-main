import json
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import typer

from .config import CA_CERT_FILE, CADDY_ROOT_CERT, CADDY_SERVICE, DASHBOARD_DOMAIN, LOCAL_DIR, MAIN_DIR
from .runner import Runner
from .sites import SECRET_PLACEHOLDER, read_env

API_URL = f"https://{DASHBOARD_DOMAIN}/api/operations"
TOKEN_KEY = "DASHBOARD_API_TOKEN"
TIMEOUT_SECONDS = 3


class ApiError(Exception):
    pass


def api_token(main_dir: Path = MAIN_DIR) -> str:
    token = read_env(main_dir).get(TOKEN_KEY, "")
    if not token or token == SECRET_PLACEHOLDER:
        raise ApiError(f"{main_dir / '.env'} に {TOKEN_KEY} がありません")
    return token


def ca_file(runner: Runner) -> Path:
    # キーチェーンを参照しない検証にするため、書き出した Caddy のルート証明書を使う（--skip-trust の環境でも通る）
    if not CA_CERT_FILE.exists():
        LOCAL_DIR.mkdir(exist_ok=True)
        result = runner.run(
            ["docker", "compose", "cp", f"{CADDY_SERVICE}:{CADDY_ROOT_CERT}", str(CA_CERT_FILE)],
            cwd=MAIN_DIR, check=False, mutate=False,
        )
        if result.returncode != 0 or not CA_CERT_FILE.exists():
            raise ApiError("Caddy のルート証明書を取得できません")
    return CA_CERT_FILE


def call_api(method: str, query: str = "", payload: dict | None = None, *, runner: Runner | None = None) -> tuple[int, object]:
    """ダッシュボードの操作履歴 API を呼び、ステータスコードと JSON を返す。接続できなければ ApiError。"""
    request = urllib.request.Request(
        API_URL + query,
        method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {api_token()}", "Content-Type": "application/json"},
    )
    context = ssl.create_default_context(cafile=str(ca_file(runner or Runner())))
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise ApiError(str(getattr(error, "reason", error))) from error


def send(payload: dict) -> None:
    status, _ = call_api("POST", payload=payload)
    if status != 201:
        raise ApiError(f"ダッシュボードが {status} を返しました")


def record(
    command: str,
    options: dict,
    started_at: datetime,
    finished_at: datetime,
    *,
    exit_code: int,
    succeeded: bool,
    summary: str,
    sender: Callable[[dict], None] | None = None,
) -> bool:
    """操作を記録する。失敗しても警告を出すだけで、呼び出し元の結果は変えない。"""
    payload = {
        "command": command,
        "options": {key: str(value) if isinstance(value, Path) else value for key, value in options.items()},
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "exit_code": exit_code,
        "succeeded": succeeded,
        "summary": summary,
    }
    try:
        (sender or send)(payload)
    except Exception as error:  # 記録は best effort。どんな失敗でも本来のコマンドを止めない
        typer.secho(f"警告: 操作履歴を記録できませんでした: {error}", fg=typer.colors.YELLOW, err=True)
        return False
    return True
