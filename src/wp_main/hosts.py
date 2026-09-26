import tempfile
from pathlib import Path

from .runner import DevEnvError, Runner

HOSTS_FILE = Path("/etc/hosts")
BACKUP_FILE = Path("/etc/hosts.wp-dev-env.bak")
BEGIN = "# >>> wp-dev-env >>>"
END = "# <<< wp-dev-env <<<"


def strip_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    kept: list[str] = []
    inside = False
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped == BEGIN:
            if inside:
                raise DevEnvError(f"{number} 行目: {BEGIN} が閉じられる前に再び現れました")
            inside = True
            continue
        if stripped == END:
            if not inside:
                raise DevEnvError(f"{number} 行目: 対応する {BEGIN} がない {END} があります")
            inside = False
            continue
        if not inside:
            kept.append(line)
    # 終了マーカーが欠けたまま除去すると、開始マーカー以降の無関係な行まで消してしまう
    if inside:
        raise DevEnvError(f"{END} がありません。/etc/hosts を手動で確認してください")
    return "".join(kept)


def with_block(text: str, domains: list[str], ip: str = "127.0.0.1") -> str:
    base = strip_block(text)
    if base and not base.endswith("\n"):
        base += "\n"
    block = [BEGIN, *(f"{ip}\t{domain}" for domain in domains), END]
    return base + "\n".join(block) + "\n"


def write_hosts(
    runner: Runner, new_text: str, path: Path | None = None, backup: Path | None = None
) -> bool:
    path = path or HOSTS_FILE
    backup = backup or BACKUP_FILE
    if path.read_text() == new_text:
        return False
    # /etc/hosts は root 所有なので、一時ファイル経由で sudo cp して権限と所有者を維持する
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".hosts") as tmp:
        tmp.write(new_text)
    try:
        runner.run(["sudo", "cp", "-p", str(path), str(backup)])
        runner.run(["sudo", "cp", tmp.name, str(path)])
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    runner.run(["dscacheutil", "-flushcache"], check=False)
    runner.run(["sudo", "killall", "-HUP", "mDNSResponder"], check=False)
    return True
