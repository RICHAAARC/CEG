"""验证外部 CEG detector command plan 与结果包 provenance 接入。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.detection_plan import load_detection_command_plan, validate_detection_output_root
from main.analysis.result_package import export_paper_results_package


@pytest.mark.quick
def test_detection_command_plan_runs_and_writes_execution_manifest(tmp_path) -> None:
    """detection plan CLI 应执行外部 detector 并复制统一 detection 输出。"""
    detector_output = tmp_path / "detector_output"
    code = (
        "import json, pathlib; "
        f"root=pathlib.Path(r'{detector_output}'); root.mkdir(parents=True, exist_ok=True); "
        "events=[{'event_id':'e1','split':'test','sample_role':'positive_source','attack_family':'clean','attack_condition':'clean_none','is_watermarked':True,"
        "'payload':{'thresholds':{'content_threshold':0.5,'attestation_threshold':0.5},'content':{'content_score_raw':0.8},'attestation':{'attestation_score':0.9}}}]; "
        "(root/'detection_events.json').write_text(json.dumps(events), encoding='utf-8'); "
        "(root/'detection_thresholds.json').write_text(json.dumps({'ceg':0.5}), encoding='utf-8')"
    )
    plan_path = tmp_path / "detection_plan.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "detector_id": "ceg_external_detector",
                    "command": [sys.executable, "-c", code],
                    "output_root": str(detector_output),
                    "timeout_seconds": 30,
                }
            ]
        ),
        encoding="utf-8",
    )
    output_root = tmp_path / "ceg_detection"

    specs = load_detection_command_plan(plan_path)
    assert specs[0].detector_id == "ceg_external_detector"
    subprocess.run(
        [sys.executable, "scripts/run_detection_plan.py", "--plan", str(plan_path), "--out", str(output_root), "--require-pass"],
        cwd=".",
        check=True,
    )

    manifest = json.loads((output_root / "ceg_detection_execution_manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifact_name"] == "ceg_detection_execution_manifest.json"
    assert manifest["formal_result_claim"] is False
    assert manifest["pass_count"] == 1
    assert (output_root / "detection_events.json").is_file()
    assert (output_root / "detection_thresholds.json").is_file()
    contract = validate_detection_output_root(output_root)
    assert contract["overall_decision"] == "pass"
    assert contract["event_count"] == 1


@pytest.mark.quick
def test_build_paper_outputs_copies_detection_execution_manifest(tmp_path) -> None:
    """build_paper_outputs 应将 detection execution manifest 纳入结果包。"""
    events_path = tmp_path / "events.json"
    thresholds_path = tmp_path / "thresholds.json"
    detection_manifest_path = tmp_path / "ceg_detection_execution_manifest.json"
    output_root = tmp_path / "paper_outputs"
    package_root = tmp_path / "paper_results_package"
    events_path.write_text(
        json.dumps(
            [
                {
                    "event_id": "e1",
                    "split": "test",
                    "sample_role": "positive_source",
                    "attack_family": "clean",
                    "attack_condition": "clean_none",
                    "is_watermarked": True,
                    "payload": {
                        "thresholds": {"content_threshold": 0.5, "attestation_threshold": 0.5},
                        "content": {"content_score_raw": 0.8},
                        "attestation": {"attestation_score": 0.9},
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    thresholds_path.write_text(json.dumps({"ceg": 0.5}), encoding="utf-8")
    detection_manifest_path.write_text(
        json.dumps(
            {
                "artifact_name": "ceg_detection_execution_manifest.json",
                "producer_id": "test_detector",
                "formal_result_claim": False,
                "events_path": str(events_path),
                "thresholds_path": str(thresholds_path),
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/build_paper_outputs.py",
            "--events",
            str(events_path),
            "--thresholds",
            str(thresholds_path),
            "--detection-execution-manifest",
            str(detection_manifest_path),
            "--out",
            str(output_root),
        ],
        cwd=".",
        check=True,
    )
    summary = json.loads((output_root / "paper_outputs_summary.json").read_text(encoding="utf-8"))
    package_manifest = export_paper_results_package(output_root, package_root, require_readiness=False)

    assert summary["detection_execution_manifest_path"] == "detection_results/ceg_detection_execution_manifest.json"
    assert "detection_results/ceg_detection_execution_manifest.json" in package_manifest["copied_files"]
