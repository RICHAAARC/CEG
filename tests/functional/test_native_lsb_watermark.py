"""测试 CEG 内部 pilot 水印模块。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from main.watermarking.native_lsb import build_native_watermark_bits, embed_native_lsb_watermark


def _write_test_image(path: Path) -> None:
    """写出一个小型 RGB 图像, 使测试不依赖外部图像文件。"""
    image = Image.new("RGB", (16, 16), color=(128, 64, 32))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


@pytest.mark.quick
def test_native_lsb_bits_are_stable() -> None:
    """相同 prompt 元数据应生成稳定 bit 序列。"""
    row = {"image_id": "img_001", "prompt_id": "prompt_001"}
    generation_meta = {"prompt_text": "a cat", "seed": 7, "num_inference_steps": 28, "guidance_scale": 7.0}
    first = build_native_watermark_bits(row, generation_meta, bit_count=64)
    second = build_native_watermark_bits(row, generation_meta, bit_count=64)
    assert first == second
    assert len(first) == 64


@pytest.mark.quick
def test_native_lsb_embedding_writes_distinct_watermarked_image(tmp_path: Path) -> None:
    """CEG 内部 pilot 水印应真实改写图像, 并显式标记它不是论文主方法 ready。"""
    clean = tmp_path / "clean.png"
    watermarked = tmp_path / "watermarked.png"
    _write_test_image(clean)
    result = embed_native_lsb_watermark(
        clean_path=clean,
        watermarked_path=watermarked,
        row={"image_id": "img_001", "prompt_id": "prompt_001"},
        generation_meta={"prompt_text": "a cat", "seed": 7, "num_inference_steps": 28, "guidance_scale": 7.0},
        bit_count=128,
    )
    report = result.to_report()
    assert watermarked.is_file()
    assert clean.read_bytes() != watermarked.read_bytes()
    assert report["watermark_backend"] == "ceg_native_lsb"
    assert report["paper_main_method_ready"] is False
