import subprocess
import sys

import pytest

from wp_main.cli.legacy import replacement


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["dev-env:check-health", "--json"], "uv run manage.py devenv check-health --json"),
        (["dev-env:migrate", "--auto"], "uv run manage.py devenv migrate --auto"),
        (["version"], "uv run manage.py devenv version"),
        (["help"], "uv run manage.py help devenv"),
        ([], "uv run manage.py help devenv"),
    ],
)
def test_replacement(args, expected):
    assert replacement(args) == expected


def test_legacy_cli_only_guides():
    result = subprocess.run(
        [sys.executable, "-c", "from wp_main.cli.legacy import main; main()", "dev-env:check-health"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert "uv run manage.py devenv check-health" in result.stderr
