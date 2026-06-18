"""将外部 baseline 输出适配为统一事件 records。

该模块的职责是定义 baseline 结果进入 CEG 论文流程时的最小接口。它不实现
Tree-Ring、Gaussian Shading、Shallow Diffuse 或 T2SMark 的第三方
算法本体, 只把这些方法的外部检测分数规范化为统一 records, 以便后续聚合。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from main.methods.baselines import get_baseline_spec
from main.protocol.experiment import EventProtocolRecord

STANDARD_METRIC_RECORD_FIELDS = (
    "bit_correct_count",
    "bit_total_count",
    "bit_accuracy",
    "payload_recovered",
    "psnr",
    "ssim",
    "lpips",
    "fid",
    "clip_score",
)


def _coerce_metric_value(field_name: str, value: Any) -> Any:
    """把 baseline metadata 中的标准指标转换为 records 可聚合的标量。"""
    if value is None:
        return None
    if field_name == "payload_recovered":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return None
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _standard_metric_fields(metadata: dict[str, Any]) -> dict[str, Any]:
    """从 baseline metadata 中提升标准水印指标字段。"""
    extracted: dict[str, Any] = {}
    for field_name in STANDARD_METRIC_RECORD_FIELDS:
        value = _coerce_metric_value(field_name, metadata.get(field_name))
        if value is not None:
            extracted[field_name] = value
    return extracted


def _finite_float(value: float | int, *, field_name: str) -> float:
    """校验并规范化 baseline 分数或阈值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be finite number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    return normalized


@dataclass(frozen=True)
class BaselineObservation:
    """表示一个外部 baseline 对单个事件的检测输出。"""

    baseline_id: str
    score: float
    threshold: float
    score_name: str = "baseline_score"
    higher_is_positive: bool = True
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """保证 baseline 适配输入是显式、有限且可审计的。"""
        _finite_float(self.score, field_name="score")
        _finite_float(self.threshold, field_name="threshold")
        if not isinstance(self.higher_is_positive, bool):
            raise TypeError("higher_is_positive must be bool")

    def to_dict(self) -> dict[str, Any]:
        """转为普通字典, 便于写入 protocol manifest 或调试输出。"""
        return asdict(self)


def adapt_baseline_observation(
    event: EventProtocolRecord,
    observation: BaselineObservation,
) -> dict[str, Any]:
    """将一个外部 baseline 检测结果适配为统一 event record。

    通用工程写法:
    - event 保存样本身份与协议字段。
    - observation 保存 baseline 自己的 score / threshold。
    - 输出 record 使用统一 `final_decision`, 让聚合器可以跨方法比较。

    项目特定写法:
    - baseline 不输出 CEG 的 geometry rescue 机制字段。
    - baseline 的 rescue 统计在聚合阶段自然为 0, 不与 CEG 内部机制混读。
    """
    spec = get_baseline_spec(observation.baseline_id)
    score = _finite_float(observation.score, field_name="score")
    threshold = _finite_float(observation.threshold, field_name="threshold")
    final_decision = score >= threshold if observation.higher_is_positive else score <= threshold
    metadata = observation.metadata or {}
    return {
        "event_id": event.event_id,
        "method_name": spec.baseline_id,
        "baseline_id": spec.baseline_id,
        "baseline_display_name": spec.display_name,
        "comparison_role": spec.comparison_role,
        "split": event.split,
        "sample_role": event.sample_role,
        "attack_family": event.attack_family,
        "attack_condition": event.attack_condition,
        "is_watermarked": event.is_watermarked,
        "final_decision": bool(final_decision),
        "baseline_score": score,
        "baseline_threshold": threshold,
        "baseline_score_name": observation.score_name,
        "higher_is_positive": observation.higher_is_positive,
        "baseline_metadata": metadata,
        **_standard_metric_fields(metadata),
    }
