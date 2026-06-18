"""验证轻量 paper protocol runner 串联 CEG、baseline 和产物流程。"""

from __future__ import annotations

import pytest

from experiments.protocol_runner import run_paper_protocol
from main.protocol.runtime import run_protocol_events
from main.protocol.experiment import EventProtocolRecord


def _event_rows() -> list[dict[str, object]]:
    """构造覆盖 CEG rescue 与外部 baseline 的轻量事件。"""
    base_payload = {
        "thresholds": {"content_threshold": 0.5, "attestation_threshold": 0.5},
        "content": {
            "content_score_raw": 0.49,
            "content_score_aligned": 0.52,
            "content_fail_reason": "geometry_suspected",
        },
        "geometry": {
            "registration_confidence": 0.9,
            "anchor_inlier_ratio": 0.8,
            "recovered_sync_consistency": 0.85,
        },
        "attestation": {"attestation_score": 0.8},
        "baseline_observations": [
            {"baseline_id": "tree_ring", "score": 0.7, "threshold": 0.5},
            {"baseline_id": "gaussian_shading", "score": 0.4, "threshold": 0.5},
            {"baseline_id": "shallow_diffuse", "score": 0.6, "threshold": 0.5},
            {"baseline_id": "t2smark", "score": 0.8, "threshold": 0.5},
        ],
    }
    return [
        {
            "event_id": "event_positive",
            "split": "test",
            "sample_role": "positive_source",
            "attack_family": "rotate",
            "attack_condition": "rotate_light",
            "is_watermarked": True,
            "payload": base_payload,
        }
    ]


@pytest.mark.quick
def test_run_protocol_events_emits_ceg_and_baseline_records() -> None:
    """统一协议应为一个事件生成一条 CEG record 和多条 baseline records。"""
    event = EventProtocolRecord(
        event_id="event_positive",
        method_name="ceg",
        split="test",
        sample_role="positive_source",
        attack_family="rotate",
        attack_condition="rotate_light",
        is_watermarked=True,
        payload=dict(_event_rows()[0]["payload"]),
    )

    records = run_protocol_events([event])

    assert {record["method_name"] for record in records} == {
        "ceg",
        "tree_ring",
        "gaussian_shading",
        "shallow_diffuse",
        "t2smark",
    }
    ceg_record = next(record for record in records if record["method_name"] == "ceg")
    assert ceg_record["positive_by_geo_rescue"] is True
    assert ceg_record["final_decision"] is True


@pytest.mark.quick
def test_run_paper_protocol_builds_records_and_artifacts() -> None:
    """paper protocol runner 应同时返回 records、PW02 产物和 PW04 表格。"""
    result = run_paper_protocol(
        _event_rows(),
        profile="paper_main_probe",
        content_thresholds={"ceg": 0.5},
    )

    assert result["profile"] == "paper_main_probe"
    assert len(result["records"]) == 5
    assert "formal_final_decision_metrics.json" in result["pw02_artifacts"]
    assert "formal_main_table.csv" in result["pw04_tables"]
    assert "method_group_comparison_table.csv" in result["pw04_tables"]


@pytest.mark.quick
def test_protocol_runner_emits_mechanism_ablation_records() -> None:
    """payload 中显式请求机制消融时, runner 应输出对应 ablation records。"""
    rows = _event_rows()
    payload = dict(rows[0]["payload"])
    payload["ceg_ablation_variants"] = ["Full", "No-rescue", "No-attestation"]
    rows[0]["payload"] = payload

    result = run_paper_protocol(rows, profile="paper_mechanism_quickcheck", content_thresholds={"ceg": 0.5})

    method_names = {record["method_name"] for record in result["records"]}
    assert {"ceg_full", "ceg_no_rescue", "ceg_no_attestation"} <= method_names
