"""测试 CEG 水印运行时接口契约。"""

from __future__ import annotations

from pathlib import Path

import pytest

from main.watermarking.interfaces import (
    WatermarkDetectionRequest,
    WatermarkDetectionResult,
    WatermarkEmbeddingRequest,
    WatermarkEmbeddingResult,
    WatermarkPromptContext,
)


@pytest.mark.quick
def test_watermark_prompt_context_to_record_is_manifest_safe() -> None:
    """prompt 上下文应能转换为 manifest 可序列化记录。"""

    context = WatermarkPromptContext(
        image_id="img_001",
        prompt_id="prompt_001",
        prompt_text="a small bird",
        seed=11,
        model_id="stabilityai/stable-diffusion-3.5-medium",
        generation_params={"guidance_scale": 7.0},
    )
    record = context.to_record()
    assert record["image_id"] == "img_001"
    assert record["generation_params"] == {"guidance_scale": 7.0}


@pytest.mark.quick
def test_embedding_and_detection_records_keep_method_boundary(tmp_path: Path) -> None:
    """嵌入与检测结果应保留 backend、方法和正式论文可用性边界。"""

    context = WatermarkPromptContext(
        image_id="img_001",
        prompt_id="prompt_001",
        prompt_text="a small bird",
    )
    embedding_request = WatermarkEmbeddingRequest(
        clean_image_path=tmp_path / "clean.png",
        watermarked_image_path=tmp_path / "watermarked.png",
        prompt_context=context,
        watermark_config={"bit_count": 128},
    )
    assert embedding_request.prompt_context.image_id == "img_001"

    embedding_result = WatermarkEmbeddingResult(
        watermarked_image_path=embedding_request.watermarked_image_path,
        backend_id="ceg_native_lsb",
        backend_role="pilot_self_contained_pixel_watermark",
        method_name="ceg",
        paper_main_method_ready=False,
        diagnostics={"changed_pixel_count": 64},
        provenance={"implementation": "main.watermarking.native_lsb"},
    )
    embedding_record = embedding_result.to_record()
    assert embedding_record["paper_main_method_ready"] is False
    assert embedding_record["backend_role"] == "pilot_self_contained_pixel_watermark"

    detection_request = WatermarkDetectionRequest(image_path=tmp_path / "watermarked.png", prompt_context=context)
    detection_result = WatermarkDetectionResult(
        score=0.75,
        threshold=0.5,
        decision=True,
        backend_id="ceg_detector_placeholder",
        method_name=detection_request.method_name,
        diagnostics={"score_type": "content_chain_probe"},
    )
    detection_record = detection_result.to_record()
    assert detection_record["score"] == 0.75
    assert detection_record["decision"] is True
