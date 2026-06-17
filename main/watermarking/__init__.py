"""CEG 项目内部水印运行时模块。

该包保存 CEG 自身的图像水印原语、后续正式 embedding pipeline 和 detection pipeline。
它不能依赖 CEG-WM 运行时; 如需参考 CEG-WM 的方法机制, 应在本包内迁移或重写为
CEG 自包含实现。
"""

from main.watermarking.interfaces import (
    WatermarkDetectionRequest,
    WatermarkDetectionResult,
    WatermarkDetector,
    WatermarkEmbedder,
    WatermarkEmbeddingRequest,
    WatermarkEmbeddingResult,
    WatermarkPromptContext,
)
from main.watermarking.native_lsb import NativeLsbWatermarkResult, embed_native_lsb_watermark

__all__ = [
    "NativeLsbWatermarkResult",
    "WatermarkDetectionRequest",
    "WatermarkDetectionResult",
    "WatermarkDetector",
    "WatermarkEmbedder",
    "WatermarkEmbeddingRequest",
    "WatermarkEmbeddingResult",
    "WatermarkPromptContext",
    "embed_native_lsb_watermark",
]
