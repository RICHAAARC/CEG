"""验证 Colab 论文结果包流水线编排入口。"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image
import pytest

from main.watermarking.content_chain import ContentChainEmbeddingRequest, embed_content_chain_watermark
from main.watermarking.interfaces import WatermarkPromptContext
from main.watermarking.semantic_mask import SemanticMaskRequest, extract_semantic_mask


def _write_test_image(path: Path) -> None:
    """写出具有结构信息的测试图像。"""

    image = Image.new("RGB", (40, 40), color=(50, 50, 50))
    for x in range(8, 28):
        for y in range(10, 30):
            image.putpixel((x, y), (220, 220, 220))
    for x in range(29, 35):
        for y in range(6, 15):
            image.putpixel((x, y), (80, 180, 120))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _write_workspace(tmp_path: Path) -> Path:
    """构造最小 Drive workspace, 其中 image_pairs 指向真实 clean / watermarked 图像。"""

    workspace = tmp_path / "real_pilot_input_workspace_test"
    clean = workspace / "inputs" / "images" / "clean" / "img_001.png"
    watermarked = workspace / "inputs" / "images" / "watermarked" / "img_001.png"
    mask_path = workspace / "inputs" / "images" / "semantic_masks" / "img_001.png"
    _write_test_image(clean)
    prompt_context = WatermarkPromptContext(
        image_id="img_001",
        prompt_id="prompt_001",
        prompt_text="a bright square on dark background",
        seed=17,
        model_id="test-model",
    )
    semantic_mask = extract_semantic_mask(SemanticMaskRequest(image_path=clean, output_mask_path=mask_path, threshold_quantile=0.75))
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
    image_pairs = workspace / "inputs" / "images" / "image_pairs.json"
    image_pairs.write_text(
        json.dumps(
            [
                {
                    "image_id": "img_001",
                    "prompt_id": "prompt_001",
                    "prompt_text": "a bright square on dark background",
                    "seed": 17,
                    "model_id": "test-model",
                    "clean_image_path": clean.resolve().as_posix(),
                    "watermarked_image_path": watermarked.resolve().as_posix(),
                    "split": "calibration",
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return workspace


@pytest.mark.quick
def test_colab_paper_results_pipeline_cli(tmp_path: Path) -> None:
    """一条命令应完成 attack、真实 detection、校准结果包和 Drive 分类归档。"""

    short_root = Path(".tmp_colab_pipeline_test")
    if short_root.exists():
        shutil.rmtree(short_root)
    workspace = _write_workspace(short_root)
    drive_root = short_root / "MyDrive" / "CEG"
    out = workspace / "paper_results_pipeline"

    try:
        subprocess.run(
            [
                sys.executable,
                "scripts/run_colab_paper_results_pipeline.py",
                "--workspace",
                str(workspace),
                "--drive-root",
                str(drive_root),
                "--out",
                str(out),
                "--attack-families",
                "brightness_contrast",
                "--target-fpr",
                "0.01",
                "--allow-incomplete-package",
                "--allow-invalid-archive",
                "--affine-rotation-degrees",
                "0",
                "--affine-scales",
                "1.0",
            ],
            cwd=".",
            check=True,
        )

        manifest = json.loads((out / "colab_paper_results_pipeline_manifest.json").read_text(encoding="utf-8"))
        assert manifest["overall_decision"] == "pass"
        assert (out / "attack_outputs" / "image_manifests" / "attacked_image_manifest.json").is_file()
        assert (out / "detection_outputs" / "detection_events.json").is_file()
        assert (
            out / "calibrated_paper_results_package" / "paper_results_package" / "paper_results_package_manifest.json"
        ).is_file()
        assert any((drive_root / "package_archives").glob("paper_results_package_*.zip"))
    finally:
        if short_root.exists():
            shutil.rmtree(short_root)
