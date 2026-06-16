"""生成论文结果链路的端到端 dry-run 输入。

该模块生成的是受治理的最小覆盖 fixture, 不是正式实验结果。
它的作用是让开发者在没有真实大规模图像数据和第三方 baseline 输出时, 仍然可以验证 records、baseline、标准指标、图表、LaTeX、PDF 和 readiness 报告的完整链路。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from main.methods.baselines import list_baseline_specs
from main.methods.ceg.ablations import CEG_ABLATIONS
from main.core.digest import build_stable_digest

SAMPLE_BLUEPRINTS = (
    {
        "sample_role": "positive_source",
        "is_watermarked": True,
        "attack_family": "crop",
        "attack_condition": "crop_light",
        "content_score_raw": 0.48,
        "content_score_aligned": 0.63,
        "attestation_score": 0.91,
    },
    {
        "sample_role": "positive_source",
        "is_watermarked": True,
        "attack_family": "jpeg",
        "attack_condition": "jpeg_medium",
        "content_score_raw": 0.74,
        "content_score_aligned": 0.76,
        "attestation_score": 0.93,
    },
    {
        "sample_role": "clean_negative",
        "is_watermarked": False,
        "attack_family": "clean",
        "attack_condition": "clean_none",
        "content_score_raw": 0.16,
        "content_score_aligned": 0.17,
        "attestation_score": 0.14,
    },
    {
        "sample_role": "attacked_negative",
        "is_watermarked": False,
        "attack_family": "rotation",
        "attack_condition": "rotation_medium",
        "content_score_raw": 0.22,
        "content_score_aligned": 0.24,
        "attestation_score": 0.21,
    },
)


def _baseline_score(baseline_id: str, is_watermarked: bool, index: int) -> float:
    """生成可分离但不完全相同的 baseline 检测分数。"""
    offset = (sum(ord(char) for char in baseline_id) % 7) * 0.01
    if is_watermarked:
        return round(0.72 + offset - index * 0.01, 4)
    return round(0.16 + offset + index * 0.005, 4)


def _standard_metrics(is_watermarked: bool, index: int) -> dict[str, Any]:
    """生成标准图像水印指标字段。"""
    bit_total = 32
    bit_correct = 30 + (index % 3) if is_watermarked else 28 + (index % 2)
    return {
        "bit_correct_count": bit_correct,
        "bit_total_count": bit_total,
        "bit_accuracy": bit_correct / bit_total,
        "payload_recovered": bool(is_watermarked and bit_correct >= 30),
        "psnr": round(39.0 - index * 0.35, 4),
        "ssim": round(0.972 - index * 0.006, 4),
        "lpips": round(0.028 + index * 0.004, 4),
        "fid": round(7.2 + index * 0.45, 4),
        "clip_score": round(0.35 - index * 0.006, 4),
    }


def _event_id(index: int, role: str, attack_family: str) -> str:
    """构造稳定事件标识。"""
    return f"dry_run_{index:03d}_{role}_{attack_family}"


def build_paper_dry_run_inputs(*, repetitions: int = 1) -> dict[str, Any]:
    """构造完整论文产物链路 dry-run 输入。

    repetitions 用于放大每个样本蓝图的重复次数。默认值为1, 保证默认 pytest 路径保持轻量。
    """
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    event_rows: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    baseline_ids = tuple(spec.baseline_id for spec in list_baseline_specs())
    event_index = 0
    for repetition in range(repetitions):
        for blueprint in SAMPLE_BLUEPRINTS:
            event_index += 1
            sample_role = str(blueprint["sample_role"])
            attack_family = str(blueprint["attack_family"])
            is_watermarked = bool(blueprint["is_watermarked"])
            event_id = _event_id(event_index + repetition * len(SAMPLE_BLUEPRINTS), sample_role, attack_family)
            metrics = _standard_metrics(is_watermarked, event_index)
            event_rows.append(
                {
                    "event_id": event_id,
                    "split": "test",
                    "sample_role": sample_role,
                    "attack_family": attack_family,
                    "attack_condition": str(blueprint["attack_condition"]),
                    "is_watermarked": is_watermarked,
                    "payload": {
                        "thresholds": {"content_threshold": 0.5, "attestation_threshold": 0.5},
                        "content": {
                            "content_score_raw": float(blueprint["content_score_raw"]),
                            "content_score_aligned": float(blueprint["content_score_aligned"]),
                            "content_fail_reason": "dry_run_borderline" if is_watermarked else "dry_run_negative",
                        },
                        "geometry": {
                            "registration_confidence": 0.9 if is_watermarked else 0.62,
                            "anchor_inlier_ratio": 0.84 if is_watermarked else 0.58,
                            "recovered_sync_consistency": 0.88 if is_watermarked else 0.55,
                            "alignment_residual": 0.08 if is_watermarked else 0.22,
                        },
                        "attestation": {"attestation_score": float(blueprint["attestation_score"])},
                        "ceg_ablation_variants": list(CEG_ABLATIONS),
                        "standard_metrics": metrics,
                    },
                }
            )
            metric_rows.append({"event_id": event_id, "method_name": "ceg", **metrics})
            for variant in CEG_ABLATIONS:
                metric_rows.append(
                    {
                        "event_id": event_id,
                        "method_name": f"ceg_{variant.lower().replace('-', '_')}",
                        **metrics,
                    }
                )
            for baseline_index, baseline_id in enumerate(baseline_ids):
                baseline_metrics = _standard_metrics(is_watermarked, event_index + baseline_index + 1)
                baseline_rows.append(
                    {
                        "event_id": event_id,
                        "baseline_id": baseline_id,
                        "score": _baseline_score(baseline_id, is_watermarked, baseline_index),
                        "threshold": 0.5,
                        "score_name": "dry_run_detection_score",
                        "higher_is_positive": True,
                        **baseline_metrics,
                    }
                )
                metric_rows.append({"event_id": event_id, "baseline_id": baseline_id, **baseline_metrics})
    thresholds = {"ceg": 0.5}
    for variant in CEG_ABLATIONS:
        thresholds[f"ceg_{variant.lower().replace('-', '_')}"] = 0.5
    for baseline_id in baseline_ids:
        thresholds[baseline_id] = 0.5
    manifest = {
        "artifact_name": "paper_dry_run_inputs_manifest.json",
        "fixture_role": "paper_readiness_dry_run",
        "event_count": len(event_rows),
        "baseline_observation_count": len(baseline_rows),
        "metric_row_count": len(metric_rows),
        "baseline_ids": list(baseline_ids),
        "ceg_ablation_variants": list(CEG_ABLATIONS),
        "sample_roles": sorted({str(row["sample_role"]) for row in event_rows}),
        "attack_families": sorted({str(row["attack_family"]) for row in event_rows}),
    }
    manifest["fixture_digest"] = build_stable_digest(
        {
            "event_rows": event_rows,
            "baseline_rows": baseline_rows,
            "metric_rows": metric_rows,
            "thresholds": thresholds,
        }
    )
    return {
        "events": event_rows,
        "baseline_observations": baseline_rows,
        "metric_rows": metric_rows,
        "thresholds": thresholds,
        "manifest": manifest,
    }


def write_paper_dry_run_inputs(output_root: str | Path, *, repetitions: int = 1) -> dict[str, Any]:
    """写出 dry-run 输入文件并返回 manifest。"""
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    bundle = build_paper_dry_run_inputs(repetitions=repetitions)
    file_map = {
        "events_path": "events.json",
        "baseline_observations_path": "baseline_observations.json",
        "metric_rows_path": "metric_rows.json",
        "thresholds_path": "thresholds.json",
    }
    (output_path / file_map["events_path"]).write_text(
        json.dumps(bundle["events"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_path / file_map["baseline_observations_path"]).write_text(
        json.dumps(bundle["baseline_observations"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_path / file_map["metric_rows_path"]).write_text(
        json.dumps(bundle["metric_rows"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_path / file_map["thresholds_path"]).write_text(
        json.dumps(bundle["thresholds"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {**bundle["manifest"], **file_map}
    (output_path / "paper_dry_run_inputs_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
