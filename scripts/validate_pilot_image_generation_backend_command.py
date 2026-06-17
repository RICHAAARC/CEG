"""校验 P2 真实外部图像生成 backend 命令文件。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_image_generation_backend_command import (  # noqa: E402
    VALIDATION_REPORT_NAME,
    write_backend_command_validation_report,
)


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(description="校验 P2 外部 backend 命令文件。")
    parser.add_argument("--command-file", required=True, help="p2_external_backend_command JSON 文件路径。")
    parser.add_argument("--out", default=None, help="校验报告输出路径, 默认写到命令文件所在目录。")
    parser.add_argument("--require-ready", action="store_true", help="命令文件未就绪时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    command_file = Path(args.command_file)
    out = Path(args.out) if args.out else command_file.parent / VALIDATION_REPORT_NAME
    report = write_backend_command_validation_report(command_file, out)
    print(
        json.dumps(
            {
                "artifact_name": report["artifact_name"],
                "overall_decision": report["overall_decision"],
                "recommended_next_stage": report["recommended_next_stage"],
                "summary": report["summary"],
                "out": str(out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_ready and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
