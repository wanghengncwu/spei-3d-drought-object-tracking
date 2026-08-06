import subprocess
import sys
from pathlib import Path


def test_verify_release_help_is_available() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_release.py", "--help"],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Verify repository checks and Python build artifacts" in result.stdout
