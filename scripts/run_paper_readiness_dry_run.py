"""运行 CEG 论文结果链路的端到端 readiness dry-run。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.paper_fixture_factory import write_paper_dry_run_inputs


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="生成 dry-run 输入并构建完整论文输出包。")
    parser.add_argument("--out", required=True, help="dry-run 根输出目录。")
    parser.add_argument("--profile", default="paper_main_probe", help="传递给 build_paper_outputs.py 的 profile。")
    parser.add_argument("--repetitions", type=int, default=1, help="每个样本蓝图重复次数。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    output_root = Path(args.out)
    input_root = output_root / "inputs"
    paper_output_root = output_root / "paper_outputs"
    manifest = write_paper_dry_run_inputs(input_root, repetitions=args.repetitions)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_paper_outputs.py"),
        "--events",
        str(input_root / manifest["events_path"]),
        "--thresholds",
        str(input_root / manifest["thresholds_path"]),
        "--baseline-observations",
        str(input_root / manifest["baseline_observations_path"]),
        "--metric-rows",
        str(input_root / manifest["metric_rows_path"]),
        "--profile",
        args.profile,
        "--out",
        str(paper_output_root),
        "--require-paper-readiness",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    summary = {
        "artifact_name": "paper_readiness_dry_run_summary.json",
        "inputs_manifest_path": "inputs/paper_dry_run_inputs_manifest.json",
        "paper_outputs_root": "paper_outputs",
        "command": command,
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "paper_readiness_dry_run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
