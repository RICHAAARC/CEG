"""从图像配对清单计算论文图像质量指标。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.image_metrics import build_quality_metric_rows
from main.core.digest import build_stable_digest

BASIC_QUALITY_METRIC_NAMES = ["mse", "mae", "psnr", "ssim"]


def _load_pairs(path: Path) -> list[dict[str, str]]:
    """读取 JSON / JSONL / CSV 图像配对清单。"""
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            raise TypeError("pairs JSON must contain a list")
        return [dict(row) for row in payload]
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"unsupported pairs file extension: {path.suffix}")


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    """按输出扩展名写出 JSON / JSONL / CSV 指标行。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    if path.suffix == ".jsonl":
        path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        return
    if path.suffix == ".csv":
        fieldnames = sorted({key for row in rows for key in row})
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return
    raise ValueError(f"unsupported output extension: {path.suffix}")



def _assess_quality_metric_readiness(rows: list[dict[str, object]]) -> dict[str, object]:
    """检查基础图像质量指标是否具备正式论文结果包使用条件。"""

    required_metrics = set(BASIC_QUALITY_METRIC_NAMES)
    row_checks = []
    for index, row in enumerate(rows):
        present_metrics = {name for name in required_metrics if row.get(name) is not None}
        row_checks.append(
            {
                "row_index": index,
                "event_id": row.get("event_id") or row.get("image_id"),
                "all_required_metrics_present": present_metrics == required_metrics,
                "present_metrics": sorted(present_metrics),
                "reference_path": row.get("reference_path"),
                "watermarked_path": row.get("watermarked_path"),
            }
        )
    failed_rows = [item for item in row_checks if not item["all_required_metrics_present"]]
    return {
        "overall_decision": "pass" if rows and not failed_rows else "fail",
        "row_count": len(rows),
        "required_metrics": BASIC_QUALITY_METRIC_NAMES,
        "failed_row_count": len(failed_rows),
        "row_checks": row_checks,
    }

def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="计算图像水印论文质量指标。")
    parser.add_argument("--pairs", required=True, help="图像配对清单, 支持 JSON / JSONL / CSV。")
    parser.add_argument("--out", required=True, help="质量指标输出路径, 支持 JSON / JSONL / CSV。")
    parser.add_argument("--manifest", default=None, help="可选 metric_execution_manifest.json 输出路径。")
    parser.add_argument(
        "--formal-result-claim",
        action="store_true",
        help="当基础质量指标 readiness 通过时声明正式质量指标结果。",
    )
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    pairs_path = Path(args.pairs)
    output_path = Path(args.out)
    pair_rows = _load_pairs(pairs_path)
    rows = build_quality_metric_rows(pair_rows)
    readiness = _assess_quality_metric_readiness(rows)
    _write_rows(output_path, rows)
    manifest_path = Path(args.manifest) if args.manifest else output_path.parent / "metric_execution_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    formal_result_claim = bool(args.formal_result_claim and readiness["overall_decision"] == "pass")
    manifest = {
        "artifact_name": "metric_execution_manifest.json",
        "producer_id": "ceg_basic_image_quality_metric_runner",
        "producer_role": "real_cpu_image_quality_metric_runner",
        "formal_result_claim": formal_result_claim,
        "metric_rows_path": str(output_path),
        "input_pairs_path": str(pairs_path),
        "pair_count": len(pair_rows),
        "metric_row_count": len(rows),
        "metric_names": BASIC_QUALITY_METRIC_NAMES,
        "advanced_metric_names": [],
        "metric_readiness": readiness,
        "execution_boundary": "basic_image_quality_metrics_internal_cpu_runner",
        "producer_digest": build_stable_digest({"pairs": pair_rows, "rows": rows, "formal_result_claim": formal_result_claim}),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"row_count": len(rows), "output_path": args.out, "manifest_path": str(manifest_path)},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
