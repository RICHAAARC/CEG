"""测试 CEG 内容链嵌入原语。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from main.watermarking.content_chain import (
    ContentChainEmbeddingRequest,
    ContentChainRequest,
    embed_content_chain_watermark,
    extract_content_chain_evidence,
)
from main.watermarking.interfaces import WatermarkPromptContext
from main.watermarking.semantic_mask import GRADIENT_SALIENCY_BACKEND_ID, SemanticMaskRequest, extract_semantic_mask


def _write_pattern_image(path: Path) -> None:
    """写出含有低频背景和高频边缘的小图像。"""

    image = Image.new("RGB", (32, 32), color=(40, 40, 40))
    for x in range(8, 24):
        for y in range(8, 24):
            image.putpixel((x, y), (210, 210, 210))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _context() -> WatermarkPromptContext:
    """构造稳定 prompt 上下文。"""

    return WatermarkPromptContext(
        image_id="img_embed_001",
        prompt_id="prompt_embed_001",
        prompt_text="a bright square on a dark background",
        seed=23,
        model_id="stabilityai/stable-diffusion-3.5-medium",
    )


def _mask_for(image_path: Path, mask_path: Path):
    """生成测试用 semantic mask。"""

    return extract_semantic_mask(
        SemanticMaskRequest(
            image_path=image_path,
            output_mask_path=mask_path,
            backend_id=GRADIENT_SALIENCY_BACKEND_ID,
            threshold_quantile=0.75,
            open_iters=0,
            close_iters=0,
        )
    )


@pytest.mark.quick
def test_content_chain_embedding_writes_real_watermarked_image(tmp_path: Path) -> None:
    """内容链 embedding 应真实改写 clean 图像并写出 watermarked 图像。"""

    clean = tmp_path / "clean.png"
    watermarked = tmp_path / "watermarked.png"
    _write_pattern_image(clean)
    semantic_mask = _mask_for(clean, tmp_path / "mask.png")

    result = embed_content_chain_watermark(
        ContentChainEmbeddingRequest(
            clean_image_path=clean,
            watermarked_image_path=watermarked,
            semantic_mask=semantic_mask,
            prompt_context=_context(),
            lf_grid_size=4,
            lf_strength=4.0,
            hf_strength=3.0,
        )
    )
    record = result.to_record()

    assert watermarked.is_file()
    assert clean.read_bytes() != watermarked.read_bytes()
    assert record["changed_pixel_count"] > 0
    assert record["changed_channel_count"] > 0
    assert record["lf_modified_pixel_count"] > 0
    assert record["hf_modified_pixel_count"] > 0
    assert record["paper_main_method_ready"] is False
    assert len(record["embedding_digest"]) == 64


@pytest.mark.quick
def test_content_chain_embedding_digest_is_stable(tmp_path: Path) -> None:
    """相同输入和配置应生成稳定 embedding digest。"""

    clean = tmp_path / "clean.png"
    first_watermarked = tmp_path / "watermarked_first.png"
    second_watermarked = tmp_path / "watermarked_second.png"
    _write_pattern_image(clean)
    semantic_mask = _mask_for(clean, tmp_path / "mask.png")
    base_kwargs = {
        "clean_image_path": clean,
        "semantic_mask": semantic_mask,
        "prompt_context": _context(),
        "lf_grid_size": 4,
        "lf_strength": 4.0,
        "hf_strength": 3.0,
        "config": {"content_key": "unit-test"},
    }

    first = embed_content_chain_watermark(
        ContentChainEmbeddingRequest(watermarked_image_path=first_watermarked, **base_kwargs)
    )
    second = embed_content_chain_watermark(
        ContentChainEmbeddingRequest(watermarked_image_path=second_watermarked, **base_kwargs)
    )

    assert first.embedding_digest == second.embedding_digest
    assert first.lf_embedding_trace_digest == second.lf_embedding_trace_digest
    assert first.hf_embedding_trace_digest == second.hf_embedding_trace_digest
    assert first_watermarked.read_bytes() == second_watermarked.read_bytes()


@pytest.mark.quick
def test_embedded_image_can_be_scored_by_content_chain(tmp_path: Path) -> None:
    """嵌入后的图像应可被现有内容链 scoring 原语直接读取。"""

    clean = tmp_path / "clean.png"
    watermarked = tmp_path / "watermarked.png"
    _write_pattern_image(clean)
    context = _context()
    semantic_mask = _mask_for(clean, tmp_path / "mask.png")
    clean_score = extract_content_chain_evidence(
        ContentChainRequest(clean, semantic_mask, context, lf_grid_size=4, hf_grid_size=4)
    )
    embed_content_chain_watermark(
        ContentChainEmbeddingRequest(
            clean_image_path=clean,
            watermarked_image_path=watermarked,
            semantic_mask=semantic_mask,
            prompt_context=context,
            lf_grid_size=4,
            lf_strength=4.0,
            hf_strength=3.0,
        )
    )
    watermarked_score = extract_content_chain_evidence(
        ContentChainRequest(watermarked, semantic_mask, context, lf_grid_size=4, hf_grid_size=4)
    )

    assert watermarked_score.status == "ok"
    assert watermarked_score.content_chain_digest != clean_score.content_chain_digest
