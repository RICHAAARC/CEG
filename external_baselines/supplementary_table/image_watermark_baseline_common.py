"""补充表图像水印 baseline 的通用适配工具。

该文件属于 `external_baselines/` 实验适配层, 只负责把第三方图像水印方法接入
CEG 统一的 baseline observation 契约。它不属于 CEG 主方法, 也不会被
`main/methods/ceg/` 反向依赖。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def load_json(path: str | Path) -> Any:
    """读取 JSON 文件, 使用 utf-8-sig 兼容 Colab 或 Windows 产生的 BOM。"""

    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: Any) -> None:
    """写出 UTF-8 JSON 文件, 供后续论文流程读取。"""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_text(value: Any, default: str = "") -> str:
    """把可选字段规范化为去空白字符串。"""

    if value is None:
        return default
    text = str(value).strip()
    return text or default


def load_image_pairs(path: str | Path) -> list[dict[str, Any]]:
    """读取 CEG image_pairs.json, 该文件是补充表图像水印 baseline 的输入。"""

    payload = load_json(path)
    if not isinstance(payload, list):
        raise TypeError("image_pairs.json 必须是 JSON list。")
    rows = [dict(row) for row in payload]
    if not rows:
        raise ValueError("image_pairs.json 不能为空。")
    for index, row in enumerate(rows, start=1):
        if not clean_image_path(row):
            raise ValueError(f"image_pairs 第 {index} 行缺少 clean_image_path/reference_path。")
    return rows


def clean_image_path(row: dict[str, Any]) -> str:
    """从 image pair 行读取 clean 图像路径。"""

    return as_text(row.get("clean_image_path") or row.get("reference_path") or row.get("clean_path"))


def row_image_id(row: dict[str, Any], index: int) -> str:
    """读取稳定图像 ID, 缺失时使用序号兜底。"""

    return as_text(row.get("image_id") or row.get("event_id"), f"image_{index:04d}")


def row_prompt_id(row: dict[str, Any], image_id: str) -> str:
    """读取 prompt_id, 用于 provenance 追踪。"""

    return as_text(row.get("prompt_id"), f"prompt_for_{image_id}")


def row_split(row: dict[str, Any]) -> str:
    """读取 split, 缺失时默认归入 test。"""

    return as_text(row.get("split"), "test")


def safe_file_stem(value: str, fallback: str) -> str:
    """把 image_id 转为安全文件名主干。"""

    candidate = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value).strip("._")
    return candidate or fallback


def bytes_to_bits(payload: bytes) -> list[int]:
    """把 bytes payload 转成 bit 列表, 便于计算 bit accuracy。"""

    bits: list[int] = []
    for value in payload:
        bits.extend((value >> shift) & 1 for shift in range(7, -1, -1))
    return bits


def bit_accuracy(decoded_bits: Iterable[int], target_bits: Iterable[int]) -> float:
    """计算两个 bit 序列的平均一致率。"""

    decoded = [int(value) & 1 for value in decoded_bits]
    target = [int(value) & 1 for value in target_bits]
    if not target:
        return 0.0
    limit = min(len(decoded), len(target))
    if limit == 0:
        return 0.0
    matches = sum(1 for left, right in zip(decoded[:limit], target[:limit]) if left == right)
    return float(matches) / float(len(target))


def derive_threshold(observations: Iterable[dict[str, Any]], explicit_threshold: float | None) -> tuple[float, str]:
    """从 calibration split 的 clean_negative 与 positive_source 分数派生阈值。"""

    if explicit_threshold is not None:
        return float(explicit_threshold), "cli_threshold"
    negative_scores: list[float] = []
    positive_scores: list[float] = []
    for row in observations:
        if row.get("split") != "calibration":
            continue
        if row.get("sample_role") == "clean_negative":
            negative_scores.append(float(row["score"]))
        elif row.get("sample_role") == "positive_source":
            positive_scores.append(float(row["score"]))
    if negative_scores and positive_scores:
        return (max(negative_scores) + min(positive_scores)) / 2.0, "calibration_midpoint_between_negative_max_and_positive_min"
    return 0.5, "fallback_half_no_calibration_pairs"


def build_observation(
    *,
    baseline_id: str,
    score_name: str,
    producer_id: str,
    event_id: str,
    score: float,
    threshold: float,
    threshold_source: str,
    source_row: dict[str, Any],
    source_index: int,
    sample_role: str,
    attack_family: str,
    attack_condition: str,
    image_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造一条 CEG baseline observation。"""

    row = {
        "event_id": event_id,
        "baseline_id": baseline_id,
        "score": float(score),
        "threshold": float(threshold),
        "score_name": score_name,
        "higher_is_positive": True,
        "split": row_split(source_row),
        "sample_role": sample_role,
        "attack_family": attack_family,
        "attack_condition": attack_condition,
        "prompt_id": row_prompt_id(source_row, image_id),
        "image_id": image_id,
        "producer_id": producer_id,
        "producer_role": "external_supplementary_image_watermark_adapter",
        "formal_result_claim": False,
        "threshold_source": threshold_source,
    }
    if extra:
        row.update(extra)
    row["final_decision"] = bool(float(score) >= float(threshold))
    return row
