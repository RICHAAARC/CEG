"""CEG 内部语义掩码与显著性路由原语。

该模块提供真实图像驱动的 mask 计算能力, 不依赖 CEG-WM 运行时, 也不包含 notebook、
Google Drive 打包或 harness 门禁逻辑。它的职责是把输入图像转换为稳定的二值 mask、
统计量、空间绑定和 digest, 为后续 LF/HF 内容链、几何恢复和 attestation 提供可复用的
方法原语。

当前实现包含两类 backend:
1. `gradient_saliency`: 通用工程写法, 直接根据图像灰度梯度生成显著区域, 可在无 GPU 环境运行。
2. `inspyrenet`: 项目特定的真实模型入口, 当运行环境安装了 `transparent_background` 并具备权重时,
   会调用其 InSPyReNet 推理输出 alpha / saliency map。

注意: 单独的 mask 原语不是完整 CEG 论文主方法。只有在内容链、几何恢复和 attestation 均接入后,
完整 backend 才能声明 `paper_main_method_ready = True`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from main.core.digest import build_stable_digest


GRADIENT_SALIENCY_BACKEND_ID = "ceg_gradient_saliency_mask"
INSPYRENET_BACKEND_ID = "ceg_inspyrenet_semantic_mask"
SEMANTIC_MASK_BACKEND_ROLE = "semantic_mask_and_lf_hf_routing_primitive"
MASK_SUMMARY_VERSION = "ceg_semantic_mask_v1"
ROUTING_SUMMARY_VERSION = "ceg_mask_routing_v1"


@dataclass(frozen=True)
class SemanticMaskRequest:
    """描述一次 mask 提取请求。

    该结构属于通用工程写法: 它把图像路径、backend 选择、阈值和形态学参数集中保存,
    避免后续 embedding、detection 或实验脚本重复解析松散字典。
    """

    image_path: Path
    output_mask_path: Path | None = None
    backend_id: str = GRADIENT_SALIENCY_BACKEND_ID
    threshold_quantile: float = 0.80
    open_iters: int = 1
    close_iters: int = 1
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticMaskResult:
    """描述 mask 提取结果及其可追溯信息。

    `paper_main_method_ready` 保持为 False, 因为该模块只是正式 CEG 水印机制中的一个原语,
    不能单独支撑顶会论文主结果中的最终检测结论。
    """

    mask: np.ndarray
    saliency_map: np.ndarray
    backend_id: str
    backend_role: str
    mask_digest: str
    routing_digest: str
    mask_stats: Mapping[str, Any]
    resolution_binding: Mapping[str, Any]
    mask_path: str | None = None
    paper_main_method_ready: bool = False

    def to_record(self) -> dict[str, Any]:
        """转换为 manifest 或 detection record 可消费的普通字典。"""

        return {
            "backend_id": self.backend_id,
            "backend_role": self.backend_role,
            "mask_digest": self.mask_digest,
            "routing_digest": self.routing_digest,
            "mask_stats": dict(self.mask_stats),
            "resolution_binding": dict(self.resolution_binding),
            "mask_path": self.mask_path,
            "paper_main_method_ready": self.paper_main_method_ready,
            "paper_main_method_blocking_reason": "semantic_mask_is_only_one_ceg_method_primitive",
        }


def extract_semantic_mask(request: SemanticMaskRequest) -> SemanticMaskResult:
    """根据请求提取语义或显著性 mask。

    该函数是本模块的主入口。`gradient_saliency` 路径始终基于真实图像像素计算, 不是 mock。
    `inspyrenet` 路径会在依赖可用时调用真实模型入口; 如果依赖不可用则显式报错, 不进行静默降级。
    """

    _validate_request(request)
    if request.backend_id == GRADIENT_SALIENCY_BACKEND_ID:
        mask, saliency_map, source_metadata = build_gradient_saliency_mask(request)
    elif request.backend_id == INSPYRENET_BACKEND_ID:
        mask, saliency_map, source_metadata = build_inspyrenet_semantic_mask(request)
    else:
        raise ValueError(f"unsupported semantic mask backend_id: {request.backend_id}")

    image_array = _load_rgb_array(request.image_path)
    resolution_binding = _build_resolution_binding(image_array)
    mask_stats = _build_mask_stats(mask, saliency_map, request, source_metadata)
    mask_digest = compute_mask_digest(mask, mask_stats, resolution_binding, request)
    routing_digest = compute_routing_digest(mask_stats)
    mask_path = _write_mask_image(mask, request.output_mask_path)
    return SemanticMaskResult(
        mask=mask.astype(bool),
        saliency_map=saliency_map.astype(np.float32),
        backend_id=request.backend_id,
        backend_role=SEMANTIC_MASK_BACKEND_ROLE,
        mask_digest=mask_digest,
        routing_digest=routing_digest,
        mask_stats=mask_stats,
        resolution_binding=resolution_binding,
        mask_path=mask_path,
        paper_main_method_ready=False,
    )


def build_gradient_saliency_mask(request: SemanticMaskRequest) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """使用图像梯度显著性生成确定性 mask。

    该实现属于通用工程写法。它不理解物体类别, 但会真实读取图像像素, 以灰度梯度能量的高分位区域
    作为 LF/HF 路由中的高频候选区域。该能力可用于无模型 dry-run、CPU pilot 和后续 detector 对齐测试。
    """

    image_array = _load_rgb_array(request.image_path)
    gray = _to_gray(image_array)
    saliency_map = _compute_gradient_energy(gray)
    mask = _threshold_saliency(saliency_map, request.threshold_quantile)
    mask = _apply_morphology(mask, request.open_iters, request.close_iters)
    return mask, saliency_map, {"saliency_source": "gradient_energy", "requires_external_model": False}


def build_inspyrenet_semantic_mask(request: SemanticMaskRequest) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """调用 InSPyReNet 兼容入口生成真实语义显著性 mask。

    当前采用 `transparent_background.Remover` 作为 InSPyReNet 常见封装入口。该依赖不存在时会显式失败,
    以避免正式实验在用户没有模型环境的情况下误用 proxy 结果。
    """

    try:
        from PIL import Image
        from transparent_background import Remover  # type: ignore
    except ImportError as exc:  # pragma: no cover - 依赖由 GPU / Colab 环境提供
        raise RuntimeError(
            "InSPyReNet backend 需要安装 transparent-background 并准备对应权重。"
        ) from exc

    remover_kwargs = dict(request.config.get("inspyrenet_remover_kwargs", {}))
    process_kwargs = dict(request.config.get("inspyrenet_process_kwargs", {}))
    with Image.open(request.image_path) as image:
        rgb_image = image.convert("RGB")
        remover = Remover(**remover_kwargs)
        raw_output = remover.process(rgb_image, type="map", **process_kwargs)

    saliency_map = _normalize_saliency_array(np.asarray(raw_output, dtype=np.float32))
    mask = _threshold_saliency(saliency_map, request.threshold_quantile)
    mask = _apply_morphology(mask, request.open_iters, request.close_iters)
    return mask, saliency_map, {"saliency_source": "inspyrenet", "requires_external_model": True}


def compute_mask_digest(
    mask: np.ndarray,
    mask_stats: Mapping[str, Any],
    resolution_binding: Mapping[str, Any],
    request: SemanticMaskRequest,
) -> str:
    """计算 mask 摘要, 用于绑定空间结构、配置和统计量。"""

    row_sum = mask.astype(np.uint8).sum(axis=1).astype(int).tolist()
    col_sum = mask.astype(np.uint8).sum(axis=0).astype(int).tolist()
    payload = {
        "summary_version": MASK_SUMMARY_VERSION,
        "backend_id": request.backend_id,
        "threshold_quantile": request.threshold_quantile,
        "open_iters": request.open_iters,
        "close_iters": request.close_iters,
        "mask_shape": [int(v) for v in mask.shape],
        "mask_population": int(mask.sum()),
        "row_projection_digest": build_stable_digest({"row_sum": row_sum}),
        "col_projection_digest": build_stable_digest({"col_sum": col_sum}),
        "mask_stats": dict(mask_stats),
        "resolution_binding": dict(resolution_binding),
    }
    return build_stable_digest(payload)


def compute_routing_digest(mask_stats: Mapping[str, Any]) -> str:
    """计算 LF/HF 路由摘要。"""

    area_ratio = float(mask_stats.get("area_ratio", 0.0))
    payload = {
        "routing_version": ROUTING_SUMMARY_VERSION,
        "hf_region_ratio": round(area_ratio, 8),
        "lf_region_ratio": round(1.0 - area_ratio, 8),
        "connected_components": int(mask_stats.get("connected_components", 0)),
        "largest_component_ratio": float(mask_stats.get("largest_component_ratio", 0.0)),
        "perimeter_to_area_ratio": float(mask_stats.get("perimeter_to_area_ratio", 0.0)),
        "downsample_grid_shape": mask_stats.get("downsample_grid_shape", [8, 8]),
        "downsample_grid_true_indices": mask_stats.get("downsample_grid_true_indices", []),
        "downsample_grid_digest": mask_stats.get("downsample_grid_digest", "<absent>"),
        "mask_to_band_mapping": {"mask_true": "hf", "mask_false": "lf"},
    }
    return build_stable_digest(payload)


def _validate_request(request: SemanticMaskRequest) -> None:
    """校验 mask 请求, 使错误在方法入口处显式暴露。"""

    if not request.image_path.is_file():
        raise FileNotFoundError(f"image_path not found: {request.image_path}")
    if not 0.0 < float(request.threshold_quantile) < 1.0:
        raise ValueError("threshold_quantile must be in (0, 1)")
    if request.open_iters < 0 or request.close_iters < 0:
        raise ValueError("open_iters and close_iters must be >= 0")


def _load_rgb_array(image_path: Path) -> np.ndarray:
    """读取图像并转换为 RGB HWC 数组。"""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境依赖决定
        raise RuntimeError("semantic mask 需要安装 Pillow。") from exc
    with Image.open(image_path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32)


def _to_gray(image_array: np.ndarray) -> np.ndarray:
    """将 RGB 图像转换为归一化灰度图。"""

    rgb = image_array[:, :, :3]
    gray = 0.2989 * rgb[:, :, 0] + 0.5870 * rgb[:, :, 1] + 0.1140 * rgb[:, :, 2]
    max_value = float(np.max(gray)) if gray.size else 1.0
    if max_value <= 0.0:
        return np.zeros_like(gray, dtype=np.float32)
    return (gray / max_value).astype(np.float32)


def _compute_gradient_energy(gray: np.ndarray) -> np.ndarray:
    """计算灰度图的梯度能量。"""

    gx = np.zeros_like(gray, dtype=np.float32)
    gy = np.zeros_like(gray, dtype=np.float32)
    gx[:, 1:] = np.abs(gray[:, 1:] - gray[:, :-1])
    gy[1:, :] = np.abs(gray[1:, :] - gray[:-1, :])
    energy = np.sqrt(gx * gx + gy * gy)
    return _normalize_saliency_array(energy)


def _normalize_saliency_array(array: np.ndarray) -> np.ndarray:
    """把任意 saliency 输出归一化到 `[0, 1]`。"""

    if array.ndim == 3:
        array = array[:, :, 0]
    if array.ndim != 2:
        raise ValueError("saliency map must be 2-D or single-channel image")
    arr = array.astype(np.float32)
    min_value = float(np.min(arr)) if arr.size else 0.0
    max_value = float(np.max(arr)) if arr.size else 1.0
    if max_value <= min_value:
        return np.zeros_like(arr, dtype=np.float32)
    return ((arr - min_value) / (max_value - min_value)).astype(np.float32)


def _threshold_saliency(saliency_map: np.ndarray, threshold_quantile: float) -> np.ndarray:
    """按分位数阈值把 saliency map 转换为二值 mask。

    当图像大部分区域为零梯度时, 分位数阈值可能等于最小值。此时使用严格大于阈值,
    可以避免把整张背景图误判为高显著性区域。
    """

    threshold = float(np.quantile(saliency_map.reshape(-1), threshold_quantile))
    min_value = float(np.min(saliency_map)) if saliency_map.size else 0.0
    max_value = float(np.max(saliency_map)) if saliency_map.size else 0.0
    if max_value > min_value and threshold <= min_value:
        return saliency_map > threshold
    return saliency_map >= threshold


def _apply_morphology(mask: np.ndarray, open_iters: int, close_iters: int) -> np.ndarray:
    """执行轻量开闭运算, 降低孤立噪声对 digest 和路由的影响。"""

    result = mask.astype(bool)
    for _ in range(open_iters):
        result = _binary_dilate(_binary_erode(result))
    for _ in range(close_iters):
        result = _binary_erode(_binary_dilate(result))
    return result.astype(bool)


def _binary_dilate(mask: np.ndarray) -> np.ndarray:
    """执行 3x3 二值膨胀。"""

    padded = np.pad(mask.astype(np.uint8), 1, mode="edge")
    acc = np.zeros_like(mask, dtype=np.uint8)
    for di in range(3):
        for dj in range(3):
            acc = np.maximum(acc, padded[di : di + mask.shape[0], dj : dj + mask.shape[1]])
    return acc > 0


def _binary_erode(mask: np.ndarray) -> np.ndarray:
    """执行 3x3 二值腐蚀。"""

    padded = np.pad(mask.astype(np.uint8), 1, mode="edge")
    acc = np.ones_like(mask, dtype=np.uint8)
    for di in range(3):
        for dj in range(3):
            acc = np.minimum(acc, padded[di : di + mask.shape[0], dj : dj + mask.shape[1]])
    return acc > 0


def _build_mask_stats(
    mask: np.ndarray,
    saliency_map: np.ndarray,
    request: SemanticMaskRequest,
    source_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """构造 mask 统计量, 供 routing、records 和论文审计复用。"""

    area_ratio = float(np.mean(mask.astype(np.float32))) if mask.size else 0.0
    boundary_length = _mask_boundary_length(mask)
    foreground_count = int(mask.sum())
    perimeter_to_area = float(boundary_length / max(1, foreground_count))
    downsample_grid = _build_downsample_binary_grid(mask, rows=8, cols=8)
    true_indices = np.flatnonzero(downsample_grid.reshape(-1)).astype(int).tolist()
    saliency_threshold = float(np.quantile(saliency_map.reshape(-1), request.threshold_quantile))
    return {
        "area_ratio": round(area_ratio, 8),
        "foreground_coverage_ratio": round(area_ratio, 8),
        "connected_components": _count_connected_components(mask),
        "largest_component_ratio": round(_largest_component_ratio(mask), 8),
        "boundary_length": int(boundary_length),
        "perimeter_to_area_ratio": round(perimeter_to_area, 8),
        "downsample_grid_shape": [8, 8],
        "downsample_grid_true_indices": true_indices,
        "downsample_grid_digest": build_stable_digest({"grid": downsample_grid.astype(int).tolist()}),
        "saliency_threshold": round(saliency_threshold, 8),
        "saliency_mean": round(float(np.mean(saliency_map)), 8),
        "saliency_std": round(float(np.std(saliency_map)), 8),
        "saliency_source": source_metadata.get("saliency_source"),
        "requires_external_model": bool(source_metadata.get("requires_external_model", False)),
    }


def _build_resolution_binding(image_array: np.ndarray) -> dict[str, Any]:
    """绑定 mask 与原始图像空间的分辨率关系。"""

    height, width, channels = image_array.shape
    return {
        "space": "image_space",
        "height": int(height),
        "width": int(width),
        "channels": int(channels),
        "aspect_ratio": round(float(width) / float(height), 8) if height else 1.0,
        "resize_rule": "identity",
        "binding_version": "v1",
    }


def _write_mask_image(mask: np.ndarray, output_mask_path: Path | None) -> str | None:
    """按需写出二值 mask 图像。"""

    if output_mask_path is None:
        return None
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境依赖决定
        raise RuntimeError("写出 semantic mask 需要安装 Pillow。") from exc
    output_mask_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    image.save(output_mask_path)
    return output_mask_path.as_posix()


def _count_connected_components(mask: np.ndarray) -> int:
    """统计 4 邻接前景连通域数量。"""

    if mask.size == 0:
        return 0
    visited = np.zeros(mask.shape, dtype=bool)
    component_count = 0
    height, width = mask.shape
    for row in range(height):
        for col in range(width):
            if not mask[row, col] or visited[row, col]:
                continue
            component_count += 1
            stack = [(row, col)]
            visited[row, col] = True
            while stack:
                cur_row, cur_col = stack.pop()
                for next_row, next_col in (
                    (cur_row - 1, cur_col),
                    (cur_row + 1, cur_col),
                    (cur_row, cur_col - 1),
                    (cur_row, cur_col + 1),
                ):
                    if next_row < 0 or next_row >= height or next_col < 0 or next_col >= width:
                        continue
                    if visited[next_row, next_col] or not mask[next_row, next_col]:
                        continue
                    visited[next_row, next_col] = True
                    stack.append((next_row, next_col))
    return component_count


def _largest_component_ratio(mask: np.ndarray) -> float:
    """计算最大连通域占全部前景像素的比例。"""

    total = int(mask.sum())
    if total <= 0:
        return 0.0
    visited = np.zeros(mask.shape, dtype=bool)
    height, width = mask.shape
    max_count = 0
    for row in range(height):
        for col in range(width):
            if not mask[row, col] or visited[row, col]:
                continue
            count = 0
            stack = [(row, col)]
            visited[row, col] = True
            while stack:
                cur_row, cur_col = stack.pop()
                count += 1
                for next_row, next_col in (
                    (cur_row - 1, cur_col),
                    (cur_row + 1, cur_col),
                    (cur_row, cur_col - 1),
                    (cur_row, cur_col + 1),
                ):
                    if next_row < 0 or next_row >= height or next_col < 0 or next_col >= width:
                        continue
                    if visited[next_row, next_col] or not mask[next_row, next_col]:
                        continue
                    visited[next_row, next_col] = True
                    stack.append((next_row, next_col))
            max_count = max(max_count, count)
    return float(max_count / total)


def _mask_boundary_length(mask: np.ndarray) -> int:
    """估计前景与背景之间的边界长度。"""

    boundary = 0
    height, width = mask.shape
    for row in range(height):
        for col in range(width):
            if not mask[row, col]:
                continue
            for next_row, next_col in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if next_row < 0 or next_row >= height or next_col < 0 or next_col >= width or not mask[next_row, next_col]:
                    boundary += 1
    return int(boundary)


def _build_downsample_binary_grid(mask: np.ndarray, rows: int, cols: int) -> np.ndarray:
    """构造低分辨率二值网格, 用于稳定表达 mask 空间结构。"""

    height, width = mask.shape
    row_edges = np.linspace(0, height, rows + 1, dtype=np.int64)
    col_edges = np.linspace(0, width, cols + 1, dtype=np.int64)
    grid = np.zeros((rows, cols), dtype=bool)
    for row in range(rows):
        for col in range(cols):
            block = mask[row_edges[row] : row_edges[row + 1], col_edges[col] : col_edges[col + 1]]
            grid[row, col] = bool(block.size and np.mean(block.astype(np.float32)) >= 0.5)
    return grid
