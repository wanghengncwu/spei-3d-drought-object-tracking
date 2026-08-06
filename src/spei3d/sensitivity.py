"""One-factor-at-a-time sensitivity experiments for drought-object extraction."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

from .config import (
    LinkingConfig,
    OutputConfig,
    ProjectConfig,
    RuntimeConfig,
)
from .engine import run_extraction


@dataclass(frozen=True)
class Scenario:
    name: str
    factor: str
    level: str
    config: ProjectConfig

    @property
    def signature(self) -> tuple[Any, ...]:
        event = self.config.event_definition
        linking = self.config.linking
        effective_iou = linking.minimum_iou if linking.rule == "maximum_iou" else 0.0
        return (
            str(self.config.input.spei.resolve()),
            event.spei_threshold,
            event.connectivity,
            event.minimum_monthly_patch_area_km2,
            event.minimum_duration_months,
            event.minimum_peak_area_km2,
            linking.rule,
            linking.minimum_overlap_cells,
            effective_iou,
        )


def build_scenarios(config: ProjectConfig) -> list[Scenario]:
    """Build unique one-factor-at-a-time scenarios, beginning with the baseline."""

    sensitivity = config.sensitivity
    if sensitivity is None:
        raise ValueError("the configuration does not contain a sensitivity section")

    scenarios: list[Scenario] = [Scenario("baseline", "baseline", "baseline", config)]

    for scale in sensitivity.accumulation_scales:
        source = sensitivity.scale_inputs[scale]
        if (
            scale == sensitivity.baseline_scale_months
            and source.resolve() == config.input.spei.resolve()
        ):
            continue
        input_cfg = replace(config.input, spei=source)
        scenarios.append(
            Scenario(
                name=f"accumulation_scale_{scale:02d}",
                factor="accumulation_scale",
                level=str(scale),
                config=replace(config, input=input_cfg),
            )
        )

    baseline_event = config.event_definition
    for threshold in sensitivity.spei_thresholds:
        if threshold == baseline_event.spei_threshold:
            continue
        scenarios.append(
            Scenario(
                name=f"spei_threshold_{_number_tag(threshold)}",
                factor="spei_threshold",
                level=str(threshold),
                config=replace(
                    config,
                    event_definition=replace(baseline_event, spei_threshold=threshold),
                ),
            )
        )
    for area in sensitivity.monthly_patch_areas_km2:
        if area == baseline_event.minimum_monthly_patch_area_km2:
            continue
        scenarios.append(
            Scenario(
                name=f"monthly_patch_area_{_integer_tag(area)}",
                factor="monthly_patch_area",
                level=str(area),
                config=replace(
                    config,
                    event_definition=replace(
                        baseline_event, minimum_monthly_patch_area_km2=area
                    ),
                ),
            )
        )
    for duration in sensitivity.minimum_durations_months:
        if duration == baseline_event.minimum_duration_months:
            continue
        scenarios.append(
            Scenario(
                name=f"minimum_duration_{duration:02d}",
                factor="minimum_duration",
                level=str(duration),
                config=replace(
                    config,
                    event_definition=replace(
                        baseline_event, minimum_duration_months=duration
                    ),
                ),
            )
        )
    for area in sensitivity.minimum_peak_areas_km2:
        if area == baseline_event.minimum_peak_area_km2:
            continue
        scenarios.append(
            Scenario(
                name=f"minimum_peak_area_{_integer_tag(area)}",
                factor="minimum_peak_area",
                level=str(area),
                config=replace(
                    config,
                    event_definition=replace(baseline_event, minimum_peak_area_km2=area),
                ),
            )
        )

    baseline_linking = config.linking
    for linking in sensitivity.linking_rules:
        candidate = _normalize_linking(linking)
        baseline = _normalize_linking(baseline_linking)
        if candidate == baseline:
            continue
        suffix = candidate.rule
        if candidate.rule == "maximum_iou":
            suffix += f"_{_number_tag(candidate.minimum_iou)}"
        scenarios.append(
            Scenario(
                name=f"linking_{suffix}",
                factor="linking_rule",
                level=suffix,
                config=replace(config, linking=candidate),
            )
        )

    unique: list[Scenario] = []
    seen: set[tuple[Any, ...]] = set()
    for scenario in scenarios:
        signature = scenario.signature
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(scenario)
    return unique


def run_sensitivity(config: ProjectConfig) -> Path:
    """Run all unique sensitivity scenarios and write a combined summary table."""

    root = config.output.root
    root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for scenario in build_scenarios(config):
        scenario_output = root / "scenarios" / scenario.name
        scenario_config = replace(
            scenario.config,
            output=OutputConfig(scenario_output),
            runtime=RuntimeConfig(
                time_block_months=scenario.config.runtime.time_block_months,
                write_labels=scenario.config.runtime.write_labels,
                overwrite=scenario.config.runtime.overwrite,
                hash_inputs=scenario.config.runtime.hash_inputs,
            ),
        )
        result = run_extraction(scenario_config)
        event = scenario_config.event_definition
        linking = scenario_config.linking
        rows.append(
            {
                "scenario": scenario.name,
                "factor": scenario.factor,
                "level": scenario.level,
                "dataset_name": scenario_config.input.dataset_name,
                "spei_file": scenario_config.input.spei.name,
                "spei_threshold": event.spei_threshold,
                "connectivity": event.connectivity,
                "minimum_monthly_patch_area_km2": event.minimum_monthly_patch_area_km2,
                "minimum_duration_months": event.minimum_duration_months,
                "minimum_peak_area_km2": event.minimum_peak_area_km2,
                "linking_rule": linking.rule,
                "minimum_overlap_cells": linking.minimum_overlap_cells,
                "minimum_iou": (
                    linking.minimum_iou if linking.rule == "maximum_iou" else 0.0
                ),
                "raw_object_count": result.raw_object_count,
                "object_count": result.object_count,
                "total_AD_km2months": result.total_AD_km2months,
                "total_catalogue_severity": result.total_catalogue_severity,
                "upper_decile_AD_share": result.upper_decile_AD_share,
                "upper_decile_catalogue_severity_share": (
                    result.upper_decile_catalogue_severity_share
                ),
            }
        )
    summary_path = root / "sensitivity_summary.csv"
    pd.DataFrame(rows).to_csv(summary_path, index=False)
    return summary_path


def _normalize_linking(linking: LinkingConfig) -> LinkingConfig:
    if linking.rule == "maximum_iou":
        return linking
    return replace(linking, minimum_iou=0.0)


def _number_tag(value: float) -> str:
    sign = "m" if value < 0 else "p"
    magnitude = f"{abs(value):.2f}".replace(".", "p")
    return f"{sign}{magnitude}"


def _integer_tag(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return _number_tag(value)
