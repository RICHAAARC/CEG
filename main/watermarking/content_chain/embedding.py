"""CEG 内容链水印嵌入原语。

该模块把 semantic mask 的 LF/HF 空间路由用于真实图像像素改写, 使检测侧
`content_chain.scoring` 产生的 LF/HF evidence 有对应的 embedding 侧来源。
它不包含 notebook、Colab、Google Drive 打包、harness 门禁或 CEG-WM 运行时依赖。

当前实现是轻量图像域原语:
1. `mask_false -> lf`: 按低分辨率网格对低显著性区域施加平滑亮度偏移。
2. `mask_true -> hf`: 对高显著性区域施加由 prompt、mask 和配置绑定的细粒度符号扰动。
3. 输出 embedding digest、LF/HF trace digest 和可写入 manifest 的 provenance。

该模块执行真实像素改写, 但仍不是完整论文主方法。完整 CEG 方法还需要几何恢复、
attestation 绑定和固定 FPR detection records 闭环后, 才能声明 `paper_main_method_ready = True`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from main.core.digest import build_stable_digest
from main.watermarking.content_chain.scoring import CONTENT_CHAIN_VERSION
from main.watermarking.interfaces import WatermarkPromptContext
from main.watermarking.semantic_mask import SemanticMaskResult


CONTENT_CHAIN_EMBEDDING_BACKEND_ID = "ceg_mask_routed_content_chain_embedding"
CONTENT_CHAIN_EMBEDDING_BACKEND_ROLE = "lf_hf_content_embedding_primitive"
CONTENT_CHAIN_EMBEDDING_VERSION = "ceg_content_chain_embedding_v1"


@dataclass(frozen=True)
class ContentChainEmbeddingRequest:
    """描述一次内容链水印嵌入请求。

    该结构属于通用工程写法: 它把 clean 图像、watermarked 输出、semantic mask、prompt 上下文和
    LF/HF 强度参数固定到一个入口, 使 Colab 或 CLI 只负责调度, 不直接手写方法逻辑。
    """

    clean_image_path: Path
    watermarked_image_path: Path
    semantic_mask: SemanticMaskResult
    prompt_context: WatermarkPromptContext
    lf_grid_size: int = 8
    lf_strength: float = 3.0
    hf_strength: float = 2.0
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContentChainEmbeddingResult:
    """描述内容链嵌入输出和 provenance。"""

    watermarked_image_path: Path
    embedding_digest: str
    lf_embedding_trace_digest: str
    hf_embedding_trace_digest: str
    changed_pixel_count: int
    changed_channel_count: int
    lf_modified_pixel_count: int
    hf_modified_pixel_count: int
    diagnostics: Mapping[str, Any]
    backend_id: str = CONTENT_CHAIN_EMBEDDING_BACKEND_ID
    backend_role: str = CONTENT_CHAIN_EMBEDDING_BACKEND_ROLE
    paper_main_method_ready: bool = False

    def to_record(self) -> dict[str, Any]:
        """转换为 image generation manifest 可消费的普通字典。"""

        return {
            "watermarked_image_path": self.watermarked_image_path.as_posix(),
            "embedding_digest": self.embedding_digest,
            "lf_embedding_trace_digest": self.lf_embedding_trace_digest,
            "hf_embedding_trace_digest": self.hf_embedding_trace_digest,
            "changed_pixel_count": self.changed_pixel_count,
            "changed_channel_count": self.changed_channel_count,
            "lf_modified_pixel_count": self.lf_modified_pixel_count,
            "hf_modified_pixel_count": self.hf_modified_pixel_count,
            "diagnostics": dict(self.diagnostics),
            "backend_id": self.backend_id,
            "backend_role": self.backend_role,
            "paper_main_method_ready": self.paper_main_method_ready,
            "paper_main_method_blocking_reason": "embedding_lacks_geometry_recovery_and_attestation_closure",
        }


def embed_content_chain_watermark(request: ContentChainEmbeddingRequest) -> ContentChainEmbeddingResult:
    """在 clean 图像中嵌入 mask 路由的 LF/HF 内容链水印。"""

    _validate_request(request)
    image_array = _load_rgb_array(request.clean_image_path)
    mask = _coerce_mask(request.semantic_mask.mask, image_array.shape[:2])
    before = image_array.copy()

    lf_delta, lf_evidence = _build_lf_delta(image_array, mask, request)
    after_lf = np.clip(image_array + lf_delta, 0.0, 255.0)
    hf_delta, hf_evidence = _build_hf_delta(after_lf, mask, request)
    watermarked = np.clip(after_lf + hf_delta, 0.0, 255.0).round().astype(np.uint8)

    changed_channels = np.any(watermarked.astype(np.int16) != before.round().astype(np.uint8).astype(np.int16), axis=2)
    changed_channel_count = int(np.count_nonzero(watermarked.astype(np.int16) != before.round().astype(np.uint8).astype(np.int16)))
    changed_pixel_count = int(np.count_nonzero(changed_channels))
    _write_rgb_image(watermarked, request.watermarked_image_path)

    lf_embedding_trace_digest = build_stable_digest(lf_evidence)
    hf_embedding_trace_digest = build_stable_digest(hf_evidence)
    diagnostics = {
        "content_chain_embedding_version": CONTENT_CHAIN_EMBEDDING_VERSION,
        "content_chain_version": CONTENT_CHAIN_VERSION,
        "prompt_context": request.prompt_context.to_record(),
        "mask_digest": request.semantic_mask.mask_digest,
        "routing_digest": request.semantic_mask.routing_digest,
        "lf_evidence": lf_evidence,
        "hf_evidence": hf_evidence,
    }
    embedding_digest = build_stable_digest(
        {
            "embedding_version": CONTENT_CHAIN_EMBEDDING_VERSION,
            "lf_embedding_trace_digest": lf_embedding_trace_digest,
            "hf_embedding_trace_digest": hf_embedding_trace_digest,
            "changed_pixel_count": changed_pixel_count,
            "changed_channel_count": changed_channel_count,
            "mask_digest": request.semantic_mask.mask_digest,
            "routing_digest": request.semantic_mask.routing_digest,
        }
    )
    return ContentChainEmbeddingResult(
        watermarked_image_path=request.watermarked_image_path,
        embedding_digest=embedding_digest,
        lf_embedding_trace_digest=lf_embedding_trace_digest,
        hf_embedding_trace_digest=hf_embedding_trace_digest,
        changed_pixel_count=changed_pixel_count,
        changed_channel_count=changed_channel_count,
        lf_modified_pixel_count=int(lf_evidence["modified_pixel_count"]),
        hf_modified_pixel_count=int(hf_evidence["modified_pixel_count"]),
        diagnostics=diagnostics,
        paper_main_method_ready=False,
    )


def _validate_request(request: ContentChainEmbeddingRequest) -> None:
    """校验嵌入请求。"""

    if not request.clean_image_path.is_file():
        raise FileNotFoundError(f"clean_image_path not found: {request.clean_image_path}")
    if request.lf_grid_size <= 0:
        raise ValueError("lf_grid_size must be positive")
    if request.lf_strength < 0 or request.hf_strength < 0:
        raise ValueError("lf_strength and hf_strength must be non-negative")


def _load_rgb_array(image_path: Path) -> np.ndarray:
    """读取 RGB 图像为 float32 数组。"""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境决定
        raise RuntimeError("content chain embedding 需要安装 Pillow。") from exc
    with Image.open(image_path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32)


def _write_rgb_image(image_array: np.ndarray, path: Path) -> None:
    """写出 RGB 图像。"""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境决定
        raise RuntimeError("写出 content chain watermarked 图像需要安装 Pillow。") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image_array.astype(np.uint8), mode="RGB").save(path)


def _coerce_mask(mask: np.ndarray, expected_shape: tuple[int, int]) -> np.ndarray:
    """把 mask 规整为图像尺寸一致的布尔数组。"""

    arr = np.asarray(mask, dtype=bool)
    if arr.shape != expected_shape:
        raise ValueError(f"mask shape {arr.shape} does not match image shape {expected_shape}")
    return arr


def _build_lf_delta(
    image_array: np.ndarray,
    mask: np.ndarray,
    request: ContentChainEmbeddingRequest,
) -> tuple[np.ndarray, dict[str, Any]]:
    """构造低频区域的平滑亮度偏移。"""

    delta = np.zeros_like(image_array, dtype=np.float32)
    lf_region = np.logical_not(mask)
    challenge_grid = _derive_grid_challenge("lf", request.lf_grid_size, request)
    height, width = mask.shape
    row_edges = np.linspace(0, height, request.lf_grid_size + 1, dtype=np.int64)
    col_edges = np.linspace(0, width, request.lf_grid_size + 1, dtype=np.int64)
    modified_pixels = 0
    for row in range(request.lf_grid_size):
        for col in range(request.lf_grid_size):
            region = lf_region[row_edges[row] : row_edges[row + 1], col_edges[col] : col_edges[col + 1]]
            if not np.any(region):
                continue
            value = float(challenge_grid[row, col]) * float(request.lf_strength)
            block_delta = delta[row_edges[row] : row_edges[row + 1], col_edges[col] : col_edges[col + 1], :]
            block_delta[region, :] += value
            modified_pixels += int(np.count_nonzero(region))
    evidence = {
        "channel": "lf",
        "embedding_version": CONTENT_CHAIN_EMBEDDING_VERSION,
        "grid_size": int(request.lf_grid_size),
        "strength": float(request.lf_strength),
        "modified_pixel_count": int(modified_pixels),
        "challenge_grid_digest": build_stable_digest({"grid": _round_array(challenge_grid)}),
        "mask_digest": request.semantic_mask.mask_digest,
    }
    return delta, evidence


def _build_hf_delta(
    image_array: np.ndarray,
    mask: np.ndarray,
    request: ContentChainEmbeddingRequest,
) -> tuple[np.ndarray, dict[str, Any]]:
    """构造高频区域的细粒度符号扰动。"""

    delta = np.zeros_like(image_array, dtype=np.float32)
    if not np.any(mask) or request.hf_strength <= 0:
        return delta, {
            "channel": "hf",
            "embedding_version": CONTENT_CHAIN_EMBEDDING_VERSION,
            "strength": float(request.hf_strength),
            "modified_pixel_count": 0,
            "pattern_digest": build_stable_digest({"pattern": []}),
            "mask_digest": request.semantic_mask.mask_digest,
        }
    signs = _derive_pixel_signs(mask.shape, request)
    signed_delta = signs.astype(np.float32) * float(request.hf_strength)
    # 高频分支只写入 mask_true 区域, 并使用互补通道符号降低整体亮度漂移。
    delta[:, :, 0][mask] += signed_delta[mask]
    delta[:, :, 1][mask] -= signed_delta[mask]
    delta[:, :, 2][mask] += signed_delta[mask]
    evidence = {
        "channel": "hf",
        "embedding_version": CONTENT_CHAIN_EMBEDDING_VERSION,
        "strength": float(request.hf_strength),
        "modified_pixel_count": int(np.count_nonzero(mask)),
        "pattern_digest": build_stable_digest({"sign_row_sum": signs.astype(np.int32).sum(axis=1).astype(int).tolist()}),
        "mask_digest": request.semantic_mask.mask_digest,
    }
    return delta, evidence


def _derive_grid_challenge(channel: str, grid_size: int, request: ContentChainEmbeddingRequest) -> np.ndarray:
    """派生 LF 网格 challenge。"""

    seed = _derive_seed(channel, request, {"grid_size": grid_size})
    rng = np.random.default_rng(seed)
    challenge = rng.choice(np.array([-1.0, 1.0], dtype=np.float32), size=(grid_size, grid_size))
    return challenge.astype(np.float32)


def _derive_pixel_signs(shape: tuple[int, int], request: ContentChainEmbeddingRequest) -> np.ndarray:
    """派生 HF 像素符号图。"""

    seed = _derive_seed("hf", request, {"height": int(shape[0]), "width": int(shape[1])})
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1, 1], dtype=np.int8), size=shape)
    return signs


def _derive_seed(channel: str, request: ContentChainEmbeddingRequest, extra: Mapping[str, Any]) -> int:
    """从 prompt、mask、配置和通道名派生稳定随机种子。"""

    payload = {
        "embedding_version": CONTENT_CHAIN_EMBEDDING_VERSION,
        "channel": channel,
        "prompt_context": request.prompt_context.to_record(),
        "mask_digest": request.semantic_mask.mask_digest,
        "routing_digest": request.semantic_mask.routing_digest,
        "config": dict(request.config),
        "extra": dict(extra),
    }
    return int(build_stable_digest(payload)[:16], 16)


def _round_array(array: np.ndarray) -> list[list[float]]:
    """把二维数组转换为稳定 JSON 数值网格。"""

    return [[round(float(value), 8) for value in row] for row in array.astype(np.float32).tolist()]
