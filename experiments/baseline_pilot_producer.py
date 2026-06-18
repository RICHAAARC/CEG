"""从 CEG detection events 生成外部 baseline pilot observations。

该模块服务于论文结果包推进阶段的外部 baseline 接口验证。它不会实现 Tree-Ring、
Gaussian Shading、Shallow Diffuse 或 T2SMark 的第三方算法本体, 也不会
声明正式论文数值。它的职责是把已经受治理的 `detection_events.json` 转换成统一的
`baseline_observations.json` 与 `baseline_execution_manifest.json`, 让后续表格、fixed-FPR
统计和结果包导出可以先验证数据契约。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from main.core.digest import build_stable_digest
from main.methods.baselines import get_baseline_spec, list_baseline_specs

BASELINE_OBSERVATIONS_NAME = "baseline_observations.json"
BASELINE_EXECUTION_MANIFEST_NAME = "baseline_execution_manifest.json"
BASELINE_PILOT_PRODUCER_ID = "external_baseline_pilot_producer"


def _as_bool(value: Any, *, default: bool) -> bool:
    """读取布尔值, 支持 JSON、CSV 或命令行产物中常见的字符串表示。"""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    lowered = str(value).strip().lower()
    if lowered in {"true", "1", "yes", "y", "positive", "watermarked"}:
        return True
    if lowered in {"false", "0", "no", "n", "negative", "clean"}:
        return False
    return default


def _event_identifier(event: dict[str, Any], index: int) -> str:
    """读取稳定事件标识, 缺失时生成可复现的 dry-run 标识。"""
    value = event.get("event_id")
    text = str(value).strip() if value is not None else ""
    return text or f"event_{index:04d}"


def _attack_penalty(event: dict[str, Any]) -> float:
    """根据 attack family 生成 deterministic 分数惩罚, 用于模拟鲁棒性退化。"""
    family = str(event.get("attack_family", "clean")).strip().lower()
    if family in {"clean", "none", "clean_none"}:
        return 0.0
    penalties = {
        "jpeg": 0.08,
        "crop": 0.12,
        "resize": 0.07,
        "rotate": 0.11,
        "rotation": 0.11,
        "gaussian_noise": 0.1,
        "gaussian_blur": 0.09,
        "brightness_contrast": 0.06,
    }
    return penalties.get(family, 0.1)


def _baseline_offset(baseline_id: str) -> float:
    """为不同 baseline 生成稳定小偏移, 避免 pilot 表格完全同分。"""
    return (sum(ord(char) for char in baseline_id) % 11) / 100.0


def _event_offset(event_id: str) -> float:
    """为不同事件生成稳定小偏移, 保持 dry-run 分数可复现。"""
    return (sum(ord(char) for char in event_id) % 13) / 1000.0


def _pilot_score(*, event: dict[str, Any], event_id: str, baseline_id: str) -> float:
    """生成外部 baseline pilot 分数。

    该规则属于项目特定 dry-run 逻辑, 只用于验证 observation 契约和结果包链路。真实论文实验
    必须由第三方 baseline 脚本或离线结果文件提供分数。
    """
    is_watermarked = _as_bool(event.get("is_watermarked"), default=False)
    base = 0.72 if is_watermarked else 0.18
    score = base + _baseline_offset(baseline_id) + _event_offset(event_id)
    if is_watermarked:
        score -= _attack_penalty(event)
    else:
        score += min(_attack_penalty(event), 0.04)
    return round(max(0.0, min(1.0, score)), 6)


def build_baseline_pilot_observations(
    detection_events: Iterable[dict[str, Any]],
    *,
    baseline_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """从 detection events 构建统一 baseline observation rows。"""
    selected_baselines = tuple(baseline_ids or (spec.baseline_id for spec in list_baseline_specs()))
    normalized_baselines = tuple(get_baseline_spec(baseline_id).baseline_id for baseline_id in selected_baselines)
    rows: list[dict[str, Any]] = []
    for index, event in enumerate(detection_events, start=1):
        event_id = _event_identifier(dict(event), index)
        for baseline_id in normalized_baselines:
            rows.append(
                {
                    "event_id": event_id,
                    "baseline_id": baseline_id,
                    "score": _pilot_score(event=dict(event), event_id=event_id, baseline_id=baseline_id),
                    "threshold": 0.5,
                    "score_name": "baseline_pilot_detection_score",
                    "higher_is_positive": True,
                    "producer_id": BASELINE_PILOT_PRODUCER_ID,
                    "producer_role": "external_baseline_pilot_dry_run",
                    "formal_result_claim": False,
                    "split": str(event.get("split", "")),
                    "sample_role": str(event.get("sample_role", "")),
                    "attack_family": str(event.get("attack_family", "clean")),
                    "attack_condition": str(event.get("attack_condition", "clean_none")),
                }
            )
    return rows


def build_baseline_execution_manifest(
    *,
    events_path: str | Path,
    observations_path: str | Path,
    detection_events: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """构建 external baseline pilot 执行 manifest。"""
    baseline_ids = sorted({str(row["baseline_id"]) for row in observations})
    return {
        "artifact_name": BASELINE_EXECUTION_MANIFEST_NAME,
        "producer_id": BASELINE_PILOT_PRODUCER_ID,
        "producer_role": "external_baseline_pilot_dry_run",
        "formal_result_claim": False,
        "events_path": str(events_path),
        "baseline_observations_path": str(observations_path),
        "baseline_ids": baseline_ids,
        "event_count": len(detection_events),
        "observation_count": len(observations),
        "score_name": "baseline_pilot_detection_score",
        "higher_is_positive": True,
        "threshold": 0.5,
        "execution_boundary": "contract_validation_only_not_third_party_algorithm",
        "producer_digest": build_stable_digest(
            {
                "baseline_ids": baseline_ids,
                "event_count": len(detection_events),
                "observations": observations,
            }
        ),
    }


def write_baseline_pilot_outputs(
    detection_events: Iterable[dict[str, Any]],
    output_root: str | Path,
    *,
    events_path: str | Path,
    baseline_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """写出 baseline pilot observations 和 execution manifest。"""
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    events = [dict(event) for event in detection_events]
    observations = build_baseline_pilot_observations(events, baseline_ids=baseline_ids)
    observations_path = output_path / BASELINE_OBSERVATIONS_NAME
    manifest_path = output_path / BASELINE_EXECUTION_MANIFEST_NAME
    observations_path.write_text(json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = build_baseline_execution_manifest(
        events_path=events_path,
        observations_path=observations_path,
        detection_events=events,
        observations=observations,
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
