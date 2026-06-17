"""验证 CEG attestation 绑定原语。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from main.core.digest import build_stable_digest
from main.watermarking.attestation import AttestationBindingRequest, build_attestation_binding
from main.watermarking.interfaces import WatermarkPromptContext


def _write_image(path: Path) -> None:
    """写出 attestation 测试图像。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color=(120, 90, 60)).save(path)


def _digest(name: str) -> str:
    """构造稳定 64 位 digest。"""

    return build_stable_digest({"name": name})


@pytest.mark.quick
def test_attestation_binding_scores_complete_evidence(tmp_path: Path) -> None:
    """完整 evidence 应得到通过分数和可复现 digest。"""

    image_path = tmp_path / "image.png"
    _write_image(image_path)
    prompt_context = WatermarkPromptContext(
        image_id="img_001",
        prompt_id="prompt_001",
        prompt_text="a test image",
        seed=1,
        model_id="test-model",
    )
    semantic = {"mask_digest": _digest("mask"), "routing_digest": _digest("routing")}
    content = {"content_chain_digest": _digest("content")}
    aligned_content = {"content_chain_digest": _digest("aligned")}
    geometry = {
        "alignment_digest": _digest("geometry"),
        "registration_confidence": 0.9,
        "anchor_inlier_ratio": 0.8,
        "recovered_sync_consistency": 0.7,
        "alignment_residual": 0.1,
    }
    provenance = {
        "image_path": image_path.as_posix(),
        "reference_image_path": image_path.as_posix(),
        "aligned_image_path": image_path.as_posix(),
    }

    result = build_attestation_binding(
        AttestationBindingRequest(
            event_id="event_001",
            method_name="ceg",
            sample_role="positive_source",
            image_path=image_path,
            prompt_context=prompt_context,
            semantic_mask_record=semantic,
            content_chain_record=content,
            aligned_content_chain_record=aligned_content,
            geometry_record=geometry,
            image_provenance=provenance,
        )
    )

    assert result.status == "ok"
    assert result.attestation_score == 1.0
    assert len(result.attestation_digest) == 64
    assert result.paper_main_method_ready is False
    assert all(item["passed"] for item in result.check_results.values())
