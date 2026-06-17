"""测试 CEG 内部 semantic mask 原语。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from main.watermarking.semantic_mask import (
    GRADIENT_SALIENCY_BACKEND_ID,
    INSPYRENET_BACKEND_ID,
    SemanticMaskRequest,
    extract_semantic_mask,
)


def _write_edge_image(path: Path) -> None:
    """写出带有明确边缘的小图像, 使梯度显著性 mask 有真实像素依据。"""

    image = Image.new("RGB", (24, 24), color=(20, 20, 20))
    for x in range(6, 18):
        for y in range(6, 18):
            image.putpixel((x, y), (230, 230, 230))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


@pytest.mark.quick
def test_gradient_semantic_mask_uses_real_image_pixels_and_writes_mask(tmp_path: Path) -> None:
    """梯度 semantic mask 应读取真实图像并写出二值 mask 产物。"""

    image_path = tmp_path / "clean.png"
    mask_path = tmp_path / "mask.png"
    _write_edge_image(image_path)

    result = extract_semantic_mask(
        SemanticMaskRequest(
            image_path=image_path,
            output_mask_path=mask_path,
            backend_id=GRADIENT_SALIENCY_BACKEND_ID,
            threshold_quantile=0.75,
            open_iters=0,
            close_iters=0,
        )
    )
    record = result.to_record()

    assert mask_path.is_file()
    assert result.mask.shape == (24, 24)
    assert result.mask.any()
    assert 0.0 < record["mask_stats"]["area_ratio"] < 1.0
    assert record["backend_id"] == GRADIENT_SALIENCY_BACKEND_ID
    assert record["paper_main_method_ready"] is False
    assert record["resolution_binding"]["height"] == 24


@pytest.mark.quick
def test_gradient_semantic_mask_digest_is_stable(tmp_path: Path) -> None:
    """相同图像和配置应生成稳定 mask digest 与 routing digest。"""

    image_path = tmp_path / "clean.png"
    _write_edge_image(image_path)
    request = SemanticMaskRequest(
        image_path=image_path,
        backend_id=GRADIENT_SALIENCY_BACKEND_ID,
        threshold_quantile=0.75,
        open_iters=0,
        close_iters=0,
    )

    first = extract_semantic_mask(request)
    second = extract_semantic_mask(request)

    assert first.mask_digest == second.mask_digest
    assert first.routing_digest == second.routing_digest
    assert first.to_record()["mask_stats"]["downsample_grid_digest"] == second.to_record()["mask_stats"]["downsample_grid_digest"]


@pytest.mark.quick
def test_inspyrenet_backend_fails_explicitly_without_optional_dependency(tmp_path: Path) -> None:
    """当 InSPyReNet 依赖不可用时, backend 应显式失败而不是静默降级。"""

    image_path = tmp_path / "clean.png"
    _write_edge_image(image_path)
    request = SemanticMaskRequest(image_path=image_path, backend_id=INSPYRENET_BACKEND_ID)

    try:
        import transparent_background  # type: ignore  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="InSPyReNet backend"):
            extract_semantic_mask(request)
    else:
        result = extract_semantic_mask(request)
        assert result.backend_id == INSPYRENET_BACKEND_ID
        assert result.mask.shape == (24, 24)
