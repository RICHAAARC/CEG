"""执行外部 CEG detector 命令计划并写出 detection 执行 manifest。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.detection_plan import (
    DETECTION_EVENTS_NAME,
    DETECTION_EXECUTION_MANIFEST_NAME,
    DETECTION_THRESHOLDS_NAME,
    build_detection_plan_manifest,
    load_detection_command_plan,
    run_detection_command_plan,
)
from main.core.digest import build_stable_digest


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="执行 CEG 外部 detector 命令计划。")
    parser.add_argument("--plan", required=True, help="detection 命令计划 JSON / JSONL / CSV 文件。")
    parser.add_argument("--out", required=True, help="命令计划执行摘要输出目录。")
    parser.add_argument("--require-pass", action="store_true", help="任一 detector 输出契约失败时返回非零退出码。")
    return parser


def _copy_primary_detection_outputs(result: dict[str, object], output_root: Path) -> dict[str, str | None]:
    """把第一个通过契约校验的 detector 输出复制到统一 detection 输出目录。"""
    results = result.get("results", [])
    if not isinstance(results, list):
        return {"events_path": None, "thresholds_path": None}
    for item in results:
        if not isinstance(item, dict):
            continue
        contract = item.get("output_contract")
        if not isinstance(contract, dict) or contract.get("overall_decision") != "pass":
            continue
        source_root = Path(str(contract["output_root"]))
        events_target = output_root / DETECTION_EVENTS_NAME
        thresholds_target = output_root / DETECTION_THRESHOLDS_NAME
        shutil.copy2(source_root / DETECTION_EVENTS_NAME, events_target)
        shutil.copy2(source_root / DETECTION_THRESHOLDS_NAME, thresholds_target)
        return {"events_path": str(events_target), "thresholds_path": str(thresholds_target)}
    return {"events_path": None, "thresholds_path": None}


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    specs = load_detection_command_plan(args.plan)
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    plan_manifest = build_detection_plan_manifest(specs)
    result = run_detection_command_plan(specs)
    copied_outputs = _copy_primary_detection_outputs(result, output_root)
    execution_manifest = {
        "artifact_name": DETECTION_EXECUTION_MANIFEST_NAME,
        "producer_id": "external_ceg_detector_command_plan_runner",
        "producer_role": "external_ceg_detector_execution",
        "formal_result_claim": False,
        "execution_boundary": "external_detector_results_require_separate_formal_evidence",
        "detector_count": len(specs),
        "pass_count": result["pass_count"],
        "detector_ids": [spec.detector_id for spec in specs],
        "events_path": copied_outputs["events_path"],
        "thresholds_path": copied_outputs["thresholds_path"],
        "command_results_path": str(output_root / "ceg_detection_command_results.json"),
        "execution_digest": build_stable_digest(
            {
                "specs": [spec.to_dict() for spec in specs],
                "results": result,
                "copied_outputs": copied_outputs,
            }
        ),
    }
    (output_root / "ceg_detection_command_plan_manifest.json").write_text(
        json.dumps(plan_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "ceg_detection_command_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / DETECTION_EXECUTION_MANIFEST_NAME).write_text(
        json.dumps(execution_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "detector_count": len(specs),
                "pass_count": result["pass_count"],
                "detection_execution_manifest_path": DETECTION_EXECUTION_MANIFEST_NAME,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_pass and result["pass_count"] != len(specs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
