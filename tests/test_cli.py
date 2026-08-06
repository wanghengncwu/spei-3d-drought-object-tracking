from pathlib import Path

from spei3d.cli import main


def test_cli_help_lists_commands(capsys) -> None:
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    output = capsys.readouterr().out
    assert "extract" in output
    assert "sensitivity" in output
    assert "validate-config" in output


def test_validate_config_command_reports_success(tmp_path: Path, capsys) -> None:
    path = tmp_path / "config.yml"
    path.write_text(
        """
input:
  spei: data/spei06.nc
  dataset_name: test
output:
  root: outputs
""",
        encoding="utf-8",
    )
    assert main(["validate-config", "--config", str(path)]) == 0
    assert "Configuration is valid" in capsys.readouterr().out


def test_cli_reports_software_version(capsys) -> None:
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "spei3d 1.0.0" in capsys.readouterr().out
