"""审计 CEG 清理式重构目标是否具备完成证据。



该脚本属于外层完成度审计工具, 不参与 CEG 方法判定本身。

它把方法边界、baseline 接入、消融配置、产物重建和发布包抽取放在同一份

机器可执行报告中, 便于在结束重构前做最后校验。

"""



from __future__ import annotations



import argparse

import importlib

import json

import shutil

import subprocess

import sys

from pathlib import Path

from typing import Any



ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))



from main.analysis.rebuild_artifacts import (

    PW02_ARTIFACT_NAMES,

    PW04_ARTIFACT_NAMES,

    PW05_STANDARD_METRIC_ARTIFACT_NAMES,

    PW06_FIGURE_ARTIFACT_NAMES,

    PW07_UNCERTAINTY_ARTIFACT_NAMES,

    PW08_DETECTION_CURVE_ARTIFACT_NAMES,

    PW09_CLAIM_AUDIT_ARTIFACT_NAMES,

    PW10_FIXED_FPR_ARTIFACT_NAMES,

)

from main.methods.baselines import BASELINE_REGISTRY

from main.methods.ceg.ablations import CEG_ABLATIONS

from main.protocol.experiment import ACTIVE_PROFILES

from scripts.extract_minimal_paper_package import extract_profile



FORBIDDEN_CORE_TOKENS = (

    "freeze_gate",

    "runtime_whitelist",

    "policy_path_semantics",

    "main.policy",

    ".codex",

    "tools.harness",

)



REQUIRED_CLEAN_FILES = (
    "main/methods/ceg/decision.py",
    "main/methods/ceg/ablations.py",
    "main/methods/baselines.py",
    "main/methods/baseline_adapters.py",
    "main/protocol/runtime.py",
    "main/analysis/rebuild_artifacts.py",
    "main/analysis/standard_metrics.py",
    "main/analysis/figure_specs.py",
    "main/analysis/image_metrics.py",
    "main/analysis/image_examples.py",
    "main/analysis/attack_images.py",
    "main/analysis/render_figures.py",
    "experiments/baseline_file_adapter.py",
    "experiments/baseline_command_adapter.py",
    "experiments/baseline_pilot_producer.py",
    "experiments/ceg_detection_producer.py",
    "experiments/detection_plan.py",
    "experiments/pilot_input_manifest.py",
    "experiments/image_generation_backend.py",
    "experiments/image_generation_plan.py",
    "experiments/protocol_runner.py",
    "main/cli/run_paper_protocol.py",
    "scripts/build_release_package.py",
    "scripts/run_paper_protocol_with_baseline_file.py",
    "scripts/compute_image_quality_metrics.py",
    "scripts/export_image_examples.py",
    "scripts/run_image_attack_workflow.py",
    "scripts/render_paper_figures.py",
    "scripts/build_paper_outputs.py",
    "scripts/build_pilot_package_from_provided_results.py",
    "scripts/validate_pilot_input_manifest.py",
    "scripts/export_latex_tables.py",
    "scripts/run_baseline_plan.py",
    "scripts/import_baseline_observations.py",
    "scripts/run_baseline_pilot_producer.py",
    "scripts/run_detection_plan.py",
    "experiments/baseline_plan.py",
    "experiments/metric_file_adapter.py",
    "configs/paper_experiment_matrix.json",
    "configs/baseline_command_templates.json",
    "configs/external_metric_command_templates.json",
    "configs/external_image_generation_command_templates.json",
    "configs/external_detection_command_templates.json",
    "configs/paper_output_requirements.json",
    "configs/pilot_input_manifest_template.json",
    "main/analysis/latex_tables.py",
    "main/analysis/pdf_figures.py",
    "main/analysis/paper_readiness.py",
    "main/analysis/uncertainty.py",
    "main/analysis/detection_curves.py",
    "main/analysis/fixed_fpr.py",
    "main/analysis/claim_audit.py",
    "main/analysis/result_package.py",
    "main/analysis/result_archive.py",
    "main/analysis/paper_report.py",
    "main/analysis/paper_result_evidence.py",
    "experiments/experiment_matrix.py",
    "experiments/experiment_coverage.py",
    "experiments/command_templates.py",
    "experiments/metric_plan.py",
    "experiments/paper_fixture_factory.py",
    "experiments/sample_manifest.py",
    "experiments/threshold_calibration.py",
    "scripts/build_experiment_matrix.py",
    "scripts/validate_experiment_coverage.py",
    "scripts/materialize_command_templates.py",
    "scripts/import_metric_rows.py",
    "scripts/run_metric_plan.py",
    "scripts/export_pdf_figures.py",
    "scripts/validate_paper_outputs.py",
    "scripts/export_paper_results_report.py",
    "scripts/export_paper_results_package.py",
    "scripts/archive_paper_results_to_drive.py",
    "scripts/build_paper_dry_run_inputs.py",
    "scripts/generate_mock_image_generation.py",
    "scripts/run_image_generation_plan.py",
    "scripts/run_ceg_detection_producer.py",
    "scripts/run_detection_plan.py",
    "scripts/build_protocol_events_from_sample_manifest.py",
    "scripts/calibrate_thresholds_from_sample_manifest.py",
    "scripts/run_paper_readiness_dry_run.py",
    "scripts/validate_colab_run_bundle.py",
    "scripts/validate_paper_result_evidence.py",
    "scripts/build_colab_formal_run_checklist.py",
    "scripts/run_colab_acceptance_checks.py",
    "paper_workflow/colab_ceg_cold_start.ipynb",
    "paper_workflow/colab_utils/cold_start.py",
    "paper_workflow/notebook_utils/protocol_entrypoint.py",
)


REQUIRED_BASELINES = {

    "tree_ring",

    "gaussian_shading",

    "shallow_diffuse",

    "stable_signature_dee",

}



REQUIRED_ABLATIONS = {

    "Full",

    "Content-only",

    "Recover-then-Content",

    "No-rescue",

    "No-attestation",

}



REQUIRED_PROFILES = {

    "paper_main_probe",

    "paper_main_pilot",

    "paper_main_full",

    "paper_mechanism_geo_search",

    "paper_mechanism_quickcheck",

    "paper_mechanism_pilot",

}



REQUIRED_CONFIGS = {

    "paper_main_probe": "configs/paper_main_probe.yaml",

    "paper_main_pilot": "configs/paper_main_pilot.yaml",

    "paper_main_full": "configs/paper_main_full.yaml",

    "paper_mechanism_geo_search": "configs/paper_mechanism_geo_search.yaml",

    "paper_mechanism_quickcheck": "configs/paper_mechanism_quickcheck.yaml",

    "paper_mechanism_pilot": "configs/paper_mechanism_pilot.yaml",

}



REQUIRED_ARTIFACT_NAMES = (

    set(PW02_ARTIFACT_NAMES)

    | set(PW04_ARTIFACT_NAMES)

    | set(PW05_STANDARD_METRIC_ARTIFACT_NAMES)

    | set(PW06_FIGURE_ARTIFACT_NAMES)

    | set(PW07_UNCERTAINTY_ARTIFACT_NAMES)

    | set(PW08_DETECTION_CURVE_ARTIFACT_NAMES)

    | set(PW09_CLAIM_AUDIT_ARTIFACT_NAMES)

    | set(PW10_FIXED_FPR_ARTIFACT_NAMES)

)



REQUIRED_MINIMAL_RELEASE_FILES = {

    "main/methods/ceg/decision.py",

    "main/methods/ceg/ablations.py",

    "main/methods/baselines.py",

    "main/protocol/runtime.py",

    "README.md",

    "pyproject.toml",

}



FORBIDDEN_MINIMAL_RELEASE_PREFIXES = (

    ".codex/",

    "tools/",

    "tests/",

    "experiments/",

    "scripts/",

    "paper_workflow/",

    "audit_reports/",

    "outputs/",

)



REQUIRED_ARTIFACT_RELEASE_FILES = {
    "main/cli/run_paper_protocol.py",
    "main/analysis/rebuild_artifacts.py",
    "main/analysis/standard_metrics.py",
    "main/analysis/figure_specs.py",
    "main/analysis/image_metrics.py",
    "main/analysis/image_examples.py",
    "main/analysis/attack_images.py",
    "main/analysis/render_figures.py",
    "experiments/protocol_runner.py",
    "experiments/image_generation_backend.py",
    "experiments/image_generation_plan.py",
    "experiments/detection_plan.py",
    "experiments/pilot_input_manifest.py",
    "scripts/build_release_package.py",
    "scripts/compute_image_quality_metrics.py",
    "scripts/export_image_examples.py",
    "scripts/run_image_attack_workflow.py",
    "scripts/render_paper_figures.py",
    "scripts/build_paper_outputs.py",
    "scripts/build_pilot_package_from_provided_results.py",
    "scripts/validate_pilot_input_manifest.py",
    "scripts/export_latex_tables.py",
    "scripts/run_baseline_plan.py",
    "scripts/import_baseline_observations.py",
    "scripts/run_baseline_pilot_producer.py",
    "scripts/run_detection_plan.py",
    "experiments/baseline_plan.py",
    "experiments/baseline_pilot_producer.py",
    "experiments/metric_file_adapter.py",
    "main/analysis/latex_tables.py",
    "main/analysis/pdf_figures.py",
    "main/analysis/paper_readiness.py",
    "main/analysis/uncertainty.py",
    "main/analysis/detection_curves.py",
    "main/analysis/fixed_fpr.py",
    "main/analysis/claim_audit.py",
    "main/analysis/result_package.py",
    "main/analysis/result_archive.py",
    "main/analysis/paper_report.py",
    "main/analysis/paper_result_evidence.py",
    "experiments/experiment_matrix.py",
    "experiments/experiment_coverage.py",
    "experiments/command_templates.py",
    "experiments/metric_plan.py",
    "experiments/paper_fixture_factory.py",
    "experiments/sample_manifest.py",
    "experiments/threshold_calibration.py",
    "scripts/build_experiment_matrix.py",
    "scripts/validate_experiment_coverage.py",
    "scripts/materialize_command_templates.py",
    "scripts/import_metric_rows.py",
    "scripts/run_metric_plan.py",
    "scripts/export_pdf_figures.py",
    "scripts/validate_paper_outputs.py",
    "scripts/export_paper_results_report.py",
    "scripts/export_paper_results_package.py",
    "scripts/archive_paper_results_to_drive.py",
    "scripts/build_paper_dry_run_inputs.py",
    "scripts/generate_mock_image_generation.py",
    "scripts/run_image_generation_plan.py",
    "scripts/run_ceg_detection_producer.py",
    "scripts/run_detection_plan.py",
    "scripts/build_protocol_events_from_sample_manifest.py",
    "scripts/calibrate_thresholds_from_sample_manifest.py",
    "scripts/run_paper_readiness_dry_run.py",
    "scripts/validate_colab_run_bundle.py",
    "scripts/validate_paper_result_evidence.py",
    "scripts/build_colab_formal_run_checklist.py",
    "scripts/run_colab_acceptance_checks.py",
    "paper_workflow/colab_ceg_cold_start.ipynb",
    "paper_workflow/colab_utils/cold_start.py",
    "paper_workflow/notebook_utils/protocol_entrypoint.py",
}


def _pass(name: str, evidence: Any) -> dict[str, Any]:

    """构造通过项, 统一 completion audit 的报告结构。"""

    return {"requirement": name, "status": "pass", "evidence": evidence}





def _fail(name: str, evidence: Any) -> dict[str, Any]:

    """构造失败项, 统一 completion audit 的报告结构。"""

    return {"requirement": name, "status": "fail", "evidence": evidence}





def _read_text(root: Path, relative: str) -> str:

    """按 UTF-8 读取项目内文本文件, 让审计逻辑不依赖当前终端编码。"""

    return (root / relative).read_text(encoding="utf-8")





def _check_required_files(root: Path) -> dict[str, Any]:

    """检查 CEG 清理式重构应具备的核心模块是否已经落盘。"""

    missing = [relative for relative in REQUIRED_CLEAN_FILES if not (root / relative).is_file()]

    if missing:

        return _fail("required_clean_ceg_modules", {"missing": missing})

    return _pass("required_clean_ceg_modules", list(REQUIRED_CLEAN_FILES))





def _iter_core_source_files(root: Path) -> list[Path]:

    """列出需要保持纯方法语义的核心源码文件。"""

    candidates: list[Path] = []

    for relative_root in ("main/methods", "main/protocol"):

        source_root = root / relative_root

        if source_root.exists():

            candidates.extend(path for path in source_root.rglob("*.py") if path.is_file())

    return sorted(candidates)





def _check_forbidden_core_tokens(root: Path) -> dict[str, Any]:

    """确认核心方法层没有重新嵌入旧项目治理门禁或工具依赖。"""

    violations: list[dict[str, str]] = []

    for source_file in _iter_core_source_files(root):

        text = source_file.read_text(encoding="utf-8")

        for token in FORBIDDEN_CORE_TOKENS:

            if token in text:

                violations.append({"path": source_file.relative_to(root).as_posix(), "token": token})

    if violations:

        return _fail("core_method_has_no_embedded_legacy_gate", violations)

    return _pass(

        "core_method_has_no_embedded_legacy_gate",

        {"checked_roots": ["main/methods", "main/protocol"], "forbidden_tokens": list(FORBIDDEN_CORE_TOKENS)},

    )





def _check_baselines() -> dict[str, Any]:

    """确认外部 baseline 注册表覆盖论文对照组。"""

    registered = set(BASELINE_REGISTRY)

    missing = sorted(REQUIRED_BASELINES - registered)

    if missing:

        return _fail("external_baseline_registry_complete", {"missing": missing, "registered": sorted(registered)})

    return _pass("external_baseline_registry_complete", sorted(REQUIRED_BASELINES))





def _check_ablations() -> dict[str, Any]:

    """确认 CEG 机制消融包含完整主方法、无救援和无证明等变体。"""

    registered = set(CEG_ABLATIONS)

    missing = sorted(REQUIRED_ABLATIONS - registered)

    if missing:

        return _fail("ceg_mechanism_ablations_complete", {"missing": missing, "registered": sorted(registered)})

    return _pass("ceg_mechanism_ablations_complete", sorted(REQUIRED_ABLATIONS))





def _check_profiles(root: Path) -> dict[str, Any]:

    """确认 paper main 与 mechanism 两类 profile 同时存在配置和运行时注册。"""

    registered = set(ACTIVE_PROFILES)

    missing_profiles = sorted(REQUIRED_PROFILES - registered)

    missing_configs = [relative for relative in REQUIRED_CONFIGS.values() if not (root / relative).is_file()]

    if missing_profiles or missing_configs:

        return _fail(

            "active_profile_configs_complete",

            {"missing_profiles": missing_profiles, "missing_configs": missing_configs, "registered": sorted(registered)},

        )

    return _pass("active_profile_configs_complete", sorted(REQUIRED_PROFILES))





def _check_method_equations(root: Path) -> dict[str, Any]:

    """用源码级约束确认 CEG 判定公式没有偏离方法机制。"""

    decision_text = _read_text(root, "main/methods/ceg/decision.py")

    required_snippets = {

        "positive_by_content": "positive_by_content = content_margin_raw >= 0",

        "positive_by_geo_rescue": "positive_by_geo_rescue = bool(",

        "geo_rescue_requires_aligned_threshold": "and content_margin_aligned >= 0",

        "evidence_decision": "evidence_decision = positive_by_content or positive_by_geo_rescue",

        "final_decision": "final_decision = evidence_decision and attestation_pass",

        "payload_probe_is_record_only": "payload_probe_score=content.payload_probe_score",

    }

    missing = [name for name, snippet in required_snippets.items() if snippet not in decision_text]

    if missing:

        return _fail("method_mechanism_contract_matches_source_semantics", {"missing_snippets": missing})

    return _pass(

        "method_mechanism_contract_matches_source_semantics",

        [

            "positive_by_content",

            "positive_by_geo_rescue",

            'evidence_decision: "positive_by_content OR positive_by_geo_rescue"',

            'final_decision: "evidence_decision AND attestation_pass"',

            "payload_probe: record_only",

        ],

    )





def _check_artifact_flow(root: Path) -> dict[str, Any]:

    """确认 PW02/PW04 等价产物可以从 records 重建, 而不是手工拼接。"""

    rebuild_text = _read_text(root, "main/analysis/rebuild_artifacts.py")

    missing_artifacts = [name for name in REQUIRED_ARTIFACT_NAMES if name not in rebuild_text]

    missing_functions = [

        name

        for name in (

            "build_pw02_artifacts",

            "build_pw04_tables",

            "build_standard_metric_artifacts",

            "build_figure_artifacts",

            "build_uncertainty_artifacts",

            "build_detection_curve_artifacts",

            "build_claim_audit_artifact",

            "build_all_paper_artifacts",

            "write_artifact_bundle",

        )

        if name not in rebuild_text

    ]

    if missing_artifacts or missing_functions:

        return _fail(

            "artifact_flow_rebuilds_required_outputs",

            {"missing_artifacts": sorted(missing_artifacts), "missing_functions": sorted(missing_functions)},

        )

    return _pass("artifact_flow_rebuilds_required_outputs", sorted(REQUIRED_ARTIFACT_NAMES))





def _run_import_smoke(package_root: Path) -> dict[str, Any]:

    """在抽取后的最小包内执行一次独立导入和判定冒烟测试。"""

    code = """

from main.methods.ceg import AttestationEvidence, CegThresholds, ContentEvidence, GeometryEvidence, decide_ceg_event

result = decide_ceg_event(

    ContentEvidence(content_score_raw=0.8),

    GeometryEvidence(registration_confidence=0.9, anchor_inlier_ratio=0.8, recovered_sync_consistency=0.9),

    AttestationEvidence(attestation_score=0.7),

    CegThresholds(content_threshold=0.5, attestation_threshold=0.6),

)

assert result.final_decision is True

"""

    completed = subprocess.run(

        [sys.executable, "-c", code],

        cwd=package_root,

        check=False,

        text=True,

        capture_output=True,

    )

    if completed.returncode == 0:

        return {"status": "pass"}

    return {"status": "fail", "stdout": completed.stdout, "stderr": completed.stderr, "return_code": completed.returncode}





def _check_minimal_release(root: Path, output_path: Path) -> dict[str, Any]:

    """确认最小方法包可抽取, 且不携带治理层、实验层或脚本层。"""

    package_root = output_path / "minimal_method_package"

    manifest = extract_profile(root, package_root, "minimal_method_package", dry_run=False)

    copied = set(manifest["copied_files"])

    missing = sorted(REQUIRED_MINIMAL_RELEASE_FILES - copied)

    forbidden = sorted(

        copied_file

        for copied_file in copied

        if any(copied_file == prefix.rstrip("/") or copied_file.startswith(prefix) for prefix in FORBIDDEN_MINIMAL_RELEASE_PREFIXES)

    )

    smoke = _run_import_smoke(package_root)

    if missing or forbidden or smoke["status"] != "pass":

        return _fail(

            "minimal_method_package_extractable",

            {"missing": missing, "forbidden": forbidden, "import_smoke": smoke},

        )

    return _pass(

        "minimal_method_package_extractable",

        {"copied_file_count": len(copied), "import_smoke": smoke["status"]},

    )





def _check_artifact_release(root: Path, output_path: Path) -> dict[str, Any]:

    """确认产物重建包包含 CLI、实验 runner、重建器和 release helper。"""

    package_root = output_path / "paper_artifact_rebuild_package"

    manifest = extract_profile(root, package_root, "paper_artifact_rebuild_package", dry_run=False)

    copied = set(manifest["copied_files"])

    missing = sorted(REQUIRED_ARTIFACT_RELEASE_FILES - copied)

    if missing:

        return _fail("paper_artifact_rebuild_package_extractable", {"missing": missing})

    return _pass(

        "paper_artifact_rebuild_package_extractable",

        {"copied_file_count": len(copied), "required": sorted(REQUIRED_ARTIFACT_RELEASE_FILES)},

    )





def _check_ceg_wm_untouched(ceg_wm_root: Path | None) -> dict[str, Any]:

    """确认本次清理式重构没有改动原始 CEG-WM 仓库。"""

    if ceg_wm_root is None or not ceg_wm_root.exists():

        return _pass("ceg_wm_not_modified", "not_checked_no_path")

    completed = subprocess.run(

        ["git", "status", "--short"],

        cwd=ceg_wm_root,

        check=False,

        text=True,

        capture_output=True,

    )

    if completed.returncode == 0 and completed.stdout.strip() == "":

        return _pass("ceg_wm_not_modified", "git_status_empty")

    return _fail(

        "ceg_wm_not_modified",

        {"return_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr},

    )





def run_completion_audit(

    root: str | Path,

    *,

    ceg_wm_root: str | Path | None = None,

    output_root: str | Path | None = None,

) -> dict[str, Any]:

    """执行 CEG 清理式重构完成度审计并返回结构化报告。"""

    root_path = Path(root).resolve()

    output_path = Path(output_root).resolve() if output_root else root_path / ".completion_audit_tmp"

    if output_path.exists():

        shutil.rmtree(output_path)

    output_path.mkdir(parents=True, exist_ok=True)



    # 重新导入一次关键模块, 避免长进程测试复用过期模块状态。

    for module_name in (

        "main.methods.baselines",

        "main.methods.ceg.ablations",

        "main.protocol.experiment",

        "main.analysis.rebuild_artifacts",

    ):

        if module_name in sys.modules:

            importlib.reload(sys.modules[module_name])



    checks = [

        _check_required_files(root_path),

        _check_forbidden_core_tokens(root_path),

        _check_baselines(),

        _check_ablations(),

        _check_profiles(root_path),

        _check_method_equations(root_path),

        _check_artifact_flow(root_path),

        _check_minimal_release(root_path, output_path),

        _check_artifact_release(root_path, output_path),

        _check_ceg_wm_untouched(Path(ceg_wm_root).resolve() if ceg_wm_root else None),

    ]

    fail_count = sum(1 for item in checks if item["status"] != "pass")

    return {

        "audit_name": "ceg_completion_audit",

        "overall_decision": "fail" if fail_count else "pass",

        "checks": checks,

        "summary": {"total": len(checks), "fail_count": fail_count, "pass_count": len(checks) - fail_count},

    }





def build_parser() -> argparse.ArgumentParser:

    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="审计 CEG 清理式重构目标完成度。")

    parser.add_argument("--root", default=".")

    parser.add_argument("--ceg-wm-root", default=None)

    parser.add_argument("--output-root", default=None)

    return parser





def main() -> None:

    """CLI 入口, 输出 JSON 审计报告并用退出码表达结果。"""

    parser = build_parser()

    args = parser.parse_args()

    report = run_completion_audit(args.root, ceg_wm_root=args.ceg_wm_root, output_root=args.output_root)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    raise SystemExit(0 if report["overall_decision"] == "pass" else 1)





if __name__ == "__main__":

    main()

