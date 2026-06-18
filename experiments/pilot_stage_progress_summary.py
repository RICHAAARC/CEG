"""汇总真实 pilot 工作区的阶段门禁状态与下一步行动清单。

该模块位于 experiments 层, 只读取已经落盘的门禁报告, 不运行模型、不生成图像、
不重新计算论文指标。它的作用是把分散在 MyDrive 工作区中的 preflight、image、attack、
detection、baseline、metric、fixed-FPR、package 和 archive 报告汇总为一个阶段进度快照。

通用工程写法是: 将多阶段流水线的 gate report 聚合为 dashboard。项目特定写法是:
明确区分 `pass`、`fail` 和 `missing`, 并把第一个阻断阶段作为下一步真实执行入口。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPORT_NAME = "pilot_stage_progress_summary.json"
MARKDOWN_NAME = "pilot_stage_progress_summary.md"


@dataclass(frozen=True)
class StageSpec:
    """描述一个真实 pilot 阶段门禁报告的位置和语义。"""

    stage_id: str
    stage_name: str
    report_path: str
    pass_next_stage: str
    fail_action: str


STAGE_SPECS = (
    StageSpec(
        "p0_input_freeze",
        "真实 pilot P0 输入冻结聚合门禁",
        "pilot_p0_input_freeze_report.json",
        "image_generation_launch_plan",
        "先打开填写指南并补齐 CSV 中的 value_json, 再运行 build_pilot_p0_input_freeze_report.py --require-pass。",
    ),
    StageSpec(
        "p0_input_preflight",
        "真实 pilot 输入模板预检",
        "pilot_input_plan_preflight_report.json",
        "apply_value_pack_or_launch_plan",
        "补齐 prompt / split / seed / model / watermark 中的真实值, 然后重新运行输入模板预检。",
    ),
    StageSpec(
        "p0_value_pack_status",
        "真实 pilot value pack 填写状态",
        "pilot_input_value_pack_status_report.json",
        "apply_value_pack",
        "逐项填写 pilot_input_value_pack.draft.json 中缺失的真实 value, 直到 value pack 状态报告通过。",
    ),
    StageSpec(
        "p0_value_pack",
        "真实 pilot value pack 应用",
        "pilot_input_value_pack_application_report.json",
        "execution_readiness",
        "在 pilot_input_value_pack.draft.json 中填写真实 value, 然后重新应用 value pack。",
    ),
    StageSpec(
        "p0_execution_readiness",
        "真实 pilot 执行就绪门禁",
        "pilot_execution_readiness_report.json",
        "image_generation_launch_plan",
        "先让输入预检与 value pack 应用通过, 再重新生成 execution readiness。",
    ),
    StageSpec(
        "p1_image_generation_launch",
        "图像生成启动计划",
        "pilot_image_generation_launch_plan_report.json",
        "image_generation_backend",
        "填写图像生成 backend、输出目录和资源变量, 重新生成 launch plan。",
    ),
    StageSpec(
        "p2_image_generation_outputs",
        "图像生成输出接收门禁",
        "pilot_image_generation_output_acceptance_report.json",
        "image_attack_pilot",
        "运行真实 SD / watermark backend, 写出 clean / watermarked 图像和 image manifests。",
    ),
    StageSpec(
        "p3_attack_outputs",
        "attack 输出接收门禁",
        "pilot_attack_output_acceptance_report.json",
        "ceg_detection_pilot",
        "基于 watermarked 图像运行 attack workflow, 写出 attacked images 和 attack manifests。",
    ),
    StageSpec(
        "p4_detection_outputs",
        "detection 输出接收门禁",
        "pilot_detection_output_acceptance_report.json",
        "fixed_fpr_statistics_pilot",
        "运行 CEG detector 或外部 detector backend, 写出 detection events、thresholds 和 manifest。",
    ),
    StageSpec(
        "p5_baseline_outputs",
        "external baseline 输出接收门禁",
        "pilot_baseline_output_acceptance_report.json",
        "quality_metric_pilot",
        "运行或导入 external baseline observations, 写出 baseline execution manifest。",
    ),
    StageSpec(
        "p6_metric_outputs",
        "quality metric 输出接收门禁",
        "pilot_metric_output_acceptance_report.json",
        "fixed_fpr_statistics_pilot",
        "运行轻量或高级 metric backend, 写出 metric_rows.json 和 metric_execution_manifest.json。",
    ),
    StageSpec(
        "p7_fixed_fpr_outputs",
        "fixed-FPR 统计输出接收门禁",
        "pilot_fixed_fpr_output_acceptance_report.json",
        "paper_result_package_pilot",
        "用真实 detection records 重建 fixed-FPR / TPR@FPR / attack TPR / baseline comparison 表格。",
    ),
    StageSpec(
        "p8_package_outputs",
        "paper_results_package 输出接收门禁",
        "pilot_paper_results_package_acceptance_report.json",
        "mydrive_archive_pilot",
        "导出 paper_results_package, 并确保 readiness、claim audit、主表和图表 manifest 完整。",
    ),
    StageSpec(
        "p8_archive_outputs",
        "MyDrive 归档输出接收门禁",
        "pilot_mydrive_archive_acceptance_report.json",
        "paper_writing_ready_pilot",
        "将通过验收的 paper_results_package 归档到 MyDrive, 生成 snapshot、zip 和 archive manifest。",
    ),
)


STAGE_SCOPE_IDS = {
    "full_pilot": None,
    "image_generation_outputs": {"p2_image_generation_outputs"},
}


def _stage_specs_for_scope(stage_scope: str) -> list[StageSpec]:
    """根据阶段范围返回需要汇总的门禁列表。

    `full_pilot` 保留原有完整 pilot 门禁语义; `image_generation_outputs` 只检查
    图像生成独立 Notebook 的输出接收门禁, 避免独立图像生成归档被缺失的 P0/P1
    报告误判为失败。
    """

    if stage_scope not in STAGE_SCOPE_IDS:
        raise ValueError(f"不支持的阶段范围: {stage_scope}")
    allowed_ids = STAGE_SCOPE_IDS[stage_scope]
    if allowed_ids is None:
        return list(STAGE_SPECS)
    return [spec for spec in STAGE_SPECS if spec.stage_id in allowed_ids]


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    """读取 JSON 文件, 返回 payload 与错误信息。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:  # pragma: no cover - 错误类型由底层 JSON / IO 决定
        return None, f"{type(exc).__name__}: {exc}"


def _status_from_payload(payload: Any, error: str | None) -> str:
    """从报告 payload 中提取 pass / fail / missing / unreadable 状态。"""
    if error is not None:
        return "missing" if str(error).startswith("missing") else "unreadable"
    if isinstance(payload, dict) and payload.get("overall_decision") in {"pass", "fail"}:
        return str(payload["overall_decision"])
    return "unknown"


def _blocking_issue_count(payload: Any) -> int:
    """从报告中读取阻断问题数量。"""
    if not isinstance(payload, dict):
        return 0
    summary = payload.get("summary")
    if isinstance(summary, dict):
        if isinstance(summary.get("blocking_issue_count"), int):
            return int(summary["blocking_issue_count"])
        if isinstance(summary.get("blocking_item_count"), int):
            return int(summary["blocking_item_count"])
        if isinstance(summary.get("fail_count"), int) or isinstance(summary.get("skipped_count"), int):
            return int(summary.get("fail_count", 0)) + int(summary.get("skipped_count", 0))
    issues = payload.get("blocking_issues")
    return len(issues) if isinstance(issues, list) else 0


def _stage_row(workspace: Path, spec: StageSpec) -> dict[str, Any]:
    """构造单个阶段门禁摘要行。"""
    path = workspace / spec.report_path
    payload, error = _read_json(path) if path.is_file() else (None, "missing_report")
    status = _status_from_payload(payload, error)
    return {
        "stage_id": spec.stage_id,
        "stage_name": spec.stage_name,
        "report_path": str(path),
        "report_relative_path": spec.report_path,
        "status": status,
        "overall_decision": payload.get("overall_decision") if isinstance(payload, dict) else None,
        "recommended_next_stage": payload.get("recommended_next_stage") if isinstance(payload, dict) else None,
        "blocking_issue_count": _blocking_issue_count(payload),
        "json_error": error,
        "fail_action": spec.fail_action,
        "pass_next_stage": spec.pass_next_stage,
    }


def _first_blocking_stage(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """返回第一个未通过或缺失的阶段。"""
    for row in rows:
        if row["status"] != "pass":
            return row
    return None


def build_pilot_stage_progress_summary(workspace: str | Path, stage_scope: str = "full_pilot") -> dict[str, Any]:
    """汇总真实 pilot 工作区阶段进度。"""
    root = Path(workspace)
    specs = _stage_specs_for_scope(stage_scope)
    rows = [_stage_row(root, spec) for spec in specs]
    first_blocking = _first_blocking_stage(rows)
    pass_count = sum(1 for row in rows if row["status"] == "pass")
    fail_count = sum(1 for row in rows if row["status"] == "fail")
    missing_count = sum(1 for row in rows if row["status"] == "missing")
    unreadable_count = sum(1 for row in rows if row["status"] == "unreadable")
    overall_decision = "pass" if pass_count == len(rows) else "fail"
    return {
        "artifact_name": REPORT_NAME,
        "workspace": str(root),
        "stage_scope": stage_scope,
        "overall_decision": overall_decision,
        "current_stage": first_blocking["stage_id"] if first_blocking else "paper_writing_ready_pilot",
        "recommended_next_action": first_blocking["fail_action"] if first_blocking else "所有 pilot 门禁均通过, 可以使用结果包撰写论文。",
        "first_blocking_stage": first_blocking,
        "stage_rows": rows,
        "summary": {
            "stage_count": len(rows),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "missing_count": missing_count,
            "unreadable_count": unreadable_count,
            "blocking_issue_count": sum(row["blocking_issue_count"] for row in rows if row["status"] != "pass"),
        },
    }


def render_pilot_stage_progress_markdown(summary: dict[str, Any]) -> str:
    """把阶段进度摘要渲染为 Markdown。"""
    lines = [
        "# CEG pilot 阶段进度汇总",
        "",
        f"- 工作区: `{summary['workspace']}`",
        f"- 阶段范围: `{summary.get('stage_scope', 'full_pilot')}`",
        f"- 总体结论: `{summary['overall_decision']}`",
        f"- 当前阶段: `{summary['current_stage']}`",
        f"- 推荐下一步: {summary['recommended_next_action']}",
        "",
        "## 阶段门禁表",
        "",
        "| 顺序 | 阶段 | 状态 | 阻断数 | 建议下一阶段 | 报告 |",
        "|---:|---|---:|---:|---|---|",
    ]
    for index, row in enumerate(summary["stage_rows"], start=1):
        lines.append(
            "| {index} | {stage_name} | `{status}` | {blocking} | `{next_stage}` | `{report}` |".format(
                index=index,
                stage_name=row["stage_name"],
                status=row["status"],
                blocking=row["blocking_issue_count"],
                next_stage=row.get("recommended_next_stage") or row["pass_next_stage"],
                report=row["report_relative_path"],
            )
        )
    first = summary.get("first_blocking_stage")
    lines.extend(["", "## 当前首个阻断点", ""])
    if isinstance(first, dict):
        lines.extend(
            [
                f"- 阶段: `{first['stage_id']}` ({first['stage_name']})",
                f"- 状态: `{first['status']}`",
                f"- 报告: `{first['report_relative_path']}`",
                f"- 行动: {first['fail_action']}",
            ]
        )
    else:
        lines.append("所有阶段门禁均已通过。")
    lines.append("")
    return "\n".join(lines)


def write_pilot_stage_progress_summary(
    workspace: str | Path,
    out_json: str | Path,
    out_markdown: str | Path,
    stage_scope: str = "full_pilot",
) -> dict[str, Any]:
    """写出 JSON 与 Markdown 阶段进度汇总。"""
    summary = build_pilot_stage_progress_summary(workspace, stage_scope=stage_scope)
    json_path = Path(out_json)
    markdown_path = Path(out_markdown)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_pilot_stage_progress_markdown(summary), encoding="utf-8")
    return summary
