"""执行外部 baseline 命令计划并汇总 observation 输出。

该脚本属于实验编排层, 不实现任何第三方 baseline 算法。它只负责执行显式 argv 命令、读取
baseline observation 文件、写出命令结果和执行 manifest。正式论文结果必须通过
``--formal-result-claim`` 与 ``--evidence-path`` 绑定外部运行证据, 避免把无证据 dry-run
误当作正式对比结果。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.baseline_command_adapter import run_baseline_commands
from experiments.baseline_plan import build_baseline_plan_manifest, load_baseline_command_plan
from main.core.digest import build_stable_digest


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="运行 CEG 外部 baseline 命令计划。")
    parser.add_argument("--plan", required=True, help="baseline 命令计划 JSON / JSONL / CSV。")
    parser.add_argument("--out", required=True, help="输出目录。")
    parser.add_argument(
        "--formal-result-claim",
        action="store_true",
        help="声明该 baseline plan 的输出可作为正式论文对比结果。启用时必须提供 evidence path。",
    )
    parser.add_argument(
        "--evidence-path",
        action="append",
        default=[],
        help="外部 baseline 正式运行证据路径, 例如第三方仓库 commit、运行日志或原始输出包。",
    )
    parser.add_argument("--require-pass", action="store_true", help="任一 baseline 命令失败时返回非零退出码。")
    return parser


def _resolve_evidence_paths(values: list[str]) -> list[str]:
    """解析 evidence path, 并保留绝对路径以便结果包搬迁后仍能追溯原始证据。"""

    return [str(Path(value).resolve()) for value in values if str(value).strip()]


def _missing_evidence_paths(paths: list[str]) -> list[str]:
    """返回不存在的 evidence path 列表。"""

    return [path for path in paths if not Path(path).is_file()]


def _validate_formal_evidence(*, formal_result_claim: bool, evidence_paths: list[str]) -> None:
    """在声明正式结果时强制要求至少一份真实存在的外部证据文件。"""

    if not formal_result_claim:
        return
    missing_evidence = _missing_evidence_paths(evidence_paths)
    if not evidence_paths:
        missing_evidence.append("formal_result_claim_requires_at_least_one_evidence_path")
    if missing_evidence:
        raise FileNotFoundError(f"formal baseline evidence paths missing: {missing_evidence}")


def _tail_text(value: str, *, max_chars: int = 6000) -> str:
    """截取命令输出尾部, 避免 Colab 日志被超长模型加载信息淹没。"""

    text = value or ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def main() -> None:
    """CLI 入口。"""

    parser = build_parser()
    args = parser.parse_args()
    specs = load_baseline_command_plan(Path(args.plan))
    evidence_paths = _resolve_evidence_paths(args.evidence_path)
    _validate_formal_evidence(formal_result_claim=args.formal_result_claim, evidence_paths=evidence_paths)

    results, rows = run_baseline_commands(specs)
    failed_results = [result.to_dict() for result in results if result.return_code != 0]
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "baseline_command_plan_manifest.json").write_text(
        json.dumps(build_baseline_plan_manifest(specs), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "baseline_command_results.json").write_text(
        json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "baseline_observations.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    execution_manifest = {
        "artifact_name": "baseline_execution_manifest.json",
        "producer_id": "external_baseline_command_plan_runner",
        "producer_role": "external_baseline_command_execution",
        "formal_result_claim": bool(args.formal_result_claim),
        "execution_boundary": (
            "external_command_results_bound_to_formal_evidence"
            if args.formal_result_claim
            else "external_command_results_require_separate_formal_evidence"
        ),
        "command_count": len(specs),
        "observation_count": len(rows),
        "baseline_ids": sorted({spec.baseline_id for spec in specs}),
        "failed_command_count": len(failed_results),
        "failed_commands": failed_results,
        "evidence_paths": evidence_paths,
        "evidence_path_count": len(evidence_paths),
        "baseline_observations_path": str(output_root / "baseline_observations.json"),
        "command_results_path": str(output_root / "baseline_command_results.json"),
        "execution_digest": build_stable_digest(
            {
                "specs": [spec.to_dict() for spec in specs],
                "results": [result.to_dict() for result in results],
                "rows": rows,
                "formal_result_claim": bool(args.formal_result_claim),
                "evidence_paths": evidence_paths,
            }
        ),
    }
    (output_root / "baseline_execution_manifest.json").write_text(
        json.dumps(execution_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "command_count": len(specs),
                "observation_count": len(rows),
                "formal_result_claim": execution_manifest["formal_result_claim"],
                "failed_command_count": execution_manifest["failed_command_count"],
                "failed_baseline_ids": [row["baseline_id"] for row in failed_results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_pass and failed_results:
        print("baseline 命令失败摘要如下。完整 stdout/stderr 已写入 baseline_command_results.json。", file=sys.stderr)
        for failed in failed_results:
            print(
                json.dumps(
                    {
                        "baseline_id": failed.get("baseline_id"),
                        "return_code": failed.get("return_code"),
                        "output_path": failed.get("output_path"),
                        "stdout_tail": _tail_text(str(failed.get("stdout") or "")),
                        "stderr_tail": _tail_text(str(failed.get("stderr") or "")),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
