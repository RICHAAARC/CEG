"""测试 CEG 内容链 LF/HF 原语。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from main.watermarking.content_chain import ContentChainRequest, extract_content_chain_evidence
from main.watermarking.interfaces import WatermarkPromptContext
from main.watermarking.semantic_mask import GRADIENT_SALIENCY_BACKEND_ID, SemanticMaskRequest, extract_semantic_mask


def _write_pattern_image(path: Path, *, invert: bool = False) -> None:
    """写出带低频区域和高频边缘的小图像。"""

    image = Image.new("RGB", (32, 32), color=(25, 25, 25) if not invert else (220, 220, 220))
    for x in range(8, 24):
        for y in range(8, 24):
            value = 220 if not invert else 25
            image.putpixel((x, y), (value, value, value))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _build_mask(image_path: Path, mask_path: Path):
    """为内容链测试构造 semantic mask。"""

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


def _context() -> WatermarkPromptContext:
    """构造稳定 prompt 上下文。"""

    return WatermarkPromptContext(
        image_id="img_001",
        prompt_id="prompt_001",
        prompt_text="a square object on a plain background",
        seed=17,
        model_id="stabilityai/stable-diffusion-3.5-medium",
    )


@pytest.mark.quick
def test_content_chain_evidence_uses_lf_hf_mask_routing(tmp_path: Path) -> None:
    """内容链应基于 mask_false LF 与 mask_true HF 两条路径生成 evidence。"""

    image_path = tmp_path / "clean.png"
    _write_pattern_image(image_path)
    semantic_mask = _build_mask(image_path, tmp_path / "mask.png")

    result = extract_content_chain_evidence(
        ContentChainRequest(
            image_path=image_path,
            semantic_mask=semantic_mask,
            prompt_context=_context(),
            lf_grid_size=4,
            hf_grid_size=4,
        )
    )
    record = result.to_record()

    assert record["status"] == "ok"
    assert 0.0 <= record["content_score"] <= 1.0
    assert 0.0 <= record["lf_score"] <= 1.0
    assert 0.0 <= record["hf_score"] <= 1.0
    assert record["score_parts"]["mask_digest"] == semantic_mask.mask_digest
    assert record["paper_main_method_ready"] is False
    assert len(record["lf_trace_digest"]) == 64
    assert len(record["hf_trace_digest"]) == 64


@pytest.mark.quick
def test_content_chain_evidence_digest_is_stable(tmp_path: Path) -> None:
    """相同图像、mask、prompt 和配置应生成稳定内容链 digest。"""

    image_path = tmp_path / "clean.png"
    _write_pattern_image(image_path)
    semantic_mask = _build_mask(image_path, tmp_path / "mask.png")
    request = ContentChainRequest(
        image_path=image_path,
        semantic_mask=semantic_mask,
        prompt_context=_context(),
        lf_grid_size=4,
        hf_grid_size=4,
        config={"content_key": "unit-test"},
    )

    first = extract_content_chain_evidence(request)
    second = extract_content_chain_evidence(request)

    assert first.content_chain_digest == second.content_chain_digest
    assert first.lf_statistics_digest == second.lf_statistics_digest
    assert first.hf_statistics_digest == second.hf_statistics_digest


@pytest.mark.quick
def test_content_chain_score_changes_when_image_content_changes(tmp_path: Path) -> None:
    """图像内容变化时, 内容链统计摘要应发生变化。"""

    first_image = tmp_path / "clean_first.png"
    second_image = tmp_path / "clean_second.png"
    _write_pattern_image(first_image, invert=False)
    _write_pattern_image(second_image, invert=True)
    first_mask = _build_mask(first_image, tmp_path / "mask_first.png")
    second_mask = _build_mask(second_image, tmp_path / "mask_second.png")

    first = extract_content_chain_evidence(
        ContentChainRequest(first_image, first_mask, _context(), lf_grid_size=4, hf_grid_size=4)
    )
    second = extract_content_chain_evidence(
        ContentChainRequest(second_image, second_mask, _context(), lf_grid_size=4, hf_grid_size=4)
    )

    assert first.content_chain_digest != second.content_chain_digest
