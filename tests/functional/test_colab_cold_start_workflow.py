"""验证 Colab Notebook 冷启动入口遵守 Notebook 边界。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile

import pytest

from paper_workflow.colab_utils.cold_start import build_colab_command_plan, build_colab_formal_input_contract, build_colab_formal_run_checklist, build_colab_formal_input_templates_manifest, build_colab_formal_runbook, build_colab_input_manifest, build_colab_formal_result_gap_report, build_colab_output_layout, build_colab_output_layout_manifest, build_colab_paper_result_index, copy_provided_result_files, create_colab_bundle_archive, run_colab_cold_start_pipeline, validate_colab_run_bundle
from scripts.extract_minimal_paper_package import extract_profile


@pytest.mark.quick
def test_colab_notebook_is_parseable_and_delegates_to_helpers() -> None:
    """Colab Notebook 应能解析, 且只调度 helper, 不手写正式产物。"""
    notebook_path = "paper_workflow/colab_ceg_cold_start.ipynb"
    notebook = json.loads(open(notebook_path, encoding="utf-8").read())
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert notebook["nbformat"] == 4
    assert "prepare_p0_input_materials_from_notebook" in source
    assert "RUN_P0_INPUT_MATERIALS" in source
    assert "P0_OVERWRITE_EXISTING_MATERIALS" in source
    assert "pilot_input_value_pack_fill_sheet" in source
    assert "pilot_input_value_pack_fill_sheet_guidance" in source
    assert "pilot_input_value_pack_status_report" in source
    assert "validate_p0_fill_sheet_from_notebook" in source
    assert "RUN_P0_FILL_SHEET_VALIDATION" in source
    assert "P0_FILL_SHEET_REQUIRE_PASS" in source
    assert "pilot_input_value_pack_fill_sheet_validation_report" in source
    assert "pilot_input_value_pack_fill_sheet_validation_markdown" in source
    assert "run_p0_input_freeze_from_notebook" in source
    assert "RUN_P0_INPUT_FREEZE" in source
    assert "P0_DRY_RUN" in source
    assert "P0_REQUIRE_PASS" in source
    assert "PILOT_WORKSPACE_ROOT" in source
    assert "pilot_p0_input_freeze_dry_run_report" in source
    assert "pilot_p0_input_freeze_report" in source
    assert "run_colab_paper_outputs_from_notebook" in source
    assert "write_colab_formal_run_checklist_from_notebook" in source
    assert 'REPO_BRANCH = ""' in source
    assert "if REPO_BRANCH:" in source
    assert 'clone_command.extend(["--branch", REPO_BRANCH])' in source
    assert '"git", "clone", "--branch", REPO_BRANCH' not in source
    assert "colab_formal_run_checklist.json" in source
    assert "build_paper_outputs.py" not in source
    assert "paper_claim_audit.json" in source
    assert "REQUIRE_EXPERIMENT_COVERAGE" in source
    assert "REQUIRE_GPU_FOR_EXTERNAL_PLANS" in source
    assert "gpu_readiness" in source
    assert "/content/drive/MyDrive/CEG" in source
    assert "DRIVE_OUTPUT_ROOT" in source
    assert "build_colab_output_layout" in source
    assert "archives_root" in source
    assert "colab_output_layout_manifest" in source
    assert "colab_formal_input_contract" in source
    assert "write_colab_formal_input_templates" in source
    assert "formal_input_templates_manifest" in source
    assert "formal_input_contract_version" in source
    assert "formal_input_template_count" in source
    assert "colab_paper_result_index" in source
    assert "colab_paper_result_semantic_check_summary" in source
    assert "colab_paper_result_semantic_check_failures" in source
    assert "colab_paper_result_required_group_failures" in source
    assert "colab_paper_result_production_trace_summary" in source
    assert "colab_formal_result_gap_report" in source
    assert "colab_formal_runbook" in source
    assert "formal_result_gap_decision" in source
    assert "formal_runbook_path" in source
    assert "ceg_colab_run_bundle.zip" in source
    assert "create_colab_bundle_archive" in source
    assert "colab_bundle_archive_manifest.json" in source
    assert "archive_manifest_path" in source
    assert "files.download(str(archive_manifest_path))" in source
    assert "shutil.make_archive" not in source
    assert "colab_run_bundle_manifest.json" in source
    assert "colab_run_bundle_validation.json" in source
    assert "formal_input_source_preflight" in source
    assert "provided_result_file_preflight" in source
    assert "external_plan_preflight" in source
    assert "paper_result_evidence_decision" in source
    assert "colab_run_bundle_validation_decision" in source
    assert "colab_acceptance_decision" in source
    assert "provided_result_files_manifest" in source
    assert ".write_text" not in source


@pytest.mark.quick
def test_colab_command_plan_uses_repository_scripts(tmp_path) -> None:
    """Colab command plan 应显式调用仓库脚本生成结果和结果包。"""
    plan = build_colab_command_plan(".", tmp_path / "workspace", repetitions=2)

    assert plan["use_dry_run_inputs"] is True
    assert "build_experiment_matrix.py" in " ".join(plan["matrix_command"])
    assert "build_paper_dry_run_inputs.py" in " ".join(plan["prepare_command"])
    assert "build_paper_outputs.py" in " ".join(plan["build_command"])
    assert "export_paper_results_package.py" in " ".join(plan["package_command"])
    assert "--experiment-matrix" in plan["build_command"]
    assert plan["package_root"].endswith("paper_results_package")
    assert plan["drive_output_root"] == str((tmp_path / "workspace").resolve())
    assert plan["output_layout"]["archives_root"].endswith("archives")


@pytest.mark.quick
def test_colab_output_layout_partitions_drive_results_by_type(tmp_path) -> None:
    """Colab 输出根目录应按结果类型提供稳定子目录, 供 Notebook 和 helper 共享。"""
    layout = build_colab_output_layout(tmp_path / "workspace")

    assert layout["drive_output_root"] == str((tmp_path / "workspace").resolve())
    assert layout["paper_outputs_root"].endswith("paper_outputs")
    assert layout["paper_results_package_root"].endswith("paper_results_package")
    assert layout["colab_run_bundle_root"].endswith("colab_run_bundle")
    assert layout["provided_results_root"].endswith("provided_results")
    assert layout["external_baselines_root"].endswith("external_baselines")
    assert layout["external_metrics_root"].endswith("external_metrics")
    assert layout["archives_root"].endswith("archives")

    manifest = build_colab_output_layout_manifest(tmp_path / "workspace")
    assert manifest["artifact_name"] == "colab_output_layout_manifest.json"
    assert manifest["drive_output_root"] == layout["drive_output_root"]
    assert len(manifest["layout_digest"]) == 64
    result_types = {item["result_type"] for item in manifest["result_type_directories"]}
    assert {"paper_outputs", "paper_results_package", "external_baselines", "external_metrics", "archives"}.issubset(result_types)


@pytest.mark.quick
def test_colab_formal_input_contract_documents_formal_sources(tmp_path) -> None:
    """正式输入契约应声明 Colab 产出论文级结果所需的输入文件、字段和第三方接口。"""
    contract = build_colab_formal_input_contract(tmp_path / "workspace")

    assert contract["artifact_name"] == "colab_formal_input_contract.json"
    assert contract["contract_version"] == "ceg_colab_formal_input_contract_v1"
    assert len(contract["contract_digest"]) == 64
    roles = {item["role"] for item in contract["input_files"]}
    assert {"events", "thresholds", "sample_manifest", "baseline_observations", "metric_rows", "image_pairs"}.issubset(roles)
    baseline_entry = next(item for item in contract["input_files"] if item["role"] == "baseline_observations")
    assert {"event_id", "baseline_id", "score", "threshold"}.issubset(set(baseline_entry["required_fields"]))
    metric_entry = next(item for item in contract["input_files"] if item["role"] == "metric_rows")
    assert "one of: lpips, fid, clip_score" in metric_entry["required_fields"]
    interfaces = {item["interface_id"] for item in contract["third_party_command_interfaces"]}
    assert {"external_baseline_run_ceg_eval", "external_advanced_metric_scripts"}.issubset(interfaces)
    requirements = set(contract["formal_acceptance_requirements"])
    assert "provided_file source mode requires provided_result_files_manifest_valid" in requirements
    assert "external_plan source mode requires strict run_colab_acceptance_checks with --require-external-command-results" in requirements
    assert "colab_formal_result_gap_report records ready_for_formal_claims before formal paper claims" in requirements
    assert "colab_paper_result_index production_trace_summary missing_trace_count=0" in requirements
    templates_manifest = build_colab_formal_input_templates_manifest(tmp_path / "workspace")
    assert templates_manifest["artifact_name"] == "formal_input_templates_manifest.json"
    assert templates_manifest["template_count"] >= 6
    assert {"events", "thresholds", "sample_manifest", "baseline_observations", "metric_rows", "image_pairs"}.issubset(set(templates_manifest["template_roles"]))
    runbook = build_colab_formal_runbook(tmp_path / "workspace")
    assert "# CEG Colab 正式运行说明书" in runbook
    assert "正式输入准备" in runbook
    assert "验收命令" in runbook


@pytest.mark.quick
def test_colab_paper_result_index_maps_required_paper_outputs(tmp_path) -> None:
    """论文结果索引应显式列出表格、图表、指标、baseline 和消融交付件。"""
    index = build_colab_paper_result_index(tmp_path / "workspace")

    assert index["artifact_name"] == "colab_paper_result_index.json"
    assert index["overall_decision"] == "fail"
    assert len(index["result_index_digest"]) == 64
    result_ids = {item["result_id"] for item in index["indexed_results"]}
    assert {
        "formal_main_table",
        "formal_final_decision_metrics",
        "content_score_distribution_audit",
        "content_threshold_degeneracy_report",
        "rescue_metrics_summary",
        "standard_watermark_metrics",
        "quality_metrics_summary",
        "attack_family_metrics",
        "rate_confidence_intervals",
        "detection_roc_curve",
        "score_histogram_table",
        "baseline_comparison_table",
        "method_group_comparison_table",
        "method_pairwise_delta_table",
        "paper_figure_specs",
        "paper_results_report",
        "colab_formal_input_contract",
        "formal_input_templates_manifest",
        "colab_formal_runbook",
        "colab_bundle_archive",
    }.issubset(result_ids)
    result_groups = {item["result_group"] for item in index["indexed_results"]}
    assert {"watermark_standard_metrics", "baseline_and_ablation", "figures", "paper_reports"}.issubset(result_groups)
    requirements = json.loads(open("configs/paper_output_requirements.json", encoding="utf-8").read())
    indexed_paths = {item["relative_path"] for item in index["indexed_results"]}
    required_artifact_paths = {
        f"paper_results_package/artifacts/{artifact_name}"
        for artifact_name in requirements["required_artifacts"]
    }
    required_latex_paths = {
        f"paper_results_package/latex_tables/{table_name}"
        for table_name in requirements["required_latex_tables"]
    }
    assert required_artifact_paths.issubset(indexed_paths)
    assert required_latex_paths.issubset(indexed_paths)
    required_group_decisions = {item["result_group"]: item["overall_decision"] for item in index["required_result_group_summary"]}
    assert required_group_decisions["watermark_standard_metrics"] == "fail"
    assert required_group_decisions["baseline_and_ablation"] == "fail"
    assert index["required_result_group_count"] >= 5
    assert index["required_result_group_pass_count"] == 0
    assert index["semantic_check_summary"]["checkable_total"] == 0
    assert index["semantic_check_failures"] == []
    assert "watermark_standard_metrics" in index["required_result_group_failures"]
    watermark_group = next(item for item in index["required_result_group_summary"] if item["result_group"] == "watermark_standard_metrics")
    assert {"standard_watermark_metrics", "quality_metrics_summary", "bit_recovery_metrics"}.issubset(set(watermark_group["missing_required_results"]))
    assert index["production_trace_summary"]["missing_trace_count"] == 0
    entry_by_id = {item["result_id"]: item for item in index["indexed_results"]}
    standard_trace = entry_by_id["standard_watermark_metrics"]["production_trace"]
    assert "scripts/build_paper_outputs.py" in standard_trace["producer_steps"]
    assert "colab_paper_result_index semantic_check" in standard_trace["validation_gates"]
    baseline_trace = entry_by_id["baseline_comparison_table"]["production_trace"]
    assert "scripts/run_baseline_plan.py 或 copy_provided_result_files" in baseline_trace["producer_steps"]
    assert "paper_result_evidence_report.json baseline_source_ready" in baseline_trace["validation_gates"]
    figure_trace = entry_by_id["paper_figure_specs"]["production_trace"]
    assert "main.analysis.figure_specs.build_paper_figure_specs" in figure_trace["producer_steps"]
    archive_trace = entry_by_id["colab_bundle_archive"]["production_trace"]
    assert "create_colab_bundle_archive" in archive_trace["producer_steps"]
    assert "run_colab_acceptance_checks.py" in archive_trace["validation_gates"]


@pytest.mark.quick
def test_colab_paper_result_index_rejects_malformed_required_result_content(tmp_path) -> None:
    """论文结果索引不能只检查文件存在, 还应发现关键结果文件内容结构错误。"""
    artifact_root = tmp_path / "workspace" / "paper_results_package" / "artifacts"
    artifact_root.mkdir(parents=True)
    metrics_path = artifact_root / "standard_watermark_metrics.json"
    metrics_path.write_text(
        json.dumps({"artifact_name": "standard_watermark_metrics.json", "by_method": {"ceg": {}}}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    index = build_colab_paper_result_index(tmp_path / "workspace")

    assert index["overall_decision"] == "fail"
    assert "standard_watermark_metrics" in index["semantic_check_failures"]
    metrics_entry = next(item for item in index["indexed_results"] if item["result_id"] == "standard_watermark_metrics")
    assert metrics_entry["exists"] is True
    assert metrics_entry["semantic_check"]["status"] == "fail"
    assert metrics_entry["semantic_check"]["checks"][0]["reason"] == "required_methods_missing_from_standard_metrics"


@pytest.mark.quick
def test_colab_paper_result_index_rejects_incomplete_baseline_and_ablation_tables(tmp_path) -> None:
    """论文结果索引应拒绝缺少外部 baseline 或内部消融覆盖的关键对比表。"""
    artifact_root = tmp_path / "workspace" / "paper_results_package" / "artifacts"
    artifact_root.mkdir(parents=True)
    (artifact_root / "baseline_comparison_table.csv").write_text(
        "method_name,event_count,tpr,clean_fpr\nceg,4,0.5,0.0\n",
        encoding="utf-8",
    )
    (artifact_root / "method_group_comparison_table.csv").write_text(
        "method_name,method_group,comparison_role,event_count,tpr,clean_fpr\n"
        "ceg,ceg_primary,proposed_method,4,0.5,0.0\n"
        "tree_ring,external_baseline,mechanism_ablation,4,1.0,0.0\n",
        encoding="utf-8",
    )
    (artifact_root / "method_pairwise_delta_table.csv").write_text(
        "reference_method,method_name,metric_name,rate_delta\nceg,ceg_full,tpr,0.0\n",
        encoding="utf-8",
    )

    index = build_colab_paper_result_index(tmp_path / "workspace")

    assert index["overall_decision"] == "fail"
    assert {"baseline_comparison_table", "method_group_comparison_table", "method_pairwise_delta_table"}.issubset(
        set(index["semantic_check_failures"])
    )
    entries = {item["result_id"]: item for item in index["indexed_results"]}
    assert entries["baseline_comparison_table"]["semantic_check"]["checks"][0]["reason"] == "required_method_rows_incomplete"
    assert entries["method_group_comparison_table"]["semantic_check"]["checks"][0]["reason"] == "required_method_rows_incomplete"
    assert entries["method_pairwise_delta_table"]["semantic_check"]["checks"][0]["reason"] == "pairwise_delta_rows_incomplete"


@pytest.mark.quick
def test_colab_formal_result_gap_report_explains_missing_formal_evidence(tmp_path) -> None:
    """正式结果缺口报告应把 dry-run、覆盖率、外部结果和严格验收缺口列为阻断项。"""
    report = build_colab_formal_result_gap_report(tmp_path / "workspace")

    assert report["artifact_name"] == "colab_formal_result_gap_report.json"
    assert report["overall_decision"] == "not_ready_for_formal_claims"
    requirements = {item["requirement"] for item in report["checks"] if item["status"] != "pass"}
    assert {
        "non_dry_run_inputs_used",
        "formal_run_checklist_passed",
        "paper_result_index_complete",
        "paper_result_index_production_trace_complete",
        "experiment_matrix_coverage_enforced",
        "external_baseline_source_ready",
        "advanced_metric_source_ready",
        "strict_paper_result_evidence_passed",
        "strict_colab_acceptance_passed",
    }.issubset(requirements)


@pytest.mark.quick
def test_colab_formal_run_checklist_preflights_formal_input_sources(tmp_path) -> None:
    """正式运行清单应在启动长耗时实验前检查 events、thresholds 与 image pairs 的结构。"""
    events_path = tmp_path / "events.json"
    thresholds_path = tmp_path / "thresholds.json"
    image_pairs_path = tmp_path / "image_pairs.json"
    events_path.write_text(json.dumps([{"event_id": "e1", "split": "test"}]), encoding="utf-8")
    thresholds_path.write_text(json.dumps({}), encoding="utf-8")
    image_pairs_path.write_text(json.dumps([{"reference_path": "ref.png"}]), encoding="utf-8")

    checklist = build_colab_formal_run_checklist(
        ".",
        tmp_path / "workspace",
        use_dry_run_inputs=False,
        require_experiment_coverage=True,
        events_path=events_path,
        thresholds_path=thresholds_path,
        image_pairs_path=image_pairs_path,
    )

    assert checklist["formal_input_source_preflight"]["status"] == "fail"
    assert checklist["formal_input_source_violation_count"] >= 3
    issue_ids = {item["issue_id"] for item in checklist["issues"]}
    assert "formal_input_source_preflight_failed" in issue_ids
    checks = {item["file_kind"]: item for item in checklist["formal_input_source_preflight"]["checks"]}
    assert checks["events"]["status"] == "fail"
    assert checks["thresholds"]["status"] == "fail"
    assert checks["image_pairs"]["status"] == "fail"


@pytest.mark.quick
def test_colab_formal_result_gap_report_rejects_missing_result_index_production_trace(tmp_path) -> None:
    """正式缺口报告应把缺少生产追踪的论文结果索引列为阻断项。"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "colab_formal_run_checklist.json").write_text(
        json.dumps(
            {
                "artifact_name": "colab_formal_run_checklist.json",
                "overall_decision": "pass",
                "blocking_issue_count": 0,
                "use_dry_run_inputs": False,
                "run_external_plans": False,
                "require_experiment_coverage": True,
                "baseline_source_mode": "provided_file",
                "metric_source_mode": "provided_file",
                "gpu_readiness": {"checked_for_formal_external_plans": False, "gpu_available": False},
                "issues": [],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / "colab_paper_result_index.json").write_text(
        json.dumps(
            {
                "artifact_name": "colab_paper_result_index.json",
                "overall_decision": "pass",
                "required_missing": [],
                "required_present": 3,
                "required_total": 3,
                "required_result_group_failures": [],
                "semantic_check_summary": {"fail_count": 0},
                "semantic_check_failures": [],
                "production_trace_summary": {"missing_trace_count": 1, "missing_trace_result_ids": ["standard_watermark_metrics"]},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_colab_formal_result_gap_report(workspace)

    assert report["overall_decision"] == "not_ready_for_formal_claims"
    assert "paper_result_index_production_trace_complete" in report["blocking_gap_requirements"]
    checks = {item["requirement"]: item for item in report["checks"]}
    assert checks["paper_result_index_production_trace_complete"]["evidence"]["missing_trace_result_ids"] == ["standard_watermark_metrics"]


@pytest.mark.quick
def test_colab_formal_result_gap_report_accepts_provided_file_strict_path(tmp_path) -> None:
    """直接提供 baseline / metric 结果文件时, 严格缺口报告应依赖 provided_results manifest, 而不是强制外部命令结果。"""
    workspace = tmp_path / "workspace"
    artifacts_root = workspace / "paper_results_package" / "artifacts"
    provided_root = workspace / "provided_results"
    artifacts_root.mkdir(parents=True)
    provided_root.mkdir(parents=True)

    (workspace / "colab_formal_run_checklist.json").write_text(
        json.dumps(
            {
                "artifact_name": "colab_formal_run_checklist.json",
                "overall_decision": "pass",
                "blocking_issue_count": 0,
                "use_dry_run_inputs": False,
                "run_external_plans": False,
                "require_experiment_coverage": True,
                "baseline_source_mode": "provided_file",
                "metric_source_mode": "provided_file",
                "gpu_readiness": {"checked_for_formal_external_plans": False, "gpu_available": False},
                "issues": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / "colab_paper_result_index.json").write_text(
        json.dumps(
            {
                "artifact_name": "colab_paper_result_index.json",
                "overall_decision": "pass",
                "required_missing": [],
                "required_present": 3,
                "required_total": 3,
                "required_result_group_failures": [],
                "semantic_check_summary": {"fail_count": 0},
                "semantic_check_failures": [],
                "production_trace_summary": {"missing_trace_count": 0, "missing_trace_result_ids": []},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (artifacts_root / "paper_experiment_coverage_report.json").write_text(
        json.dumps({"artifact_name": "paper_experiment_coverage_report.json", "overall_decision": "pass"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (provided_root / "provided_result_files_manifest.json").write_text(
        json.dumps({"artifact_name": "provided_result_files_manifest.json", "overall_decision": "pass", "copied_files": []}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (workspace / "paper_result_evidence_report.json").write_text(
        json.dumps(
            {
                "artifact_name": "paper_result_evidence_report.json",
                "overall_decision": "pass",
                "allow_dry_run": False,
                "require_experiment_coverage": True,
                "require_external_command_results": False,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    acceptance_payload = {
        "artifact_name": "colab_acceptance_report.json",
        "overall_decision": "pass",
        "allow_dry_run": False,
        "require_experiment_coverage": True,
        "require_external_command_results": False,
        "report_decisions": {
            "colab_run_bundle_validation": "pass",
            "paper_result_evidence": "pass",
            "formal_result_gap": "ready_for_formal_claims",
        },
        "blocking_report_decisions": {
            "colab_run_bundle_validation": "pass",
            "paper_result_evidence": "pass",
        },
        "formal_result_gap_decision": "ready_for_formal_claims",
    }

    report_without_acceptance = build_colab_formal_result_gap_report(workspace)
    assert report_without_acceptance["overall_decision"] == "not_ready_for_formal_claims"
    assert "strict_colab_acceptance_passed" in report_without_acceptance["blocking_gap_requirements"]

    report = build_colab_formal_result_gap_report(workspace, acceptance_report_override=acceptance_payload)
    assert report["overall_decision"] == "ready_for_formal_claims"
    assert report["blocking_gap_requirements"] == []
    checks = {item["requirement"]: item for item in report["checks"]}
    assert checks["external_command_result_files_present"]["status"] == "pass"
    assert checks["provided_result_files_manifest_ready"]["status"] == "pass"
    assert checks["paper_result_index_production_trace_complete"]["status"] == "pass"
    assert checks["strict_paper_result_evidence_passed"]["status"] == "pass"
    assert checks["strict_colab_acceptance_passed"]["status"] == "pass"


@pytest.mark.quick
def test_colab_cold_start_pipeline_runs_dry_run_to_package(tmp_path) -> None:
    """本地轻量 dry-run 应验证 Colab helper 能从冷启动输入走到结果包。"""
    summary = run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)

    assert summary["overall_decision"] == "pass"
    package_root = tmp_path / "colab_workspace" / "paper_results_package"
    assert (package_root / "paper_results_package_manifest.json").exists()
    assert (package_root / "artifacts" / "paper_claim_audit.json").exists()
    assert (package_root / "artifacts" / "paper_experiment_coverage_report.json").exists()
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"
    assert (bundle_root / "colab_run_bundle_manifest.json").exists()
    assert (bundle_root / "colab_run_bundle_validation.json").exists()
    assert (bundle_root / "colab_output_layout_manifest.json").exists()
    assert (bundle_root / "colab_formal_input_contract.json").exists()
    assert (bundle_root / "inputs" / "formal_input_templates_manifest.json").exists()
    assert (bundle_root / "inputs" / "formal_input_templates" / "events_template.json").exists()
    assert (bundle_root / "colab_formal_runbook.md").exists()
    assert (bundle_root / "colab_paper_result_index.json").exists()
    assert (bundle_root / "colab_formal_result_gap_report.json").exists()
    assert (bundle_root / "colab_formal_run_checklist.json").exists()
    assert (bundle_root / "paper_result_evidence_report.json").exists()
    assert (bundle_root / "colab_acceptance_report.json").exists()
    assert (bundle_root / "acceptance" / "colab_run_bundle_validation_cli.json").exists()
    assert (bundle_root / "acceptance" / "paper_result_evidence_cli.json").exists()
    assert (bundle_root / "paper_results_package" / "paper_results_package_manifest.json").exists()
    validation = validate_colab_run_bundle(bundle_root)
    assert validation["overall_decision"] == "pass"
    validation_requirements = {item["requirement"] for item in validation["checks"] if item["status"] == "pass"}
    assert "colab_formal_runbook_contains_acceptance_guidance" in validation_requirements
    assert "colab_paper_result_index_semantic_checks_passed" in validation_requirements
    assert "colab_paper_result_index_production_trace_complete" in validation_requirements
    persisted_validation = json.loads((bundle_root / "colab_run_bundle_validation.json").read_text(encoding="utf-8"))
    assert persisted_validation["overall_decision"] == "pass"
    checklist = json.loads((bundle_root / "colab_formal_run_checklist.json").read_text(encoding="utf-8"))
    evidence_report = json.loads((bundle_root / "paper_result_evidence_report.json").read_text(encoding="utf-8"))
    acceptance_report = json.loads((bundle_root / "colab_acceptance_report.json").read_text(encoding="utf-8"))
    assert checklist["overall_decision"] == "fail"
    assert evidence_report["overall_decision"] == "pass"
    assert evidence_report["target_kind"] == "colab_run_bundle"
    bundle_check = next(item for item in evidence_report["checks"] if item["requirement"] == "colab_formal_run_checklist_passed")
    assert bundle_check["status"] == "pass"
    assert bundle_check["evidence"]["reason"] == "allow_dry_run_enabled"
    assert summary["colab_formal_run_checklist_decision"] == "fail"
    assert summary["paper_result_evidence_decision"] == "pass"
    assert summary["paper_result_evidence_target_kind"] == "colab_run_bundle"
    assert summary["colab_run_bundle_validation_decision"] == "pass"
    assert summary["colab_acceptance_decision"] == "pass"
    assert acceptance_report["overall_decision"] == "pass"
    assert acceptance_report["blocking_report_decisions"] == {
        "colab_run_bundle_validation": "pass",
        "paper_result_evidence": "pass",
    }
    assert acceptance_report["report_decisions"]["formal_result_gap"] == "not_ready_for_formal_claims"
    assert acceptance_report["formal_result_gap_decision"] == "not_ready_for_formal_claims"
    assert acceptance_report["formal_result_gap_decision_mode"] == "post_acceptance_override"
    assert "strict_colab_acceptance_passed" in acceptance_report["formal_result_gap_blocking_gap_requirements"]
    bundled_summary = json.loads((bundle_root / "colab_cold_start_summary.json").read_text(encoding="utf-8"))
    assert bundled_summary["paper_result_evidence_target_kind"] == "colab_run_bundle"
    assert bundled_summary["colab_acceptance_report_decisions"]["formal_result_gap"] == "not_ready_for_formal_claims"
    assert bundled_summary["colab_acceptance_formal_result_gap_decision"] == "not_ready_for_formal_claims"
    assert bundled_summary["colab_acceptance_formal_result_gap_decision_mode"] == "post_acceptance_override"
    layout_manifest = json.loads((tmp_path / "colab_workspace" / "colab_output_layout_manifest.json").read_text(encoding="utf-8"))
    bundled_layout_manifest = json.loads((bundle_root / "colab_output_layout_manifest.json").read_text(encoding="utf-8"))
    assert layout_manifest["artifact_name"] == "colab_output_layout_manifest.json"
    assert bundled_layout_manifest["artifact_name"] == "colab_output_layout_manifest.json"
    assert summary["colab_output_layout_manifest_path"].endswith("colab_output_layout_manifest.json")
    input_contract = json.loads((tmp_path / "colab_workspace" / "colab_formal_input_contract.json").read_text(encoding="utf-8"))
    bundled_input_contract = json.loads((bundle_root / "colab_formal_input_contract.json").read_text(encoding="utf-8"))
    assert input_contract["artifact_name"] == "colab_formal_input_contract.json"
    assert bundled_input_contract["contract_version"] == "ceg_colab_formal_input_contract_v1"
    assert summary["colab_formal_input_contract_path"].endswith("colab_formal_input_contract.json")
    templates_manifest = json.loads((tmp_path / "colab_workspace" / "inputs" / "formal_input_templates_manifest.json").read_text(encoding="utf-8"))
    bundled_templates_manifest = json.loads((bundle_root / "inputs" / "formal_input_templates_manifest.json").read_text(encoding="utf-8"))
    assert templates_manifest["template_count"] >= 6
    assert bundled_templates_manifest["artifact_name"] == "formal_input_templates_manifest.json"
    assert summary["formal_input_templates_manifest_path"].endswith("formal_input_templates_manifest.json")
    runbook_body = (tmp_path / "colab_workspace" / "colab_formal_runbook.md").read_text(encoding="utf-8")
    bundled_runbook_body = (bundle_root / "colab_formal_runbook.md").read_text(encoding="utf-8")
    assert "CEG Colab 正式运行说明书" in runbook_body
    assert "正式输入准备" in bundled_runbook_body
    assert "offline_acceptance" in bundled_runbook_body
    assert "path/to/ceg_colab_run_bundle.zip" in bundled_runbook_body
    assert summary["colab_formal_runbook_path"].endswith("colab_formal_runbook.md")
    assert {item["result_type"] for item in layout_manifest["result_type_directories"]} >= {"paper_outputs", "paper_results_package", "colab_run_bundle", "archives"}
    result_index = json.loads((tmp_path / "colab_workspace" / "colab_paper_result_index.json").read_text(encoding="utf-8"))
    bundled_result_index = json.loads((bundle_root / "colab_paper_result_index.json").read_text(encoding="utf-8"))
    assert result_index["artifact_name"] == "colab_paper_result_index.json"
    assert bundled_result_index["artifact_name"] == "colab_paper_result_index.json"
    assert summary["colab_paper_result_index_path"].endswith("colab_paper_result_index.json")
    gap_report = json.loads((tmp_path / "colab_workspace" / "colab_formal_result_gap_report.json").read_text(encoding="utf-8"))
    bundled_gap_report = json.loads((bundle_root / "colab_formal_result_gap_report.json").read_text(encoding="utf-8"))
    assert gap_report["artifact_name"] == "colab_formal_result_gap_report.json"
    assert bundled_gap_report["artifact_name"] == "colab_formal_result_gap_report.json"
    assert summary["colab_formal_result_gap_report_path"].endswith("colab_formal_result_gap_report.json")
    assert gap_report["overall_decision"] == "not_ready_for_formal_claims"
    assert "non_dry_run_inputs_used" in gap_report["blocking_gap_requirements"]
    assert "strict_paper_result_evidence_passed" in gap_report["blocking_gap_requirements"]
    assert result_index["overall_decision"] == "pass"
    assert result_index["required_missing"] == []
    assert result_index["required_result_group_failures"] == []
    assert result_index["required_result_group_pass_count"] == result_index["required_result_group_count"]
    assert all(item["overall_decision"] == "pass" for item in result_index["required_result_group_summary"])
    assert result_index["semantic_check_failures"] == []
    assert result_index["semantic_check_summary"]["checkable_total"] > 0
    assert result_index["semantic_check_summary"]["fail_count"] == 0
    assert result_index["production_trace_summary"]["missing_trace_count"] == 0
    assert result_index["production_trace_summary"]["traceable_total"] == len(result_index["indexed_results"])
    assert summary["colab_paper_result_semantic_check_summary"] == result_index["semantic_check_summary"]
    assert summary["colab_paper_result_semantic_check_failures"] == []
    assert summary["colab_paper_result_required_group_failures"] == []
    assert summary["colab_paper_result_production_trace_summary"] == result_index["production_trace_summary"]
    assert bundled_summary["colab_paper_result_semantic_check_summary"] == result_index["semantic_check_summary"]
    assert bundled_summary["colab_paper_result_semantic_check_failures"] == []
    assert bundled_summary["colab_paper_result_production_trace_summary"] == result_index["production_trace_summary"]
    standard_metrics_entry = next(item for item in result_index["indexed_results"] if item["result_id"] == "standard_watermark_metrics")
    assert standard_metrics_entry["semantic_check"]["status"] == "pass"
    assert "scripts/build_paper_outputs.py" in standard_metrics_entry["production_trace"]["producer_steps"]
    assert "colab_paper_result_index semantic_check" in standard_metrics_entry["production_trace"]["validation_gates"]
    quality_metrics_entry = next(item for item in result_index["indexed_results"] if item["result_id"] == "quality_metrics_summary")
    assert quality_metrics_entry["semantic_check"]["checks"][0]["reason"] == "quality_metric_rows_cover_standard_fields"
    baseline_entry = next(item for item in result_index["indexed_results"] if item["result_id"] == "baseline_comparison_table")
    assert baseline_entry["semantic_check"]["checks"][0]["reason"] == "baseline_comparison_methods_cover_internal_and_external"
    group_entry = next(item for item in result_index["indexed_results"] if item["result_id"] == "method_group_comparison_table")
    assert group_entry["semantic_check"]["checks"][0]["reason"] == "method_group_roles_cover_proposed_ablation_and_external"
    pairwise_entry = next(item for item in result_index["indexed_results"] if item["result_id"] == "method_pairwise_delta_table")
    assert pairwise_entry["semantic_check"]["checks"][0]["reason"] == "pairwise_delta_rows_cover_ablation_and_external_methods"
    result_ids = {item["result_id"] for item in result_index["indexed_results"] if item["exists"]}
    assert {"formal_main_table", "standard_watermark_metrics", "baseline_comparison_table", "paper_figure_specs"}.issubset(result_ids)
    archive_manifest = summary["colab_bundle_archive_manifest"]
    assert archive_manifest["artifact_name"] == "colab_bundle_archive_manifest.json"
    assert archive_manifest["archive_name"] == "ceg_colab_run_bundle.zip"
    assert archive_manifest["archive_manifest_stage"] == "post_archive_sidecar"
    assert archive_manifest["archive_size_bytes"] > 0
    assert len(archive_manifest["archive_sha256"]) == 64
    assert summary["colab_bundle_archive_path"].endswith("ceg_colab_run_bundle.zip")
    assert summary["colab_bundle_archive_sha256"] == archive_manifest["archive_sha256"]
    offline_command_text = " ".join(summary["colab_bundle_offline_acceptance_command"])
    assert "run_colab_acceptance_checks.py" in offline_command_text
    assert "--allow-dry-run" in offline_command_text
    assert "--allow-missing-experiment-coverage" in offline_command_text
    assert (tmp_path / "colab_workspace" / "archives" / "ceg_colab_run_bundle.zip").exists()
    with zipfile.ZipFile(tmp_path / "colab_workspace" / "archives" / "ceg_colab_run_bundle.zip") as archive:
        zipped_names = set(archive.namelist())
        zipped_runbook_body = archive.read("colab_formal_runbook.md").decode("utf-8")
        zipped_summary = json.loads(archive.read("colab_cold_start_summary.json").decode("utf-8"))
        embedded_archive_manifest = json.loads(archive.read("archives/colab_bundle_archive_manifest.json").decode("utf-8"))
    assert "offline_acceptance" in zipped_runbook_body
    assert "path/to/ceg_colab_run_bundle.zip" in zipped_runbook_body
    assert "archives/colab_bundle_archive_manifest.json" in zipped_names
    assert zipped_summary["colab_bundle_archive_path"].endswith("ceg_colab_run_bundle.zip")
    assert zipped_summary["colab_bundle_archive_manifest_path"].endswith("colab_bundle_archive_manifest.json")
    assert zipped_summary["colab_bundle_archive_name"] == "ceg_colab_run_bundle.zip"
    assert embedded_archive_manifest["archive_manifest_stage"] == "pre_archive_sidecar"
    assert embedded_archive_manifest["offline_acceptance_command"][embedded_archive_manifest["offline_acceptance_command"].index("--bundle") + 1] == "path/to/ceg_colab_run_bundle.zip"
    assert (tmp_path / "colab_workspace" / "archives" / "colab_bundle_archive_manifest.json").exists()
    assert archive_manifest["archive_manifest_path"].endswith("archives" + __import__("os").sep + "colab_bundle_archive_manifest.json")
    assert archive_manifest["archives_root"].endswith("archives")
    assert archive_manifest["output_layout_manifest_path"].endswith("colab_output_layout_manifest.json")
    assert archive_manifest["formal_input_contract_path"].endswith("colab_formal_input_contract.json")
    assert archive_manifest["formal_input_templates_manifest_path"].endswith("formal_input_templates_manifest.json")
    assert archive_manifest["formal_runbook_path"].endswith("colab_formal_runbook.md")
    assert archive_manifest["paper_result_index_path"].endswith("colab_paper_result_index.json")
    assert archive_manifest["formal_result_gap_report_path"].endswith("colab_formal_result_gap_report.json")
    assert archive_manifest["offline_acceptance_command"][archive_manifest["offline_acceptance_command"].index("--bundle") + 1] == "path/to/ceg_colab_run_bundle.zip"
    assert archive_manifest["colab_acceptance_command"][archive_manifest["colab_acceptance_command"].index("--bundle") + 1].endswith("ceg_colab_run_bundle.zip")
    zip_acceptance_report_path = tmp_path / "pipeline_zip_acceptance_report.json"
    zip_acceptance_command = list(archive_manifest["colab_acceptance_command"])
    zip_acceptance_command.extend(["--out", str(zip_acceptance_report_path)])
    zip_acceptance_result = subprocess.run(
        zip_acceptance_command,
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )
    assert zip_acceptance_result.returncode == 0, zip_acceptance_result.stderr
    zip_acceptance_report = json.loads(zip_acceptance_report_path.read_text(encoding="utf-8"))
    assert zip_acceptance_report["overall_decision"] == "pass"
    assert zip_acceptance_report["validated_archive_path"].endswith("ceg_colab_run_bundle.zip")
    formal_like_archive_manifest = create_colab_bundle_archive(
        tmp_path / "colab_workspace",
        archive_path=tmp_path / "formal_like_ceg_colab_run_bundle.zip",
        allow_dry_run=False,
        require_experiment_coverage=True,
        require_external_command_results=True,
    )
    formal_like_command_text = " ".join(formal_like_archive_manifest["offline_acceptance_command"])
    assert "--require-external-command-results" in formal_like_command_text
    assert "--allow-dry-run" not in formal_like_command_text
    assert "--allow-missing-experiment-coverage" not in formal_like_command_text


@pytest.mark.quick
def test_validate_colab_run_bundle_cli_accepts_directory_and_zip(tmp_path) -> None:
    """独立 CLI 应能校验 Colab bundle 目录和下载 zip, 便于离线复核 Colab 运行证据。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"

    directory_report_path = tmp_path / "directory_validation.json"
    directory_result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_colab_run_bundle.py",
            "--bundle",
            str(bundle_root),
            "--out",
            str(directory_report_path),
            "--require-pass",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert directory_result.returncode == 0, directory_result.stderr
    directory_report = json.loads(directory_report_path.read_text(encoding="utf-8"))
    assert directory_report["overall_decision"] == "pass"
    assert directory_report["validated_bundle_path"].endswith("colab_run_bundle")

    archive_base = tmp_path / "ceg_colab_run_bundle"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=bundle_root)
    archive_report_path = tmp_path / "archive_validation.json"
    archive_result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_colab_run_bundle.py",
            "--bundle",
            archive_path,
            "--out",
            str(archive_report_path),
            "--require-pass",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert archive_result.returncode == 0, archive_result.stderr
    archive_report = json.loads(archive_report_path.read_text(encoding="utf-8"))
    assert archive_report["overall_decision"] == "pass"
    assert archive_report["validated_archive_path"].endswith("ceg_colab_run_bundle.zip")

    acceptance_report_path = tmp_path / "acceptance_report.json"
    acceptance_result = subprocess.run(
        [
            sys.executable,
            "scripts/run_colab_acceptance_checks.py",
            "--bundle",
            str(bundle_root),
            "--out",
            str(acceptance_report_path),
            "--allow-dry-run",
            "--allow-missing-experiment-coverage",
            "--require-pass",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert acceptance_result.returncode == 0, acceptance_result.stderr
    acceptance_report = json.loads(acceptance_report_path.read_text(encoding="utf-8"))
    assert acceptance_report["overall_decision"] == "pass"
    assert acceptance_report["blocking_report_decisions"] == {
        "colab_run_bundle_validation": "pass",
        "paper_result_evidence": "pass",
    }
    assert acceptance_report["report_decisions"]["formal_result_gap"] == "not_ready_for_formal_claims"
    assert acceptance_report["formal_result_gap_decision"] == "not_ready_for_formal_claims"
    assert acceptance_report["formal_result_gap_decision_mode"] == "post_acceptance_override"
    assert "strict_colab_acceptance_passed" in acceptance_report["formal_result_gap_blocking_gap_requirements"]

    archive_acceptance_report_path = tmp_path / "archive_acceptance_report.json"
    archive_acceptance_result = subprocess.run(
        [
            sys.executable,
            "scripts/run_colab_acceptance_checks.py",
            "--bundle",
            archive_path,
            "--out",
            str(archive_acceptance_report_path),
            "--allow-dry-run",
            "--allow-missing-experiment-coverage",
            "--require-pass",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert archive_acceptance_result.returncode == 0, archive_acceptance_result.stderr
    archive_acceptance_report = json.loads(archive_acceptance_report_path.read_text(encoding="utf-8"))
    assert archive_acceptance_report["overall_decision"] == "pass"
    assert archive_acceptance_report["blocking_report_decisions"] == {
        "colab_run_bundle_validation": "pass",
        "paper_result_evidence": "pass",
    }
    assert archive_acceptance_report["report_decisions"]["formal_result_gap"] == "not_ready_for_formal_claims"
    assert archive_acceptance_report["formal_result_gap_decision_mode"] == "post_acceptance_override"
    assert "strict_colab_acceptance_passed" in archive_acceptance_report["formal_result_gap_blocking_gap_requirements"]
    assert archive_acceptance_report["validated_archive_path"].endswith("ceg_colab_run_bundle.zip")


@pytest.mark.quick
def test_validate_colab_run_bundle_requires_formal_provenance_files(tmp_path) -> None:
    """Colab bundle 校验应拒绝缺少正式运行清单或结果证据报告的下载包。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"

    missing_checklist_root = tmp_path / "missing_checklist_bundle"
    shutil.copytree(bundle_root, missing_checklist_root)
    (missing_checklist_root / "colab_formal_run_checklist.json").unlink()
    missing_checklist_report = validate_colab_run_bundle(missing_checklist_root)

    assert missing_checklist_report["overall_decision"] == "fail"
    missing_checklist_requirements = {check["requirement"] for check in missing_checklist_report["checks"] if check["status"] == "fail"}
    assert "colab_run_bundle_formal_provenance_files_present" in missing_checklist_requirements

    missing_evidence_root = tmp_path / "missing_evidence_bundle"
    shutil.copytree(bundle_root, missing_evidence_root)
    (missing_evidence_root / "paper_result_evidence_report.json").unlink()
    missing_evidence_report = validate_colab_run_bundle(missing_evidence_root)

    assert missing_evidence_report["overall_decision"] == "fail"
    missing_evidence_requirements = {check["requirement"] for check in missing_evidence_report["checks"] if check["status"] == "fail"}
    assert "colab_run_bundle_formal_provenance_files_present" in missing_evidence_requirements


@pytest.mark.quick
def test_validate_colab_run_bundle_rejects_result_index_semantic_failures(tmp_path) -> None:
    """Colab bundle 验收应拒绝论文结果索引中已经存在但语义结构失败的必需结果。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"

    malformed_index_root = tmp_path / "malformed_result_index_bundle"
    shutil.copytree(bundle_root, malformed_index_root)
    result_index_path = malformed_index_root / "colab_paper_result_index.json"
    result_index = json.loads(result_index_path.read_text(encoding="utf-8"))
    result_index["overall_decision"] = "fail"
    result_index["semantic_check_summary"]["fail_count"] = 1
    result_index["semantic_check_summary"]["required_failures"] = ["standard_watermark_metrics"]
    result_index["semantic_check_failures"] = ["standard_watermark_metrics"]
    result_index_path.write_text(json.dumps(result_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = validate_colab_run_bundle(malformed_index_root)

    assert report["overall_decision"] == "fail"
    failed_requirements = {check["requirement"] for check in report["checks"] if check["status"] == "fail"}
    assert "colab_paper_result_index_semantic_checks_passed" in failed_requirements


@pytest.mark.quick
def test_validate_colab_run_bundle_rejects_missing_result_index_production_trace(tmp_path) -> None:
    """Colab bundle 验收应拒绝缺少生产步骤或验收门禁追踪的论文结果索引。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"

    malformed_index_root = tmp_path / "missing_production_trace_bundle"
    shutil.copytree(bundle_root, malformed_index_root)
    result_index_path = malformed_index_root / "colab_paper_result_index.json"
    result_index = json.loads(result_index_path.read_text(encoding="utf-8"))
    result_index["production_trace_summary"]["missing_trace_count"] = 1
    result_index["production_trace_summary"]["missing_trace_result_ids"] = ["standard_watermark_metrics"]
    result_index_path.write_text(json.dumps(result_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = validate_colab_run_bundle(malformed_index_root)

    assert report["overall_decision"] == "fail"
    failed_requirements = {check["requirement"] for check in report["checks"] if check["status"] == "fail"}
    assert "colab_paper_result_index_production_trace_complete" in failed_requirements


@pytest.mark.quick
def test_validate_colab_run_bundle_requires_passing_bundle_scoped_evidence(tmp_path) -> None:
    """Colab bundle 校验应拒绝失败或未指向 bundle 的 evidence 报告。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"

    failed_evidence_root = tmp_path / "failed_evidence_bundle"
    shutil.copytree(bundle_root, failed_evidence_root)
    failed_evidence_path = failed_evidence_root / "paper_result_evidence_report.json"
    failed_evidence = json.loads(failed_evidence_path.read_text(encoding="utf-8"))
    failed_evidence["overall_decision"] = "fail"
    failed_evidence_path.write_text(json.dumps(failed_evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed_report = validate_colab_run_bundle(failed_evidence_root)

    assert failed_report["overall_decision"] == "fail"
    failed_requirements = {check["requirement"] for check in failed_report["checks"] if check["status"] == "fail"}
    assert "embedded_paper_result_evidence_report_passed" in failed_requirements

    wrong_target_root = tmp_path / "wrong_target_bundle"
    shutil.copytree(bundle_root, wrong_target_root)
    wrong_target_path = wrong_target_root / "paper_result_evidence_report.json"
    wrong_target = json.loads(wrong_target_path.read_text(encoding="utf-8"))
    wrong_target["target_kind"] = "paper_results_package"
    wrong_target_path.write_text(json.dumps(wrong_target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    wrong_target_report = validate_colab_run_bundle(wrong_target_root)

    assert wrong_target_report["overall_decision"] == "fail"
    wrong_target_requirements = {check["requirement"] for check in wrong_target_report["checks"] if check["status"] == "fail"}
    assert "embedded_paper_result_evidence_targets_colab_bundle" in wrong_target_requirements


@pytest.mark.quick
def test_validate_colab_run_bundle_rejects_malformed_archive_sidecar(tmp_path) -> None:
    """Colab bundle 校验应拒绝无法说明离线验收入口的内嵌 archive sidecar。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"

    malformed_root = tmp_path / "malformed_archive_sidecar_bundle"
    shutil.copytree(bundle_root, malformed_root)
    sidecar_path = malformed_root / "archives" / "colab_bundle_archive_manifest.json"
    sidecar_payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar_payload["archive_manifest_stage"] = "post_archive_sidecar"
    sidecar_payload["offline_acceptance_command"] = [sys.executable, "scripts/run_colab_acceptance_checks.py", "--bundle", "wrong.zip"]
    sidecar_path.write_text(json.dumps(sidecar_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = validate_colab_run_bundle(malformed_root)

    assert report["overall_decision"] == "fail"
    failed_requirements = {check["requirement"] for check in report["checks"] if check["status"] == "fail"}
    assert "embedded_colab_archive_sidecar_parseable" in failed_requirements



@pytest.mark.quick
def test_validate_colab_run_bundle_rejects_malformed_acceptance_report(tmp_path) -> None:
    """如果 bundle 已包含最终 acceptance report, 该报告必须结构正确且可复核。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"

    malformed_root = tmp_path / "malformed_acceptance_bundle"
    shutil.copytree(bundle_root, malformed_root)
    acceptance_path = malformed_root / "colab_acceptance_report.json"
    acceptance_payload = json.loads(acceptance_path.read_text(encoding="utf-8"))
    acceptance_payload.pop("report_decisions")
    acceptance_path.write_text(json.dumps(acceptance_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = validate_colab_run_bundle(malformed_root)

    assert report["overall_decision"] == "fail"
    failed_requirements = {check["requirement"] for check in report["checks"] if check["status"] == "fail"}
    assert "embedded_colab_acceptance_report_parseable" in failed_requirements


@pytest.mark.quick
def test_paper_artifact_rebuild_package_includes_colab_workflow(tmp_path) -> None:
    """论文产物重建发布包应包含 Colab Notebook 和 helper。"""
    package_root = tmp_path / "artifact_package"
    manifest = extract_profile(".", package_root, "paper_artifact_rebuild_package", dry_run=False)

    assert "paper_workflow/colab_ceg_cold_start.ipynb" in manifest["copied_files"]
    assert "paper_workflow/colab_utils/cold_start.py" in manifest["copied_files"]
    assert "paper_workflow/notebook_utils/protocol_entrypoint.py" in manifest["copied_files"]
    assert (package_root / "paper_workflow" / "colab_ceg_cold_start.ipynb").exists()


@pytest.mark.quick
def test_colab_command_plan_materializes_external_baseline_and_metric_templates(tmp_path) -> None:
    """真实实验模式可在 Colab 中物化并执行外部 baseline / metric 命令计划。"""
    events_path = tmp_path / "events.json"
    thresholds_path = tmp_path / "thresholds.json"
    events_path.write_text("[]", encoding="utf-8")
    thresholds_path.write_text("{}", encoding="utf-8")

    plan = build_colab_command_plan(
        ".",
        tmp_path / "workspace",
        use_dry_run_inputs=False,
        run_external_plans=True,
        events_path=events_path,
        thresholds_path=thresholds_path,
        baseline_root=tmp_path / "baselines",
        metric_root=tmp_path / "metrics",
        image_pairs_path=tmp_path / "pairs.json",
        reference_image_root=tmp_path / "reference_images",
        generated_image_root=tmp_path / "generated_images",
        image_prompt_rows_path=tmp_path / "prompts.json",
    )
    external_steps = plan["external_plan_steps"]
    input_manifest = build_colab_input_manifest(plan)

    assert "materialize_command_templates.py" in " ".join(external_steps["materialize_baseline_command"])
    assert "run_baseline_plan.py" in " ".join(external_steps["baseline_execution_command"])
    assert "materialize_command_templates.py" in " ".join(external_steps["materialize_metric_command"])
    assert "run_metric_plan.py" in " ".join(external_steps["metric_execution_command"])
    assert "external_baselines" in str(external_steps["baseline_observations_path"])
    assert "external_metrics" in str(external_steps["metric_rows_path"])
    assert input_manifest["missing_required_inputs"] == []


@pytest.mark.quick
def test_colab_plan_copies_provided_result_files_into_bundle_provenance(tmp_path) -> None:
    """直接提供 baseline / metric 文件时, Colab 应先复制到 workspace, 再由结果链路消费该副本。"""
    events_path = tmp_path / "events.json"
    thresholds_path = tmp_path / "thresholds.json"
    baseline_path = tmp_path / "baseline_observations.json"
    metric_path = tmp_path / "metric_rows.json"
    events_path.write_text("[]", encoding="utf-8")
    thresholds_path.write_text("{}", encoding="utf-8")
    baseline_path.write_text(
        json.dumps([{"event_id": "e1", "baseline_id": "tree_ring", "score": 0.7, "threshold": 0.5}]),
        encoding="utf-8",
    )
    metric_path.write_text(json.dumps([{"event_id": "e1", "baseline_id": "tree_ring", "lpips": 0.05}]), encoding="utf-8")

    plan = build_colab_command_plan(
        ".",
        tmp_path / "workspace",
        use_dry_run_inputs=False,
        events_path=events_path,
        thresholds_path=thresholds_path,
        baseline_observations_path=baseline_path,
        metric_rows_path=metric_path,
    )
    input_manifest = build_colab_input_manifest(plan)
    copied_manifest = copy_provided_result_files(plan)

    assert copied_manifest["overall_decision"] == "pass"
    assert copied_manifest["copied_file_count"] == 2
    assert (tmp_path / "workspace" / "provided_results" / "baseline_observations.json").exists()
    assert (tmp_path / "workspace" / "provided_results" / "metric_rows.json").exists()
    assert (tmp_path / "workspace" / "provided_results" / "provided_result_files_manifest.json").exists()
    assert "provided_results" in " ".join(plan["build_command"])
    assert any(item["role"] == "provided_result:baseline_observations" for item in input_manifest["source_input_paths"])
    assert any("provided_result_files_manifest.json" in path for path in input_manifest["preflight_outputs"])
