"""验证 CEG 干净方法层的 formal decision 语义。"""

from __future__ import annotations

import pytest

from main.methods.ceg import (
    AttestationEvidence,
    CegThresholds,
    ContentEvidence,
    GeometryEvidence,
    decide_ceg_event,
)


def _thresholds() -> CegThresholds:
    """构造轻量测试阈值, 不依赖旧项目门禁配置。"""
    return CegThresholds(content_threshold=0.5, attestation_threshold=0.5, rescue_delta_low=0.05)


def _reliable_geometry() -> GeometryEvidence:
    """构造三项指标均过线的几何恢复证据。"""
    return GeometryEvidence(
        registration_confidence=0.9,
        anchor_inlier_ratio=0.8,
        recovered_sync_consistency=0.85,
    )


@pytest.mark.quick
def test_content_pass_and_attestation_pass_make_final_positive() -> None:
    """内容链过线且 attestation 过线时, final-level 才能为 positive。"""
    decision = decide_ceg_event(
        ContentEvidence(content_score_raw=0.51),
        GeometryEvidence(),
        AttestationEvidence(attestation_score=0.8),
        _thresholds(),
    )

    assert decision.positive_by_content is True
    assert decision.evidence_decision is True
    assert decision.attestation_pass is True
    assert decision.final_decision is True
    assert decision.final_label == "final_positive"


@pytest.mark.quick
def test_geometry_score_cannot_rescue_without_aligned_content_pass() -> None:
    """几何恢复可信本身不能直接产生 formal positive。"""
    decision = decide_ceg_event(
        ContentEvidence(content_score_raw=0.49, content_score_aligned=None),
        _reliable_geometry(),
        AttestationEvidence(attestation_score=0.8),
        _thresholds(),
    )

    assert decision.rescue_eligible is True
    assert decision.positive_by_geo_rescue is False
    assert decision.evidence_decision is False
    assert decision.final_decision is False
    assert decision.geo_rescue_blocked_reason == "missing_aligned_content_score"


@pytest.mark.quick
def test_aligned_content_pass_enables_geo_rescue() -> None:
    """恢复后内容分数使用同一阈值重判, 过线后才允许 geometry rescue。"""
    decision = decide_ceg_event(
        ContentEvidence(
            content_score_raw=0.49,
            content_score_aligned=0.52,
            content_fail_reason="geometry_suspected",
        ),
        _reliable_geometry(),
        AttestationEvidence(attestation_score=0.8),
        _thresholds(),
    )

    assert decision.positive_by_content is False
    assert decision.rescue_eligible is True
    assert decision.positive_by_geo_rescue is True
    assert decision.evidence_decision is True
    assert decision.final_decision is True
    assert decision.content_margin_aligned == pytest.approx(0.02)


@pytest.mark.quick
def test_attestation_only_never_creates_final_positive() -> None:
    """attestation 不能替代 watermark 主证据。"""
    decision = decide_ceg_event(
        ContentEvidence(content_score_raw=0.2, payload_probe_score=1.0),
        _reliable_geometry(),
        AttestationEvidence(attestation_score=0.99),
        _thresholds(),
    )

    assert decision.evidence_decision is False
    assert decision.attestation_pass is True
    assert decision.final_decision is False
    assert decision.final_label == "evidence_negative"
