"""执行 CEG 与外部 baseline 的统一事件级协议。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from main.methods.baseline_adapters import BaselineObservation, adapt_baseline_observation
from main.methods.ceg import (
    AttestationEvidence,
    CegThresholds,
    ContentEvidence,
    GeometryEvidence,
    decide_ceg_event,
    decide_ceg_ablation_event,
)
from main.protocol.experiment import EventProtocolRecord

STANDARD_METRIC_RECORD_FIELDS = (
    "bit_correct_count",
    "bit_total_count",
    "bit_accuracy",
    "payload_recovered",
    "psnr",
    "ssim",
    "lpips",
    "fid",
    "clip_score",
)


def _coerce_metric_value(field_name: str, value: Any) -> Any:
    """把 payload 中的标准指标转换为 records 可聚合的标量。"""
    if value is None:
        return None
    if field_name == "payload_recovered":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _standard_metric_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """从事件 payload.standard_metrics 中提取论文标准指标字段。"""
    metrics_node = _optional_mapping(payload.get("standard_metrics"))
    extracted: dict[str, Any] = {}
    for field_name in STANDARD_METRIC_RECORD_FIELDS:
        value = _coerce_metric_value(field_name, metrics_node.get(field_name))
        if value is not None:
            extracted[field_name] = value
    return extracted


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    """读取协议 payload 中的子映射, 缺失或类型错误时 fail-fast。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be mapping")
    return value


def _optional_mapping(value: Any) -> Mapping[str, Any]:
    """读取可选子映射, 缺失时返回空映射。"""
    return value if isinstance(value, Mapping) else {}


def _number(value: Any, *, field_name: str) -> float:
    """读取必要数值字段。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be number")
    return float(value)


def _optional_number(value: Any, *, field_name: str) -> float | None:
    """读取可选数值字段。"""
    if value is None:
        return None
    return _number(value, field_name=field_name)


def build_ceg_thresholds(payload: Mapping[str, Any]) -> CegThresholds:
    """从协议 payload 中构造 CEG 阈值对象。"""
    threshold_node = _require_mapping(payload.get("thresholds"), field_name="payload.thresholds")
    return CegThresholds(
        content_threshold=_number(threshold_node.get("content_threshold"), field_name="content_threshold"),
        attestation_threshold=_number(threshold_node.get("attestation_threshold"), field_name="attestation_threshold"),
        registration_confidence_min=float(threshold_node.get("registration_confidence_min", 0.3)),
        anchor_inlier_ratio_min=float(threshold_node.get("anchor_inlier_ratio_min", 0.5)),
        recovered_sync_consistency_min=float(threshold_node.get("recovered_sync_consistency_min", 0.55)),
        rescue_delta_low=float(threshold_node.get("rescue_delta_low", 0.05)),
    )


def _build_ceg_inputs(
    event: EventProtocolRecord,
) -> tuple[ContentEvidence, GeometryEvidence, AttestationEvidence, CegThresholds]:
    """从事件 payload 中构造 CEG 方法输入。"""
    payload = event.payload
    content_node = _require_mapping(payload.get("content"), field_name="payload.content")
    geometry_node = _optional_mapping(payload.get("geometry"))
    attestation_node = _require_mapping(payload.get("attestation"), field_name="payload.attestation")
    return (
        ContentEvidence(
            content_score_raw=_number(content_node.get("content_score_raw"), field_name="content_score_raw"),
            content_score_aligned=_optional_number(
                content_node.get("content_score_aligned"),
                field_name="content_score_aligned",
            ),
            content_fail_reason=str(content_node.get("content_fail_reason", "low_confidence")),
            payload_probe_score=_optional_number(
                content_node.get("payload_probe_score"),
                field_name="payload_probe_score",
            ),
        ),
        GeometryEvidence(
            registration_confidence=_optional_number(
                geometry_node.get("registration_confidence"),
                field_name="registration_confidence",
            ),
            anchor_inlier_ratio=_optional_number(
                geometry_node.get("anchor_inlier_ratio"),
                field_name="anchor_inlier_ratio",
            ),
            recovered_sync_consistency=_optional_number(
                geometry_node.get("recovered_sync_consistency"),
                field_name="recovered_sync_consistency",
            ),
            alignment_residual=_optional_number(
                geometry_node.get("alignment_residual"),
                field_name="alignment_residual",
            ),
            geometry_fail_reason=geometry_node.get("geometry_fail_reason"),
        ),
        AttestationEvidence(
            attestation_score=_number(attestation_node.get("attestation_score"), field_name="attestation_score")
        ),
        build_ceg_thresholds(payload),
    )


def _base_record(event: EventProtocolRecord, *, method_name: str) -> dict[str, Any]:
    """构造所有方法共享的事件身份字段。"""
    return {
        "event_id": event.event_id,
        "method_name": method_name,
        "split": event.split,
        "sample_role": event.sample_role,
        "attack_family": event.attack_family,
        "attack_condition": event.attack_condition,
        "is_watermarked": event.is_watermarked,
        **_standard_metric_fields(event.payload),
    }


def run_ceg_event(event: EventProtocolRecord) -> dict[str, Any]:
    """对一个协议事件执行 CEG formal decision 并返回统一 record。"""
    content, geometry, attestation, thresholds = _build_ceg_inputs(event)
    decision = decide_ceg_event(content, geometry, attestation, thresholds)
    return {**_base_record(event, method_name="ceg"), **decision.to_record()}


def run_ceg_ablation_events(event: EventProtocolRecord) -> list[dict[str, Any]]:
    """根据 payload.ceg_ablation_variants 输出 CEG 内部机制消融 records。"""
    variants = event.payload.get("ceg_ablation_variants", [])
    if variants is None:
        return []
    if not isinstance(variants, Iterable) or isinstance(variants, (str, bytes, Mapping)):
        raise TypeError("payload.ceg_ablation_variants must be list[str]")
    content, geometry, attestation, thresholds = _build_ceg_inputs(event)
    records: list[dict[str, Any]] = []
    for variant in variants:
        variant_name = str(variant)
        decision = decide_ceg_ablation_event(variant_name, content, geometry, attestation, thresholds)
        records.append(
            {
                **_base_record(event, method_name=f"ceg_{variant_name.lower().replace('-', '_')}"),
                "ablation_name": variant_name,
                **decision.to_record(),
            }
        )
    return records


def run_baseline_events(event: EventProtocolRecord) -> list[dict[str, Any]]:
    """读取事件 payload 中的 baseline_observations 并输出统一 baseline records。"""
    observations = event.payload.get("baseline_observations", [])
    if observations is None:
        return []
    if not isinstance(observations, Iterable) or isinstance(observations, (str, bytes, Mapping)):
        raise TypeError("payload.baseline_observations must be list[Mapping]")
    records: list[dict[str, Any]] = []
    for index, raw_observation in enumerate(observations):
        if not isinstance(raw_observation, Mapping):
            raise TypeError(f"payload.baseline_observations[{index}] must be mapping")
        observation = BaselineObservation(
            baseline_id=str(raw_observation["baseline_id"]),
            score=_number(raw_observation.get("score"), field_name="baseline_observations.score"),
            threshold=_number(raw_observation.get("threshold"), field_name="baseline_observations.threshold"),
            score_name=str(raw_observation.get("score_name", "baseline_score")),
            higher_is_positive=bool(raw_observation.get("higher_is_positive", True)),
            metadata=dict(_optional_mapping(raw_observation.get("metadata"))),
        )
        records.append(adapt_baseline_observation(event, observation))
    return records


def run_protocol_events(events: Iterable[EventProtocolRecord]) -> list[dict[str, Any]]:
    """执行一批事件, 输出 CEG 与 baseline 的统一 records。"""
    records: list[dict[str, Any]] = []
    for event in events:
        records.append(run_ceg_event(event))
        records.extend(run_ceg_ablation_events(event))
        records.extend(run_baseline_events(event))
    return records
