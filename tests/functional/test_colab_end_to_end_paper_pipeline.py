"""验证 Colab 端到端论文结果包流水线入口。"""

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
    """写出具有稳定结构的测试图像, 使攻击和检测流程可以在本地快速运行。"""

    image = Image.new("RGB", (40, 40), color=(45, 45, 45))
    for x in range(8, 29):
        for y in range(9, 31):
            image.putpixel((x, y), (220, 220, 220))
    for x in range(28, 36):
        for y in range(5, 16):
            image.putpixel((x, y), (85, 175, 120))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _write_existing_image_generation_outputs(tmp_root: Path) -> Path:
    """构造已完成图像生成阶段的最小 workspace。

    该测试不启动真实 SD 模型, 因为默认测试必须轻量稳定。这里验证的是端到端编排脚本在
    “图像生成产物已存在”场景下能继续完成验收、攻击、检测、校准、结果包和 Drive 归档。
    """

    workspace = tmp_root / "real_pilot_input_workspace_end_to_end"
    image_root = workspace / "inputs" / "images"
    clean = image_root / "clean" / "img_001.png"
    watermarked = image_root / "watermarked" / "img_001.png"
    mask_path = image_root / "semantic_masks" / "img_001.png"
    _write_test_image(clean)

    prompt_context = WatermarkPromptContext(
        image_id="img_001",
        prompt_id="prompt_001",
        prompt_text="a bright square on dark background",
        seed=23,
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

    image_pairs = [
        {
            "image_id": "img_001",
            "prompt_id": "prompt_001",
            "prompt_text": "a bright square on dark background",
            "seed": 23,
            "model_id": "test-model",
            "clean_image_path": clean.resolve().as_posix(),
            "watermarked_image_path": watermarked.resolve().as_posix(),
            "split": "calibration",
        }
    ]
    (image_root / "image_pairs.json").write_text(json.dumps(image_pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (image_root / "prompt_plan.json").write_text(
        json.dumps(
            [
                {
                    "prompt_id": "prompt_001",
                    "prompt_text": "a bright square on dark background",
                    "seed": 23,
                    "split": "calibration",
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_root = image_root / "image_manifests"
    manifest_root.mkdir(parents=True, exist_ok=True)
    (manifest_root / "image_generation_manifest.json").write_text(
        json.dumps({"artifact_name": "image_generation_manifest.json", "record_count": 1}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (manifest_root / "image_pair_manifest.json").write_text(
        json.dumps({"artifact_name": "image_pair_manifest.json", "image_pair_count": 1}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return workspace


@pytest.mark.quick
def test_colab_end_to_end_paper_pipeline_uses_existing_image_generation_outputs(tmp_path: Path) -> None:
    """端到端入口应从已存在图像产物继续完成论文结果包构建与 Drive 分类归档。"""

    short_root = Path(".tmp_colab_end_to_end_pipeline_test")
    if short_root.exists():
        shutil.rmtree(short_root)
    workspace = _write_existing_image_generation_outputs(short_root)
    drive_root = short_root / "MyDrive" / "CEG"
    out = workspace / "paper_end_to_end_pipeline"

    try:
        subprocess.run(
            [
                sys.executable,
                "scripts/run_colab_end_to_end_paper_pipeline.py",
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

        manifest = json.loads((out / "colab_end_to_end_paper_pipeline_manifest.json").read_text(encoding="utf-8"))
        assert manifest["overall_decision"] == "pass"
        assert manifest["run_image_generation"] is False
        assert Path(manifest["image_acceptance_report"]).is_file()
        assert Path(manifest["paper_pipeline_manifest"]).is_file()
        assert any((drive_root / "archives" / "image_generation_outputs").glob("image_generation_outputs_*.zip"))
        assert any((drive_root / "package_archives").glob("paper_results_package_*.zip"))
    finally:
        if short_root.exists():
            shutil.rmtree(short_root)


@pytest.mark.quick
def test_validate_colab_end_to_end_formal_run_accepts_reviewed_resume_outputs(tmp_path: Path) -> None:
    """正式验收入口应能复核端到端 manifest、图像产物、结果包和 Drive 归档。"""

    short_root = Path(".tmp_colab_end_to_end_formal_acceptance_test")
    if short_root.exists():
        shutil.rmtree(short_root)
    workspace = _write_existing_image_generation_outputs(short_root)
    drive_root = short_root / "MyDrive" / "CEG"
    pipeline_out = workspace / "paper_end_to_end_pipeline"
    acceptance_report = workspace / "formal_acceptance" / "formal_run_acceptance.json"

    try:
        subprocess.run(
            [
                sys.executable,
                "scripts/run_colab_end_to_end_paper_pipeline.py",
                "--workspace",
                str(workspace),
                "--drive-root",
                str(drive_root),
                "--out",
                str(pipeline_out),
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

        subprocess.run(
            [
                sys.executable,
                "scripts/validate_colab_end_to_end_formal_run.py",
                "--manifest",
                str(pipeline_out / "colab_end_to_end_paper_pipeline_manifest.json"),
                "--out",
                str(acceptance_report),
                "--allow-existing-image-generation",
                "--allow-incomplete-package",
                "--allow-invalid-archive",
                "--require-pass",
            ],
            cwd=".",
            check=True,
        )

        report = json.loads(acceptance_report.read_text(encoding="utf-8"))
        assert report["overall_decision"] == "pass"
        assert report["allow_existing_image_generation"] is True
        assert report["summary"]["formal_run_spec_decision"] == "pass"
        assert report["summary"]["image_pair_count"] == 1
        assert Path(report["subreport_paths"]["formal_run_spec_validation"]).is_file()
        assert Path(report["subreport_paths"]["image_generation_acceptance"]).is_file()
        assert Path(report["subreport_paths"]["paper_results_package_acceptance"]).is_file()
        assert Path(report["subreport_paths"]["mydrive_archive_acceptance"]).is_file()
    finally:
        if short_root.exists():
            shutil.rmtree(short_root)


@pytest.mark.quick
def test_validate_colab_end_to_end_formal_run_rejects_non_gpu_resume_without_override(tmp_path: Path) -> None:
    """默认正式验收应拒绝未在同次流程中运行真实图像生成的结果。"""

    short_root = Path(".tmp_colab_end_to_end_formal_reject_test")
    if short_root.exists():
        shutil.rmtree(short_root)
    workspace = _write_existing_image_generation_outputs(short_root)
    drive_root = short_root / "MyDrive" / "CEG"
    pipeline_out = workspace / "paper_end_to_end_pipeline"
    acceptance_report = workspace / "formal_acceptance" / "formal_run_acceptance.json"

    try:
        subprocess.run(
            [
                sys.executable,
                "scripts/run_colab_end_to_end_paper_pipeline.py",
                "--workspace",
                str(workspace),
                "--drive-root",
                str(drive_root),
                "--out",
                str(pipeline_out),
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

        failed = subprocess.run(
            [
                sys.executable,
                "scripts/validate_colab_end_to_end_formal_run.py",
                "--manifest",
                str(pipeline_out / "colab_end_to_end_paper_pipeline_manifest.json"),
                "--out",
                str(acceptance_report),
                "--allow-incomplete-package",
                "--allow-invalid-archive",
                "--require-pass",
            ],
            cwd=".",
            check=False,
            text=True,
            capture_output=True,
        )

        assert failed.returncode == 1
        report = json.loads(acceptance_report.read_text(encoding="utf-8"))
        assert report["overall_decision"] == "fail"
        checks = {check["check_name"]: check for check in report["checks"]}
        assert checks["real_image_generation_run"]["status"] == "fail"
    finally:
        if short_root.exists():
            shutil.rmtree(short_root)


@pytest.mark.quick
def test_validate_colab_end_to_end_formal_run_rejects_under_scaled_full_profile(tmp_path: Path) -> None:
    """full 正式运行规格应拒绝只有 1 个 image pair 的最小探针结果。"""

    short_root = Path(".tmp_full_reject")
    if short_root.exists():
        shutil.rmtree(short_root)
    workspace = _write_existing_image_generation_outputs(short_root)
    drive_root = short_root / "MyDrive" / "CEG"
    pipeline_out = workspace / "paper_end_to_end_pipeline"
    acceptance_report = workspace / "formal_acceptance" / "formal_run_acceptance.json"

    try:
        subprocess.run(
            [
                sys.executable,
                "scripts/run_colab_end_to_end_paper_pipeline.py",
                "--workspace",
                str(workspace),
                "--drive-root",
                str(drive_root),
                "--out",
                str(pipeline_out),
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

        failed = subprocess.run(
            [
                sys.executable,
                "scripts/validate_colab_end_to_end_formal_run.py",
                "--manifest",
                str(pipeline_out / "colab_end_to_end_paper_pipeline_manifest.json"),
                "--out",
                str(acceptance_report),
                "--profile",
                "paper_main_full",
                "--allow-existing-image-generation",
                "--allow-incomplete-package",
                "--allow-invalid-archive",
                "--require-pass",
            ],
            cwd=".",
            check=False,
            text=True,
            capture_output=True,
        )

        assert failed.returncode == 1
        report = json.loads(acceptance_report.read_text(encoding="utf-8"))
        assert report["overall_decision"] == "fail"
        assert report["summary"]["formal_run_spec_decision"] == "fail"
        spec_report = json.loads(Path(report["subreport_paths"]["formal_run_spec_validation"]).read_text(encoding="utf-8"))
        spec_checks = {check["check_name"]: check for check in spec_report["checks"]}
        assert spec_checks["image_pair_count_meets_minimum"]["status"] == "fail"
        assert spec_checks["required_attack_families_present"]["status"] == "fail"
    finally:
        if short_root.exists():
            shutil.rmtree(short_root)
