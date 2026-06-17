"""生成 Google Drive 风格 CEG 论文结果目录清单。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.drive_result_inventory import write_drive_result_inventory  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="汇总 CEG Google Drive 风格结果目录中的论文产物。")
    parser.add_argument("--drive-root", default="/content/drive/MyDrive/CEG", help="CEG Drive 根目录。")
    parser.add_argument("--out", required=True, help="结果清单 JSON 输出路径。")
    parser.add_argument("--require-pass", action="store_true", help="清单判定为 fail 时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    inventory = write_drive_result_inventory(args.drive_root, args.out)
    print(
        json.dumps(
            {
                "artifact_name": inventory["artifact_name"],
                "overall_decision": inventory["overall_decision"],
                "summary": inventory["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_pass and inventory["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
