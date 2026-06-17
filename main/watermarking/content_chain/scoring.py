"""CEG 内容链 LF/HF 证据提取模块。

该模块把 semantic mask 的空间路由转换为 LF/HF 内容链分数、trace digest 和可写入
records 的 evidence。它只实现方法原语, 不包含 notebook、Colab、Google Drive 打包、
harness 门禁或 CEG-WM 兼容层。

当前实现是图像驱动的轻量内容链:
1. LF 分支读取 `mask_false` 区域, 通过低分辨率亮度块均值形成低频内容向量。
2. HF 分支读取 `mask_true` 区域, 通过梯度能量块统计形成高频内容向量。
3. 两个分支均绑定 prompt、模型、mask digest 和配置参数派生确定性 challenge。
4. 输出 `lf_score`、`hf_score`、`content_score`、`lf_trace_digest`、`hf_trace_digest`。

该实现是真实图像像素计算路径, 但仍不是完整论文主方法。完整方法还需要 embedding 侧改写、
几何恢复和 attestation 绑定后, 才能声明 `paper_main_method_ready = True`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from main.core.digest import build_stable_digest
from main.watermarking.interfaces import WatermarkPromptContext
from main.watermarking.semantic_mask import SemanticMaskResult


CONTENT_CHAIN_BACKEND_ID = "ceg_mask_routed_content_chain"
CONTENT_CHAIN_BACKEND_ROLE = "lf_hf_content_evidence_primitive"
CONTENT_CHAIN_VERSION = "ceg_content_chain_v1"
LF_TRACE_VERSION = "ceg_lf_trace_v1"
HF_TRACE_VERSION = "ceg_hf_trace_v1"


@dataclass(frozen=True)
class ContentChainRequest:
    """描述一次内容链证据提取请求。

    该结构属于通用工程写法: 它把图像、mask、prompt 上下文和分支权重固定为一个入口,
    使后续 detector、实验脚本和 records 生成器可以复用同一套输入契约。
    """

    image_path: Path
    semantic_mask: SemanticMaskResult
    prompt_context: WatermarkPromptContext
    lf_grid_size: int = 8
    hf_grid_size: int = 8
    lf_weight: float = 0.5
    hf_weight: float = 0.5
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContentChainResult:
    """描述 LF/HF 内容链输出。

    `paper_main_method_ready` 固定为 False, 因为该模块只给出内容链 evidence, 尚未包含图像水印
    embedding、几何恢复和 attestation 的完整闭环。
    """

    status: str
    content_score: float
    lf_score: float
    hf_score: float
    lf_trace_digest: str
    hf_trace_digest: str
    content_chain_digest: str
    lf_statistics_digest: str
    hf_statistics_digest: str
    score_parts: Mapping[str, Any]
    diagnostics: Mapping[str, Any]
    backend_id: str = CONTENT_CHAIN_BACKEND_ID
    backend_role: str = CONTENT_CHAIN_BACKEND_ROLE
    paper_main_method_ready: bool = False

    def to_record(self) -> dict[str, Any]:
        """转换为 detection record 或 manifest 可消费的普通字典。"""

        return {
            "status": self.status,
            "score": self.content_score,
            "content_score": self.content_score,
            "lf_score": self.lf_score,
            "hf_score": self.hf_score,
            "lf_trace_digest": self.lf_trace_digest,
            "hf_trace_digest": self.hf_trace_digest,
            "content_chain_digest": self.content_chain_digest,
            "lf_statistics_digest": self.lf_statistics_digest,
            "hf_statistics_digest": self.hf_statistics_digest,
            "score_parts": dict(self.score_parts),
            "diagnostics": dict(self.diagnostics),
            "backend_id": self.backend_id,
            "backend_role": self.backend_role,
            "paper_main_method_ready": self.paper_main_method_ready,
            "paper_main_method_blocking_reason": "content_chain_lacks_embedding_geometry_and_attestation_closure",
        }


def extract_content_chain_evidence(request: ContentChainRequest) -> ContentChainResult:
    """从图像和 semantic mask 中提取 LF/HF 内容链证据。"""

    _validate_request(request)
    image_array = _load_rgb_array(request.image_path)
    mask = _coerce_mask(request.semantic_mask.mask, image_array.shape[:2])
    gray = _to_gray(image_array)
    lf_vector = _extract_lf_vector(gray, mask, request.lf_grid_size)
    hf_vector = _extract_hf_vector(gray, mask, request.hf_grid_size)

    lf_challenge = _derive_channel_challenge(
        channel="lf",
        length=int(lf_vector.shape[0]),
        request=request,
    )
    hf_challenge = _derive_channel_challenge(
        channel="hf",
        length=int(hf_vector.shape[0]),
        request=request,
    )
    lf_score = _bounded_cosine_score(lf_vector, lf_challenge)
    hf_score = _bounded_cosine_score(hf_vector, hf_challenge)
    lf_weight, hf_weight = _normalize_weights(request.lf_weight, request.hf_weight)
    content_score = float(lf_weight * lf_score + hf_weight * hf_score)

    lf_statistics = _build_channel_statistics("lf", lf_vector, lf_score, request, request.semantic_mask.mask_digest)
    hf_statistics = _build_channel_statistics("hf", hf_vector, hf_score, request, request.semantic_mask.mask_digest)
    lf_statistics_digest = build_stable_digest(lf_statistics)
    hf_statistics_digest = build_stable_digest(hf_statistics)
    lf_trace_digest = build_stable_digest(
        {
            "trace_version": LF_TRACE_VERSION,
            "statistics_digest": lf_statistics_digest,
            "challenge_digest": build_stable_digest({"challenge": _round_vector(lf_challenge)}),
            "mask_digest": request.semantic_mask.mask_digest,
        }
    )
    hf_trace_digest = build_stable_digest(
        {
            "trace_version": HF_TRACE_VERSION,
            "statistics_digest": hf_statistics_digest,
            "challenge_digest": build_stable_digest({"challenge": _round_vector(hf_challenge)}),
            "mask_digest": request.semantic_mask.mask_digest,
        }
    )
    score_parts = {
        "lf_weight": lf_weight,
        "hf_weight": hf_weight,
        "lf_score": lf_score,
        "hf_score": hf_score,
        "mask_digest": request.semantic_mask.mask_digest,
        "routing_digest": request.semantic_mask.routing_digest,
    }
    diagnostics = {
        "content_chain_version": CONTENT_CHAIN_VERSION,
        "lf_vector_length": int(lf_vector.shape[0]),
        "hf_vector_length": int(hf_vector.shape[0]),
        "lf_grid_size": int(request.lf_grid_size),
        "hf_grid_size": int(request.hf_grid_size),
        "prompt_context": request.prompt_context.to_record(),
        "lf_statistics": lf_statistics,
        "hf_statistics": hf_statistics,
    }
    content_chain_digest = build_stable_digest(
        {
            "content_chain_version": CONTENT_CHAIN_VERSION,
            "lf_trace_digest": lf_trace_digest,
            "hf_trace_digest": hf_trace_digest,
            "score_parts": score_parts,
        }
    )
    return ContentChainResult(
        status="ok",
        content_score=round(content_score, 8),
        lf_score=round(lf_score, 8),
        hf_score=round(hf_score, 8),
        lf_trace_digest=lf_trace_digest,
        hf_trace_digest=hf_trace_digest,
        content_chain_digest=content_chain_digest,
        lf_statistics_digest=lf_statistics_digest,
        hf_statistics_digest=hf_statistics_digest,
        score_parts=score_parts,
        diagnostics=diagnostics,
        paper_main_method_ready=False,
    )


def _validate_request(request: ContentChainRequest) -> None:
    """校验内容链请求, 避免隐式使用错误输入。"""

    if not request.image_path.is_file():
        raise FileNotFoundError(f"image_path not found: {request.image_path}")
    if request.lf_grid_size <= 0 or request.hf_grid_size <= 0:
        raise ValueError("lf_grid_size and hf_grid_size must be positive")
    if request.lf_weight < 0 or request.hf_weight < 0:
        raise ValueError("lf_weight and hf_weight must be non-negative")
    if request.lf_weight + request.hf_weight <= 0:
        raise ValueError("at least one content chain weight must be positive")


def _load_rgb_array(image_path: Path) -> np.ndarray:
    """读取 RGB 图像。"""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境决定
        raise RuntimeError("content chain 需要安装 Pillow。") from exc
    with Image.open(image_path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32)


def _coerce_mask(mask: np.ndarray, expected_shape: tuple[int, int]) -> np.ndarray:
    """把 mask 规整为与图像同尺寸的布尔数组。"""

    arr = np.asarray(mask, dtype=bool)
    if arr.shape != expected_shape:
        raise ValueError(f"mask shape {arr.shape} does not match image shape {expected_shape}")
    return arr


def _to_gray(image_array: np.ndarray) -> np.ndarray:
    """将 RGB 图像转换为 `[0, 1]` 灰度图。"""

    rgb = image_array[:, :, :3]
    gray = 0.2989 * rgb[:, :, 0] + 0.5870 * rgb[:, :, 1] + 0.1140 * rgb[:, :, 2]
    max_value = float(np.max(gray)) if gray.size else 1.0
    if max_value <= 0:
        return np.zeros_like(gray, dtype=np.float32)
    return (gray / max_value).astype(np.float32)


def _extract_lf_vector(gray: np.ndarray, mask: np.ndarray, grid_size: int) -> np.ndarray:
    """从 `mask_false` 低频区域提取块均值向量。"""

    lf_region = np.logical_not(mask)
    return _block_mean_vector(gray, lf_region, grid_size)


def _extract_hf_vector(gray: np.ndarray, mask: np.ndarray, grid_size: int) -> np.ndarray:
    """从 `mask_true` 高频区域提取梯度能量块向量。"""

    gradient = _compute_gradient_energy(gray)
    return _block_mean_vector(gradient, mask, grid_size)


def _block_mean_vector(values: np.ndarray, region: np.ndarray, grid_size: int) -> np.ndarray:
    """按固定网格计算区域加权块均值。"""

    height, width = values.shape
    row_edges = np.linspace(0, height, grid_size + 1, dtype=np.int64)
    col_edges = np.linspace(0, width, grid_size + 1, dtype=np.int64)
    features: list[float] = []
    for row in range(grid_size):
        for col in range(grid_size):
            block_values = values[row_edges[row] : row_edges[row + 1], col_edges[col] : col_edges[col + 1]]
            block_region = region[row_edges[row] : row_edges[row + 1], col_edges[col] : col_edges[col + 1]]
            if block_values.size == 0 or not np.any(block_region):
                features.append(0.0)
            else:
                features.append(float(np.mean(block_values[block_region])))
    return np.asarray(features, dtype=np.float32)


def _compute_gradient_energy(gray: np.ndarray) -> np.ndarray:
    """计算灰度梯度能量。"""

    gx = np.zeros_like(gray, dtype=np.float32)
    gy = np.zeros_like(gray, dtype=np.float32)
    gx[:, 1:] = np.abs(gray[:, 1:] - gray[:, :-1])
    gy[1:, :] = np.abs(gray[1:, :] - gray[:-1, :])
    energy = np.sqrt(gx * gx + gy * gy)
    max_value = float(np.max(energy)) if energy.size else 1.0
    if max_value <= 0:
        return np.zeros_like(energy, dtype=np.float32)
    return (energy / max_value).astype(np.float32)


def _derive_channel_challenge(channel: str, length: int, request: ContentChainRequest) -> np.ndarray:
    """根据 prompt、mask 和配置派生确定性内容链 challenge。"""

    seed_payload = {
        "content_chain_version": CONTENT_CHAIN_VERSION,
        "channel": channel,
        "length": int(length),
        "prompt_context": request.prompt_context.to_record(),
        "mask_digest": request.semantic_mask.mask_digest,
        "routing_digest": request.semantic_mask.routing_digest,
        "config": dict(request.config),
    }
    seed = int(build_stable_digest(seed_payload)[:16], 16)
    rng = np.random.default_rng(seed)
    challenge = rng.standard_normal(length).astype(np.float32)
    norm = float(np.linalg.norm(challenge))
    if norm <= 1e-12:
        return np.ones(length, dtype=np.float32)
    return (challenge / norm).astype(np.float32)


def _bounded_cosine_score(vector: np.ndarray, challenge: np.ndarray) -> float:
    """计算 `[0, 1]` 有界余弦分数。"""

    vec = np.asarray(vector, dtype=np.float32)
    ref = np.asarray(challenge, dtype=np.float32)
    if vec.shape != ref.shape:
        raise ValueError("vector and challenge shape mismatch")
    vec_norm = float(np.linalg.norm(vec))
    ref_norm = float(np.linalg.norm(ref))
    if vec_norm <= 1e-12 or ref_norm <= 1e-12:
        return 0.0
    cosine = float(np.dot(vec, ref) / (vec_norm * ref_norm))
    return max(0.0, min(1.0, 0.5 + 0.5 * cosine))


def _normalize_weights(lf_weight: float, hf_weight: float) -> tuple[float, float]:
    """归一化 LF/HF 权重。"""

    total = float(lf_weight + hf_weight)
    return float(lf_weight / total), float(hf_weight / total)


def _build_channel_statistics(
    channel: str,
    vector: np.ndarray,
    score: float,
    request: ContentChainRequest,
    mask_digest: str,
) -> dict[str, Any]:
    """构造单个内容链分支的统计摘要。"""

    return {
        "channel": channel,
        "content_chain_version": CONTENT_CHAIN_VERSION,
        "vector_length": int(vector.shape[0]),
        "vector_mean": round(float(np.mean(vector)), 8) if vector.size else 0.0,
        "vector_std": round(float(np.std(vector)), 8) if vector.size else 0.0,
        "vector_norm": round(float(np.linalg.norm(vector)), 8),
        "nonzero_count": int(np.count_nonzero(vector)),
        "score": round(float(score), 8),
        "mask_digest": mask_digest,
        "prompt_id": request.prompt_context.prompt_id,
        "image_id": request.prompt_context.image_id,
    }


def _round_vector(vector: np.ndarray) -> list[float]:
    """把向量转换为稳定 JSON 数值列表。"""

    return [round(float(value), 8) for value in vector.astype(np.float32).tolist()]
