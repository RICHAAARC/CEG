"""提供轻量 paper protocol runner, 用于本地验证 CEG 与 baseline 流程。"""

from __future__ import annotations

from typing import Any, Iterable

from experiments.baseline_file_adapter import attach_baseline_observations
from main.analysis.rebuild_artifacts import build_all_paper_artifacts, build_pw02_artifacts, build_pw04_tables
from main.protocol.experiment import EventProtocolRecord, validate_active_profile
from main.protocol.runtime import run_protocol_events


def build_event_from_mapping(row: dict[str, Any]) -> EventProtocolRecord:
    """从普通字典构造协议事件, 便于 JSON / Notebook / 测试复用。"""
    return EventProtocolRecord(
        event_id=str(row["event_id"]),
        method_name=str(row.get("method_name", "ceg")),
        split=str(row["split"]),
        sample_role=str(row["sample_role"]),
        attack_family=str(row.get("attack_family", "clean")),
        attack_condition=str(row.get("attack_condition", "none")),
        is_watermarked=bool(row["is_watermarked"]),
        payload=dict(row["payload"]),
    )


def run_paper_protocol(
    event_rows: Iterable[dict[str, Any]],
    *,
    profile: str,
    content_thresholds: dict[str, float],
    baseline_observation_rows: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """运行轻量 paper protocol 并返回 records 与可重建产物。

    此函数属于实验 runner, 用于连接协议事件、CEG 方法、baseline 适配器和
    产物重建模块。它不写正式输出目录, 调用方可以在临时目录或外部输出目录中
    显式写入产物。
    """
    active_profile = validate_active_profile(profile)
    events = [build_event_from_mapping(row) for row in event_rows]
    if baseline_observation_rows is not None:
        events = attach_baseline_observations(events, baseline_observation_rows)
    records = run_protocol_events(events)
    pw02_artifacts = build_pw02_artifacts(records, content_thresholds=content_thresholds)
    pw04_tables = build_pw04_tables(records)
    all_artifacts = build_all_paper_artifacts(records, content_thresholds=content_thresholds)
    return {
        "profile": active_profile,
        "records": records,
        "pw02_artifacts": pw02_artifacts,
        "pw04_tables": pw04_tables,
        "standard_metric_artifacts": {
            name: payload
            for name, payload in all_artifacts.items()
            if name in {
                "standard_watermark_metrics.json",
                "quality_metrics_summary.csv",
                "bit_recovery_metrics.csv",
                "attack_family_metrics.csv",
            }
        },
        "figure_artifacts": {"paper_figure_specs.json": all_artifacts["paper_figure_specs.json"]},
        "all_paper_artifacts": all_artifacts,
    }
