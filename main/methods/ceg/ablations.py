"""实现 CEG 机制消融的统一判定口径。

该模块只围绕 `doc/方法机制.md` 中定义的机制版本做派生判定:

- Full: 完整 CEG, 包含内容链、几何链、恢复后重判和 attestation。
- Content-only: 仅使用原始内容链。
- Recover-then-Content: 仅使用恢复后内容重判。
- No-rescue: 保留诊断字段, 但禁止 geometry rescue。
- No-attestation: 保留 evidence-level, 去掉 final-level attestation 约束。

这些消融属于方法机制分析, 因此保留在 `main/methods/` 中, 可进入最小论文方法包。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from main.methods.ceg.decision import (
    AttestationEvidence,
    CegDecision,
    CegThresholds,
    ContentEvidence,
    GeometryEvidence,
    decide_ceg_event,
    evaluate_geometry_reliability,
)

AblationName = Literal["Full", "Content-only", "Recover-then-Content", "No-rescue", "No-attestation"]

CEG_ABLATIONS: tuple[AblationName, ...] = (
    "Full",
    "Content-only",
    "Recover-then-Content",
    "No-rescue",
    "No-attestation",
)


def _label(evidence_decision: bool, final_decision: bool) -> str:
    """根据 evidence-level 和 final-level 结果生成离散标签。"""
    if final_decision:
        return "final_positive"
    if evidence_decision:
        return "evidence_positive_but_unattested"
    return "evidence_negative"


def _with_recomputed_final(
    decision: CegDecision,
    *,
    positive_by_content: bool,
    rescue_eligible: bool,
    positive_by_geo_rescue: bool,
    attestation_pass: bool,
    geo_rescue_blocked_reason: str | None,
) -> CegDecision:
    """复用原始诊断字段, 重算消融版本的核心布尔语义。"""
    evidence_decision = bool(positive_by_content or positive_by_geo_rescue)
    final_decision = bool(evidence_decision and attestation_pass)
    return replace(
        decision,
        positive_by_content=positive_by_content,
        rescue_eligible=rescue_eligible,
        positive_by_geo_rescue=positive_by_geo_rescue,
        evidence_decision=evidence_decision,
        attestation_pass=attestation_pass,
        final_decision=final_decision,
        final_label=_label(evidence_decision, final_decision),
        geo_rescue_blocked_reason=geo_rescue_blocked_reason,
    )


def decide_ceg_ablation_event(
    variant: AblationName,
    content: ContentEvidence,
    geometry: GeometryEvidence,
    attestation: AttestationEvidence,
    thresholds: CegThresholds,
) -> CegDecision:
    """执行一个 CEG 机制消融版本的单事件判定。"""
    if variant not in CEG_ABLATIONS:
        raise ValueError(f"unsupported CEG ablation variant: {variant}")
    full_decision = decide_ceg_event(content, geometry, attestation, thresholds)
    if variant == "Full":
        return full_decision
    if variant == "Content-only":
        return _with_recomputed_final(
            full_decision,
            positive_by_content=full_decision.positive_by_content,
            rescue_eligible=False,
            positive_by_geo_rescue=False,
            attestation_pass=full_decision.attestation_pass,
            geo_rescue_blocked_reason="ablation_content_only",
        )
    if variant == "No-rescue":
        return _with_recomputed_final(
            full_decision,
            positive_by_content=full_decision.positive_by_content,
            rescue_eligible=full_decision.rescue_eligible,
            positive_by_geo_rescue=False,
            attestation_pass=full_decision.attestation_pass,
            geo_rescue_blocked_reason="ablation_no_rescue",
        )
    if variant == "No-attestation":
        return _with_recomputed_final(
            full_decision,
            positive_by_content=full_decision.positive_by_content,
            rescue_eligible=full_decision.rescue_eligible,
            positive_by_geo_rescue=full_decision.positive_by_geo_rescue,
            attestation_pass=True,
            geo_rescue_blocked_reason=full_decision.geo_rescue_blocked_reason,
        )

    geometry_reliable, quality_bin, geometry_failure_reason = evaluate_geometry_reliability(geometry, thresholds)
    content_score_aligned = content.content_score_aligned
    content_margin_aligned = (
        content_score_aligned - thresholds.content_threshold if content_score_aligned is not None else None
    )
    positive_by_recovered_content = bool(content_margin_aligned is not None and content_margin_aligned >= 0)
    recovered_decision = replace(
        full_decision,
        positive_by_content=False,
        rescue_eligible=geometry_reliable,
        positive_by_geo_rescue=positive_by_recovered_content,
        evidence_decision=positive_by_recovered_content,
        final_decision=bool(positive_by_recovered_content and full_decision.attestation_pass),
        final_label=_label(positive_by_recovered_content, bool(positive_by_recovered_content and full_decision.attestation_pass)),
        content_margin_aligned=content_margin_aligned,
        geometry_reliable=geometry_reliable,
        geometry_recovery_quality_bin=quality_bin,
        geometry_fail_reason=geometry_failure_reason,
        geo_rescue_blocked_reason=None if positive_by_recovered_content else "ablation_recover_then_content_not_positive",
    )
    return recovered_decision


def decide_all_ceg_ablation_events(
    content: ContentEvidence,
    geometry: GeometryEvidence,
    attestation: AttestationEvidence,
    thresholds: CegThresholds,
) -> dict[str, CegDecision]:
    """一次性输出所有机制消融版本的判定。"""
    return {
        variant: decide_ceg_ablation_event(variant, content, geometry, attestation, thresholds)
        for variant in CEG_ABLATIONS
    }
