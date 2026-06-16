"""读取外部 baseline 输出文件并附加到协议事件。

该模块位于 `experiments/`, 因为它面向实验编排和外部方法适配。核心方法层
`main/methods/ceg/` 不依赖这里, 从而保持最小 CEG 方法包干净可抽离。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from main.protocol.experiment import EventProtocolRecord


REQUIRED_BASELINE_COLUMNS = ("event_id", "baseline_id", "score", "threshold")
BASELINE_OBSERVATION_IMPORT_MANIFEST_NAME = "baseline_execution_manifest.json"


def _load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSON 数组或 JSONL baseline 输出。"""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise TypeError("baseline JSON file must contain a list")
    return [dict(row) for row in payload]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    """读取 CSV baseline 输出。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_baseline_observation_rows(path: str | Path) -> list[dict[str, Any]]:
    """从 JSON / JSONL / CSV 文件读取 baseline observation rows。"""
    input_path = Path(path)
    if input_path.suffix in {".json", ".jsonl"}:
        rows = _load_json_or_jsonl(input_path)
    elif input_path.suffix == ".csv":
        rows = _load_csv(input_path)
    else:
        raise ValueError(f"unsupported baseline file extension: {input_path.suffix}")
    missing_by_index = {
        index: [column for column in REQUIRED_BASELINE_COLUMNS if column not in row]
        for index, row in enumerate(rows)
    }
    missing_by_index = {index: missing for index, missing in missing_by_index.items() if missing}
    if missing_by_index:
        raise ValueError(f"baseline observation rows missing columns: {missing_by_index}")
    return rows


def build_baseline_observation_import_manifest(
    rows: Iterable[dict[str, Any]],
    *,
    source_observation_path: str | Path,
    output_observation_path: str | Path,
    formal_result_claim: bool = False,
    evidence_paths: Iterable[str | Path] = (),
    producer_id: str = "external_baseline_observation_importer",
) -> dict[str, Any]:
    """为离线 baseline observation 文件生成可归档的执行 manifest.

    通用工程写法:
    - 第三方 baseline 可以在外部仓库、Colab 或其他服务器中运行.
    - 进入本项目时只要求 observation rows 满足统一契约, 并用 manifest 记录来源.

    项目特定写法:
    - `formal_result_claim=False` 表示该导入只证明接口和 provenance 链路, 不能支撑论文结论.
    - 当用户显式声明 `formal_result_claim=True` 时, 必须额外提供外部证据文件路径.
    """
    materialized_rows = [dict(row) for row in rows]
    materialized_evidence_paths = [str(path) for path in evidence_paths]
    if formal_result_claim and not materialized_evidence_paths:
        raise ValueError("formal baseline import requires at least one evidence path")
    baseline_ids = sorted({str(row["baseline_id"]) for row in materialized_rows})
    return {
        "artifact_name": BASELINE_OBSERVATION_IMPORT_MANIFEST_NAME,
        "producer_id": producer_id,
        "producer_role": "offline_external_baseline_observation_import",
        "formal_result_claim": bool(formal_result_claim),
        "execution_boundary": (
            "offline_external_baseline_evidence_provided"
            if formal_result_claim
            else "offline_observation_import_requires_separate_formal_evidence"
        ),
        "source_observation_path": str(source_observation_path),
        "baseline_observations_path": str(output_observation_path),
        "observation_count": len(materialized_rows),
        "baseline_ids": baseline_ids,
        "evidence_paths": materialized_evidence_paths,
    }


def attach_baseline_observations(
    events: Iterable[EventProtocolRecord],
    observation_rows: Iterable[dict[str, Any]],
) -> list[EventProtocolRecord]:
    """按 event_id 将外部 baseline 输出附加到协议事件 payload。"""
    observations_by_event: dict[str, list[dict[str, Any]]] = {}
    for row in observation_rows:
        event_id = str(row["event_id"])
        observations_by_event.setdefault(event_id, []).append(
            {
                "baseline_id": str(row["baseline_id"]),
                "score": float(row["score"]),
                "threshold": float(row["threshold"]),
                "score_name": str(row.get("score_name", "baseline_score")),
                "higher_is_positive": str(row.get("higher_is_positive", "true")).lower() not in {"false", "0", "no"},
                "metadata": {
                    key: value
                    for key, value in row.items()
                    if key not in {"event_id", "baseline_id", "score", "threshold", "score_name", "higher_is_positive"}
                },
            }
        )
    attached: list[EventProtocolRecord] = []
    for event in events:
        payload = dict(event.payload)
        merged = list(payload.get("baseline_observations") or [])
        merged.extend(observations_by_event.get(event.event_id, []))
        payload["baseline_observations"] = merged
        attached.append(
            EventProtocolRecord(
                event_id=event.event_id,
                method_name=event.method_name,
                split=event.split,
                sample_role=event.sample_role,
                attack_family=event.attack_family,
                attack_condition=event.attack_condition,
                is_watermarked=event.is_watermarked,
                payload=payload,
            )
        )
    return attached
