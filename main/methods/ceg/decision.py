"""实现 CEG 双链方法的最小 formal decision 语义。

该模块是从 CEG-WM 中抽取出的干净方法核心。它只表达论文方法机制本身:

- 内容链负责主证据。
- 几何链只负责参考系恢复可信度, 不能直接产生 positive。
- 恢复后重判使用同一个内容阈值。
- attestation 只约束 final-level 归因, 不能替代 watermark evidence。
- payload probe 只作为诊断字段, 不进入 formal decision。

这里不读取治理目录、审计工具、旧白名单、旧冻结门禁或 workflow
门禁配置。这样设计的主要原因是保证 `main/methods/` 可以被抽取为最小论文方法包。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any


RESCUE_ALLOWED_CONTENT_FAIL_REASONS = frozenset({"geometry_suspected", "low_confidence"})


def _finite_float(value: float | int | None, *, field_name: str) -> float | None:
    """把可选数值规范化为有限 float, 便于所有判定路径共享同一校验逻辑。"""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a finite number or None")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    return normalized


@dataclass(frozen=True)
class CegThresholds:
    """保存 CEG formal decision 所需的最小阈值集合。"""

    content_threshold: float
    attestation_threshold: float
    registration_confidence_min: float = 0.3
    anchor_inlier_ratio_min: float = 0.5
    recovered_sync_consistency_min: float = 0.55
    rescue_delta_low: float = 0.05

    def __post_init__(self) -> None:
        """在构造期检查阈值, 避免后续判定出现隐式 NaN 或非法窗口。"""
        for field_name, value in asdict(self).items():
            _finite_float(value, field_name=field_name)
        if self.rescue_delta_low < 0:
            raise ValueError("rescue_delta_low must be non-negative")


@dataclass(frozen=True)
class ContentEvidence:
    """表示内容链在原始坐标系和恢复坐标系上的证据。"""

    content_score_raw: float
    content_score_aligned: float | None = None
    content_fail_reason: str = "low_confidence"
    payload_probe_score: float | None = None

    def __post_init__(self) -> None:
        """检查内容分数与诊断分数, 保证判定输入可复现。"""
        _finite_float(self.content_score_raw, field_name="content_score_raw")
        _finite_float(self.content_score_aligned, field_name="content_score_aligned")
        _finite_float(self.payload_probe_score, field_name="payload_probe_score")
        if not self.content_fail_reason.strip():
            raise ValueError("content_fail_reason must be non-empty")


@dataclass(frozen=True)
class GeometryEvidence:
    """表示几何链的参考系恢复证据。"""

    registration_confidence: float | None = None
    anchor_inlier_ratio: float | None = None
    recovered_sync_consistency: float | None = None
    alignment_residual: float | None = None
    geometry_fail_reason: str | None = None

    def __post_init__(self) -> None:
        """检查几何诊断量, 该诊断量只能影响 rescue eligibility。"""
        _finite_float(self.registration_confidence, field_name="registration_confidence")
        _finite_float(self.anchor_inlier_ratio, field_name="anchor_inlier_ratio")
        _finite_float(self.recovered_sync_consistency, field_name="recovered_sync_consistency")
        _finite_float(self.alignment_residual, field_name="alignment_residual")


@dataclass(frozen=True)
class AttestationEvidence:
    """表示事件级归因一致性证据。"""

    attestation_score: float

    def __post_init__(self) -> None:
        """检查 attestation 分数, 该分数只参与 final-level 约束。"""
        _finite_float(self.attestation_score, field_name="attestation_score")


@dataclass(frozen=True)
class CegDecision:
    """保存 CEG 单事件 formal decision 与机制诊断字段。"""

    positive_by_content: bool
    rescue_eligible: bool
    positive_by_geo_rescue: bool
    evidence_decision: bool
    attestation_pass: bool
    final_decision: bool
    final_label: str
    content_score_raw: float
    content_score_aligned: float | None
    content_margin_raw: float
    content_margin_aligned: float | None
    geometry_reliable: bool
    registration_confidence: float | None
    anchor_inlier_ratio: float | None
    recovered_sync_consistency: float | None
    alignment_residual: float | None
    geometry_recovery_quality_bin: str
    content_fail_reason: str
    geometry_fail_reason: str | None
    attestation_score: float
    payload_probe_score: float | None
    geo_rescue_blocked_reason: str | None

    def to_record(self) -> dict[str, Any]:
        """转为可写入 records 或被聚合器消费的扁平字典。"""
        return asdict(self)


def evaluate_geometry_reliability(
    evidence: GeometryEvidence,
    thresholds: CegThresholds,
) -> tuple[bool, str, str | None]:
    """根据三项几何指标判断参考系恢复是否可信。

    返回值依次为:
    - `geometry_reliable`: 三项指标是否全部过线。
    - `geometry_recovery_quality_bin`: 可解释质量分桶。
    - `failure_reason`: 首个阻断原因。
    """
    checks = (
        (
            evidence.registration_confidence,
            thresholds.registration_confidence_min,
            "registration_confidence_missing",
            "registration_confidence_below_threshold",
        ),
        (
            evidence.anchor_inlier_ratio,
            thresholds.anchor_inlier_ratio_min,
            "anchor_inlier_ratio_missing",
            "anchor_inlier_ratio_below_threshold",
        ),
        (
            evidence.recovered_sync_consistency,
            thresholds.recovered_sync_consistency_min,
            "recovered_sync_consistency_missing",
            "recovered_sync_consistency_below_threshold",
        ),
    )
    below_count = 0
    for metric_value, minimum_value, missing_reason, below_reason in checks:
        if metric_value is None:
            return False, "incomplete", missing_reason
        if metric_value < minimum_value:
            below_count += 1
            if below_count == 1:
                first_below_reason = below_reason
    if below_count:
        quality_bin = "borderline" if below_count == 1 else "unreliable"
        return False, quality_bin, first_below_reason
    return True, "reliable", evidence.geometry_fail_reason


def decide_ceg_event(
    content: ContentEvidence,
    geometry: GeometryEvidence,
    attestation: AttestationEvidence,
    thresholds: CegThresholds,
) -> CegDecision:
    """执行 CEG 单事件 formal decision。

    该函数是当前干净仓库的核心方法入口。它只接收显式证据和显式阈值,
    不读取旧项目内嵌门禁, 因而可以直接进入最小论文发布包。
    """
    content_margin_raw = content.content_score_raw - thresholds.content_threshold
    positive_by_content = content_margin_raw >= 0
    geometry_reliable, quality_bin, geometry_failure_reason = evaluate_geometry_reliability(geometry, thresholds)
    content_score_aligned = content.content_score_aligned
    content_margin_aligned = (
        content_score_aligned - thresholds.content_threshold if content_score_aligned is not None else None
    )

    rescue_eligible = (
        -thresholds.rescue_delta_low <= content_margin_raw < 0
        and geometry_reliable
        and content.content_fail_reason in RESCUE_ALLOWED_CONTENT_FAIL_REASONS
    )
    positive_by_geo_rescue = bool(
        rescue_eligible
        and content_margin_aligned is not None
        and content_margin_aligned >= 0
    )
    if positive_by_geo_rescue:
        blocked_reason = None
    elif positive_by_content:
        blocked_reason = None
    elif not (-thresholds.rescue_delta_low <= content_margin_raw < 0):
        blocked_reason = "outside_rescue_band"
    elif not geometry_reliable:
        blocked_reason = "geometry_gate_failed"
    elif content.content_fail_reason not in RESCUE_ALLOWED_CONTENT_FAIL_REASONS:
        blocked_reason = "content_fail_reason_not_rescuable"
    elif content_margin_aligned is None:
        blocked_reason = "missing_aligned_content_score"
    else:
        blocked_reason = "aligned_content_below_threshold"

    evidence_decision = positive_by_content or positive_by_geo_rescue
    attestation_pass = attestation.attestation_score >= thresholds.attestation_threshold
    final_decision = evidence_decision and attestation_pass
    if final_decision:
        final_label = "final_positive"
    elif evidence_decision:
        final_label = "evidence_positive_but_unattested"
    else:
        final_label = "evidence_negative"

    return CegDecision(
        positive_by_content=positive_by_content,
        rescue_eligible=rescue_eligible,
        positive_by_geo_rescue=positive_by_geo_rescue,
        evidence_decision=evidence_decision,
        attestation_pass=attestation_pass,
        final_decision=final_decision,
        final_label=final_label,
        content_score_raw=content.content_score_raw,
        content_score_aligned=content_score_aligned,
        content_margin_raw=content_margin_raw,
        content_margin_aligned=content_margin_aligned,
        geometry_reliable=geometry_reliable,
        registration_confidence=geometry.registration_confidence,
        anchor_inlier_ratio=geometry.anchor_inlier_ratio,
        recovered_sync_consistency=geometry.recovered_sync_consistency,
        alignment_residual=geometry.alignment_residual,
        geometry_recovery_quality_bin=quality_bin,
        content_fail_reason=content.content_fail_reason,
        geometry_fail_reason=geometry_failure_reason,
        attestation_score=attestation.attestation_score,
        payload_probe_score=content.payload_probe_score,
        geo_rescue_blocked_reason=blocked_reason,
    )
