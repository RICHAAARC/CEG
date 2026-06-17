"""测试真实图像生成 backend 的轻量治理逻辑。

这些测试不加载 SD 模型, 不调用 GPU, 只覆盖命令模板、prompt plan 解析和 watermark
安全边界。正式 GPU 运行应在 Colab 中执行, 不进入默认 pytest 路径。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_pilot_real_image_generation_backend as backend


def test_render_command_template_rejects_placeholder() -> None:
    """watermark 命令模板不能保留 placeholder, 避免误把草稿当正式命令。"""
    with pytest.raises(ValueError, match="placeholder"):
        backend._render_command_template(["python", "replace_with_backend.py"], {})


def test_render_command_template_substitutes_image_paths(tmp_path: Path) -> None:
    """外部 watermark 命令使用 argv 模板渲染, 不经过 shell 字符串拼接。"""
    clean = tmp_path / "clean.png"
    watermarked = tmp_path / "watermarked.png"
    metadata = tmp_path / "meta.json"
    command = backend._render_command_template(
        ["python", "wm.py", "--input", "{clean_image}", "--output", "{watermarked_image}", "--meta", "{metadata_json}"],
        {
            "clean_image": str(clean),
            "watermarked_image": str(watermarked),
            "metadata_json": str(metadata),
        },
    )
    assert command == ["python", "wm.py", "--input", str(clean), "--output", str(watermarked), "--meta", str(metadata)]


def test_load_prompt_rows_accepts_prompt_list(tmp_path: Path) -> None:
    """prompt plan 可以是列表, 且必须包含可消费的 prompt 文本。"""
    path = tmp_path / "prompt_plan.json"
    path.write_text(json.dumps([{"prompt_id": "a", "prompt_text": "a cat", "seed": 7}]), encoding="utf-8")
    rows = backend._load_prompt_rows(path)
    assert rows[0]["prompt_text"] == "a cat"


def test_watermarked_file_cannot_equal_clean_file(tmp_path: Path) -> None:
    """真实 watermarked 图像不能是 clean 图像的字节级复制。"""
    clean = tmp_path / "clean.png"
    watermarked = tmp_path / "watermarked.png"
    clean.write_bytes(b"same-bytes")
    watermarked.write_bytes(b"same-bytes")
    with pytest.raises(RuntimeError, match="字节完全一致"):
        backend._assert_valid_watermarked(clean, watermarked)
