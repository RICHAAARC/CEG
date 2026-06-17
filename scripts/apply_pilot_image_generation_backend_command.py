"""把真实 P2 外部 backend 命令写入命令文件。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_image_generation_backend_command import (  # noqa: E402
    apply_external_command_to_file,
    write_backend_command_validation_report,
)


def _load_external_command(args: argparse.Namespace) -> list[str]:
    """从命令行读取外部 backend argv。"""
    if args.external_command_json:
        payload = json.loads(args.external_command_json)
        if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
            raise SystemExit("--external-command-json must be a JSON list[str]")
        return payload
    if args.external_command:
        command = list(args.external_command)
        if command and command[0] == "--":
            command = command[1:]
        return command
    raise SystemExit("must provide --external-command-json or --external-command")


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(description="写入 P2 外部 backend 真实命令。")
    parser.add_argument("--command-file", required=True, help="p2_external_backend_command JSON 文件路径。")
    parser.add_argument("--out", default=None, help="输出命令文件路径, 默认覆盖 --command-file。")
    parser.add_argument("--validation-report", default=None, help="可选校验报告输出路径。")
    parser.add_argument("--external-command-json", default=None, help="真实 backend argv 的 JSON 字符串列表。")
    parser.add_argument("--external-command", nargs=argparse.REMAINDER, help="真实 backend argv。")
    parser.add_argument("--require-ready", action="store_true", help="写入后校验失败时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    command = _load_external_command(args)
    output_file = Path(args.out) if args.out else Path(args.command_file)
    apply_external_command_to_file(args.command_file, command, output_file)
    report_path = Path(args.validation_report) if args.validation_report else output_file.parent / "p2_external_backend_command_validation_report.json"
    report = write_backend_command_validation_report(output_file, report_path)
    print(
        json.dumps(
            {
                "command_file": str(output_file),
                "validation_report": str(report_path),
                "overall_decision": report["overall_decision"],
                "summary": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_ready and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
