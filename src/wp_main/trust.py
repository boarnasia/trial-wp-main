import base64
import hashlib
import json
import re

from .config import CA_CERT_FILE, CADDY_ROOT_CERT, CADDY_SERVICE, LOCAL_DIR, STATE_FILE
from .docker import compose, wait_for
from .runner import Runner

SYSTEM_KEYCHAIN = "/Library/Keychains/System.keychain"


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def update_state(**values) -> dict:
    # CA の SHA-1 と環境バージョンを別々の処理が書くため、読み直してから既存のキーに重ねる
    state = {**load_state(), **values}
    LOCAL_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    return state


def pem_sha1(pem: str) -> str:
    body = re.search(r"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", pem, re.S)
    if not body:
        raise ValueError("PEM 証明書ではありません")
    return hashlib.sha1(base64.b64decode("".join(body.group(1).split()))).hexdigest().upper()


def export_root_cert(runner: Runner) -> str:
    wait_for(
        lambda: compose(
            runner, "exec", "-T", CADDY_SERVICE, "test", "-f", CADDY_ROOT_CERT, check=False, mutate=False
        ).returncode
        == 0,
        "Caddy のルート証明書の生成",
        timeout=60,
    )
    LOCAL_DIR.mkdir(exist_ok=True)
    compose(runner, "cp", f"{CADDY_SERVICE}:{CADDY_ROOT_CERT}", str(CA_CERT_FILE), mutate=False)
    return CA_CERT_FILE.read_text()


def untrust(runner: Runner, sha1: str) -> None:
    runner.run(["sudo", "security", "delete-certificate", "-Z", sha1, SYSTEM_KEYCHAIN])


def trust_caddy_ca(runner: Runner) -> str:
    state = load_state()
    sha1 = pem_sha1(export_root_cert(runner))
    if state.get("ca_sha1") == sha1:
        return sha1
    # caddy_data ボリュームが作り直されると CA も変わるため、古い証明書を残さない
    if state.get("ca_sha1"):
        runner.run(
            ["sudo", "security", "delete-certificate", "-Z", state["ca_sha1"], SYSTEM_KEYCHAIN],
            check=False,
        )
    runner.run(
        ["sudo", "security", "add-trusted-cert", "-d", "-r", "trustRoot", "-k", SYSTEM_KEYCHAIN, str(CA_CERT_FILE)]
    )
    if not runner.dry_run:
        update_state(ca_sha1=sha1)
    return sha1
