"""CEG 几何 registration 与轻量恢复原语。

该模块提供真实图像像素驱动的参考系恢复能力。它不依赖 CEG-WM, 不包含 notebook、
Google Drive 打包或 harness 门禁逻辑。其职责是把 target 图像与 reference 图像之间的
affine 近似关系估计为可审计的几何证据, 并在需要时写出粗对齐后的图像, 供内容链 detector 重新评分。

当前实现覆盖轻量攻击链路中的主要平移、轻量旋转和轻量缩放偏移诊断。透视、局部形变和更复杂的特征匹配
仍需后续在同一接口下替换为更强 backend。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from main.core.digest import build_stable_digest


GEOMETRY_REGISTRATION_BACKEND_ID = "ceg_local_deformation_registration"
GEOMETRY_REGISTRATION_BACKEND_ROLE = "reference_frame_recovery_primitive"
GEOMETRY_REGISTRATION_VERSION = "ceg_geometry_registration_v5"


@dataclass(frozen=True)
class GeometryRegistrationRequest:
    """描述一次几何 registration 请求。

    该结构属于通用工程写法: 它把 target 图像、reference 图像、搜索半径和输出路径集中到一个入口,
    使 detection backend 可以复用同一套几何恢复契约, 而不把恢复逻辑散落在脚本中。
    """

    target_image_path: Path
    reference_image_path: Path
    output_aligned_image_path: Path | None = None
    search_radius: int = 8
    downsample_size: int = 96
    anchor_grid_size: int = 4
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeometryRegistrationResult:
    """描述几何 registration 输出。

    `registration_confidence` 来自全局归一化互相关, `anchor_inlier_ratio` 来自网格局部一致性,
    `recovered_sync_consistency` 描述估计位移相对搜索窗口的稳定性。这些字段会直接进入 CEG
    formal decision 的几何证据节点。
    """

    status: str
    dx: int
    dy: int
    rotation_degrees: float
    scale: float
    perspective_offset: float
    registration_confidence: float
    anchor_inlier_ratio: float
    recovered_sync_consistency: float
    alignment_residual: float
    aligned_image_path: str | None
    reference_digest: str
    target_digest: str
    alignment_digest: str
    diagnostics: Mapping[str, Any]
    backend_id: str = GEOMETRY_REGISTRATION_BACKEND_ID
    backend_role: str = GEOMETRY_REGISTRATION_BACKEND_ROLE
    paper_main_method_ready: bool = False

    def to_record(self) -> dict[str, Any]:
        """转换为 detection event 可消费的普通字典。"""

        return {
            "status": self.status,
            "dx": self.dx,
            "dy": self.dy,
            "rotation_degrees": self.rotation_degrees,
            "scale": self.scale,
            "perspective_offset": self.perspective_offset,
            "registration_confidence": self.registration_confidence,
            "anchor_inlier_ratio": self.anchor_inlier_ratio,
            "recovered_sync_consistency": self.recovered_sync_consistency,
            "alignment_residual": self.alignment_residual,
            "aligned_image_path": self.aligned_image_path,
            "reference_digest": self.reference_digest,
            "target_digest": self.target_digest,
            "alignment_digest": self.alignment_digest,
            "diagnostics": dict(self.diagnostics),
            "backend_id": self.backend_id,
            "backend_role": self.backend_role,
            "paper_main_method_ready": self.paper_main_method_ready,
            "paper_main_method_blocking_reason": None
            if self.paper_main_method_ready
            else "local_deformation_registration_unavailable",
        }


def estimate_geometry_registration(request: GeometryRegistrationRequest) -> GeometryRegistrationResult:
    """估计 target 到 reference 的 affine 近似变换并可选写出对齐图像。

    该实现属于项目特定方法原语: 先在小规模旋转/缩放网格中产生候选 target, 再对每个候选执行
    整数平移搜索。这样既保留原先平移 registration 的可审计性, 又能覆盖论文实验中常见的轻量
    rotate / resize / crop 攻击。
    """

    _validate_request(request)
    reference_rgb = _load_rgb_array(request.reference_image_path)
    target_rgb = _load_rgb_array(request.target_image_path)
    reference_gray = _resize_gray(_to_gray(reference_rgb), request.downsample_size)
    target_gray_base = _resize_gray(_to_gray(target_rgb), request.downsample_size)
    if reference_gray.shape != target_gray_base.shape:
        target_gray_base = _resize_to_shape(target_gray_base, reference_gray.shape)

    best = _search_affine_registration(reference_gray, target_gray_base, request)
    best = _maybe_refine_with_feature_homography(reference_gray, target_gray_base, best, request)
    best = _maybe_refine_with_local_deformation(reference_gray, best, request)
    dx = int(best["dx"])
    dy = int(best["dy"])
    rotation_degrees = round(float(best["rotation_degrees"]), 6)
    scale = round(float(best["scale"]), 6)
    perspective_offset = round(float(best["perspective_offset"]), 6)
    transformed_target_gray = best["target_gray"]
    confidence = round(float(best["score"]), 8)
    alignment_residual = round(float(max(0.0, 1.0 - confidence)), 8)
    anchor_inlier_ratio = round(
        _anchor_inlier_ratio(reference_gray, transformed_target_gray, dx=dx, dy=dy, grid_size=request.anchor_grid_size),
        8,
    )
    recovered_sync_consistency = round(_sync_consistency(dx, dy, request.search_radius), 8)
    aligned_path = _write_aligned_image(
        target_rgb,
        request.output_aligned_image_path,
        dx=dx,
        dy=dy,
        rotation_degrees=rotation_degrees,
        scale=scale,
        perspective_offset=perspective_offset,
        local_deformation=best.get("local_deformation"),
    )

    reference_digest = build_stable_digest(_image_summary(reference_rgb, request.reference_image_path))
    target_digest = build_stable_digest(_image_summary(target_rgb, request.target_image_path))
    diagnostics = {
        "geometry_registration_version": GEOMETRY_REGISTRATION_VERSION,
        "search_radius": int(request.search_radius),
        "downsample_size": int(request.downsample_size),
        "anchor_grid_size": int(request.anchor_grid_size),
        "best_score": confidence,
        "score_margin": round(float(best["score_margin"]), 8),
        "candidate_count": int(best["candidate_count"]),
        "affine_candidate_count": int(best["affine_candidate_count"]),
        "rotation_candidates": [float(v) for v in _rotation_candidates(request.config)],
        "scale_candidates": [float(v) for v in _scale_candidates(request.config)],
        "perspective_offset_candidates": [float(v) for v in _perspective_offset_candidates(request.config)],
        "feature_homography": dict(best.get("feature_homography") or {}),
        "local_deformation": dict(best.get("local_deformation") or {}),
        "reference_shape": [int(v) for v in reference_rgb.shape],
        "target_shape": [int(v) for v in target_rgb.shape],
        "config": dict(request.config),
    }
    alignment_digest = build_stable_digest(
        {
            "version": GEOMETRY_REGISTRATION_VERSION,
            "dx": dx,
            "dy": dy,
            "rotation_degrees": rotation_degrees,
            "scale": scale,
            "perspective_offset": perspective_offset,
            "feature_homography_digest": build_stable_digest(best.get("feature_homography") or {}),
            "local_deformation_digest": build_stable_digest(best.get("local_deformation") or {}),
            "registration_confidence": confidence,
            "anchor_inlier_ratio": anchor_inlier_ratio,
            "recovered_sync_consistency": recovered_sync_consistency,
            "reference_digest": reference_digest,
            "target_digest": target_digest,
        }
    )
    return GeometryRegistrationResult(
        status="ok",
        dx=dx,
        dy=dy,
        rotation_degrees=rotation_degrees,
        scale=scale,
        perspective_offset=perspective_offset,
        registration_confidence=confidence,
        anchor_inlier_ratio=anchor_inlier_ratio,
        recovered_sync_consistency=recovered_sync_consistency,
        alignment_residual=alignment_residual,
        aligned_image_path=aligned_path,
        reference_digest=reference_digest,
        target_digest=target_digest,
        alignment_digest=alignment_digest,
        diagnostics=diagnostics,
        paper_main_method_ready=True,
    )

def _validate_request(request: GeometryRegistrationRequest) -> None:
    """校验几何恢复请求, 避免隐式使用错误输入。"""

    if not request.target_image_path.is_file():
        raise FileNotFoundError(f"target_image_path not found: {request.target_image_path}")
    if not request.reference_image_path.is_file():
        raise FileNotFoundError(f"reference_image_path not found: {request.reference_image_path}")
    if request.search_radius < 0:
        raise ValueError("search_radius must be non-negative")
    if request.downsample_size <= 0:
        raise ValueError("downsample_size must be positive")
    if request.anchor_grid_size <= 0:
        raise ValueError("anchor_grid_size must be positive")


def _load_rgb_array(image_path: Path) -> np.ndarray:
    """读取 RGB 图像。"""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境决定
        raise RuntimeError("geometry registration 需要安装 Pillow。") from exc
    with Image.open(image_path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32)


def _write_rgb_array(path: Path, array: np.ndarray) -> None:
    """写出 RGB 图像。"""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境决定
        raise RuntimeError("写出 geometry aligned image 需要安装 Pillow。") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(array, 0, 255).round().astype(np.uint8), mode="RGB").save(path)


def _to_gray(image_array: np.ndarray) -> np.ndarray:
    """将 RGB 图像转换为 `[0, 1]` 灰度图。"""

    rgb = image_array[:, :, :3]
    gray = 0.2989 * rgb[:, :, 0] + 0.5870 * rgb[:, :, 1] + 0.1140 * rgb[:, :, 2]
    min_value = float(np.min(gray)) if gray.size else 0.0
    max_value = float(np.max(gray)) if gray.size else 1.0
    if max_value <= min_value:
        return np.zeros_like(gray, dtype=np.float32)
    return ((gray - min_value) / (max_value - min_value)).astype(np.float32)


def _resize_gray(gray: np.ndarray, max_size: int) -> np.ndarray:
    """按最长边限制下采样灰度图, 降低搜索成本。"""

    height, width = gray.shape
    scale = min(1.0, float(max_size) / float(max(height, width)))
    if scale >= 1.0:
        return gray.astype(np.float32)
    new_height = max(1, int(round(height * scale)))
    new_width = max(1, int(round(width * scale)))
    return _nearest_resize(gray, (new_height, new_width)).astype(np.float32)


def _resize_to_shape(gray: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """把灰度图重采样到指定形状。"""

    return _nearest_resize(gray, shape).astype(np.float32)


def _nearest_resize(array: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """使用最近邻重采样, 避免为轻量测试引入额外依赖。"""

    out_h, out_w = shape
    in_h, in_w = array.shape
    row_idx = np.clip(np.round(np.linspace(0, in_h - 1, out_h)).astype(int), 0, in_h - 1)
    col_idx = np.clip(np.round(np.linspace(0, in_w - 1, out_w)).astype(int), 0, in_w - 1)
    return array[row_idx[:, None], col_idx[None, :]]


def _rotation_candidates(config: Mapping[str, Any]) -> list[float]:
    """读取 affine rotation 网格, 默认覆盖轻量旋转攻击。"""

    values = config.get("affine_rotation_degrees", [-6.0, -3.0, 0.0, 3.0, 6.0])
    if isinstance(values, str):
        values = [item.strip() for item in values.split(",") if item.strip()]
    candidates = sorted({round(float(value), 6) for value in values})
    return candidates or [0.0]


def _scale_candidates(config: Mapping[str, Any]) -> list[float]:
    """读取 affine scale 网格, 默认覆盖轻量缩放攻击。"""

    values = config.get("affine_scales", [0.95, 1.0, 1.05])
    if isinstance(values, str):
        values = [item.strip() for item in values.split(",") if item.strip()]
    candidates = sorted({round(float(value), 6) for value in values if float(value) > 0.0})
    return candidates or [1.0]


def _perspective_offset_candidates(config: Mapping[str, Any]) -> list[float]:
    """读取轻量透视候选网格。

    `perspective_offset` 表示上边两个角向中心收缩的比例。正值用于校正常见 top-keystone,
    负值用于校正反向 keystone。该参数是项目特定的轻量透视原语, 不是完整单应性特征匹配。
    """

    values = config.get("perspective_offsets", [0.0])
    if isinstance(values, str):
        values = [item.strip() for item in values.split(",") if item.strip()]
    candidates = sorted({round(float(value), 6) for value in values if abs(float(value)) < 0.45})
    return candidates or [0.0]


def _perspective_coefficients(source_points: list[tuple[float, float]], target_points: list[tuple[float, float]]) -> list[float]:
    """计算 Pillow perspective transform 系数。

    Pillow 的 perspective 系数把输出坐标映射回输入坐标。这里使用线性方程直接求解, 避免引入 OpenCV
    依赖, 便于在 Colab 和最小测试环境中复用。
    """

    matrix = []
    vector = []
    for (src_x, src_y), (dst_x, dst_y) in zip(source_points, target_points):
        matrix.append([dst_x, dst_y, 1.0, 0.0, 0.0, 0.0, -src_x * dst_x, -src_x * dst_y])
        matrix.append([0.0, 0.0, 0.0, dst_x, dst_y, 1.0, -src_y * dst_x, -src_y * dst_y])
        vector.extend([src_x, src_y])
    solution = np.linalg.solve(np.asarray(matrix, dtype=np.float64), np.asarray(vector, dtype=np.float64))
    return [float(value) for value in solution]


def _perspective_source_quad(width: int, height: int, perspective_offset: float) -> list[tuple[float, float]]:
    """构造用于轻量 keystone 校正的源四边形。"""

    offset = float(width - 1) * float(perspective_offset)
    return [
        (offset, 0.0),
        (float(width - 1) - offset, 0.0),
        (float(width - 1), float(height - 1)),
        (0.0, float(height - 1)),
    ]


def _apply_perspective_gray(array: np.ndarray, *, perspective_offset: float) -> np.ndarray:
    """对灰度图执行轻量透视候选校正。"""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境决定
        raise RuntimeError("perspective geometry registration 需要安装 Pillow。") from exc
    height, width = array.shape
    rect = [(0.0, 0.0), (float(width - 1), 0.0), (float(width - 1), float(height - 1)), (0.0, float(height - 1))]
    coeffs = _perspective_coefficients(_perspective_source_quad(width, height, perspective_offset), rect)
    image = Image.fromarray(np.clip(array * 255.0, 0, 255).round().astype(np.uint8), mode="L")
    transformed = image.transform((width, height), Image.Transform.PERSPECTIVE, coeffs, resample=Image.Resampling.BILINEAR)
    return (np.asarray(transformed, dtype=np.float32) / 255.0).astype(np.float32)


def _apply_perspective_rgb(array: np.ndarray, *, perspective_offset: float) -> np.ndarray:
    """对 RGB 图执行轻量透视候选校正。"""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境决定
        raise RuntimeError("perspective geometry aligned image 写出需要安装 Pillow。") from exc
    height, width, _ = array.shape
    rect = [(0.0, 0.0), (float(width - 1), 0.0), (float(width - 1), float(height - 1)), (0.0, float(height - 1))]
    coeffs = _perspective_coefficients(_perspective_source_quad(width, height, perspective_offset), rect)
    image = Image.fromarray(np.clip(array, 0, 255).round().astype(np.uint8), mode="RGB")
    transformed = image.transform((width, height), Image.Transform.PERSPECTIVE, coeffs, resample=Image.Resampling.BILINEAR)
    return np.asarray(transformed.convert("RGB"), dtype=np.float32)


def _feature_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """读取 feature homography refinement 配置。"""

    return {
        "enabled": str(config.get("feature_homography_enabled", "true")).lower() not in {"false", "0", "no"},
        "max_features": int(config.get("feature_max_features", 48)),
        "patch_radius": int(config.get("feature_patch_radius", 3)),
        "ransac_max_trials": int(config.get("homography_ransac_max_trials", 160)),
        "inlier_threshold": float(config.get("homography_inlier_threshold", 3.0)),
        "min_inliers": int(config.get("homography_min_inliers", 4)),
    }


def _maybe_refine_with_feature_homography(
    reference: np.ndarray,
    target: np.ndarray,
    current_best: dict[str, Any],
    request: GeometryRegistrationRequest,
) -> dict[str, Any]:
    """使用轻量特征匹配和 RANSAC homography 对网格结果做可审计 refinement。"""

    cfg = _feature_config(request.config)
    if not cfg["enabled"]:
        current_best["feature_homography"] = {"enabled": False, "status": "disabled"}
        return current_best
    try:
        result = _estimate_feature_homography(reference, target, cfg)
    except Exception as exc:  # pragma: no cover - 保护正式检测不中断
        current_best["feature_homography"] = {"enabled": True, "status": "error", "error": str(exc)}
        return current_best
    if result["status"] != "ok":
        current_best["feature_homography"] = result
        return current_best
    warped = result["warped_target"]
    translation = _search_translation(reference, warped, request.search_radius)
    feature_score = float(translation["score"])
    result_record = {key: value for key, value in result.items() if key != "warped_target"}
    result_record["post_homography_translation_score"] = round(feature_score, 8)
    result_record["post_homography_dx"] = int(translation["dx"])
    result_record["post_homography_dy"] = int(translation["dy"])
    if feature_score >= float(current_best["score"]):
        return {
            **translation,
            "rotation_degrees": 0.0,
            "scale": 1.0,
            "perspective_offset": 0.0,
            "target_gray": warped,
            "affine_candidate_count": int(current_best.get("affine_candidate_count", 0)),
            "candidate_count": int(current_best.get("candidate_count", 0)) + int(translation.get("candidate_count", 0)),
            "feature_homography": {**result_record, "selected": True},
        }
    current_best["feature_homography"] = {**result_record, "selected": False}
    return current_best


def _estimate_feature_homography(reference: np.ndarray, target: np.ndarray, cfg: Mapping[str, Any]) -> dict[str, Any]:
    """估计 target 到 reference 的特征匹配 homography。"""

    ref_points = _detect_feature_points(reference, max_points=int(cfg["max_features"]))
    tgt_points = _detect_feature_points(target, max_points=int(cfg["max_features"]))
    matches = _match_patch_descriptors(reference, target, ref_points, tgt_points, patch_radius=int(cfg["patch_radius"]))
    if len(matches) < 4:
        return {
            "enabled": True,
            "status": "insufficient_matches",
            "reference_feature_count": len(ref_points),
            "target_feature_count": len(tgt_points),
            "match_count": len(matches),
        }
    homography = _ransac_homography(
        matches,
        max_trials=int(cfg["ransac_max_trials"]),
        inlier_threshold=float(cfg["inlier_threshold"]),
        min_inliers=int(cfg["min_inliers"]),
    )
    if homography is None:
        return {
            "enabled": True,
            "status": "homography_not_found",
            "reference_feature_count": len(ref_points),
            "target_feature_count": len(tgt_points),
            "match_count": len(matches),
        }
    matrix, inlier_indices = homography
    warped = _warp_gray_homography(target, matrix, reference.shape)
    return {
        "enabled": True,
        "status": "ok",
        "reference_feature_count": len(ref_points),
        "target_feature_count": len(tgt_points),
        "match_count": len(matches),
        "inlier_count": len(inlier_indices),
        "inlier_ratio": round(float(len(inlier_indices) / max(1, len(matches))), 8),
        "homography_matrix": np.round(matrix, 8).tolist(),
        "warped_target": warped,
    }


def _detect_feature_points(gray: np.ndarray, *, max_points: int) -> list[tuple[float, float]]:
    """用梯度角点响应提取轻量特征点。"""

    if gray.shape[0] < 5 or gray.shape[1] < 5:
        return []
    gy, gx = np.gradient(gray.astype(np.float32))
    response = gx * gx + gy * gy
    candidates = []
    for y in range(2, gray.shape[0] - 2):
        for x in range(2, gray.shape[1] - 2):
            value = float(response[y, x])
            if value <= 1e-6:
                continue
            local = response[y - 1 : y + 2, x - 1 : x + 2]
            if value >= float(np.max(local)):
                candidates.append((value, float(x), float(y)))
    candidates.sort(reverse=True, key=lambda item: item[0])
    points: list[tuple[float, float]] = []
    min_distance_sq = 16.0
    for _, x, y in candidates:
        if all((x - px) ** 2 + (y - py) ** 2 >= min_distance_sq for px, py in points):
            points.append((x, y))
        if len(points) >= max_points:
            break
    return points


def _patch_descriptor(gray: np.ndarray, point: tuple[float, float], *, radius: int) -> np.ndarray | None:
    """提取归一化 patch descriptor。"""

    x, y = int(round(point[0])), int(round(point[1]))
    if y - radius < 0 or y + radius + 1 > gray.shape[0] or x - radius < 0 or x + radius + 1 > gray.shape[1]:
        return None
    patch = gray[y - radius : y + radius + 1, x - radius : x + radius + 1].astype(np.float32).reshape(-1)
    patch = patch - float(np.mean(patch))
    norm = float(np.linalg.norm(patch))
    if norm <= 1e-8:
        return None
    return patch / norm


def _match_patch_descriptors(
    reference: np.ndarray,
    target: np.ndarray,
    ref_points: list[tuple[float, float]],
    tgt_points: list[tuple[float, float]],
    *,
    patch_radius: int,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """按 patch descriptor 最近邻匹配 target 点到 reference 点。"""

    ref_desc = [(point, _patch_descriptor(reference, point, radius=patch_radius)) for point in ref_points]
    tgt_desc = [(point, _patch_descriptor(target, point, radius=patch_radius)) for point in tgt_points]
    ref_desc = [(point, desc) for point, desc in ref_desc if desc is not None]
    tgt_desc = [(point, desc) for point, desc in tgt_desc if desc is not None]
    matches = []
    used_ref: set[int] = set()
    for tgt_point, tgt_vector in tgt_desc:
        distances = []
        for index, (ref_point, ref_vector) in enumerate(ref_desc):
            if index in used_ref:
                continue
            distances.append((float(np.linalg.norm(tgt_vector - ref_vector)), index, ref_point))
        if not distances:
            continue
        distances.sort(key=lambda item: item[0])
        best_distance, best_index, best_ref = distances[0]
        second_distance = distances[1][0] if len(distances) > 1 else best_distance + 1.0
        if best_distance <= 0.9 * max(second_distance, 1e-8):
            matches.append((tgt_point, best_ref))
            used_ref.add(best_index)
    return matches


def _homography_from_points(src: np.ndarray, dst: np.ndarray) -> np.ndarray | None:
    """使用 DLT 从 4 对或更多点估计 homography, 方向为 src -> dst。"""

    if src.shape[0] < 4 or dst.shape[0] < 4:
        return None
    rows = []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([-x, -y, -1.0, 0.0, 0.0, 0.0, u * x, u * y, u])
        rows.append([0.0, 0.0, 0.0, -x, -y, -1.0, v * x, v * y, v])
    _, _, vh = np.linalg.svd(np.asarray(rows, dtype=np.float64))
    h = vh[-1, :].reshape(3, 3)
    if abs(float(h[2, 2])) <= 1e-12:
        return None
    return h / h[2, 2]


def _ransac_homography(
    matches: list[tuple[tuple[float, float], tuple[float, float]]],
    *,
    max_trials: int,
    inlier_threshold: float,
    min_inliers: int,
) -> tuple[np.ndarray, list[int]] | None:
    """对匹配点执行确定性 RANSAC homography。"""

    src = np.asarray([match[0] for match in matches], dtype=np.float64)
    dst = np.asarray([match[1] for match in matches], dtype=np.float64)
    best_indices: list[int] = []
    best_matrix: np.ndarray | None = None
    trial_count = 0
    n = len(matches)
    for a in range(0, n - 3):
        for b in range(a + 1, n - 2):
            for c in range(b + 1, n - 1):
                for d in range(c + 1, n):
                    matrix = _homography_from_points(src[[a, b, c, d]], dst[[a, b, c, d]])
                    trial_count += 1
                    if matrix is None:
                        continue
                    projected = _project_points(src, matrix)
                    errors = np.linalg.norm(projected - dst, axis=1)
                    inliers = [int(index) for index, error in enumerate(errors) if float(error) <= inlier_threshold]
                    if len(inliers) > len(best_indices):
                        best_indices = inliers
                        best_matrix = matrix
                    if trial_count >= max_trials:
                        break
                if trial_count >= max_trials:
                    break
            if trial_count >= max_trials:
                break
        if trial_count >= max_trials:
            break
    if best_matrix is None or len(best_indices) < min_inliers:
        return None
    refined = _homography_from_points(src[best_indices], dst[best_indices])
    if refined is None:
        refined = best_matrix
    return refined, best_indices


def _project_points(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """应用 homography 投影点。"""

    homogeneous = np.concatenate([points, np.ones((points.shape[0], 1), dtype=np.float64)], axis=1)
    projected = homogeneous @ matrix.T
    denom = np.clip(projected[:, 2:3], 1e-12, None)
    return projected[:, :2] / denom


def _warp_gray_homography(array: np.ndarray, matrix: np.ndarray, output_shape: tuple[int, int]) -> np.ndarray:
    """使用 Pillow 将 target 图像按 homography warp 到 reference 坐标。"""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境决定
        raise RuntimeError("feature homography warp 需要安装 Pillow。") from exc
    out_h, out_w = output_shape
    inverse = np.linalg.inv(matrix)
    inverse = inverse / inverse[2, 2]
    coeffs = [float(inverse[0, 0]), float(inverse[0, 1]), float(inverse[0, 2]), float(inverse[1, 0]), float(inverse[1, 1]), float(inverse[1, 2]), float(inverse[2, 0]), float(inverse[2, 1])]
    image = Image.fromarray(np.clip(array * 255.0, 0, 255).round().astype(np.uint8), mode="L")
    warped = image.transform((out_w, out_h), Image.Transform.PERSPECTIVE, coeffs, resample=Image.Resampling.BILINEAR)
    return (np.asarray(warped, dtype=np.float32) / 255.0).astype(np.float32)


def _search_affine_registration(reference: np.ndarray, target: np.ndarray, request: GeometryRegistrationRequest) -> dict[str, Any]:
    """在 affine 网格和整数平移窗口中搜索最优 registration。"""

    all_candidates: list[dict[str, Any]] = []
    for rotation_degrees in _rotation_candidates(request.config):
        for scale in _scale_candidates(request.config):
            for perspective_offset in _perspective_offset_candidates(request.config):
                candidate_target = _apply_affine_gray(
                    target,
                    rotation_degrees=rotation_degrees,
                    scale=scale,
                    perspective_offset=perspective_offset,
                )
                if candidate_target.shape != reference.shape:
                    candidate_target = _resize_to_shape(candidate_target, reference.shape)
                translation = _search_translation(reference, candidate_target, request.search_radius)
                all_candidates.append(
                    {
                        **translation,
                        "rotation_degrees": rotation_degrees,
                        "scale": scale,
                        "perspective_offset": perspective_offset,
                        "target_gray": candidate_target,
                    }
                )
    all_candidates.sort(reverse=True, key=lambda item: float(item["score"]))
    best = dict(all_candidates[0])
    second_score = float(all_candidates[1]["score"]) if len(all_candidates) > 1 else float(best["score"])
    best["score_margin"] = float(best["score"]) - second_score
    best["affine_candidate_count"] = len(all_candidates)
    best["candidate_count"] = sum(int(item["candidate_count"]) for item in all_candidates)
    return best


def _apply_affine_gray(array: np.ndarray, *, rotation_degrees: float, scale: float, perspective_offset: float = 0.0) -> np.ndarray:
    """对灰度图执行中心缩放、透视候选校正和旋转, 输出尺寸保持不变。"""

    transformed = _center_scale_array(array, scale=scale)
    if abs(perspective_offset) > 1e-9:
        transformed = _apply_perspective_gray(transformed, perspective_offset=perspective_offset)
    if abs(rotation_degrees) <= 1e-9:
        return transformed.astype(np.float32)
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境决定
        raise RuntimeError("affine geometry registration 需要安装 Pillow。") from exc
    image = Image.fromarray(np.clip(transformed * 255.0, 0, 255).round().astype(np.uint8), mode="L")
    rotated = image.rotate(float(rotation_degrees), resample=Image.Resampling.BILINEAR, expand=False, fillcolor=0)
    return (np.asarray(rotated, dtype=np.float32) / 255.0).astype(np.float32)


def _apply_affine_rgb(array: np.ndarray, *, rotation_degrees: float, scale: float, perspective_offset: float = 0.0) -> np.ndarray:
    """对 RGB 图执行中心缩放、透视候选校正和旋转, 输出尺寸保持不变。"""

    transformed = _center_scale_rgb(array, scale=scale)
    if abs(perspective_offset) > 1e-9:
        transformed = _apply_perspective_rgb(transformed, perspective_offset=perspective_offset)
    if abs(rotation_degrees) <= 1e-9:
        return transformed.astype(np.float32)
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 由运行环境决定
        raise RuntimeError("affine geometry aligned image 写出需要安装 Pillow。") from exc
    image = Image.fromarray(np.clip(transformed, 0, 255).round().astype(np.uint8), mode="RGB")
    rotated = image.rotate(float(rotation_degrees), resample=Image.Resampling.BILINEAR, expand=False, fillcolor=(0, 0, 0))
    return np.asarray(rotated.convert("RGB"), dtype=np.float32)


def _center_scale_array(array: np.ndarray, *, scale: float) -> np.ndarray:
    """以图像中心为锚点缩放二维数组, 再裁剪或补零回原始尺寸。"""

    if abs(scale - 1.0) <= 1e-9:
        return array.astype(np.float32)
    height, width = array.shape
    new_height = max(1, int(round(height * scale)))
    new_width = max(1, int(round(width * scale)))
    scaled = _nearest_resize(array, (new_height, new_width)).astype(np.float32)
    return _center_crop_or_pad_2d(scaled, (height, width))


def _center_scale_rgb(array: np.ndarray, *, scale: float) -> np.ndarray:
    """以图像中心为锚点缩放 RGB 数组, 再裁剪或补零回原始尺寸。"""

    if abs(scale - 1.0) <= 1e-9:
        return array.astype(np.float32)
    height, width, channels = array.shape
    scaled_channels = []
    for channel_index in range(channels):
        scaled_channels.append(_center_scale_array(array[:, :, channel_index], scale=scale))
    return np.stack(scaled_channels, axis=2).astype(np.float32)


def _center_crop_or_pad_2d(array: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """把二维数组按中心裁剪或补零到指定形状。"""

    out_h, out_w = shape
    result = np.zeros((out_h, out_w), dtype=np.float32)
    in_h, in_w = array.shape
    copy_h = min(out_h, in_h)
    copy_w = min(out_w, in_w)
    src_y0 = max(0, (in_h - copy_h) // 2)
    src_x0 = max(0, (in_w - copy_w) // 2)
    dst_y0 = max(0, (out_h - copy_h) // 2)
    dst_x0 = max(0, (out_w - copy_w) // 2)
    result[dst_y0 : dst_y0 + copy_h, dst_x0 : dst_x0 + copy_w] = array[src_y0 : src_y0 + copy_h, src_x0 : src_x0 + copy_w]
    return result


def _search_translation(reference: np.ndarray, target: np.ndarray, radius: int) -> dict[str, Any]:
    """在整数平移窗口中搜索最大归一化互相关。"""

    candidates: list[tuple[float, int, int]] = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            ref_crop, tgt_crop = _overlap_for_shift(reference, target, dx=dx, dy=dy)
            score = _normalized_correlation(ref_crop, tgt_crop)
            candidates.append((score, dx, dy))
    candidates.sort(reverse=True, key=lambda item: item[0])
    best_score, best_dx, best_dy = candidates[0]
    second_score = candidates[1][0] if len(candidates) > 1 else best_score
    return {
        "score": best_score,
        "dx": best_dx,
        "dy": best_dy,
        "score_margin": best_score - second_score,
        "candidate_count": len(candidates),
    }


def _overlap_for_shift(reference: np.ndarray, target: np.ndarray, *, dx: int, dy: int) -> tuple[np.ndarray, np.ndarray]:
    """返回给定位移下 reference 与 target 的重叠区域。

    `dx` 和 `dy` 表示 target 需要移动多少像素才能对齐 reference。
    """

    height, width = reference.shape
    ref_y0 = max(0, dy)
    ref_y1 = min(height, height + dy)
    tgt_y0 = max(0, -dy)
    tgt_y1 = min(height, height - dy)
    ref_x0 = max(0, dx)
    ref_x1 = min(width, width + dx)
    tgt_x0 = max(0, -dx)
    tgt_x1 = min(width, width - dx)
    return reference[ref_y0:ref_y1, ref_x0:ref_x1], target[tgt_y0:tgt_y1, tgt_x0:tgt_x1]


def _normalized_correlation(a: np.ndarray, b: np.ndarray) -> float:
    """计算 `[0, 1]` 归一化互相关分数。"""

    if a.size == 0 or b.size == 0:
        return 0.0
    av = a.astype(np.float32).reshape(-1)
    bv = b.astype(np.float32).reshape(-1)
    av = av - float(np.mean(av))
    bv = bv - float(np.mean(bv))
    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    if denom <= 1e-12:
        return 1.0 if float(np.mean(np.abs(a - b))) <= 1e-6 else 0.0
    cosine = float(np.dot(av, bv) / denom)
    return max(0.0, min(1.0, 0.5 + 0.5 * cosine))


def _anchor_inlier_ratio(reference: np.ndarray, target: np.ndarray, *, dx: int, dy: int, grid_size: int) -> float:
    """按网格统计局部块在估计平移下是否保持一致。"""

    height, width = reference.shape
    row_edges = np.linspace(0, height, grid_size + 1, dtype=np.int64)
    col_edges = np.linspace(0, width, grid_size + 1, dtype=np.int64)
    inliers = 0
    total = 0
    for row in range(grid_size):
        for col in range(grid_size):
            ref_block = reference[row_edges[row] : row_edges[row + 1], col_edges[col] : col_edges[col + 1]]
            tgt_aligned = _apply_shift_gray(target, dx=dx, dy=dy)
            tgt_block = tgt_aligned[row_edges[row] : row_edges[row + 1], col_edges[col] : col_edges[col + 1]]
            if ref_block.size == 0 or tgt_block.size == 0:
                continue
            total += 1
            if _normalized_correlation(ref_block, tgt_block) >= 0.55:
                inliers += 1
    return float(inliers / total) if total else 0.0


def _local_deformation_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """读取局部网格 deformation refinement 配置。"""

    return {
        "enabled": str(config.get("local_deformation_enabled", "true")).lower() not in {"false", "0", "no"},
        "grid_size": int(config.get("local_deformation_grid_size", 4)),
        "search_radius": int(config.get("local_deformation_search_radius", 2)),
        "min_score_gain": float(config.get("local_deformation_min_score_gain", 0.0)),
    }


def _maybe_refine_with_local_deformation(
    reference: np.ndarray,
    current_best: dict[str, Any],
    request: GeometryRegistrationRequest,
) -> dict[str, Any]:
    """使用局部网格位移对已全局对齐的 target 做 refinement。"""

    cfg = _local_deformation_config(request.config)
    if not cfg["enabled"]:
        current_best["local_deformation"] = {"enabled": False, "status": "disabled"}
        return current_best
    target = current_best["target_gray"]
    globally_aligned = _apply_shift_gray(target, dx=int(current_best["dx"]), dy=int(current_best["dy"]))
    local = _estimate_local_deformation(
        reference,
        globally_aligned,
        grid_size=int(cfg["grid_size"]),
        search_radius=int(cfg["search_radius"]),
    )
    local_score = _normalized_correlation(reference, local["warped_target"])
    global_score = float(current_best["score"])
    local_record = {key: value for key, value in local.items() if key != "warped_target"}
    local_record["enabled"] = True
    local_record["global_score"] = round(global_score, 8)
    local_record["local_score"] = round(float(local_score), 8)
    if local_score + 1e-12 >= global_score + float(cfg["min_score_gain"]):
        return {
            **current_best,
            "dx": 0,
            "dy": 0,
            "target_gray": local["warped_target"],
            "score": float(local_score),
            "score_margin": max(float(current_best.get("score_margin", 0.0)), float(local_score) - global_score),
            "local_deformation": {**local_record, "selected": True},
        }
    current_best["local_deformation"] = {**local_record, "selected": False}
    return current_best


def _estimate_local_deformation(reference: np.ndarray, aligned_target: np.ndarray, *, grid_size: int, search_radius: int) -> dict[str, Any]:
    """估计局部网格位移并返回局部 warp 后的 target。"""

    height, width = reference.shape
    row_edges = np.linspace(0, height, grid_size + 1, dtype=np.int64)
    col_edges = np.linspace(0, width, grid_size + 1, dtype=np.int64)
    warped = np.zeros_like(aligned_target)
    shifts: list[dict[str, Any]] = []
    inliers = 0
    total = 0
    for row in range(grid_size):
        for col in range(grid_size):
            y0, y1 = int(row_edges[row]), int(row_edges[row + 1])
            x0, x1 = int(col_edges[col]), int(col_edges[col + 1])
            ref_block = reference[y0:y1, x0:x1]
            best = {"score": -1.0, "dx": 0, "dy": 0}
            for dy in range(-search_radius, search_radius + 1):
                for dx in range(-search_radius, search_radius + 1):
                    candidate = _crop_shifted_block(aligned_target, x0=x0, x1=x1, y0=y0, y1=y1, dx=dx, dy=dy)
                    score = _normalized_correlation(ref_block, candidate)
                    if score > float(best["score"]):
                        best = {"score": float(score), "dx": int(dx), "dy": int(dy)}
            warped[y0:y1, x0:x1] = _crop_shifted_block(
                aligned_target,
                x0=x0,
                x1=x1,
                y0=y0,
                y1=y1,
                dx=int(best["dx"]),
                dy=int(best["dy"]),
            )
            total += 1
            if float(best["score"]) >= 0.55:
                inliers += 1
            shifts.append({"row": row, "col": col, "dx": int(best["dx"]), "dy": int(best["dy"]), "score": round(float(best["score"]), 8)})
    return {
        "status": "ok",
        "grid_size": int(grid_size),
        "search_radius": int(search_radius),
        "block_count": int(total),
        "local_inlier_ratio": round(float(inliers / total), 8) if total else 0.0,
        "shifts": shifts,
        "warped_target": warped,
    }


def _crop_shifted_block(array: np.ndarray, *, x0: int, x1: int, y0: int, y1: int, dx: int, dy: int) -> np.ndarray:
    """从局部位移后的数组中裁剪与 reference block 同尺寸的块。"""

    result = np.zeros((y1 - y0, x1 - x0), dtype=np.float32)
    src_y0 = max(0, y0 - dy)
    src_y1 = min(array.shape[0], y1 - dy)
    src_x0 = max(0, x0 - dx)
    src_x1 = min(array.shape[1], x1 - dx)
    dst_y0 = max(0, src_y0 + dy - y0)
    dst_x0 = max(0, src_x0 + dx - x0)
    copy_h = max(0, src_y1 - src_y0)
    copy_w = max(0, src_x1 - src_x0)
    if copy_h and copy_w:
        result[dst_y0 : dst_y0 + copy_h, dst_x0 : dst_x0 + copy_w] = array[src_y0:src_y1, src_x0:src_x1]
    return result


def _apply_local_deformation_rgb(array: np.ndarray, local_deformation: Mapping[str, Any] | None) -> np.ndarray:
    """把局部网格位移应用到 RGB 图像。"""

    if not isinstance(local_deformation, Mapping) or not local_deformation.get("selected"):
        return array
    grid_size = int(local_deformation.get("grid_size", 0))
    shifts = local_deformation.get("shifts") or []
    if grid_size <= 0 or not isinstance(shifts, list):
        return array
    height, width, channels = array.shape
    row_edges = np.linspace(0, height, grid_size + 1, dtype=np.int64)
    col_edges = np.linspace(0, width, grid_size + 1, dtype=np.int64)
    result = np.zeros_like(array)
    shift_lookup = {(int(item.get("row", -1)), int(item.get("col", -1))): item for item in shifts if isinstance(item, Mapping)}
    for row in range(grid_size):
        for col in range(grid_size):
            y0, y1 = int(row_edges[row]), int(row_edges[row + 1])
            x0, x1 = int(col_edges[col]), int(col_edges[col + 1])
            item = shift_lookup.get((row, col), {})
            dx = int(item.get("dx", 0)) if isinstance(item, Mapping) else 0
            dy = int(item.get("dy", 0)) if isinstance(item, Mapping) else 0
            for channel in range(channels):
                result[y0:y1, x0:x1, channel] = _crop_shifted_block(array[:, :, channel], x0=x0, x1=x1, y0=y0, y1=y1, dx=dx, dy=dy)
    return result


def _sync_consistency(dx: int, dy: int, radius: int) -> float:
    """根据估计位移相对搜索窗口的位置给出同步一致性。"""

    if radius <= 0:
        return 1.0 if dx == 0 and dy == 0 else 0.0
    shift_norm = float((dx * dx + dy * dy) ** 0.5)
    max_norm = float((2 * radius * radius) ** 0.5)
    return max(0.0, min(1.0, 1.0 - shift_norm / max_norm))


def _apply_shift_gray(array: np.ndarray, *, dx: int, dy: int) -> np.ndarray:
    """把灰度图按估计位移移动到 reference 坐标系。"""

    result = np.zeros_like(array)
    height, width = array.shape
    src_y0 = max(0, -dy)
    src_y1 = min(height, height - dy)
    dst_y0 = max(0, dy)
    dst_y1 = min(height, height + dy)
    src_x0 = max(0, -dx)
    src_x1 = min(width, width - dx)
    dst_x0 = max(0, dx)
    dst_x1 = min(width, width + dx)
    result[dst_y0:dst_y1, dst_x0:dst_x1] = array[src_y0:src_y1, src_x0:src_x1]
    return result


def _apply_shift_rgb(array: np.ndarray, *, dx: int, dy: int) -> np.ndarray:
    """把 RGB 图像按估计位移移动到 reference 坐标系。"""

    result = np.zeros_like(array)
    height, width, _ = array.shape
    src_y0 = max(0, -dy)
    src_y1 = min(height, height - dy)
    dst_y0 = max(0, dy)
    dst_y1 = min(height, height + dy)
    src_x0 = max(0, -dx)
    src_x1 = min(width, width - dx)
    dst_x0 = max(0, dx)
    dst_x1 = min(width, width + dx)
    result[dst_y0:dst_y1, dst_x0:dst_x1, :] = array[src_y0:src_y1, src_x0:src_x1, :]
    return result


def _write_aligned_image(
    target_rgb: np.ndarray,
    output_path: Path | None,
    *,
    dx: int,
    dy: int,
    rotation_degrees: float,
    scale: float,
    perspective_offset: float = 0.0,
    local_deformation: Mapping[str, Any] | None = None,
) -> str | None:
    """按需写出经过 affine 候选变换和平移恢复后的 target 图像。"""

    if output_path is None:
        return None
    transformed = _apply_affine_rgb(
        target_rgb,
        rotation_degrees=rotation_degrees,
        scale=scale,
        perspective_offset=perspective_offset,
    )
    aligned = _apply_shift_rgb(transformed, dx=dx, dy=dy)
    aligned = _apply_local_deformation_rgb(aligned, local_deformation)
    _write_rgb_array(output_path, aligned)
    return output_path.as_posix()


def _image_summary(array: np.ndarray, path: Path) -> dict[str, Any]:
    """构造用于 digest 的轻量图像摘要。"""

    gray = _to_gray(array)
    return {
        "path_name": path.name,
        "shape": [int(v) for v in array.shape],
        "mean": round(float(np.mean(gray)), 8),
        "std": round(float(np.std(gray)), 8),
        "row_projection_digest": build_stable_digest({"row_sum": np.round(gray.sum(axis=1), 6).tolist()}),
        "col_projection_digest": build_stable_digest({"col_sum": np.round(gray.sum(axis=0), 6).tolist()}),
    }
