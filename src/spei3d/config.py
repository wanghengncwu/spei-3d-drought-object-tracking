"""YAML configuration models and validation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

LINK_RULES = {"maximum_overlap", "overlap_union", "maximum_iou"}


class ConfigError(ValueError):
    """Raised when a project configuration is internally inconsistent."""


@dataclass(frozen=True)
class InputConfig:
    spei: Path
    dataset_name: str
    variable: str = "spei"
    time_start: str | None = None
    time_end: str | None = None
    target_grid: Path | None = None
    land_mask: Path | None = None


@dataclass(frozen=True)
class OutputConfig:
    root: Path


@dataclass(frozen=True)
class EventDefinitionConfig:
    spei_threshold: float = -1.0
    connectivity: int = 8
    minimum_monthly_patch_area_km2: float = 25_000.0
    minimum_duration_months: int = 3
    minimum_peak_area_km2: float = 50_000.0


@dataclass(frozen=True)
class LinkingConfig:
    rule: str = "maximum_overlap"
    minimum_overlap_cells: int = 1
    minimum_iou: float = 0.10


@dataclass(frozen=True)
class RuntimeConfig:
    time_block_months: int = 12
    write_labels: bool = False
    overwrite: bool = False
    hash_inputs: bool = False


@dataclass(frozen=True)
class SensitivityConfig:
    baseline_scale_months: int = 6
    accumulation_scales: tuple[int, ...] = ()
    scale_inputs: dict[int, Path] = field(default_factory=dict)
    spei_thresholds: tuple[float, ...] = ()
    monthly_patch_areas_km2: tuple[float, ...] = ()
    minimum_durations_months: tuple[int, ...] = ()
    minimum_peak_areas_km2: tuple[float, ...] = ()
    linking_rules: tuple[LinkingConfig, ...] = ()


@dataclass(frozen=True)
class ProjectConfig:
    input: InputConfig
    output: OutputConfig
    event_definition: EventDefinitionConfig = field(default_factory=EventDefinitionConfig)
    linking: LinkingConfig = field(default_factory=LinkingConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    sensitivity: SensitivityConfig | None = None

    def with_output(self, root: Path) -> ProjectConfig:
        return replace(self, output=OutputConfig(root=root))


def _resolve_path(base: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a mapping")
    return value


def _linking_from_raw(raw: dict[str, Any]) -> LinkingConfig:
    return LinkingConfig(
        rule=str(raw.get("rule", "maximum_overlap")),
        minimum_overlap_cells=int(raw.get("minimum_overlap_cells", 1)),
        minimum_iou=float(raw.get("minimum_iou", 0.10)),
    )


def load_config(path: str | Path) -> ProjectConfig:
    """Load and validate a project configuration.

    Relative paths are resolved from the directory containing the YAML file.
    """

    config_path = Path(path).resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError("configuration root must be a mapping")
    base = config_path.parent

    input_raw = _section(raw, "input")
    output_raw = _section(raw, "output")
    if "spei" not in input_raw:
        raise ConfigError("input.spei is required")
    if not input_raw.get("dataset_name"):
        raise ConfigError("input.dataset_name is required")
    if "root" not in output_raw:
        raise ConfigError("output.root is required")

    input_cfg = InputConfig(
        spei=_resolve_path(base, input_raw["spei"]),  # type: ignore[arg-type]
        dataset_name=str(input_raw["dataset_name"]),
        variable=str(input_raw.get("variable", "spei")),
        time_start=input_raw.get("time_start"),
        time_end=input_raw.get("time_end"),
        target_grid=_resolve_path(base, input_raw.get("target_grid")),
        land_mask=_resolve_path(base, input_raw.get("land_mask")),
    )
    output_cfg = OutputConfig(
        root=_resolve_path(base, output_raw["root"])  # type: ignore[arg-type]
    )

    event_raw = _section(raw, "event_definition")
    event_cfg = EventDefinitionConfig(
        spei_threshold=float(event_raw.get("spei_threshold", -1.0)),
        connectivity=int(event_raw.get("connectivity", 8)),
        minimum_monthly_patch_area_km2=float(
            event_raw.get("minimum_monthly_patch_area_km2", 25_000.0)
        ),
        minimum_duration_months=int(event_raw.get("minimum_duration_months", 3)),
        minimum_peak_area_km2=float(event_raw.get("minimum_peak_area_km2", 50_000.0)),
    )
    linking_cfg = _linking_from_raw(_section(raw, "linking"))

    runtime_raw = _section(raw, "runtime")
    runtime_cfg = RuntimeConfig(
        time_block_months=int(runtime_raw.get("time_block_months", 12)),
        write_labels=bool(runtime_raw.get("write_labels", False)),
        overwrite=bool(runtime_raw.get("overwrite", False)),
        hash_inputs=bool(runtime_raw.get("hash_inputs", False)),
    )

    sensitivity_cfg: SensitivityConfig | None = None
    if "sensitivity" in raw and raw["sensitivity"] is not None:
        sensitivity_raw = _section(raw, "sensitivity")
        scale_inputs_raw = sensitivity_raw.get("scale_inputs", {}) or {}
        if not isinstance(scale_inputs_raw, dict):
            raise ConfigError("sensitivity.scale_inputs must be a mapping")
        link_rules_raw = sensitivity_raw.get("linking_rules", []) or []
        if not isinstance(link_rules_raw, list):
            raise ConfigError("sensitivity.linking_rules must be a list")
        sensitivity_cfg = SensitivityConfig(
            baseline_scale_months=int(sensitivity_raw.get("baseline_scale_months", 6)),
            accumulation_scales=tuple(
                int(value) for value in sensitivity_raw.get("accumulation_scales", [])
            ),
            scale_inputs={
                int(scale): _resolve_path(base, value)  # type: ignore[arg-type]
                for scale, value in scale_inputs_raw.items()
            },
            spei_thresholds=tuple(
                float(value) for value in sensitivity_raw.get("spei_thresholds", [])
            ),
            monthly_patch_areas_km2=tuple(
                float(value)
                for value in sensitivity_raw.get("monthly_patch_areas_km2", [])
            ),
            minimum_durations_months=tuple(
                int(value)
                for value in sensitivity_raw.get("minimum_durations_months", [])
            ),
            minimum_peak_areas_km2=tuple(
                float(value)
                for value in sensitivity_raw.get("minimum_peak_areas_km2", [])
            ),
            linking_rules=tuple(_linking_from_raw(item) for item in link_rules_raw),
        )

    config = ProjectConfig(
        input=input_cfg,
        output=output_cfg,
        event_definition=event_cfg,
        linking=linking_cfg,
        runtime=runtime_cfg,
        sensitivity=sensitivity_cfg,
    )
    validate_config(config)
    return config


def validate_config(config: ProjectConfig) -> None:
    """Validate configuration values without requiring input files to exist."""

    event = config.event_definition
    if event.spei_threshold >= 0:
        raise ConfigError("event_definition.spei_threshold must be negative")
    if event.connectivity not in {4, 8}:
        raise ConfigError("event_definition.connectivity must be 4 or 8")
    if event.minimum_monthly_patch_area_km2 < 0:
        raise ConfigError("minimum_monthly_patch_area_km2 must be non-negative")
    if event.minimum_duration_months < 1:
        raise ConfigError("minimum_duration_months must be at least 1")
    if event.minimum_peak_area_km2 < 0:
        raise ConfigError("minimum_peak_area_km2 must be non-negative")

    linking = config.linking
    if linking.rule not in LINK_RULES:
        raise ConfigError(f"linking.rule must be one of {sorted(LINK_RULES)}")
    if linking.minimum_overlap_cells < 1:
        raise ConfigError("linking.minimum_overlap_cells must be at least 1")
    if not 0 <= linking.minimum_iou <= 1:
        raise ConfigError("linking.minimum_iou must be between 0 and 1")
    if config.runtime.time_block_months < 1:
        raise ConfigError("runtime.time_block_months must be at least 1")

    sensitivity = config.sensitivity
    if sensitivity is None:
        return
    if sensitivity.baseline_scale_months < 1:
        raise ConfigError("sensitivity.baseline_scale_months must be at least 1")
    missing_scales = sorted(set(sensitivity.accumulation_scales) - set(sensitivity.scale_inputs))
    if missing_scales:
        raise ConfigError(
            "sensitivity.scale_inputs is missing accumulation scales: "
            + ", ".join(str(value) for value in missing_scales)
        )
    if any(value >= 0 for value in sensitivity.spei_thresholds):
        raise ConfigError("all sensitivity.spei_thresholds must be negative")
    if any(value < 0 for value in sensitivity.monthly_patch_areas_km2):
        raise ConfigError("monthly patch areas must be non-negative")
    if any(value < 1 for value in sensitivity.minimum_durations_months):
        raise ConfigError("minimum durations must be at least 1")
    if any(value < 0 for value in sensitivity.minimum_peak_areas_km2):
        raise ConfigError("minimum peak areas must be non-negative")
    for item in sensitivity.linking_rules:
        validate_config(
            ProjectConfig(
                input=config.input,
                output=config.output,
                event_definition=config.event_definition,
                linking=item,
                runtime=config.runtime,
            )
        )
