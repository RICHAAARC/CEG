"""生成 P2 真实外部图像生成 backend 命令草稿。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_image_generation_backend_command import (  # noqa: E402
    COMMAND_ARTIFACT_NAME,
    build_external_backend_command_template,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(description="生成 P2 外部 backend 命令草稿。")
    parser.add_argument("--workspace", required=True, help="pilot 工作区根目录。")
    parser.add_argument("--out", default=None, help="输出 JSON 路径, 默认写入 workspace/configs。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    workspace = Path(args.workspace)
    out = Path(args.out) if args.out else workspace / "configs" / COMMAND_ARTIFACT_NAME
    payload = build_external_backend_command_template(workspace_root=workspace)
    write_json(out, payload)
    print(json.dumps({"artifact_name": COMMAND_ARTIFACT_NAME, "out": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
