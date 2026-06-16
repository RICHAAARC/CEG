from pathlib import Path

from scripts.audit_completion import run_completion_audit


def test_completion_audit_passes_and_covers_release_boundaries(tmp_path):
    """完成度审计应同时覆盖方法边界、baseline、发布包和原仓库未修改状态。"""
    repo_root = Path(__file__).resolve().parents[2]
    ceg_wm_root = Path("D:/Code/CEG-WM")
    report = run_completion_audit(
        repo_root,
        ceg_wm_root=ceg_wm_root if ceg_wm_root.exists() else None,
        output_root=tmp_path / "completion_audit",
    )

    assert report["overall_decision"] == "pass"
    requirement_names = {item["requirement"] for item in report["checks"]}
    assert {
        "core_method_has_no_embedded_legacy_gate",
        "external_baseline_registry_complete",
        "minimal_method_package_extractable",
        "paper_artifact_rebuild_package_extractable",
        "ceg_wm_not_modified",
    } <= requirement_names
    clean_files_check = next(item for item in report["checks"] if item["requirement"] == "required_clean_ceg_modules")
    artifact_package_check = next(
        item for item in report["checks"] if item["requirement"] == "paper_artifact_rebuild_package_extractable"
    )
    assert "scripts/run_colab_acceptance_checks.py" in clean_files_check["evidence"]
    assert "scripts/run_colab_acceptance_checks.py" in artifact_package_check["evidence"]["required"]

