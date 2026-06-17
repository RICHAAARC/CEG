"""测试真实图像生成 backend 的轻量治理逻辑。

这些测试不加载 SD 模型, 不调用 GPU, 只覆盖命令模板、prompt plan 解析和 watermark
安全边界。正式 GPU 运行应在 Colab 中执行, 不进入默认 pytest 路径。
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
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


def test_real_image_generation_backend_defaults_to_content_chain_watermark(tmp_path: Path) -> None:
    """真实图像生成 CLI 默认应使用 CEG 主方法水印, 而不是 pilot-only LSB fallback。"""

    args = backend.build_parser().parse_args(
        [
            "--prompt-plan",
            str(tmp_path / "prompt_plan.json"),
            "--out",
            str(tmp_path / "images"),
            "--model-config",
            str(tmp_path / "model_config.json"),
        ]
    )

    assert args.watermark_backend == "ceg_content_chain_embedding"
    assert args.content_mask_backend == backend.GRADIENT_SALIENCY_BACKEND_ID


def test_watermarked_file_cannot_equal_clean_file(tmp_path: Path) -> None:
    """真实 watermarked 图像不能是 clean 图像的字节级复制。"""
    clean = tmp_path / "clean.png"
    watermarked = tmp_path / "watermarked.png"
    clean.write_bytes(b"same-bytes")
    watermarked.write_bytes(b"same-bytes")
    with pytest.raises(RuntimeError, match="字节完全一致"):
        backend._assert_valid_watermarked(clean, watermarked)


def _write_backend_test_image(path: Path) -> None:
    """写出内容链 backend 测试用小图像。"""

    image = Image.new("RGB", (32, 32), color=(40, 40, 40))
    for x in range(8, 24):
        for y in range(8, 24):
            image.putpixel((x, y), (215, 215, 215))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


@pytest.mark.quick
def test_content_chain_watermark_backend_writes_real_outputs(tmp_path: Path) -> None:
    """真实图像生成 backend 的内容链水印路径应写出 watermarked 图像和 mask provenance。"""

    clean = tmp_path / "clean.png"
    watermarked = tmp_path / "watermarked.png"
    mask = tmp_path / "mask.png"
    _write_backend_test_image(clean)
    args = backend.build_parser().parse_args(
        [
            "--prompt-plan",
            str(tmp_path / "unused_prompt.json"),
            "--out",
            str(tmp_path / "unused_out"),
            "--model-config",
            str(tmp_path / "unused_config.json"),
            "--watermark-backend",
            "ceg_content_chain_embedding",
        ]
    )

    report = backend._run_content_chain_watermark(
        clean_path=clean,
        watermarked_path=watermarked,
        mask_path=mask,
        row={"image_id": "img_001", "prompt_id": "prompt_001"},
        generation_meta={
            "prompt_text": "a bright square",
            "seed": 5,
            "num_inference_steps": 4,
            "guidance_scale": 1.0,
            "height": 32,
            "width": 32,
        },
        model_id="test-model",
        image_id="img_001",
        prompt_id="prompt_001",
        args=args,
    )

    assert watermarked.is_file()
    assert mask.is_file()
    assert clean.read_bytes() != watermarked.read_bytes()
    assert report["watermark_backend"] == "ceg_content_chain_embedding"
    assert report["returncode"] == 0
    assert report["changed_pixel_count"] > 0
    assert len(report["embedding_digest"]) == 64
    assert len(report["semantic_mask_digest"]) == 64
    assert report["paper_main_method_ready"] is True
    assert report["paper_main_method_blocking_reason"] is None
    assert report["embedding_readiness_checks"]["overall_decision"] == "pass"
    readiness = backend._summarize_watermark_readiness([report])
    assert readiness["overall_decision"] == "pass"
    assert readiness["ready_count"] == 1
