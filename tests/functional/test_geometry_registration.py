"""验证 CEG 几何 registration 原语。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from main.watermarking.geometry import GeometryRegistrationRequest, estimate_geometry_registration


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
    assert result.paper_main_method_ready is False
