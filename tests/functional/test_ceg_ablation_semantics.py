"""验证 CEG 机制消融不偏离方法机制定义。"""

from __future__ import annotations

import pytest

from main.methods.ceg import AttestationEvidence, CegThresholds, ContentEvidence, GeometryEvidence
from main.methods.ceg.ablations import CEG_ABLATIONS, decide_all_ceg_ablation_events, decide_ceg_ablation_event


def _thresholds() -> CegThresholds:
    """构造机制消融测试阈值。"""
    return CegThresholds(content_threshold=0.5, attestation_threshold=0.5, rescue_delta_low=0.05)


def _content() -> ContentEvidence:
    """构造原始内容失败但恢复后过线的样本。"""
    return ContentEvidence(
        content_score_raw=0.49,
        content_score_aligned=0.52,
        content_fail_reason="geometry_suspected",
    )


def _geometry() -> GeometryEvidence:
    """构造可信几何恢复。"""
    return GeometryEvidence(
        registration_confidence=0.9,
        anchor_inlier_ratio=0.8,
        recovered_sync_consistency=0.85,
    )


@pytest.mark.quick
def test_all_required_ablation_variants_are_available() -> None:
    """机制消融必须覆盖方法文档定义的 5 个版本。"""
    assert set(CEG_ABLATIONS) == {
        "Full",
        "Content-only",
        "Recover-then-Content",
        "No-rescue",
        "No-attestation",
    }


@pytest.mark.quick
def test_no_rescue_blocks_geometry_rescue_gain() -> None:
    """No-rescue 保留诊断但禁止 positive_by_geo_rescue。"""
    decision = decide_ceg_ablation_event(
        "No-rescue",
        _content(),
        _geometry(),
        AttestationEvidence(attestation_score=0.8),
        _thresholds(),
    )

    assert decision.rescue_eligible is True
    assert decision.positive_by_geo_rescue is False
    assert decision.final_decision is False
    assert decision.geo_rescue_blocked_reason == "ablation_no_rescue"


@pytest.mark.quick
def test_no_attestation_uses_evidence_level_as_final_level() -> None:
    """No-attestation 去掉 final-level 事件约束。"""
    decision = decide_ceg_ablation_event(
        "No-attestation",
        _content(),
        _geometry(),
        AttestationEvidence(attestation_score=0.1),
        _thresholds(),
    )

    assert decision.evidence_decision is True
    assert decision.attestation_pass is True
    assert decision.final_decision is True


@pytest.mark.quick
def test_decide_all_ceg_ablation_events_returns_all_variants() -> None:
    """批量消融入口必须稳定返回全部版本。"""
    decisions = decide_all_ceg_ablation_events(
        _content(),
        _geometry(),
        AttestationEvidence(attestation_score=0.8),
        _thresholds(),
    )

    assert set(decisions) == set(CEG_ABLATIONS)
    assert decisions["Full"].positive_by_geo_rescue is True
    assert decisions["Content-only"].positive_by_geo_rescue is False
