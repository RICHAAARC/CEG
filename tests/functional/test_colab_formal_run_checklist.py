"""验证 Colab 正式实验运行清单。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

import paper_workflow.colab_utils.cold_start as cold_start_mod
from paper_workflow.colab_utils.cold_start import build_colab_formal_run_checklist, write_colab_formal_run_checklist


def _write_json(path, payload) -> None:
    """写出测试输入 JSON 文件。"""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _formal_event(event_id: str = "formal_e1") -> dict[str, object]:
    """构造满足正式输入源预检的最小事件行。"""
    return {
        "event_id": event_id,
        "method_name": "ceg",
        "split": "test",
        "sample_role": "formal",
        "attack_family": "clean",
        "attack_condition": "none",
        "is_watermarked": True,
        "payload": {"content_score_raw": 0.8, "attestation_score": 0.9},
    }


def _image_pair(image_id: str = "img_1") -> dict[str, object]:
    """构造满足正式输入源预检的最小图像配对行。"""
    return {
        "image_id": image_id,
        "reference_path": "reference.png",
        "watermarked_path": "watermarked.png",
        "method_name": "ceg",
    }


@pytest.mark.quick
def test_colab_formal_run_checklist_passes_with_formal_sources(tmp_path) -> None:
    """正式清单在具备真实输入、baseline 文件和高级指标文件时应通过预检。"""
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    events_path = input_root / "events.json"
    thresholds_path = input_root / "thresholds.json"
    baseline_path = input_root / "baseline_observations.json"
    metric_path = input_root / "metric_rows.json"
    _write_json(events_path, [_formal_event()])
    _write_json(thresholds_path, {"ceg": 0.5})
    _write_json(baseline_path, [{"event_id": "formal_e1", "baseline_id": "tree_ring", "score": 0.8, "threshold": 0.5}])
    _write_json(metric_path, [{"event_id": "formal_e1", "method_name": "ceg", "lpips": 0.04, "fid": 8.0, "clip_score": 0.3}])

    checklist = build_colab_formal_run_checklist(
        ".",
        tmp_path / "workspace",
        profile="paper_main_full",
        use_dry_run_inputs=False,
        require_experiment_coverage=True,
        events_path=events_path,
        thresholds_path=thresholds_path,
        baseline_observations_path=baseline_path,
        metric_rows_path=metric_path,
    )

    assert checklist["overall_decision"] == "pass"
    assert checklist["baseline_source_mode"] == "provided_file"
    assert checklist["metric_source_mode"] == "provided_file"
    assert checklist["blocking_issue_count"] == 0
    evidence_command_text = " ".join(checklist["acceptance_commands"]["validate_paper_result_evidence"])
    acceptance_command_text = " ".join(checklist["acceptance_commands"]["run_colab_acceptance_checks"])
    assert "validate_paper_result_evidence.py" in evidence_command_text
    assert "run_colab_acceptance_checks.py" in acceptance_command_text
    assert "--allow-dry-run" not in acceptance_command_text
    assert "--allow-missing-experiment-coverage" not in acceptance_command_text


@pytest.mark.quick
def test_colab_formal_run_checklist_rejects_dry_run_and_missing_sources(tmp_path) -> None:
    """正式清单应显式拒绝 dry-run 和缺失 baseline / metric 来源。"""
    checklist = build_colab_formal_run_checklist(
        ".",
        tmp_path / "workspace",
        use_dry_run_inputs=True,
        require_experiment_coverage=False,
    )

    assert checklist["overall_decision"] == "fail"
    issue_ids = {issue["issue_id"] for issue in checklist["issues"]}
    assert "dry_run_inputs_enabled" in issue_ids
    assert "external_baseline_source_missing" in issue_ids
    assert "advanced_metric_source_missing" in issue_ids
    acceptance_command_text = " ".join(checklist["acceptance_commands"]["run_colab_acceptance_checks"])
    assert "--allow-dry-run" in acceptance_command_text
    assert "--allow-missing-experiment-coverage" in acceptance_command_text


@pytest.mark.quick
def test_colab_formal_run_checklist_rejects_malformed_provided_result_files(tmp_path) -> None:
    """正式清单应拒绝结构错误或只包含基础指标的外部结果文件。"""
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    events_path = input_root / "events.json"
    thresholds_path = input_root / "thresholds.json"
    baseline_path = input_root / "baseline_observations.json"
    metric_path = input_root / "metric_rows.json"
    _write_json(events_path, [_formal_event()])
    _write_json(thresholds_path, {"ceg": 0.5})
    _write_json(baseline_path, [{"event_id": "formal_e1", "baseline_id": "tree_ring", "score": 0.8}])
    _write_json(metric_path, [{"event_id": "formal_e1", "method_name": "ceg", "psnr": 32.0, "ssim": 0.91}])

    checklist = build_colab_formal_run_checklist(
        ".",
        tmp_path / "workspace",
        profile="paper_main_full",
        use_dry_run_inputs=False,
        require_experiment_coverage=True,
        events_path=events_path,
        thresholds_path=thresholds_path,
        baseline_observations_path=baseline_path,
        metric_rows_path=metric_path,
    )

    assert checklist["overall_decision"] == "fail"
    assert checklist["provided_result_file_preflight"]["status"] == "fail"
    assert checklist["provided_result_file_violation_count"] >= 2
    issue_ids = {issue["issue_id"] for issue in checklist["issues"]}
    assert "provided_result_file_preflight_failed" in issue_ids
    checks_by_kind = {check["file_kind"]: check for check in checklist["provided_result_file_preflight"]["checks"]}
    assert checks_by_kind["baseline_observations"]["status"] == "fail"
    assert checks_by_kind["metric_rows"]["status"] == "fail"


@pytest.mark.quick
def test_build_colab_formal_run_checklist_cli_writes_report_and_blocks_failure(tmp_path) -> None:
    """CLI 应写出运行清单, 并在 require-pass 时用退出码阻断不完整正式配置。"""
    report_path = tmp_path / "colab_formal_run_checklist.json"
    failed = subprocess.run(
        [
            sys.executable,
            "scripts/build_colab_formal_run_checklist.py",
            "--workspace-root",
            str(tmp_path / "workspace"),
            "--out",
            str(report_path),
            "--use-dry-run-inputs",
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert failed.returncode == 1
    failed_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert failed_report["overall_decision"] == "fail"

    input_root = tmp_path / "inputs"
    input_root.mkdir()
    events_path = input_root / "events.json"
    thresholds_path = input_root / "thresholds.json"
    baseline_path = input_root / "baseline_observations.json"
    metric_path = input_root / "metric_rows.json"
    _write_json(events_path, [_formal_event()])
    _write_json(thresholds_path, {"ceg": 0.5})
    _write_json(baseline_path, [{"event_id": "formal_e1", "baseline_id": "tree_ring", "score": 0.8, "threshold": 0.5}])
    _write_json(metric_path, [{"event_id": "formal_e1", "method_name": "ceg", "lpips": 0.04, "fid": 8.0, "clip_score": 0.3}])

    passed_path = tmp_path / "passing_colab_formal_run_checklist.json"
    passed = subprocess.run(
        [
            sys.executable,
            "scripts/build_colab_formal_run_checklist.py",
            "--workspace-root",
            str(tmp_path / "workspace"),
            "--out",
            str(passed_path),
            "--profile",
            "paper_main_full",
            "--events",
            str(events_path),
            "--thresholds",
            str(thresholds_path),
            "--baseline-observations",
            str(baseline_path),
            "--metric-rows",
            str(metric_path),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert passed.returncode == 0, passed.stderr
    passed_report = json.loads(passed_path.read_text(encoding="utf-8"))
    assert passed_report["overall_decision"] == "pass"


def _prepare_external_plan_roots(tmp_path):
    """创建轻量第三方 baseline 和 metric 脚本目录, 只用于预检文件存在性。"""
    baseline_root = tmp_path / "baselines"
    for baseline_id in ("tree_ring", "gaussian_shading", "shallow_diffuse", "stable_signature_dee"):
        script = baseline_root / baseline_id / "run_ceg_eval.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("print('baseline preflight')\n", encoding="utf-8")
    metric_root = tmp_path / "metrics"
    metric_root.mkdir(parents=True, exist_ok=True)
    for script_name in ("compute_lpips.py", "compute_fid.py", "compute_clip_score.py"):
        (metric_root / script_name).write_text("print('metric preflight')\n", encoding="utf-8")
    return baseline_root, metric_root


@pytest.mark.quick
def test_colab_formal_run_checklist_preflights_external_plan_scripts(tmp_path) -> None:
    """启用外部计划时, 正式清单应提前检查第三方脚本和工作目录存在性。"""
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    events_path = input_root / "events.json"
    thresholds_path = input_root / "thresholds.json"
    pairs_path = input_root / "pairs.json"
    prompt_rows_path = input_root / "prompts.json"
    reference_root = input_root / "reference_images"
    generated_root = input_root / "generated_images"
    reference_root.mkdir()
    generated_root.mkdir()
    _write_json(events_path, [_formal_event()])
    _write_json(thresholds_path, {"ceg": 0.5})
    _write_json(pairs_path, [_image_pair()])
    _write_json(prompt_rows_path, [])
    baseline_root, metric_root = _prepare_external_plan_roots(tmp_path)

    checklist = build_colab_formal_run_checklist(
        ".",
        tmp_path / "workspace",
        profile="paper_main_full",
        use_dry_run_inputs=False,
        run_external_plans=True,
        require_gpu_for_external_plans=False,
        require_experiment_coverage=True,
        events_path=events_path,
        thresholds_path=thresholds_path,
        baseline_root=baseline_root,
        metric_root=metric_root,
        image_pairs_path=pairs_path,
        reference_image_root=reference_root,
        generated_image_root=generated_root,
        image_prompt_rows_path=prompt_rows_path,
    )

    assert checklist["overall_decision"] == "pass"
    assert checklist["baseline_source_mode"] == "external_plan"
    assert checklist["metric_source_mode"] == "external_plan"
    assert checklist["external_plan_preflight"]["status"] == "pass"
    assert checklist["external_command_plan_violation_count"] == 0
    acceptance_command_text = " ".join(checklist["acceptance_commands"]["run_colab_acceptance_checks"])
    assert "--require-external-command-results" in acceptance_command_text


@pytest.mark.quick
def test_colab_formal_run_checklist_requires_gpu_for_external_plans_by_default(tmp_path, monkeypatch) -> None:
    """正式外部 baseline / metric 计划默认要求 Colab GPU runtime, 防止在 CPU runtime 中误跑正式实验。"""
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    events_path = input_root / "events.json"
    thresholds_path = input_root / "thresholds.json"
    pairs_path = input_root / "pairs.json"
    prompt_rows_path = input_root / "prompts.json"
    reference_root = input_root / "reference_images"
    generated_root = input_root / "generated_images"
    reference_root.mkdir()
    generated_root.mkdir()
    _write_json(events_path, [_formal_event()])
    _write_json(thresholds_path, {"ceg": 0.5})
    _write_json(pairs_path, [_image_pair()])
    _write_json(prompt_rows_path, [])
    baseline_root, metric_root = _prepare_external_plan_roots(tmp_path)

    def fake_environment_summary(repo_root):
        return {
            "artifact_name": "colab_environment_summary.json",
            "is_colab_runtime": True,
            "repo_root": str(repo_root),
            "nvidia_smi": {"available": False},
            "torch_cuda": {"torch_imported": True, "cuda_available": False},
        }

    monkeypatch.setattr(cold_start_mod, "build_colab_environment_summary", fake_environment_summary)

    checklist = build_colab_formal_run_checklist(
        ".",
        tmp_path / "workspace",
        profile="paper_main_full",
        use_dry_run_inputs=False,
        run_external_plans=True,
        require_experiment_coverage=True,
        events_path=events_path,
        thresholds_path=thresholds_path,
        baseline_root=baseline_root,
        metric_root=metric_root,
        image_pairs_path=pairs_path,
        reference_image_root=reference_root,
        generated_image_root=generated_root,
        image_prompt_rows_path=prompt_rows_path,
    )

    assert checklist["overall_decision"] == "fail"
    assert checklist["gpu_readiness"]["required_for_external_plans"] is True
    assert checklist["gpu_readiness"]["gpu_available"] is False
    issue_ids = {issue["issue_id"] for issue in checklist["issues"]}
    assert "gpu_runtime_unavailable_for_external_plans" in issue_ids

    relaxed_checklist = build_colab_formal_run_checklist(
        ".",
        tmp_path / "workspace_relaxed",
        profile="paper_main_full",
        use_dry_run_inputs=False,
        run_external_plans=True,
        require_gpu_for_external_plans=False,
        require_experiment_coverage=True,
        events_path=events_path,
        thresholds_path=thresholds_path,
        baseline_root=baseline_root,
        metric_root=metric_root,
        image_pairs_path=pairs_path,
        reference_image_root=reference_root,
        generated_image_root=generated_root,
        image_prompt_rows_path=prompt_rows_path,
    )

    relaxed_issue_ids = {issue["issue_id"] for issue in relaxed_checklist["issues"]}
    assert "gpu_runtime_unavailable_for_external_plans" not in relaxed_issue_ids
    assert relaxed_checklist["gpu_readiness"]["required_for_external_plans"] is False


@pytest.mark.quick
def test_colab_formal_run_checklist_reports_missing_external_plan_scripts(tmp_path) -> None:
    """外部计划根目录缺少第三方脚本时, 正式清单应返回阻断问题。"""
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    events_path = input_root / "events.json"
    thresholds_path = input_root / "thresholds.json"
    _write_json(events_path, [_formal_event()])
    _write_json(thresholds_path, {"ceg": 0.5})

    checklist = build_colab_formal_run_checklist(
        ".",
        tmp_path / "workspace",
        profile="paper_main_full",
        use_dry_run_inputs=False,
        run_external_plans=True,
        require_experiment_coverage=True,
        events_path=events_path,
        thresholds_path=thresholds_path,
        baseline_root=tmp_path / "missing_baselines",
        metric_root=tmp_path / "missing_metrics",
        image_pairs_path=tmp_path / "pairs.json",
        reference_image_root=tmp_path / "reference_images",
        generated_image_root=tmp_path / "generated_images",
        image_prompt_rows_path=tmp_path / "prompts.json",
    )

    assert checklist["overall_decision"] == "fail"
    assert checklist["external_plan_preflight"]["status"] == "fail"
    issue_ids = {issue["issue_id"] for issue in checklist["issues"]}
    assert "external_command_plan_preflight_failed" in issue_ids
    assert checklist["external_command_plan_violation_count"] > 0

