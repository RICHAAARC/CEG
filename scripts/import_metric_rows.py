"""导入离线外部高级指标 rows 并生成结果包可消费的 manifest."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metric_file_adapter import (
    METRIC_ROW_IMPORT_MANIFEST_NAME,
    build_metric_row_import_manifest,
    load_metric_rows,
)


def build_parser() -> argparse.ArgumentParser:
    """构造离线高级指标 rows 导入命令行参数."""
    parser = argparse.ArgumentParser(description="导入离线外部高级指标 rows 文件.")
    parser.add_argument("--metric-rows", required=True, help="外部 metric rows JSON / JSONL / CSV 文件.")
    parser.add_argument("--out", required=True, help="输出目录.")
    parser.add_argument(
        "--formal-result-claim",
        action="store_true",
        help="声明该导入可作为正式论文指标证据. 启用时必须提供至少一个 --evidence-path.",
    )
    parser.add_argument(
        "--evidence-path",
        action="append",
        default=[],
        help="外部高级指标正式运行证据路径, 可重复提供.",
    )
    parser.add_argument(
        "--producer-id",
        default="external_metric_row_importer",
        help="写入 manifest 的 producer_id.",
    )
    return parser


def main() -> None:
    """CLI 入口."""
    parser = build_parser()
    args = parser.parse_args()
    metric_rows_path = Path(args.metric_rows)
    rows = load_metric_rows(metric_rows_path)
    if args.formal_result_claim:
        missing_evidence = [path for path in args.evidence_path if not Path(path).exists()]
        if missing_evidence:
            raise FileNotFoundError(f"formal metric evidence paths missing: {missing_evidence}")
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    output_metric_rows_path = output_root / "metric_rows.json"
    if metric_rows_path.suffix == ".json":
        shutil.copy2(metric_rows_path, output_metric_rows_path)
    else:
        output_metric_rows_path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    manifest = build_metric_row_import_manifest(
        rows,
        source_metric_rows_path=metric_rows_path,
        output_metric_rows_path=output_metric_rows_path,
        formal_result_claim=args.formal_result_claim,
        evidence_paths=args.evidence_path,
        producer_id=args.producer_id,
    )
    (output_root / METRIC_ROW_IMPORT_MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "metric_row_count": manifest["metric_row_count"],
                "metric_fields": manifest["metric_fields"],
                "advanced_metric_fields": manifest["advanced_metric_fields"],
                "formal_result_claim": manifest["formal_result_claim"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
