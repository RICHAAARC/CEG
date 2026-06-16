"""校验论文结果包是否具备正式实验证据完整性。

该模块属于产物审计层, 不重新运行 CEG 判定算法, 也不生成论文表格或图像。
它只读取已经由 `build_paper_outputs.py`、`export_paper_results_package.py` 或 Colab workflow
生成的 records、artifacts、manifests 和命令结果, 判断这些证据能否支撑“正式论文结果”这一更强声明。

与 `paper_readiness.py` 的区别在于:
- readiness 证明产物链路完整且可重建;
- 本模块额外检查 dry-run 标记、实验矩阵覆盖、标准图像水印指标覆盖率、外部 baseline / metric 命令 provenance。
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from main.analysis.paper_readiness import DEFAULT_REQUIRED_METHODS
from main.analysis.result_package import validate_paper_results_package
from main.analysis.standard_metrics import QUALITY_METRIC_FIELDS


DEFAULT_REQUIRED_QUALITY_METRICS = tuple(QUALITY_METRIC_FIELDS)


def _pass(requirement: str, evidence: Any) -> dict[str, Any]:
    """构造通过检查项, 统一正式证据审计报告结构。"""
    return {"requirement": requirement, "status": "pass", "evidence": evidence}


def _fail(requirement: str, evidence: Any) -> dict[str, Any]:
    """构造失败检查项, 统一正式证据审计报告结构。"""
    return {"requirement": requirement, "status": "fail", "evidence": evidence}


def _read_json(path: Path) -> Any:
    """按 UTF-8 读取 JSON 文件, 支持带 BOM 的 Colab 下载文件。"""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    """读取 CSV 表格为字典行列表。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _file_sha256(path: Path) -> str:
    """计算文件 SHA-256 摘要, 用于离线复核 Colab bundle 中的输入副本。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    """读取 JSON 数组文件, 非对象行会被忽略并交由上层检查缺失证据。"""
    if not path.is_file():
        return []
    payload = _read_json(path)
    if not isinstance(payload, list):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)]


def _resolve_roots(target_root: str | Path) -> dict[str, Path | str | None]:
    """识别输入是 Colab bundle、paper results package 还是 build output 目录。"""
    root = Path(target_root).resolve()
    if (root / "colab_run_bundle_manifest.json").is_file():
        return {"target_kind": "colab_run_bundle", "target_root": root, "bundle_root": root, "result_root": root / "paper_results_package"}
    if (root / "paper_results_package_manifest.json").is_file():
        return {"target_kind": "paper_results_package", "target_root": root, "bundle_root": None, "result_root": root}
    if (root / "event_records.json").is_file() and (root / "artifacts").is_dir():
        return {"target_kind": "paper_output_directory", "target_root": root, "bundle_root": None, "result_root": root}
    return {"target_kind": "unknown", "target_root": root, "bundle_root": None, "result_root": root}


def _check_result_root_identified(roots: dict[str, Path | str | None]) -> dict[str, Any]:
    """确认目标目录可以映射到受治理论文结果根目录。"""
    kind = str(roots["target_kind"])
    result_root = Path(str(roots["result_root"]))
    if kind == "unknown":
        return _fail("result_root_identified", {"target_root": str(roots["target_root"]), "reason": "unknown_layout"})
    if not result_root.exists():
        return _fail("result_root_identified", {"result_root": str(result_root), "reason": "missing"})
    return _pass("result_root_identified", {"target_kind": kind, "result_root": str(result_root)})


def _check_package_integrity(roots: dict[str, Path | str | None]) -> dict[str, Any]:
    """如果目标包含 paper results package manifest, 则校验文件摘要和 readiness / claim 状态。"""
    result_root = Path(str(roots["result_root"]))
    manifest_path = result_root / "paper_results_package_manifest.json"
    if not manifest_path.exists():
        return _pass("paper_results_package_integrity", "not_applicable_for_build_output_directory")
    validation = validate_paper_results_package(result_root)
    status = "pass" if validation.get("overall_decision") == "pass" else "fail"
    return {"requirement": "paper_results_package_integrity", "status": status, "evidence": validation}


def _check_readiness_and_claims(result_root: Path) -> dict[str, Any]:
    """检查 readiness 报告和 claim audit 均已通过。"""
    readiness_path = result_root / "paper_readiness_report.json"
    claim_path = result_root / "artifacts" / "paper_claim_audit.json"
    evidence: dict[str, Any] = {
        "readiness_report_path": str(readiness_path),
        "claim_audit_path": str(claim_path),
        "readiness_decision": None,
        "claim_audit_decision": None,
    }
    if readiness_path.exists():
        readiness = _read_json(readiness_path)
        evidence["readiness_decision"] = readiness.get("overall_decision") if isinstance(readiness, dict) else None
    if claim_path.exists():
        claim = _read_json(claim_path)
        evidence["claim_audit_decision"] = claim.get("overall_decision") if isinstance(claim, dict) else None
    if evidence["readiness_decision"] == "pass" and evidence["claim_audit_decision"] == "pass":
        return _pass("readiness_and_claims_passed", evidence)
    return _fail("readiness_and_claims_passed", evidence)


def _contains_dry_run_marker(value: Any) -> bool:
    """递归检查值中是否包含 dry-run 语义标记。"""
    if isinstance(value, str):
        normalized = value.lower().replace("-", "_")
        return "dry_run" in normalized or "dryrun" in normalized
    if isinstance(value, dict):
        return any(_contains_dry_run_marker(key) or _contains_dry_run_marker(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_dry_run_marker(item) for item in value)
    return False


def _check_no_dry_run_markers(roots: dict[str, Path | str | None], *, allow_dry_run: bool) -> dict[str, Any]:
    """检查正式结果证据中是否仍然包含 dry-run 输入或 dry-run 记录。"""
    if allow_dry_run:
        return _pass("dry_run_markers_absent", "allow_dry_run_enabled")
    result_root = Path(str(roots["result_root"]))
    bundle_root = roots.get("bundle_root")
    violations: list[dict[str, Any]] = []

    for index, row in enumerate(_load_json_list(result_root / "event_records.json")):
        if _contains_dry_run_marker(row):
            violations.append({"source": "event_records.json", "row_index": index, "event_id": row.get("event_id")})

    dry_manifest = result_root / "inputs" / "paper_dry_run_inputs_manifest.json"
    if dry_manifest.exists():
        violations.append({"source": "paper_results_package/inputs/paper_dry_run_inputs_manifest.json"})

    if isinstance(bundle_root, Path):
        bundle_dry_manifest = bundle_root / "inputs" / "paper_dry_run_inputs_manifest.json"
        if bundle_dry_manifest.exists():
            violations.append({"source": "colab_run_bundle/inputs/paper_dry_run_inputs_manifest.json"})
        summary_path = bundle_root / "colab_cold_start_summary.json"
        if summary_path.exists():
            summary = _read_json(summary_path)
            command_plan = summary.get("command_plan", {}) if isinstance(summary, dict) else {}
            if isinstance(command_plan, dict) and command_plan.get("use_dry_run_inputs") is True:
                violations.append({"source": "colab_cold_start_summary.json", "field": "command_plan.use_dry_run_inputs"})

    if violations:
        return _fail("dry_run_markers_absent", violations[:20])
    return _pass("dry_run_markers_absent", {"checked_records": str(result_root / "event_records.json")})


def _check_experiment_coverage(result_root: Path, *, require_experiment_coverage: bool) -> dict[str, Any]:
    """检查实验矩阵覆盖率报告是否存在且通过。"""
    if not require_experiment_coverage:
        return _pass("experiment_matrix_coverage_passed", "not_required")
    report_path = result_root / "artifacts" / "paper_experiment_coverage_report.json"
    summary_path = result_root / "paper_outputs_summary.json"
    evidence: dict[str, Any] = {"coverage_report_path": str(report_path), "coverage_decision": None, "summary_decision": None}
    if report_path.exists():
        report = _read_json(report_path)
        evidence["coverage_decision"] = report.get("overall_decision") if isinstance(report, dict) else None
    if summary_path.exists():
        summary = _read_json(summary_path)
        evidence["summary_decision"] = summary.get("experiment_coverage_decision") if isinstance(summary, dict) else None
    if evidence["coverage_decision"] == "pass" and evidence["summary_decision"] == "pass":
        return _pass("experiment_matrix_coverage_passed", evidence)
    return _fail("experiment_matrix_coverage_passed", evidence)


def _as_float(value: Any) -> float | None:
    """把 CSV 或 JSON 中的数值字段转为 float, 空值和非法值返回 None。"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check_quality_metric_coverage(
    result_root: Path,
    *,
    required_methods: tuple[str, ...],
    required_metrics: tuple[str, ...],
    minimum_coverage: float,
) -> dict[str, Any]:
    """检查 PSNR、SSIM、LPIPS、FID、CLIP score 等标准水印指标覆盖率。"""
    table_path = result_root / "artifacts" / "quality_metrics_summary.csv"
    if not table_path.exists():
        return _fail("standard_quality_metrics_complete", {"missing": str(table_path)})
    rows = _read_csv_rows(table_path)
    by_key = {(str(row.get("method_name")), str(row.get("metric_name"))): row for row in rows}
    violations: list[dict[str, Any]] = []
    for method_name in required_methods:
        for metric_name in required_metrics:
            row = by_key.get((method_name, metric_name))
            if row is None:
                violations.append({"method_name": method_name, "metric_name": metric_name, "reason": "missing_row"})
                continue
            metric_mean = _as_float(row.get("metric_mean"))
            coverage_rate = _as_float(row.get("metric_coverage_rate"))
            if metric_mean is None:
                violations.append({"method_name": method_name, "metric_name": metric_name, "reason": "missing_metric_mean"})
            if coverage_rate is None or coverage_rate < minimum_coverage:
                violations.append(
                    {
                        "method_name": method_name,
                        "metric_name": metric_name,
                        "reason": "coverage_below_minimum",
                        "coverage_rate": coverage_rate,
                        "minimum_coverage": minimum_coverage,
                    }
                )
    if violations:
        return _fail("standard_quality_metrics_complete", violations[:30])
    return _pass(
        "standard_quality_metrics_complete",
        {"required_methods": list(required_methods), "required_metrics": list(required_metrics), "minimum_coverage": minimum_coverage},
    )


def _check_colab_formal_run_checklist(bundle_root: Path | None, *, allow_dry_run: bool) -> dict[str, Any]:
    """检查 Colab bundle 中的正式运行清单是否已经通过。

    该检查只读取 `colab_formal_run_checklist.json`, 不重新生成 records 或图表。
    dry-run 调试链路允许清单失败, 但正式论文证据默认必须要求清单通过。
    """
    if bundle_root is None:
        return _pass("colab_formal_run_checklist_passed", "not_applicable_for_non_bundle_target")
    checklist_path = bundle_root / "colab_formal_run_checklist.json"
    evidence: dict[str, Any] = {
        "checklist_path": str(checklist_path),
        "checklist_decision": None,
        "blocking_issue_count": None,
        "issue_ids": [],
    }
    if not checklist_path.is_file():
        return _fail("colab_formal_run_checklist_passed", {**evidence, "reason": "missing"})
    try:
        checklist = _read_json(checklist_path)
    except json.JSONDecodeError as exc:
        return _fail("colab_formal_run_checklist_passed", {**evidence, "reason": "json_parse_failed", "error": str(exc)})
    if not isinstance(checklist, dict):
        return _fail("colab_formal_run_checklist_passed", {**evidence, "reason": "checklist_not_object"})

    issues = checklist.get("issues", [])
    evidence["checklist_decision"] = checklist.get("overall_decision")
    evidence["blocking_issue_count"] = checklist.get("blocking_issue_count")
    evidence["issue_ids"] = [str(item.get("issue_id")) for item in issues if isinstance(item, dict) and item.get("issue_id")]
    if checklist.get("overall_decision") == "pass" and int(checklist.get("blocking_issue_count", 0) or 0) == 0:
        return _pass("colab_formal_run_checklist_passed", evidence)
    if allow_dry_run:
        return _pass("colab_formal_run_checklist_passed", {**evidence, "reason": "allow_dry_run_enabled"})
    return _fail("colab_formal_run_checklist_passed", evidence)


ADVANCED_EXTERNAL_METRIC_FIELDS = {"lpips", "fid", "clip_score"}


def _check_external_result_payloads(bundle_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """检查外部命令生成的 baseline observation 与高级指标行是否可被后续 artifact rebuild 消费。

    该函数只读取 Colab bundle 中已经生成的 JSON 结果文件, 不重新运行外部命令。
    它位于 `main.analysis`, 因此不能导入 `experiments.*` 适配器, 只能执行与结果文件契约一致的轻量结构检查。
    """
    evidence: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []

    baseline_path = bundle_root / "external_baselines" / "baseline_observations.json"
    if not baseline_path.is_file():
        failures.append({"kind": "baseline", "reason": "missing_observations", "path": str(baseline_path)})
    else:
        baseline_rows = _load_json_list(baseline_path)
        evidence["baseline_observation_count"] = len(baseline_rows)
        if not baseline_rows:
            failures.append({"kind": "baseline", "reason": "empty_observations", "path": str(baseline_path)})
        baseline_required = {"event_id", "baseline_id", "score", "threshold"}
        for index, row in enumerate(baseline_rows):
            missing = sorted(column for column in baseline_required if column not in row or row.get(column) in {None, ""})
            if missing:
                failures.append({"kind": "baseline", "row_index": index, "reason": "observation_missing_columns", "missing_columns": missing})

    metric_path = bundle_root / "external_metrics" / "metric_rows.json"
    if not metric_path.is_file():
        failures.append({"kind": "metric", "reason": "missing_metric_rows", "path": str(metric_path)})
    else:
        metric_rows = _load_json_list(metric_path)
        metric_fields = sorted({key for row in metric_rows for key in row if key not in {"event_id", "method_name", "baseline_id"}})
        advanced_fields = sorted(set(metric_fields) & ADVANCED_EXTERNAL_METRIC_FIELDS)
        evidence["external_metric_row_count"] = len(metric_rows)
        evidence["external_metric_fields"] = metric_fields
        evidence["external_advanced_metric_fields"] = advanced_fields
        if not metric_rows:
            failures.append({"kind": "metric", "reason": "empty_metric_rows", "path": str(metric_path)})
        if not advanced_fields:
            failures.append(
                {
                    "kind": "metric",
                    "reason": "advanced_metric_fields_missing",
                    "required_any_of": sorted(ADVANCED_EXTERNAL_METRIC_FIELDS),
                }
            )
        for index, row in enumerate(metric_rows):
            if "event_id" not in row or row.get("event_id") in {None, ""}:
                failures.append({"kind": "metric", "row_index": index, "reason": "metric_row_missing_event_id"})
            if not any(field in row and row.get(field) not in {None, ""} for field in ADVANCED_EXTERNAL_METRIC_FIELDS):
                failures.append({"kind": "metric", "row_index": index, "reason": "metric_row_missing_advanced_metric"})

    return evidence, failures


def _check_provided_result_files(bundle_root: Path | None) -> dict[str, Any]:
    """校验直接提供 baseline / metric 文件时写入 bundle 的受治理副本 manifest。

    该检查只读取 `provided_results/` 中已经复制的文件和摘要, 不重新运行模型或重新生成 records。
    它属于项目特定的 Colab provenance 门禁: 当正式运行使用 provided_file 来源时, 离线验收必须能看到
    被消费的 baseline / metric 文件副本, 而不是只看到 Colab 会话里的临时外部路径。
    """
    if bundle_root is None:
        return _pass("provided_result_files_manifest_valid", "not_applicable_for_non_bundle_target")

    checklist_path = bundle_root / "colab_formal_run_checklist.json"
    expected_from_checklist = False
    checklist_modes: dict[str, Any] = {}
    if checklist_path.is_file():
        try:
            checklist = _read_json(checklist_path)
        except json.JSONDecodeError:
            checklist = None
        if isinstance(checklist, dict):
            checklist_modes = {
                "baseline_source_mode": checklist.get("baseline_source_mode"),
                "metric_source_mode": checklist.get("metric_source_mode"),
            }
            expected_from_checklist = "provided_file" in set(checklist_modes.values())

    manifest_path = bundle_root / "provided_results" / "provided_result_files_manifest.json"
    if not manifest_path.is_file():
        if expected_from_checklist:
            return _fail(
                "provided_result_files_manifest_valid",
                {"reason": "missing", "manifest_path": str(manifest_path), **checklist_modes},
            )
        return _pass("provided_result_files_manifest_valid", "not_applicable_without_provided_file_source")

    try:
        manifest = _read_json(manifest_path)
    except json.JSONDecodeError as exc:
        return _fail("provided_result_files_manifest_valid", {"reason": "json_parse_failed", "error": str(exc)})
    if not isinstance(manifest, dict):
        return _fail("provided_result_files_manifest_valid", {"reason": "manifest_not_object"})

    copied_files = manifest.get("copied_files", [])
    failures: list[dict[str, Any]] = []
    if manifest.get("artifact_name") != "provided_result_files_manifest.json":
        failures.append({"reason": "unexpected_artifact_name", "artifact_name": manifest.get("artifact_name")})
    if manifest.get("overall_decision") != "pass":
        failures.append({"reason": "manifest_decision_not_pass", "overall_decision": manifest.get("overall_decision")})
    if expected_from_checklist and not copied_files:
        failures.append({"reason": "copied_files_empty_for_provided_file_source"})
    if not isinstance(copied_files, list):
        failures.append({"reason": "copied_files_not_list"})
        copied_files = []

    copied_roles: set[str] = set()
    for index, entry in enumerate(copied_files):
        if not isinstance(entry, dict):
            failures.append({"row_index": index, "reason": "copied_file_entry_not_object"})
            continue
        role = str(entry.get("role") or "")
        copied_roles.add(role)
        relative = entry.get("relative_target_path")
        if not relative:
            failures.append({"row_index": index, "role": role, "reason": "relative_target_path_missing"})
            continue
        copied_path = bundle_root / str(relative)
        if not copied_path.is_file():
            failures.append({"row_index": index, "role": role, "reason": "copied_file_missing", "path": str(copied_path)})
            continue
        expected_size = int(entry.get("byte_count", -1))
        expected_sha = entry.get("sha256")
        if copied_path.stat().st_size != expected_size or _file_sha256(copied_path) != expected_sha:
            failures.append({"row_index": index, "role": role, "reason": "digest_or_size_mismatch", "path": str(copied_path)})

    if checklist_modes.get("baseline_source_mode") == "provided_file" and "baseline_observations" not in copied_roles:
        failures.append({"reason": "baseline_copy_missing_for_provided_file_source"})
    if checklist_modes.get("metric_source_mode") == "provided_file" and "metric_rows" not in copied_roles:
        failures.append({"reason": "metric_copy_missing_for_provided_file_source"})

    evidence = {
        "manifest_path": str(manifest_path),
        "copied_file_count": len(copied_files),
        "copied_roles": sorted(copied_roles),
        **checklist_modes,
    }
    if failures:
        return _fail("provided_result_files_manifest_valid", {"failures": failures, **evidence})
    return _pass("provided_result_files_manifest_valid", evidence)


def _check_external_command_results(bundle_root: Path | None, *, require_external_command_results: bool) -> dict[str, Any]:
    """检查 Colab bundle 中外部 baseline 与高级指标命令是否真实执行成功。"""
    if not require_external_command_results:
        return _pass("external_command_results_passed", "not_required")
    if bundle_root is None:
        return _fail("external_command_results_passed", "requires_colab_run_bundle_target")
    required_files = {
        "baseline": bundle_root / "external_baselines" / "baseline_command_results.json",
        "metric": bundle_root / "external_metrics" / "metric_command_results.json",
    }
    evidence: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    for kind, path in required_files.items():
        if not path.exists():
            failures.append({"kind": kind, "reason": "missing_results", "path": str(path)})
            continue
        rows = _load_json_list(path)
        evidence[f"{kind}_command_count"] = len(rows)
        if not rows:
            failures.append({"kind": kind, "reason": "empty_results", "path": str(path)})
        for index, row in enumerate(rows):
            if int(row.get("return_code", -1)) != 0:
                failures.append({"kind": kind, "row_index": index, "return_code": row.get("return_code")})
    payload_evidence, payload_failures = _check_external_result_payloads(bundle_root)
    evidence.update(payload_evidence)
    failures.extend(payload_failures)
    if failures:
        return _fail("external_command_results_passed", {"failures": failures, **evidence})
    return _pass("external_command_results_passed", evidence)


def validate_paper_result_evidence(
    target_root: str | Path,
    *,
    allow_dry_run: bool = False,
    require_experiment_coverage: bool = True,
    require_external_command_results: bool = False,
    minimum_quality_metric_coverage: float = 1.0,
    required_methods: tuple[str, ...] = tuple(DEFAULT_REQUIRED_METHODS),
    required_quality_metrics: tuple[str, ...] = DEFAULT_REQUIRED_QUALITY_METRICS,
) -> dict[str, Any]:
    """校验论文结果目标是否能支撑正式论文结果声明。"""
    roots = _resolve_roots(target_root)
    result_root = Path(str(roots["result_root"]))
    bundle_root = roots.get("bundle_root") if isinstance(roots.get("bundle_root"), Path) else None
    checks = [
        _check_result_root_identified(roots),
        _check_package_integrity(roots),
        _check_readiness_and_claims(result_root),
        _check_no_dry_run_markers(roots, allow_dry_run=allow_dry_run),
        _check_experiment_coverage(result_root, require_experiment_coverage=require_experiment_coverage),
        _check_quality_metric_coverage(
            result_root,
            required_methods=required_methods,
            required_metrics=required_quality_metrics,
            minimum_coverage=minimum_quality_metric_coverage,
        ),
        _check_colab_formal_run_checklist(bundle_root, allow_dry_run=allow_dry_run),
        _check_provided_result_files(bundle_root),
        _check_external_command_results(bundle_root, require_external_command_results=require_external_command_results),
    ]
    fail_count = sum(1 for item in checks if item["status"] != "pass")
    return {
        "artifact_name": "paper_result_evidence_report.json",
        "overall_decision": "fail" if fail_count else "pass",
        "target_kind": str(roots["target_kind"]),
        "evidence_target_path": str(Path(target_root).resolve()),
        "result_root": str(result_root),
        "allow_dry_run": allow_dry_run,
        "require_experiment_coverage": require_experiment_coverage,
        "require_external_command_results": require_external_command_results,
        "minimum_quality_metric_coverage": minimum_quality_metric_coverage,
        "checks": checks,
        "summary": {"total": len(checks), "fail_count": fail_count, "pass_count": len(checks) - fail_count},
    }


def write_paper_result_evidence_report(target_root: str | Path, output_path: str | Path, **kwargs: Any) -> dict[str, Any]:
    """写出正式论文结果证据完整性报告。"""
    report = validate_paper_result_evidence(target_root, **kwargs)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
