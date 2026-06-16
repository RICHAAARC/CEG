"""验证论文输出 readiness 报告和校验 CLI。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from main.analysis.paper_readiness import validate_paper_output_directory


BASELINES = ("tree_ring", "gaussian_shading", "shallow_diffuse", "stable_signature_dee")
ABLATIONS = ("Full", "Content-only", "Recover-then-Content", "No-rescue", "No-attestation")


def _baseline_observations(event_id: str, score: float) -> list[dict[str, object]]:
    """构造覆盖全部外部 baseline 的轻量 observation。"""
    return [
        {
            "baseline_id": baseline_id,
            "score": score,
            "threshold": 0.5,
            "bit_correct_count": 31,
            "bit_total_count": 32,
            "payload_recovered": True,
            "psnr": 38.0,
            "ssim": 0.96,
            "lpips": 0.04,
            "fid": 8.0,
            "clip_score": 0.32,
        }
        for baseline_id in BASELINES
    ]


def _event(event_id: str, sample_role: str, is_watermarked: bool, score: float, attack_family: str) -> dict[str, object]:
    """构造能同时驱动 CEG、消融、baseline 和标准指标的协议事件。"""
    return {
        "event_id": event_id,
        "split": "test",
        "sample_role": sample_role,
        "attack_family": attack_family,
        "attack_condition": f"{attack_family}_light" if attack_family != "clean" else "clean_none",
        "is_watermarked": is_watermarked,
        "payload": {
            "thresholds": {"content_threshold": 0.5, "attestation_threshold": 0.5},
            "content": {
                "content_score_raw": score,
                "content_score_aligned": max(score, 0.55) if is_watermarked else score,
            },
            "geometry": {
                "registration_confidence": 0.9,
                "anchor_inlier_ratio": 0.85,
                "recovered_sync_consistency": 0.88,
            },
            "attestation": {"attestation_score": 0.9},
            "ceg_ablation_variants": list(ABLATIONS),
            "baseline_observations": _baseline_observations(event_id, 0.8 if is_watermarked else 0.2),
            "standard_metrics": {
                "bit_correct_count": 31,
                "bit_total_count": 32,
                "payload_recovered": is_watermarked,
                "psnr": 39.0,
                "ssim": 0.97,
                "lpips": 0.03,
                "fid": 7.5,
                "clip_score": 0.35,
            },
        },
    }


@pytest.mark.quick
def test_build_paper_outputs_can_require_paper_readiness(tmp_path) -> None:
    """完整轻量样例应能通过一键输出和 readiness 校验。"""
    events_path = tmp_path / "events.json"
    thresholds_path = tmp_path / "thresholds.json"
    output_root = tmp_path / "paper_outputs"
    events_path.write_text(
        json.dumps(
            [
                _event("positive", "positive_source", True, 0.72, "crop"),
                _event("clean_negative", "clean_negative", False, 0.18, "clean"),
                _event("attacked_negative", "attacked_negative", False, 0.2, "jpeg"),
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    thresholds_path.write_text(json.dumps({"ceg": 0.5}), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/build_paper_outputs.py",
            "--events",
            str(events_path),
            "--thresholds",
            str(thresholds_path),
            "--out",
            str(output_root),
            "--require-paper-readiness",
        ],
        cwd=".",
        check=True,
    )

    report = json.loads((output_root / "paper_readiness_report.json").read_text(encoding="utf-8"))
    summary = json.loads((output_root / "paper_outputs_summary.json").read_text(encoding="utf-8"))
    assert report["overall_decision"] == "pass"
    assert summary["paper_readiness_decision"] == "pass"
    assert (output_root / "pdf_figures" / "paper_figures_preview.pdf").read_bytes().startswith(b"%PDF")


@pytest.mark.quick
def test_validate_paper_output_directory_reports_missing_baselines(tmp_path) -> None:
    """缺少外部 baseline 或消融 records 时 readiness 应明确失败。"""
    output_root = tmp_path / "incomplete_outputs"
    output_root.mkdir()
    (output_root / "event_records.json").write_text(
        json.dumps([{"event_id": "e1", "method_name": "ceg", "sample_role": "positive_source"}]),
        encoding="utf-8",
    )

    report = validate_paper_output_directory(output_root)

    assert report["overall_decision"] == "fail"
    method_check = next(item for item in report["checks"] if item["requirement"] == "required_methods_present")
    assert "tree_ring" in method_check["evidence"]["missing"]


@pytest.mark.quick
def test_validate_paper_outputs_cli_allows_incomplete_report(tmp_path) -> None:
    """CLI 在 allow-incomplete 模式下应写出失败报告但不阻断调试流程。"""
    output_root = tmp_path / "incomplete_outputs"
    output_root.mkdir()
    (output_root / "event_records.json").write_text("[]", encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/validate_paper_outputs.py",
            "--output-root",
            str(output_root),
            "--allow-incomplete",
        ],
        cwd=".",
        check=True,
    )

    report = json.loads((output_root / "paper_readiness_report.json").read_text(encoding="utf-8"))
    assert report["overall_decision"] == "fail"
