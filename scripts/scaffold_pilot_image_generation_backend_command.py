"""生成 P2 真实外部图像生成 backend 命令草稿。

该脚本只生成用户需要在 Colab 中补全的命令 JSON, 不下载模型、不运行 GPU、
不生成正式图像。它的主要作用是把“还需要真实 SD / watermark backend”这个口头
要求变成可落盘、可审计、可被包装入口读取的命令草稿。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_NAME = "p2_external_backend_command.draft.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """写出 UTF-8 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_external_backend_command_template(*, workspace_root: str | Path) -> dict[str, Any]:
    """构造需要用户在 Colab 中补全的外部 backend 命令草稿。

    草稿中的 `external_command_placeholder` 不是正式命令, 包装入口会拒绝执行它。
    用户必须把该字段替换为 `external_command`, 并填写真实 backend argv 列表。
    """
    workspace = Path(workspace_root)
    prompt_plan = workspace / "inputs" / "prompts" / "prompt_plan.draft.json"
    output_root = workspace / "inputs" / "images"
    model_config = workspace / "configs" / "model_config.draft.json"
    return {
        "artifact_name": ARTIFACT_NAME,
        "manifest_status": "draft_requires_real_external_backend_command",
        "workspace_root": str(workspace),
        "prompt_source": "D:/Code/CEG-WM/prompts",
        "hf_token_status": "defined_in_colab_environment_not_written_to_disk",
        "external_command_placeholder": [
            "python",
            "/content/replace_with_real_sd_watermark_backend.py",
            "--prompt-plan",
            str(prompt_plan).replace("\\", "/").replace("D:/content/drive/MyDrive/CEG", "/content/drive/MyDrive/CEG"),
            "--out",
            str(output_root).replace("\\", "/").replace("D:/content/drive/MyDrive/CEG", "/content/drive/MyDrive/CEG"),
            "--model-config",
            str(model_config).replace("\\", "/").replace("D:/content/drive/MyDrive/CEG", "/content/drive/MyDrive/CEG"),
        ],
        "required_replacement": {
            "replace_field": "external_command_placeholder",
            "with_field": "external_command",
            "value_type": "list[str]",
            "must_run_real_gpu_backend": True,
        },
        "required_outputs": [
            "prompt_plan.json",
            "clean/*",
            "watermarked/*",
            "image_pairs.json",
            "image_manifests/image_generation_manifest.json",
            "image_manifests/image_pair_manifest.json",
        ],
        "instructions": [
            "在 Colab 中安装或挂载真实 SD / watermark backend。",
            "把 external_command_placeholder 字段改名为 external_command。",
            "把 /content/replace_with_real_sd_watermark_backend.py 替换为真实 backend 入口。",
            "不要把 Hugging Face token 写入本文件、manifest、CSV、Notebook 输出或日志。",
            "真实 backend 必须写出 required_outputs 中列出的 P2 文件。",
        ],
    }


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
    out = Path(args.out) if args.out else workspace / "configs" / ARTIFACT_NAME
    payload = build_external_backend_command_template(workspace_root=workspace)
    _write_json(out, payload)
    print(json.dumps({"artifact_name": ARTIFACT_NAME, "out": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
