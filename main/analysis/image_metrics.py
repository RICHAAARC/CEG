"""计算图像水印论文常用的轻量图像质量指标。

该模块提供无重型依赖的基础实现: MSE、MAE、PSNR 和全局 SSIM。
当运行环境安装 Pillow 时, 可直接读取 PNG / JPEG / WebP 等常见格式; 否则仍支持
PNM 系列中的 PGM / PPM 文件, 便于测试和最小复现。LPIPS、FID 等需要专用模型或
数据集统计量的指标不在这里伪造, 应通过外部指标文件进入 records。
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ImageArray:
    """保存已归一化为 RGB 通道的图像像素。"""

    width: int
    height: int
    channels: int
    pixels: tuple[float, ...]
    max_value: float


@dataclass(frozen=True)
class ImageQualityMetrics:
    """保存一对图像之间的可审计质量指标。"""

    image_id: str
    reference_path: str
    watermarked_path: str
    width: int
    height: int
    channel_count: int
    mse: float
    mae: float
    psnr: float | None
    ssim: float

    def to_record(self) -> dict[str, object]:
        """转换为可写入 JSON / CSV / records 的普通字典。"""
        return asdict(self)


def _read_token(data: bytes, index: int) -> tuple[bytes, int]:
    """读取 PNM token, 支持跳过空白和注释。"""
    length = len(data)
    while index < length:
        byte = data[index]
        if byte == 35:
            while index < length and data[index] not in {10, 13}:
                index += 1
        elif chr(byte).isspace():
            index += 1
        else:
            break
    start = index
    while index < length and not chr(data[index]).isspace():
        index += 1
    return data[start:index], index


def _load_pnm(path: Path) -> ImageArray:
    """读取 PGM / PPM 图像, 作为无第三方依赖的最小图像输入格式。"""
    data = path.read_bytes()
    magic, index = _read_token(data, 0)
    if magic not in {b"P2", b"P3", b"P5", b"P6"}:
        raise ValueError(f"unsupported image format without Pillow: {path}")
    width_token, index = _read_token(data, index)
    height_token, index = _read_token(data, index)
    max_token, index = _read_token(data, index)
    width = int(width_token)
    height = int(height_token)
    max_value = float(int(max_token))
    channels = 1 if magic in {b"P2", b"P5"} else 3
    expected_count = width * height * channels
    if magic in {b"P2", b"P3"}:
        values: list[float] = []
        while len(values) < expected_count:
            token, index = _read_token(data, index)
            if not token:
                break
            values.append(float(int(token)))
    else:
        while index < len(data) and chr(data[index]).isspace():
            index += 1
        raw = data[index : index + expected_count]
        if len(raw) != expected_count:
            raise ValueError(f"PNM pixel payload length mismatch: {path}")
        values = [float(value) for value in raw]
    if len(values) != expected_count:
        raise ValueError(f"PNM pixel count mismatch: {path}")
    if channels == 1:
        rgb_values: list[float] = []
        for value in values:
            rgb_values.extend([value, value, value])
        values = rgb_values
        channels = 3
    return ImageArray(width=width, height=height, channels=channels, pixels=tuple(values), max_value=max_value)


def load_image_array(path: str | Path) -> ImageArray:
    """读取图像并转换为 RGB 像素数组。

    通用工程写法: 优先使用 Pillow 扩展真实格式支持, 无 Pillow 时使用 PNM fallback。
    项目特定写法: 输出结构固定为论文质量指标计算所需的最小数据面。
    """
    image_path = Path(path)
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return _load_pnm(image_path)
    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
        values = [float(value) for pixel in rgb_image.getdata() for value in pixel]
        return ImageArray(
            width=rgb_image.width,
            height=rgb_image.height,
            channels=3,
            pixels=tuple(values),
            max_value=255.0,
        )


def _assert_compatible(reference: ImageArray, candidate: ImageArray) -> None:
    """确认两张图像尺寸和通道一致, 避免错误配对进入正式指标。"""
    if (reference.width, reference.height, reference.channels) != (candidate.width, candidate.height, candidate.channels):
        raise ValueError("image dimensions or channels do not match")


def compute_pair_quality_metrics(
    reference_path: str | Path,
    watermarked_path: str | Path,
    *,
    image_id: str | None = None,
) -> ImageQualityMetrics:
    """计算一对参考图像和水印图像之间的质量指标。"""
    reference = load_image_array(reference_path)
    candidate = load_image_array(watermarked_path)
    _assert_compatible(reference, candidate)
    differences = [candidate_value - reference_value for reference_value, candidate_value in zip(reference.pixels, candidate.pixels)]
    squared_errors = [difference * difference for difference in differences]
    absolute_errors = [abs(difference) for difference in differences]
    mse = sum(squared_errors) / len(squared_errors) if squared_errors else 0.0
    mae = sum(absolute_errors) / len(absolute_errors) if absolute_errors else 0.0
    psnr = None if mse == 0 else 20.0 * math.log10(reference.max_value / math.sqrt(mse))
    ssim = compute_global_ssim(reference, candidate)
    return ImageQualityMetrics(
        image_id=image_id or Path(watermarked_path).stem,
        reference_path=str(reference_path),
        watermarked_path=str(watermarked_path),
        width=reference.width,
        height=reference.height,
        channel_count=reference.channels,
        mse=mse,
        mae=mae,
        psnr=psnr,
        ssim=ssim,
    )


def compute_global_ssim(reference: ImageArray, candidate: ImageArray) -> float:
    """计算全局 SSIM 近似值。

    该实现使用整图均值、方差和协方差, 适合作为轻量可复现指标。若论文最终需要窗口化
    SSIM, 可在同一接口下替换为 skimage 或专用实现。
    """
    _assert_compatible(reference, candidate)
    count = len(reference.pixels)
    if count == 0:
        return 1.0
    mean_reference = sum(reference.pixels) / count
    mean_candidate = sum(candidate.pixels) / count
    variance_reference = sum((value - mean_reference) ** 2 for value in reference.pixels) / count
    variance_candidate = sum((value - mean_candidate) ** 2 for value in candidate.pixels) / count
    covariance = sum(
        (reference_value - mean_reference) * (candidate_value - mean_candidate)
        for reference_value, candidate_value in zip(reference.pixels, candidate.pixels)
    ) / count
    c1 = (0.01 * reference.max_value) ** 2
    c2 = (0.03 * reference.max_value) ** 2
    numerator = (2 * mean_reference * mean_candidate + c1) * (2 * covariance + c2)
    denominator = (mean_reference**2 + mean_candidate**2 + c1) * (variance_reference + variance_candidate + c2)
    return numerator / denominator if denominator else 1.0


def build_quality_metric_rows(pairs: Iterable[dict[str, str]]) -> list[dict[str, object]]:
    """批量计算图像质量指标行。

    输入每行至少包含 `reference_path` / `clean_image_path` 和 `watermarked_path` / `watermarked_image_path`,
    可选包含 `image_id`、`event_id` 和 `method_name`。输出可以继续并入实验 records 或单独写入质量指标文件。
    """
    rows: list[dict[str, object]] = []
    for pair in pairs:
        reference_path = pair.get("reference_path") or pair.get("clean_image_path")
        watermarked_path = pair.get("watermarked_path") or pair.get("watermarked_image_path")
        if reference_path is None:
            raise KeyError("quality metric pair missing reference_path or clean_image_path")
        if watermarked_path is None:
            raise KeyError("quality metric pair missing watermarked_path or watermarked_image_path")
        metrics = compute_pair_quality_metrics(
            reference_path,
            watermarked_path,
            image_id=pair.get("image_id") or pair.get("event_id"),
        ).to_record()
        if "event_id" not in pair and pair.get("image_id"):
            metrics["event_id"] = f"{pair['image_id']}__positive_source"
        if "method_name" not in pair:
            metrics["method_name"] = "ceg"
        for optional_field in ("event_id", "method_name", "split", "sample_role", "attack_family", "attack_condition"):
            if optional_field in pair:
                metrics[optional_field] = pair[optional_field]
        rows.append(metrics)
    return rows
