"""命令行运行轻量 CEG paper protocol。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from main.analysis.rebuild_artifacts import build_all_paper_artifacts, write_artifact_bundle
from main.protocol.experiment import EventProtocolRecord, validate_active_profile
from main.protocol.runtime import run_protocol_events


def _load_json_list(path: Path) -> list[dict[str, object]]:
    """读取 JSON 数组事件文件。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise TypeError("events file must contain a JSON array")
    return [dict(item) for item in payload]


def _load_json_dict(path: Path) -> dict[str, float]:
    """读取 JSON 对象阈值文件并转为 float 映射。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("thresholds file must contain a JSON object")
    return {str(key): float(value) for key, value in payload.items()}


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(description="运行轻量 CEG paper protocol。")
    parser.add_argument("--events", required=True, help="输入事件 JSON 数组路径。")
    parser.add_argument("--thresholds", required=True, help="method_name 到 content_threshold 的 JSON 映射。")
    parser.add_argument("--profile", default="paper_main_probe", help="active profile 名称。")
    parser.add_argument("--out", required=True, help="输出目录。建议使用未提交的本地目录。")
    return parser


def _event_from_row(row: dict[str, object]) -> EventProtocolRecord:
    """从 JSON 行构造协议事件。"""
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


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    profile = validate_active_profile(args.profile)
    events = [_event_from_row(row) for row in _load_json_list(Path(args.events))]
    records = run_protocol_events(events)
    content_thresholds = _load_json_dict(Path(args.thresholds))
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "event_records.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    artifacts = build_all_paper_artifacts(records, content_thresholds=content_thresholds)
    write_artifact_bundle(output_root / "artifacts", artifacts)
    (output_root / "protocol_summary.json").write_text(
        json.dumps({"profile": profile, "record_count": len(records)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
