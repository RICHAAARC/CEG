"""使用外部 baseline observation 文件运行 CEG paper protocol。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.baseline_file_adapter import load_baseline_observation_rows
from experiments.protocol_runner import run_paper_protocol
from main.analysis.rebuild_artifacts import write_artifact_bundle


def _load_json_list(path: Path) -> list[dict[str, object]]:
    """读取 JSON 数组事件文件。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise TypeError("events file must contain list")
    return [dict(item) for item in payload]


def _load_json_dict(path: Path) -> dict[str, float]:
    """读取 method 到 content_threshold 的 JSON 映射。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("thresholds file must contain dict")
    return {str(key): float(value) for key, value in payload.items()}


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="运行带外部 baseline 文件的 CEG paper protocol。")
    parser.add_argument("--events", required=True)
    parser.add_argument("--thresholds", required=True)
    parser.add_argument("--baseline-observations", required=True)
    parser.add_argument("--profile", default="paper_main_probe")
    parser.add_argument("--out", required=True)
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    result = run_paper_protocol(
        _load_json_list(Path(args.events)),
        profile=args.profile,
        content_thresholds=_load_json_dict(Path(args.thresholds)),
        baseline_observation_rows=load_baseline_observation_rows(Path(args.baseline_observations)),
    )
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "event_records.json").write_text(
        json.dumps(result["records"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_artifact_bundle(output_root / "artifacts", result["all_paper_artifacts"])
    (output_root / "protocol_summary.json").write_text(
        json.dumps({"profile": result["profile"], "record_count": len(result["records"])}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
