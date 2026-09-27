import os
import shutil
import subprocess
from pathlib import Path

import pytest

from wp_main.config import MAIN_DIR

DIST = MAIN_DIR / "src" / "wp_main" / "dashboard" / "static" / "dist"

pytestmark = pytest.mark.skipif(
    shutil.which("bun") is None or not (MAIN_DIR / "node_modules").exists(),
    reason="bun と node_modules（bun install）がある環境でだけ確かめる",
)


def test_dist_matches_sources(tmp_path: Path):
    """ビルドの成果物は git で配るため、ソースを変えたらビルドし直してコミットしたかを確かめる。"""
    out = tmp_path / "dist"
    subprocess.run(
        ["bun", "run", "build"], cwd=MAIN_DIR, check=True, capture_output=True,
        env=os.environ | {"DASHBOARD_OUT_DIR": str(out)},
    )
    built = sorted(path.name for path in out.iterdir())
    assert built == sorted(path.name for path in DIST.iterdir())
    for name in built:
        assert (out / name).read_bytes() == (DIST / name).read_bytes(), f"{name} が古い。bun run build を実行してコミットする"
