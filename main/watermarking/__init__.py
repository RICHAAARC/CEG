"""CEG 项目内部水印运行时模块。

该包保存 CEG 自身的图像水印原语、后续正式 embedding pipeline 和 detection pipeline。
它不能依赖 CEG-WM 运行时; 如需参考 CEG-WM 的方法机制, 应在本包内迁移或重写为
CEG 自包含实现。
"""

from main.watermarking.content_chain import (
    CONTENT_CHAIN_BACKEND_ID,
    CONTENT_CHAIN_BACKEND_ROLE,
    CONTENT_CHAIN_EMBEDDING_BACKEND_ID,
    CONTENT_CHAIN_EMBEDDING_BACKEND_ROLE,
    ContentChainEmbeddingRequest,
    ContentChainEmbeddingResult,
    ContentChainRequest,
    ContentChainResult,
    embed_content_chain_watermark,
    extract_content_chain_evidence,
)
from main.watermarking.interfaces import (
    WatermarkDetectionRequest,
    WatermarkDetectionResult,
    WatermarkDetector,
    WatermarkEmbedder,
    WatermarkEmbeddingRequest,
    WatermarkEmbeddingResult,
    WatermarkPromptContext,
)
from main.watermarking.geometry import (
    GEOMETRY_REGISTRATION_BACKEND_ID,
    GEOMETRY_REGISTRATION_BACKEND_ROLE,
    GeometryRegistrationRequest,
    GeometryRegistrationResult,
    estimate_geometry_registration,
)
from main.watermarking.semantic_mask import (
    GRADIENT_SALIENCY_BACKEND_ID,
    INSPYRENET_BACKEND_ID,
    SemanticMaskRequest,
    SemanticMaskResult,
    build_gradient_saliency_mask,
    build_inspyrenet_semantic_mask,
    extract_semantic_mask,
)
from main.watermarking.native_lsb import NativeLsbWatermarkResult, embed_native_lsb_watermark

__all__ = [
    "CONTENT_CHAIN_EMBEDDING_BACKEND_ID",
    "CONTENT_CHAIN_EMBEDDING_BACKEND_ROLE",
    "ContentChainEmbeddingRequest",
    "ContentChainEmbeddingResult",
    "embed_content_chain_watermark",
    "CONTENT_CHAIN_BACKEND_ID",
    "CONTENT_CHAIN_BACKEND_ROLE",
    "ContentChainRequest",
    "ContentChainResult",
    "extract_content_chain_evidence",
    "GEOMETRY_REGISTRATION_BACKEND_ID",
    "GEOMETRY_REGISTRATION_BACKEND_ROLE",
    "GeometryRegistrationRequest",
    "GeometryRegistrationResult",
    "estimate_geometry_registration",
    "GRADIENT_SALIENCY_BACKEND_ID",
    "INSPYRENET_BACKEND_ID",
    "SemanticMaskRequest",
    "SemanticMaskResult",
    "build_gradient_saliency_mask",
    "build_inspyrenet_semantic_mask",
    "extract_semantic_mask",
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
