"""校验外部 baseline 与高级 metric 输入是否具备正式证据."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from main.core.digest import build_stable_digest

EXTERNAL_RESULT_EVIDENCE_REPORT_NAME = "external_result_evidence_report.json"


def _load_manifest(path: str | Path | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """读取 manifest, 并把缺失或解析失败转换为结构化问题."""
    if path is None or str(path).strip() == "":
        return None, {"status": "skip", "reason": "manifest_path_absent"}
    manifest_path = Path(path)
    if not manifest_path.is_file():
        return None, {"status": "fail", "reason": "manifest_file_missing", "path": str(manifest_path)}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return None, {"status": "fail", "reason": "manifest_parse_failed", "path": str(manifest_path), "error": str(exc)}
    if not isinstance(payload, dict):
        return None, {"status": "fail", "reason": "manifest_not_object", "path": str(manifest_path)}
    return dict(payload), None


def _check_evidence_paths(manifest_path: Path, evidence_paths: list[Any]) -> list[dict[str, Any]]:
    """检查 evidence_paths 是否存在, 相对路径按 manifest 所在目录解析."""
    checks: list[dict[str, Any]] = []
    for index, value in enumerate(evidence_paths):
        if value is None or str(value).strip() == "":
            checks.append({"index": index, "status": "fail", "reason": "empty_evidence_path"})
            continue
        candidate = Path(str(value))
        resolved = candidate if candidate.is_absolute() else manifest_path.parent / candidate
        checks.append(
            {
                "index": index,
                "path": str(resolved),
                "status": "pass" if resolved.is_file() else "fail",
                "reason": None if resolved.is_file() else "evidence_file_missing",
            }
        )
    return checks


def _validate_one_manifest(
    *,
    role: str,
    manifest_path: str | Path | None,
    expected_artifact_name: str,
    require_formal_claim: bool,
) -> dict[str, Any]:
    """校验单个外部结果 manifest 是否具备正式证据.

    通用工程写法:
    - 先检查 manifest 是否可解析, 再检查 artifact_name、formal_result_claim 和 evidence_paths.
    - 相对 evidence path 按 manifest 所在目录解析, 便于把外部结果目录整体搬迁复核.

    项目特定写法:
    - baseline 与 metric 的正式论文声明都必须显式设置 formal_result_claim=True.
    - dry-run 或接口验证允许 formal_result_claim=False, 但在 require_formal_claim=True 时会被阻断.
    """
    manifest, load_issue = _load_manifest(manifest_path)
    if load_issue is not None:
        status = "skip" if load_issue["status"] == "skip" and not require_formal_claim else load_issue["status"]
        return {"role": role, "status": status, "issues": [load_issue], "manifest_path": str(manifest_path) if manifest_path else None}

    assert manifest is not None
    path = Path(str(manifest_path))
    issues: list[dict[str, Any]] = []
    if manifest.get("artifact_name") != expected_artifact_name:
        issues.append(
            {
                "status": "fail",
                "reason": "unexpected_artifact_name",
                "expected": expected_artifact_name,
                "actual": manifest.get("artifact_name"),
            }
        )

    formal_result_claim = bool(manifest.get("formal_result_claim"))
    if require_formal_claim and not formal_result_claim:
        issues.append({"status": "fail", "reason": "formal_result_claim_not_enabled"})

    evidence_paths = manifest.get("evidence_paths", [])
    if not isinstance(evidence_paths, list):
        issues.append({"status": "fail", "reason": "evidence_paths_not_list"})
        evidence_paths = []
    if require_formal_claim and not evidence_paths:
        issues.append({"status": "fail", "reason": "formal_evidence_paths_missing"})

    evidence_checks = _check_evidence_paths(path, evidence_paths)
    issues.extend(check for check in evidence_checks if check["status"] != "pass")

    status = "fail" if issues else "pass"
    return {
        "role": role,
        "status": status,
        "manifest_path": str(path),
        "artifact_name": manifest.get("artifact_name"),
        "formal_result_claim": formal_result_claim,
        "evidence_path_count": len(evidence_paths),
        "evidence_checks": evidence_checks,
        "issues": issues,
    }


def validate_external_result_evidence(
    *,
    baseline_execution_manifest: str | Path | None = None,
    metric_execution_manifest: str | Path | None = None,
    require_formal_claim: bool = False,
) -> dict[str, Any]:
    """统一校验 external baseline 与高级 metric 的证据 manifest."""
    checks = [
        _validate_one_manifest(
            role="baseline",
            manifest_path=baseline_execution_manifest,
            expected_artifact_name="baseline_execution_manifest.json",
            require_formal_claim=require_formal_claim,
        ),
        _validate_one_manifest(
            role="metric",
            manifest_path=metric_execution_manifest,
            expected_artifact_name="metric_execution_manifest.json",
            require_formal_claim=require_formal_claim,
        ),
    ]
    fail_count = sum(1 for check in checks if check["status"] == "fail")
    skip_count = sum(1 for check in checks if check["status"] == "skip")
    return {
        "artifact_name": EXTERNAL_RESULT_EVIDENCE_REPORT_NAME,
        "overall_decision": "fail" if fail_count else "pass",
        "require_formal_claim": bool(require_formal_claim),
        "checks": checks,
        "summary": {
            "total": len(checks),
            "fail_count": fail_count,
            "skip_count": skip_count,
            "pass_count": len(checks) - fail_count - skip_count,
        },
        "evidence_digest": build_stable_digest(
            {
                "require_formal_claim": bool(require_formal_claim),
                "checks": checks,
            }
        ),
    }
