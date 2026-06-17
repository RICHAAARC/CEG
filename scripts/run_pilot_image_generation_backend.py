"""P2 真实图像生成 backend 包装入口。

该脚本的作用是为 Colab GPU 阶段提供一个仓库内可定位的入口。它本身不实现
Stable Diffusion、扩散模型采样或水印嵌入算法, 而是负责调用用户提供的真实外部
backend 命令, 然后用项目既有的 P2 接收门禁检查输出是否满足论文流程契约。

这种实现属于通用工程写法: 将不可在本地稳定复现的 GPU 任务封装为显式命令,
并在命令完成后做契约验收。项目特定写法是: 验收固定使用 CEG P2 所要求的
prompt_plan.json、image_pairs.json、clean / watermarked 图像和 image manifests。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_image_generation_output_acceptance import (  # noqa: E402
    REPORT_NAME as ACCEPTANCE_REPORT_NAME,
    write_pilot_image_generation_output_acceptance_report,
)

WRAPPER_REPORT_NAME = "pilot_image_generation_backend_wrapper_report.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """写出 UTF-8 JSON 文件, 供 Colab 和本地审计共同读取。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_external_command(args: argparse.Namespace) -> tuple[list[str] | None, str | None]:
    """从 CLI 参数中读取真实外部 backend 命令。

    `--external-command-json` 适合 notebook 或脚本生成稳定 argv 列表;
    `--external-command` 适合人工在 Colab 中直接追加命令。二者都不会被 shell
    拼接执行, 从而避免空格和特殊字符导致的命令注入或路径歧义。
    """
    if args.external_command_json:
        try:
            loaded = json.loads(args.external_command_json)
        except json.JSONDecodeError as exc:
            return None, f"external_command_json_invalid_json: {exc}"
        if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
            return None, "external_command_json_must_be_string_list"
        if not loaded:
            return None, "external_command_json_empty"
        return list(loaded), None
    if args.external_command:
        command = list(args.external_command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            return None, "external_command_empty"
        return command, None
    return None, "missing_external_backend_command"


def build_parser() -> argparse.ArgumentParser:
    """构造 P2 backend 包装入口的命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="调用真实 P2 图像生成 backend 并验收 CEG 输出契约。")
    parser.add_argument("--prompt-plan", required=True, help="P1 冻结后的 prompt plan 路径。")
    parser.add_argument("--out", required=True, help="真实 P2 图像生成输出根目录, 即 inputs/images。")
    parser.add_argument("--model-config", required=True, help="真实模型配置路径。")
    parser.add_argument("--watermark-config", default=None, help="可选水印配置路径。")
    parser.add_argument("--report", default=None, help="包装器报告输出路径, 默认写入 --out 下。")
    parser.add_argument(
        "--external-command-json",
        default=None,
        help="真实外部 backend argv 的 JSON 字符串列表, 例如 [\"python\", \"backend.py\"]。",
    )
    parser.add_argument(
        "--external-command",
        nargs=argparse.REMAINDER,
        help="真实外部 backend argv。该参数后面的所有内容都会作为子进程 argv。",
    )
    parser.add_argument("--require-pass", action="store_true", help="外部命令或验收失败时返回非零退出码。")
    return parser


def _base_report(args: argparse.Namespace, report_path: Path) -> dict[str, Any]:
    """构造包装器报告的公共字段。"""
    return {
        "artifact_name": WRAPPER_REPORT_NAME,
        "prompt_plan_path": str(Path(args.prompt_plan)),
        "output_root": str(Path(args.out)),
        "model_config_path": str(Path(args.model_config)),
        "watermark_config_path": str(Path(args.watermark_config)) if args.watermark_config else None,
        "wrapper_report_path": str(report_path),
        "acceptance_report_path": str(Path(args.out) / ACCEPTANCE_REPORT_NAME),
        "implementation_boundary": {
            "runs_stable_diffusion_itself": False,
            "embeds_watermark_itself": False,
            "requires_real_external_backend": True,
        },
    }


def main() -> None:
    """CLI 入口: 调用外部真实 backend, 再运行 P2 接收门禁。"""
    args = build_parser().parse_args()
    output_root = Path(args.out)
    report_path = Path(args.report) if args.report else output_root / WRAPPER_REPORT_NAME
    command, command_error = _load_external_command(args)
    report = _base_report(args, report_path)

    if command_error is not None or command is None:
        report.update(
            {
                "overall_decision": "fail",
                "failure_stage": "external_backend_configuration",
                "blocking_issue": command_error,
                "message": (
                    "本仓库只提供 P2 包装入口和验收门禁, 不内置真实 SD / watermark backend。"
                    "请在 Colab 中通过 --external-command-json 或 --external-command 提供真实生成命令。"
                ),
            }
        )
        _write_json(report_path, report)
        print(json.dumps({"overall_decision": "fail", "blocking_issue": command_error}, ensure_ascii=False, indent=2))
        raise SystemExit(1 if args.require_pass else 2)

    completed = subprocess.run(command, cwd=str(ROOT), check=False, text=True, capture_output=True)
    report.update(
        {
            "external_command": command,
            "external_command_returncode": completed.returncode,
            "external_command_stdout_tail": completed.stdout[-4000:],
            "external_command_stderr_tail": completed.stderr[-4000:],
        }
    )
    if completed.returncode != 0:
        report.update(
            {
                "overall_decision": "fail",
                "failure_stage": "external_backend_execution",
                "blocking_issue": "external_command_failed",
            }
        )
        _write_json(report_path, report)
        print(json.dumps({"overall_decision": "fail", "blocking_issue": "external_command_failed"}, ensure_ascii=False, indent=2))
        raise SystemExit(completed.returncode)

    acceptance_path = output_root / ACCEPTANCE_REPORT_NAME
    acceptance = write_pilot_image_generation_output_acceptance_report(output_root, acceptance_path)
    report.update(
        {
            "overall_decision": acceptance["overall_decision"],
            "failure_stage": None if acceptance["overall_decision"] == "pass" else "p2_output_acceptance",
            "acceptance_summary": acceptance["summary"],
            "acceptance_blocking_issues": acceptance["blocking_issues"],
        }
    )
    _write_json(report_path, report)
    print(
        json.dumps(
            {
                "overall_decision": report["overall_decision"],
                "acceptance_report_path": str(acceptance_path),
                "wrapper_report_path": str(report_path),
                "acceptance_summary": acceptance["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_pass and acceptance["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
