"""创建真实 pilot 输入准备工作区.

该模块不运行模型, 不生成图像, 不生成检测分数, 也不声明正式论文结果.
它的职责是把 `pilot_readiness_checklist.json` 中的缺口转换为一个可填充的
MyDrive 工作区结构, 使真实 SD / watermark / attack / detector / baseline /
metric 输出能够按统一路径进入 `pilot_input_manifest.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORKSPACE_MANIFEST_NAME = "pilot_run_workspace_manifest.json"
PILOT_INPUT_DRAFT_NAME = "pilot_input_manifest.draft.json"

WORKSPACE_DIRECTORIES = (
    "inputs",
    "inputs/prompts",
    "inputs/images",
    "inputs/images/clean",
    "inputs/images/watermarked",
    "image_attacks",
    "image_attacks/images",
    "image_attacks/image_manifests",
    "ceg_detection",
    "external_baselines",
    "external_metrics",
    "plans",
    "configs",
    "evidence",
    "paper_package_build",
)

PILOT_INPUT_DRAFT = {
    "artifact_name": "pilot_input_manifest.json",
    "manifest_status": "draft_requires_real_inputs",
    "events": "ceg_detection/detection_events.json",
    "thresholds": "ceg_detection/detection_thresholds.json",
    "baseline_observations": "external_baselines/baseline_observations.json",
    "baseline_execution_manifest": "external_baselines/baseline_execution_manifest.json",
    "metric_rows": "external_metrics/metric_rows.json",
    "metric_execution_manifest": "external_metrics/metric_execution_manifest.json",
    "detection_execution_manifest": "ceg_detection/ceg_detection_execution_manifest.json",
    "image_pairs": "inputs/image_pairs.json",
    "attacked_image_manifest": "image_attacks/image_manifests/attacked_image_manifest.json",
    "attack_shard_manifest": "image_attacks/image_manifests/attack_shard_manifest.json",
    "experiment_matrix": "plans/paper_experiment_matrix.json",
    "readiness_requirements": "configs/paper_output_requirements.json",
}

WORKSPACE_README = """# CEG 真实 pilot 输入工作区

该目录用于准备真实或半真实 pilot 输入。它不是正式论文结果包。

## 填充顺序

1. 将真实 prompt / split / seed 配置放入 `inputs/prompts/`。
2. 将真实 clean 图像放入 `inputs/images/clean/`。
3. 将真实 watermarked 图像放入 `inputs/images/watermarked/`。
4. 写入 `inputs/image_pairs.json`。
5. 运行 attack workflow, 生成 `image_attacks/image_manifests/attacked_image_manifest.json`。
6. 运行真实 CEG detector, 生成 `ceg_detection/detection_events.json` 和 `ceg_detection/detection_thresholds.json`。
7. 写入 `ceg_detection/ceg_detection_execution_manifest.json`。
8. 导入至少一个 external baseline, 生成 `external_baselines/baseline_observations.json`。
9. 导入真实 quality metric rows, 生成 `external_metrics/metric_rows.json`。
10. 将 `pilot_input_manifest.draft.json` 复制或改名为 `pilot_input_manifest.json`, 再运行 preflight 和 gap audit。

## 禁止事项

1. 不要把该工作区中的空目录或草稿 manifest 声明为正式论文结果。
2. 不要手工拼接正式论文表格。
3. 不要在没有 evidence_paths 的情况下声明 external baseline 或 advanced metric 正式结果。
"""


def load_readiness_checklist(path: str | Path) -> dict[str, Any]:
    """读取真实 pilot 启动清单."""
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("pilot readiness checklist must contain an object")
    return dict(payload)


def _required_real_inputs(checklist: dict[str, Any]) -> list[dict[str, Any]]:
    """从 checklist 中提取仍需真实输入替换的阻断项."""
    tasks: list[dict[str, Any]] = []
    for item in checklist.get("checklist_items", []):
        if not isinstance(item, dict):
            continue
        if item.get("status") == "pass":
            continue
        tasks.append(
            {
                "requirement_id": item.get("requirement_id"),
                "blocking_for_formal_pilot": bool(item.get("blocking_for_formal_pilot")),
                "next_action": item.get("next_action"),
                "evidence": item.get("evidence", {}),
            }
        )
    return tasks


def build_pilot_run_workspace_manifest(
    *,
    run_id: str,
    workspace_root: Path,
    checklist: dict[str, Any],
) -> dict[str, Any]:
    """构造工作区 manifest.

    该 manifest 记录需要填充哪些真实产物, 以及后续应该运行哪些命令.
    它属于阶段推进元数据, 不属于论文正式结果数据.
    """
    return {
        "artifact_name": WORKSPACE_MANIFEST_NAME,
        "run_id": run_id,
        "workspace_status": "awaiting_real_pilot_inputs",
        "workspace_root": str(workspace_root),
        "source_checklist_decision": checklist.get("overall_decision"),
        "source_recommended_next_stage": checklist.get("recommended_next_stage"),
        "created_directories": list(WORKSPACE_DIRECTORIES),
        "draft_pilot_input_manifest": PILOT_INPUT_DRAFT_NAME,
        "required_real_inputs": _required_real_inputs(checklist),
        "next_commands": [
            "python scripts/validate_pilot_input_manifest.py --manifest <workspace>/pilot_input_manifest.json --require-pass",
            "python scripts/analyze_pilot_input_gap.py --manifest <workspace>/pilot_input_manifest.json --out <workspace>/pilot_input_gap_report.json",
            "python scripts/build_pilot_package_from_raw_inputs.py --materialized-input-root <workspace> --out <workspace>/paper_package_build --run-id <run_id>",
        ],
        "non_formal_result_notice": (
            "该工作区只用于收集真实 pilot 输入. 只有通过 preflight、gap audit、"
            "evidence audit 和 paper package readiness 后, 其中产物才可进入论文结果包."
        ),
    }


def scaffold_pilot_run_workspace(
    *,
    checklist_path: str | Path,
    output_root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """创建真实 pilot 输入工作区并写出 manifest."""
    checklist = load_readiness_checklist(checklist_path)
    workspace_root = Path(output_root)
    workspace_root.mkdir(parents=True, exist_ok=True)

    for relative in WORKSPACE_DIRECTORIES:
        (workspace_root / relative).mkdir(parents=True, exist_ok=True)

    (workspace_root / PILOT_INPUT_DRAFT_NAME).write_text(
        json.dumps(PILOT_INPUT_DRAFT, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (workspace_root / "README.md").write_text(WORKSPACE_README, encoding="utf-8")

    manifest = build_pilot_run_workspace_manifest(
        run_id=run_id,
        workspace_root=workspace_root,
        checklist=checklist,
    )
    (workspace_root / WORKSPACE_MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
