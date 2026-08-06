import subprocess
import sys
from pathlib import Path


def run_audit(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/audit_release.py", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_release_audit_accepts_clean_minimal_tree(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = run_audit(tmp_path)
    assert result.returncode == 0
    assert "Release audit passed" in result.stdout


def test_release_audit_detects_machine_specific_path(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text(
        "DATA = r'C:\\Users\\researcher\\data.nc'\n", encoding="utf-8"
    )
    result = run_audit(tmp_path)
    assert result.returncode == 1
    assert "absolute Windows path" in result.stdout


def test_release_audit_detects_cache_and_binary_artifacts(tmp_path: Path) -> None:
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "module.pyc").write_bytes(b"binary")
    (tmp_path / "preview.png").write_bytes(b"image")
    result = run_audit(tmp_path)
    assert result.returncode == 1
    assert "cache directory" in result.stdout
    assert "binary or non-code artifact" in result.stdout


def test_release_audit_detects_packaging_artifacts(tmp_path: Path) -> None:
    artifact = tmp_path / "package.egg-info"
    artifact.mkdir()
    (artifact / "PKG-INFO").write_text("generated\n", encoding="utf-8")
    result = run_audit(tmp_path)
    assert result.returncode == 1
    assert "generated build directory" in result.stdout


def test_release_audit_detects_data_artifacts_and_secret_tokens(tmp_path: Path) -> None:
    (tmp_path / "sample.nc").write_bytes(b"netcdf")
    (tmp_path / "credentials.txt").write_text(
        "token=github_pat_1234567890abcdefghijklmnopqrstuvwxyz\n",
        encoding="utf-8",
    )
    result = run_audit(tmp_path)
    assert result.returncode == 1
    assert "data artifact" in result.stdout
    assert "credential-like secret" in result.stdout


def test_release_audit_detects_environment_files_and_generated_outputs(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("KEY=value\n", encoding="utf-8")
    output = tmp_path / "outputs"
    output.mkdir()
    (output / "events_table.csv").write_text("event_id\n1\n", encoding="utf-8")
    result = run_audit(tmp_path)
    assert result.returncode == 1
    assert "environment file" in result.stdout
    assert "generated output directory" in result.stdout
