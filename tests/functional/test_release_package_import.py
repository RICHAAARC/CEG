"""验证最小 CEG 方法发布包可独立导入。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from scripts.extract_minimal_paper_package import extract_profile


@pytest.mark.quick
def test_minimal_method_package_imports_and_runs_decision(tmp_path) -> None:
    """实际抽取的 minimal_method_package 应能独立执行核心 CEG 判定。"""
    package_root = tmp_path / "minimal_method_package"
    manifest = extract_profile(".", package_root, "minimal_method_package", dry_run=False)

    assert "main/methods/ceg/decision.py" in manifest["copied_files"]
    assert all(not path.startswith("tools/") for path in manifest["copied_files"])
    script = '''
from main.methods.ceg import AttestationEvidence, CegThresholds, ContentEvidence, GeometryEvidence, decide_ceg_event
result = decide_ceg_event(
    ContentEvidence(content_score_raw=0.49, content_score_aligned=0.52, content_fail_reason="geometry_suspected"),
    GeometryEvidence(registration_confidence=0.9, anchor_inlier_ratio=0.8, recovered_sync_consistency=0.85),
    AttestationEvidence(attestation_score=0.8),
    CegThresholds(content_threshold=0.5, attestation_threshold=0.5),
).to_record()
print(result["final_decision"])
'''
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=package_root,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "True"
    extraction_manifest = json.loads((package_root / "extraction_manifest.json").read_text(encoding="utf-8"))
    assert extraction_manifest["profile_name"] == "minimal_method_package"
