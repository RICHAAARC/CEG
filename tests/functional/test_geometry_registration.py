"""验证 CEG 几何 registration 原语。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from main.watermarking.geometry import GeometryRegistrationRequest, estimate_geometry_registration
from main.watermarking.geometry.registration import _perspective_coefficients


def _write_reference_image(path: Path) -> None:
    """写出具有非对称结构的小图像, 让平移估计有稳定依据。"""

    image = Image.new("RGB", (36, 36), color=(20, 20, 20))
    for x in range(6, 18):
        for y in range(8, 20):
            image.putpixel((x, y), (220, 220, 220))
    for x in range(22, 30):
        for y in range(20, 28):
            image.putpixel((x, y), (120, 210, 80))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _write_shifted_image(reference: Path, target: Path, *, dx: int, dy: int) -> None:
    """把 reference 图像平移后写出 target 图像。"""

    with Image.open(reference) as image:
        rgb = image.convert("RGB")
        shifted = Image.new("RGB", rgb.size, color=(0, 0, 0))
        shifted.paste(rgb, (dx, dy))
        target.parent.mkdir(parents=True, exist_ok=True)
        shifted.save(target)


def _write_rotated_shifted_image(reference: Path, target: Path, *, angle: float, dx: int, dy: int) -> None:
    """写出带旋转和平移的 target 图像, 用于验证 affine registration。"""

    with Image.open(reference) as image:
        rgb = image.convert("RGB")
        rotated = rgb.rotate(angle, resample=Image.Resampling.BILINEAR, expand=False, fillcolor=(0, 0, 0))
        shifted = Image.new("RGB", rgb.size, color=(0, 0, 0))
        shifted.paste(rotated, (dx, dy))
        target.parent.mkdir(parents=True, exist_ok=True)
        shifted.save(target)


def _write_perspective_image(reference: Path, target: Path, *, perspective_offset: float) -> None:
    """写出带轻量透视变形的 target 图像。"""

    with Image.open(reference) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        rect = [(0.0, 0.0), (float(width - 1), 0.0), (float(width - 1), float(height - 1)), (0.0, float(height - 1))]
        offset = float(width - 1) * perspective_offset
        distorted = [
            (offset, 0.0),
            (float(width - 1) - offset, 0.0),
            (float(width - 1), float(height - 1)),
            (0.0, float(height - 1)),
        ]
        coeffs = _perspective_coefficients(rect, distorted)
        target.parent.mkdir(parents=True, exist_ok=True)
        rgb.transform(rgb.size, Image.Transform.PERSPECTIVE, coeffs, resample=Image.Resampling.BILINEAR).save(target)


@pytest.mark.quick
def test_translation_registration_writes_aligned_image(tmp_path: Path) -> None:
    """registration 原语应估计平移并写出 aligned 图像。"""

    reference = tmp_path / "reference.png"
    target = tmp_path / "target.png"
    aligned = tmp_path / "aligned.png"
    _write_reference_image(reference)
    _write_shifted_image(reference, target, dx=2, dy=1)

    result = estimate_geometry_registration(
        GeometryRegistrationRequest(
            target_image_path=target,
            reference_image_path=reference,
            output_aligned_image_path=aligned,
            search_radius=5,
            downsample_size=64,
            anchor_grid_size=3,
        )
    )

    assert result.status == "ok"
    assert aligned.is_file()
    assert result.registration_confidence >= 0.5
    assert 0.0 <= result.anchor_inlier_ratio <= 1.0
    assert 0.0 <= result.recovered_sync_consistency <= 1.0
    assert len(result.alignment_digest) == 64
    assert result.paper_main_method_ready is True


@pytest.mark.quick
def test_affine_registration_records_rotation_and_scale_candidates(tmp_path: Path) -> None:
    """registration 原语应真实搜索 affine 候选, 而不是只保留平移占位字段。"""

    reference = tmp_path / "reference.png"
    target = tmp_path / "target_rotated.png"
    aligned = tmp_path / "aligned_rotated.png"
    _write_reference_image(reference)
    _write_rotated_shifted_image(reference, target, angle=3.0, dx=1, dy=0)

    result = estimate_geometry_registration(
        GeometryRegistrationRequest(
            target_image_path=target,
            reference_image_path=reference,
            output_aligned_image_path=aligned,
            search_radius=4,
            downsample_size=64,
            anchor_grid_size=3,
            config={"affine_rotation_degrees": [-3.0, 0.0, 3.0], "affine_scales": [1.0]},
        )
    )

    record = result.to_record()
    assert result.status == "ok"
    assert aligned.is_file()
    assert result.backend_id == "ceg_local_deformation_registration"
    assert result.paper_main_method_ready is True
    assert record["paper_main_method_blocking_reason"] is None
    assert result.rotation_degrees in {-3.0, 0.0, 3.0}
    assert result.diagnostics["affine_candidate_count"] == 3
    assert result.diagnostics["candidate_count"] == 3 * 81
    assert result.diagnostics["feature_homography"]["enabled"] is True
    assert result.diagnostics["local_deformation"]["enabled"] is True


@pytest.mark.quick
def test_perspective_registration_records_keystone_candidates(tmp_path: Path) -> None:
    """registration 原语应真实搜索轻量 perspective 候选。"""

    reference = tmp_path / "reference.png"
    target = tmp_path / "target_perspective.png"
    aligned = tmp_path / "aligned_perspective.png"
    _write_reference_image(reference)
    _write_perspective_image(reference, target, perspective_offset=0.08)

    result = estimate_geometry_registration(
        GeometryRegistrationRequest(
            target_image_path=target,
            reference_image_path=reference,
            output_aligned_image_path=aligned,
            search_radius=3,
            downsample_size=64,
            anchor_grid_size=3,
            config={"affine_rotation_degrees": [0.0], "affine_scales": [1.0], "perspective_offsets": [0.0, 0.08]},
        )
    )

    record = result.to_record()
    assert result.status == "ok"
    assert aligned.is_file()
    assert record["perspective_offset"] in {0.0, 0.08}
    assert result.diagnostics["perspective_offset_candidates"] == [0.0, 0.08]
    assert result.diagnostics["affine_candidate_count"] == 2
    assert result.diagnostics["candidate_count"] == 2 * 49


@pytest.mark.quick
def test_feature_homography_registration_records_matches(tmp_path: Path) -> None:
    """registration 原语应运行 feature matching homography refinement 并记录审计信息。"""

    reference = tmp_path / "reference.png"
    target = tmp_path / "target_feature.png"
    aligned = tmp_path / "aligned_feature.png"
    _write_reference_image(reference)
    _write_shifted_image(reference, target, dx=2, dy=1)

    result = estimate_geometry_registration(
        GeometryRegistrationRequest(
            target_image_path=target,
            reference_image_path=reference,
            output_aligned_image_path=aligned,
            search_radius=4,
            downsample_size=64,
            anchor_grid_size=3,
            config={
                "affine_rotation_degrees": [0.0],
                "affine_scales": [1.0],
                "perspective_offsets": [0.0],
                "feature_homography_enabled": True,
                "feature_max_features": 32,
                "homography_ransac_max_trials": 80,
            },
        )
    )

    feature = result.diagnostics["feature_homography"]
    assert result.status == "ok"
    assert feature["enabled"] is True
    assert feature["status"] in {"ok", "insufficient_matches", "homography_not_found"}
    if feature["status"] == "ok":
        assert feature["match_count"] >= 4
        assert feature["inlier_count"] >= 4
        assert len(feature["homography_matrix"]) == 3


@pytest.mark.quick
def test_local_deformation_registration_records_grid_shifts(tmp_path: Path) -> None:
    """registration 原语应运行局部网格 deformation refinement 并记录块级位移。"""

    reference = tmp_path / "reference.png"
    target = tmp_path / "target_local.png"
    aligned = tmp_path / "aligned_local.png"
    _write_reference_image(reference)
    with Image.open(reference) as image:
        rgb = image.convert("RGB")
        locally_shifted = Image.new("RGB", rgb.size, color=(0, 0, 0))
        locally_shifted.paste(rgb.crop((0, 0, rgb.width, rgb.height // 2)), (1, 0))
        locally_shifted.paste(rgb.crop((0, rgb.height // 2, rgb.width, rgb.height)), (-1, rgb.height // 2))
        target.parent.mkdir(parents=True, exist_ok=True)
        locally_shifted.save(target)

    result = estimate_geometry_registration(
        GeometryRegistrationRequest(
            target_image_path=target,
            reference_image_path=reference,
            output_aligned_image_path=aligned,
            search_radius=3,
            downsample_size=64,
            anchor_grid_size=3,
            config={
                "affine_rotation_degrees": [0.0],
                "affine_scales": [1.0],
                "perspective_offsets": [0.0],
                "feature_homography_enabled": False,
                "local_deformation_enabled": True,
                "local_deformation_grid_size": 3,
                "local_deformation_search_radius": 2,
            },
        )
    )

    local = result.diagnostics["local_deformation"]
    assert result.status == "ok"
    assert aligned.is_file()
    assert local["enabled"] is True
    assert local["status"] == "ok"
    assert local["block_count"] == 9
    assert len(local["shifts"]) == 9
