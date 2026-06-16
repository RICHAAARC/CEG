"""从 pilot 输入 gap 报告生成真实 pilot 启动清单.

该模块的作用是把 `pilot_input_gap_report.json` 中的机器可读缺口,
转换成面向后续执行的 checklist. 它不生成正式论文结果, 也不把 dry-run
伪装成真实实验; 它只回答一个问题: 若要从 rehearsal 推进到真实 pilot,
还必须补齐哪些输入与证据.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PILOT_READINESS_CHECKLIST_NAME = "pilot_readiness_checklist.json"

DRY_RUN_FIELD_ACTIONS = {
    "events": "运行真实 CEG detector 或导入真实 detector events, 替换 dry-run detection_events.json.",
    "image_pairs": "运行真实 SD / watermark backend, 生成真实 clean / watermarked 图像和 image_pairs.json.",
    "attacked_image_manifest": "基于真实 watermarked 图像运行 attack workflow, 生成真实 attacked_image_manifest.json.",
    "baseline_observations": "运行至少一个真实 external baseline 或导入正式 baseline observations.",
    "metric_rows": "运行真实 quality metric backend 或导入正式 LPIPS / FID / CLIP score rows.",
    "detection_execution_manifest": "为真实 detector 运行写入 detection_execution_manifest, 包含 backend、命令、输入、输出和证据路径.",
}

FORMAL_EVIDENCE_ACTIONS = {
    "baseline_execution_manifest": "补齐 external baseline 的 formal_result_claim 与 evidence_paths.",
    "metric_execution_manifest": "补齐 advanced quality metric 的 formal_result_claim 与 evidence_paths.",
    "detection_execution_manifest": "补齐 detector 执行 manifest 的 formal_result_claim 与 evidence_paths.",
}

MYDRIVE_TARGETS = {
    "pilot_run_root": "pilot_runs/",
    "package_snapshot_root": "package_snapshots/",
    "package_archive_root": "package_archives/",
    "package_manifest_root": "package_manifests/",
    "audit_report_root": "audit_reports/",
    "external_evidence_root": "external_evidence/",
}


def load_gap_report(path: str | Path) -> dict[str, Any]:
    """读取 pilot gap 报告.

    通用工程写法:
    - 把文件读取和 checklist 生成分开, 便于测试和复用.
    - 顶层必须是对象, 否则无法可靠读取字段语义.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("pilot input gap report must contain an object")
    return dict(payload)


def _checklist_item(
    requirement_id: str,
    status: str,
    reason: str,
    next_action: str,
    evidence: dict[str, Any] | None = None,
    blocking_for_formal_pilot: bool = False,
) -> dict[str, Any]:
    """构造统一 checklist 条目, 便于 JSON 和 Markdown 同时消费."""
    return {
        "requirement_id": requirement_id,
        "status": status,
        "reason": reason,
        "next_action": next_action,
        "blocking_for_formal_pilot": blocking_for_formal_pilot,
        "evidence": evidence or {},
    }


def build_pilot_readiness_checklist(
    gap_report: dict[str, Any],
    *,
    require_formal_claims: bool = False,
) -> dict[str, Any]:
    """根据 gap 报告生成真实 pilot 启动清单.

    项目特定写法:
    - `missing_core_fields` 属于硬阻断, 因为结果包构建无法可靠追溯输入.
    - `dry_run_marker_fields` 阻断 formal pilot, 但允许 rehearsal 或 partial pilot.
    - `formal_claim_gaps` 在要求正式声明时阻断 formal pilot; 在小规模流程 rehearsal
      中则作为下一步证据任务保留.
    """
    missing_core_fields = list(gap_report.get("missing_core_fields") or [])
    dry_run_marker_fields = list(gap_report.get("dry_run_marker_fields") or [])
    formal_claim_gaps = list(gap_report.get("formal_claim_gaps") or [])

    items: list[dict[str, Any]] = []

    if missing_core_fields:
        for field in missing_core_fields:
            items.append(
                _checklist_item(
                    requirement_id=f"core_input_present::{field}",
                    status="gap",
                    reason="core_pilot_input_missing",
                    next_action=f"补齐 pilot_input_manifest.json 中的 {field} 输入路径并通过 preflight.",
                    evidence={"field": field},
                    blocking_for_formal_pilot=True,
                )
            )
    else:
        items.append(
            _checklist_item(
                requirement_id="core_input_present::all",
                status="pass",
                reason="missing_core_fields_empty",
                next_action="核心输入字段已齐备, 可继续检查 dry-run 标记和正式执行证据.",
            )
        )

    if dry_run_marker_fields:
        for marker in dry_run_marker_fields:
            field = str(marker.get("field", "unknown"))
            items.append(
                _checklist_item(
                    requirement_id=f"dry_run_marker_absent::{field}",
                    status="gap",
                    reason="dry_run_marker_present",
                    next_action=DRY_RUN_FIELD_ACTIONS.get(
                        field,
                        f"用真实 pilot 产物替换 {field} 中的 dry-run 内容.",
                    ),
                    evidence=dict(marker),
                    blocking_for_formal_pilot=True,
                )
            )
    else:
        items.append(
            _checklist_item(
                requirement_id="dry_run_marker_absent::all",
                status="pass",
                reason="dry_run_marker_fields_empty",
                next_action="未发现 dry-run 标记, 可继续检查正式执行证据.",
            )
        )

    if formal_claim_gaps:
        for gap in formal_claim_gaps:
            field = str(gap.get("field", "unknown"))
            items.append(
                _checklist_item(
                    requirement_id=f"formal_execution_evidence::{field}",
                    status="gap",
                    reason="formal_claim_or_evidence_paths_missing",
                    next_action=FORMAL_EVIDENCE_ACTIONS.get(
                        field,
                        f"补齐 {field} 的 formal_result_claim 和 evidence_paths.",
                    ),
                    evidence=dict(gap),
                    blocking_for_formal_pilot=require_formal_claims,
                )
            )
    else:
        items.append(
            _checklist_item(
                requirement_id="formal_execution_evidence::all",
                status="pass",
                reason="formal_claim_gaps_empty",
                next_action="正式执行证据已满足当前要求.",
            )
        )

    blocking_items = [item for item in items if item["blocking_for_formal_pilot"] and item["status"] != "pass"]
    dry_run_gap_count = len(dry_run_marker_fields)
    formal_gap_count = len(formal_claim_gaps)

    readiness_decision = "ready_for_formal_pilot" if not blocking_items else "not_ready_for_formal_pilot"
    recommended_next_stage = (
        "formal_pilot_package_build"
        if readiness_decision == "ready_for_formal_pilot"
        else "real_pilot_input_preparation"
    )

    return {
        "artifact_name": PILOT_READINESS_CHECKLIST_NAME,
        "source_gap_artifact": gap_report.get("artifact_name", "pilot_input_gap_report.json"),
        "source_gap_overall_decision": gap_report.get("overall_decision"),
        "source_pilot_readiness_decision": gap_report.get("pilot_readiness_decision"),
        "require_formal_claims": require_formal_claims,
        "overall_decision": readiness_decision,
        "recommended_next_stage": recommended_next_stage,
        "mydrive_targets": MYDRIVE_TARGETS,
        "checklist_items": items,
        "summary": {
            "total_items": len(items),
            "blocking_item_count": len(blocking_items),
            "missing_core_field_count": len(missing_core_fields),
            "dry_run_gap_count": dry_run_gap_count,
            "formal_claim_gap_count": formal_gap_count,
        },
    }


def render_pilot_readiness_markdown(checklist: dict[str, Any]) -> str:
    """把 checklist 渲染为人类可读 Markdown.

    该 Markdown 仅是 JSON checklist 的展示形式, 不作为正式论文结果来源.
    """
    lines = [
        "# pilot readiness checklist",
        "",
        "## 1. 判定",
        "",
        "```text",
        f"overall_decision = {checklist['overall_decision']}",
        f"recommended_next_stage = {checklist['recommended_next_stage']}",
        f"source_pilot_readiness_decision = {checklist.get('source_pilot_readiness_decision')}",
        "```",
        "",
        "## 2. 摘要",
        "",
        "```json",
        json.dumps(checklist["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 3. 下一步清单",
        "",
    ]
    for index, item in enumerate(checklist["checklist_items"], start=1):
        lines.extend(
            [
                f"### 3.{index} {item['requirement_id']}",
                "",
                f"- 状态: `{item['status']}`",
                f"- 阻断 formal pilot: `{item['blocking_for_formal_pilot']}`",
                f"- 原因: `{item['reason']}`",
                f"- 下一步: {item['next_action']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
