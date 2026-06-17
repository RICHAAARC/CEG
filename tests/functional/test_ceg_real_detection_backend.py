"""验证 CEG 真实内容链 detection backend。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

from experiments.ceg_real_detection_backend import write_content_chain_detection_inputs
from main.watermarking.content_chain import ContentChainEmbeddingRequest, embed_content_chain_watermark
from main.watermarking.interfaces import WatermarkPromptContext
from main.watermarking.semantic_mask import SemanticMaskRequest, extract_semantic_mask


def _write_test_image(path: Path) -> None:
    """写出包含低频背景和高频边缘的小图像, 供内容链测试复用。"""

    image = Image.new("RGB", (40, 40), color=(48, 48, 48))
    for x in range(10, 30):
        for y in range(10, 30):
            image.putpixel((x, y), (215, 215, 215))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _write_embedded_pair(tmp_path: Path) -> Path:
    """构造真实 clean / watermarked 图像对和 image_pairs.json。"""

    clean = tmp_path / "clean" / "img_001.png"
    watermarked = tmp_path / "watermarked" / "img_001.png"
    mask_path = tmp_path / "semantic_masks" / "img_001.png"
    _write_test_image(clean)
    prompt_context = WatermarkPromptContext(
        image_id="img_001",
        prompt_id="prompt_001",
        prompt_text="a bright square on dark background",
        seed=17,
        model_id="test-model",
    )
    semantic_mask = extract_semantic_mask(
        SemanticMaskRequest(image_path=clean, output_mask_path=mask_path, threshold_quantile=0.75)
    )
    embed_content_chain_watermark(
        ContentChainEmbeddingRequest(
            clean_image_path=clean,
            watermarked_image_path=watermarked,
            semantic_mask=semantic_mask,
            prompt_context=prompt_context,
            lf_strength=6.0,
            hf_strength=4.0,
        )
    )
    image_pairs = tmp_path / "image_pairs.json"
    image_pairs.write_text(
        json.dumps(
            [
                {
                    "image_id": "img_001",
                    "prompt_id": "prompt_001",
                    "prompt_text": "a bright square on dark background",
                    "seed": 17,
                    "model_id": "test-model",
                    "clean_image_path": clean.as_posix(),
                    "watermarked_image_path": watermarked.as_posix(),
                    "split": "test",
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return image_pairs


@pytest.mark.quick
def test_content_chain_detection_backend_writes_real_events(tmp_path: Path) -> None:
    """真实内容链 detection backend 应写出 clean 与 watermarked 事件。"""

    image_pairs = _write_embedded_pair(tmp_path)
    output_root = tmp_path / "detection"

    manifest = write_content_chain_detection_inputs(
        image_pairs,
        output_root,
        detector_config={"mask_threshold_quantile": 0.75, "mask_open_iters": 0, "mask_close_iters": 0},
    )
    events = json.loads((output_root / "detection_events.json").read_text(encoding="utf-8"))
    records = json.loads((output_root / "content_chain_detection_records.json").read_text(encoding="utf-8"))

    assert manifest["producer_id"] == "ceg_content_chain_detection_backend"
    assert manifest["formal_result_claim"] is False
    assert manifest["paper_main_method_ready"] is False
    assert manifest["paper_main_method_blocking_reasons"] == ["keyed_attestation_ready"]
    assert manifest["method_readiness_checks"]["geometry_recovery_ready"]["passed"] is True
    assert manifest["event_count"] == 2
    assert {event["sample_role"] for event in events} == {"clean_negative", "positive_source"}
    assert len(records) == 2
    for event in events:
        payload = event["payload"]
        assert payload["detection_source"]["producer"] == "ceg_content_chain_detection_backend"
        assert payload["detection_source"]["paper_main_method_ready"] is False
        assert payload["detection_source"]["paper_main_method_blocking_reasons"] == ["keyed_attestation_ready"]
        assert 0.0 <= payload["content"]["content_score_raw"] <= 1.0
        assert len(payload["semantic_mask"]["mask_digest"]) == 64
        assert len(payload["content_chain"]["content_chain_digest"]) == 64
        assert len(payload["aligned_content_chain"]["content_chain_digest"]) == 64
        assert len(payload["geometry"]["geometry_record"]["alignment_digest"]) == 64
        assert payload["geometry"]["geometry_record"]["backend_id"] == "ceg_local_deformation_registration"
        assert "rotation_degrees" in payload["geometry"]["geometry_record"]
        assert "scale" in payload["geometry"]["geometry_record"]
        assert "perspective_offset" in payload["geometry"]["geometry_record"]
        assert payload["geometry"]["geometry_record"]["diagnostics"]["feature_homography"]["enabled"] is True
        assert payload["geometry"]["geometry_record"]["diagnostics"]["local_deformation"]["enabled"] is True
        assert payload["geometry"]["geometry_record"]["paper_main_method_ready"] is True
        assert payload["attestation"]["attestation_score"] == 1.0
        assert len(payload["attestation"]["attestation_digest"]) == 64
        assert payload["attestation"]["paper_main_method_ready"] is False


@pytest.mark.quick
def test_content_chain_detection_backend_can_claim_formal_method_with_keyed_attestation(tmp_path: Path) -> None:
    """提供 keyed attestation 后, detection backend 应能给出方法原语级正式 readiness。"""

    image_pairs = _write_embedded_pair(tmp_path)
    output_root = tmp_path / "keyed_detection"

    manifest = write_content_chain_detection_inputs(
        image_pairs,
        output_root,
        detector_config={
            "mask_threshold_quantile": 0.75,
            "mask_open_iters": 0,
            "mask_close_iters": 0,
            "attestation_secret_key": "unit-test-attestation-key",
            "attestation_key_id": "unit-test-key",
            "formal_result_claim": True,
        },
    )
    events = json.loads((output_root / "detection_events.json").read_text(encoding="utf-8"))

    assert manifest["paper_main_method_ready"] is True
    assert manifest["formal_result_claim"] is True
    assert manifest["paper_main_method_blocking_reasons"] == []
    assert manifest["method_readiness_checks"]["keyed_attestation_ready"]["passed"] is True
    for event in events:
        payload = event["payload"]
        assert payload["detection_source"]["paper_main_method_ready"] is True
        assert payload["detection_source"]["formal_result_claim"] is True
        assert payload["attestation"]["backend_id"] == "ceg_keyed_hmac_attestation"
        assert payload["attestation"]["paper_main_method_ready"] is True
        assert payload["attestation"]["paper_main_method_blocking_reason"] is None


@pytest.mark.quick
def test_detection_cli_can_run_content_chain_backend(tmp_path: Path) -> None:
    """CLI 应能通过参数切换到真实内容链 detection backend。"""

    image_pairs = _write_embedded_pair(tmp_path)
    output_root = tmp_path / "cli_detection"

    subprocess.run(
        [
            sys.executable,
            "scripts/run_ceg_detection_producer.py",
            "--image-pairs",
            str(image_pairs),
            "--out",
            str(output_root),
            "--detection-backend",
            "ceg_content_chain_detection",
            "--mask-threshold-quantile",
            "0.75",
            "--mask-open-iters",
            "0",
            "--mask-close-iters",
            "0",
        ],
        cwd=".",
        check=True,
    )
    manifest = json.loads((output_root / "ceg_detection_producer_manifest.json").read_text(encoding="utf-8"))
    assert manifest["producer_id"] == "ceg_content_chain_detection_backend"
    assert (output_root / "semantic_masks").is_dir()
    assert (output_root / "aligned_images").is_dir()
    assert (output_root / "detection_events.json").is_file()
