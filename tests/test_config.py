from pathlib import Path

import pytest

from spei3d.config import ConfigError, load_config


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_config_applies_baseline_defaults(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
input:
  spei: data/spei06.nc
  dataset_name: CRU-TS
output:
  root: outputs/baseline
""",
    )
    cfg = load_config(path)
    assert cfg.input.variable == "spei"
    assert cfg.event_definition.spei_threshold == -1.0
    assert cfg.event_definition.connectivity == 8
    assert cfg.event_definition.minimum_monthly_patch_area_km2 == 25000.0
    assert cfg.event_definition.minimum_duration_months == 3
    assert cfg.event_definition.minimum_peak_area_km2 == 50000.0
    assert cfg.linking.rule == "maximum_overlap"
    assert cfg.runtime.write_labels is False
    assert cfg.runtime.hash_inputs is False


def test_invalid_positive_drought_threshold_is_rejected(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
input:
  spei: data/spei06.nc
  dataset_name: test
output:
  root: outputs/test
event_definition:
  spei_threshold: 0.5
""",
    )
    with pytest.raises(ConfigError, match="spei_threshold"):
        load_config(path)


def test_sensitivity_scale_requires_matching_input(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
input:
  spei: data/spei06.nc
  dataset_name: test
output:
  root: outputs/test
sensitivity:
  accumulation_scales: [3, 6, 12]
  scale_inputs:
    6: data/spei06.nc
""",
    )
    with pytest.raises(ConfigError, match="scale_inputs"):
        load_config(path)


def test_example_configs_do_not_contain_absolute_paths() -> None:
    for path in Path("configs").glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        assert ":\\" not in text
        assert "/home/" not in text
        assert "/Users/" not in text
