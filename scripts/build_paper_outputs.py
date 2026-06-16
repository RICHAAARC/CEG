"""一键构建 CEG 论文 records、表格、指标、图表、HTML、PDF 和 LaTeX 表格。"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.baseline_file_adapter import load_baseline_observation_rows
from experiments.metric_file_adapter import load_metric_rows, merge_metric_rows_into_records
from experiments.experiment_coverage import build_experiment_coverage_report, load_experiment_matrix_cells
from experiments.protocol_runner import run_paper_protocol
from main.analysis.image_examples import export_image_example_package
from main.analysis.latex_tables import write_latex_tables
from main.analysis.pdf_figures import render_figure_specs_pdf_package
from main.analysis.paper_readiness import load_paper_output_requirements, write_paper_readiness_report
from main.analysis.paper_report import write_paper_results_report
from main.analysis.rebuild_artifacts import build_all_paper_artifacts, write_artifact_bundle
from main.analysis.render_figures import render_paper_figure_package


def _load_json_list(path: Path) -> list[dict[str, object]]:
    """读取 JSON 数组。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise TypeError("events file must contain list")
    return [dict(item) for item in payload]


def _load_json_rows(path: Path) -> list[dict[str, object]]:
    """读取 JSON 数组行文件。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise TypeError("row file must contain list")
    return [dict(item) for item in payload]


def _load_json_dict(path: Path) -> dict[str, float]:
    """读取 method_name 到 content_threshold 的 JSON 映射。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("thresholds file must contain dict")
    return {str(key): float(value) for key, value in payload.items()}


def _copy_optional_manifest(source: str | None, output_root: Path, file_name: str) -> str | None:
    """把可选外部 manifest 复制到 image_manifests 目录。"""
    if source is None:
        return None
    source_path = Path(source)
    target = output_root / "image_manifests" / file_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)
    return f"image_manifests/{file_name}"


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="构建 CEG 论文完整输出目录。")
    parser.add_argument("--events", required=True, help="事件 JSON 数组路径。")
    parser.add_argument("--thresholds", required=True, help="method_name 到 content_threshold 的 JSON 映射。")
    parser.add_argument("--baseline-observations", default=None, help="可选 baseline observation 文件。")
    parser.add_argument("--metric-rows", default=None, help="可选高级指标文件, 支持 JSON / JSONL / CSV。")
    parser.add_argument("--attacked-image-manifest", default=None, help="可选 attacked_image_manifest.json 路径。")
    parser.add_argument("--attack-shard-manifest", default=None, help="可选 attack_shard_manifest.json 路径。")
    parser.add_argument("--image-pairs", default=None, help="可选 image_pairs 文件, 用于导出 image_manifests 和 image_examples。")
    parser.add_argument("--experiment-matrix", default=None, help="可选 experiment_matrix.json, 用于生成论文实验覆盖率报告。")
    parser.add_argument("--require-experiment-coverage", action="store_true", help="实验矩阵覆盖率未通过时返回非零退出码。")
    parser.add_argument("--profile", default="paper_main_probe")
    parser.add_argument("--readiness-requirements", default=None, help="可选 paper output requirements JSON。")
    parser.add_argument("--require-paper-readiness", action="store_true", help="readiness 未通过时返回失败退出码。")
    parser.add_argument("--out", required=True, help="输出目录。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    baseline_rows = load_baseline_observation_rows(Path(args.baseline_observations)) if args.baseline_observations else None
    content_thresholds = _load_json_dict(Path(args.thresholds))
    result = run_paper_protocol(
        _load_json_list(Path(args.events)),
        profile=args.profile,
        content_thresholds=content_thresholds,
        baseline_observation_rows=baseline_rows,
    )
    if args.metric_rows:
        merged_records = merge_metric_rows_into_records(result["records"], load_metric_rows(Path(args.metric_rows)))
        result["records"] = merged_records
        result["all_paper_artifacts"] = build_all_paper_artifacts(merged_records, content_thresholds=content_thresholds)
    coverage_report = None
    if args.experiment_matrix:
        coverage_report = build_experiment_coverage_report(
            result["records"],
            load_experiment_matrix_cells(Path(args.experiment_matrix)),
            profile=args.profile,
        )
        result["all_paper_artifacts"]["paper_experiment_coverage_report.json"] = coverage_report
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    image_example_manifest = None
    if args.image_pairs:
        image_example_manifest = export_image_example_package(_load_json_rows(Path(args.image_pairs)), output_root)
    attacked_image_manifest_path = _copy_optional_manifest(args.attacked_image_manifest, output_root, "attacked_image_manifest.json")
    attack_shard_manifest_path = _copy_optional_manifest(args.attack_shard_manifest, output_root, "attack_shard_manifest.json")
    (output_root / "event_records.json").write_text(
        json.dumps(result["records"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    artifact_manifest = write_artifact_bundle(output_root / "artifacts", result["all_paper_artifacts"])
    rendered_manifest = render_paper_figure_package(
        result["all_paper_artifacts"]["paper_figure_specs.json"],
        output_root / "rendered_figures",
    )
    latex_manifest = write_latex_tables(output_root / "latex_tables", result["all_paper_artifacts"])
    pdf_manifest = render_figure_specs_pdf_package(
        result["all_paper_artifacts"]["paper_figure_specs.json"],
        output_root / "pdf_figures",
    )
    summary = {
        "profile": result["profile"],
        "record_count": len(result["records"]),
        "artifact_manifest_path": "artifacts/artifact_manifest.json",
        "rendered_figures_manifest_path": "rendered_figures/rendered_paper_figures_manifest.json",
        "artifact_count": len(artifact_manifest["artifact_names"]),
        "figure_count": rendered_manifest["figure_count"],
        "latex_tables_manifest_path": "latex_tables/latex_tables_manifest.json",
        "latex_table_count": latex_manifest["table_count"],
        "pdf_figures_manifest_path": "pdf_figures/paper_figures_pdf_manifest.json",
        "pdf_figure_count": pdf_manifest["figure_count"],
        "experiment_coverage_report_path": "artifacts/paper_experiment_coverage_report.json" if coverage_report else None,
        "experiment_coverage_decision": coverage_report["overall_decision"] if coverage_report else None,
        "image_generation_manifest_path": "image_manifests/image_generation_manifest.json" if image_example_manifest else None,
        "image_pair_manifest_path": "image_manifests/image_pair_manifest.json" if image_example_manifest else None,
        "image_example_manifest_path": "image_examples/image_example_manifest.json" if image_example_manifest else None,
        "image_example_count": image_example_manifest["example_count"] if image_example_manifest else None,
        "attacked_image_manifest_path": attacked_image_manifest_path,
        "attack_shard_manifest_path": attack_shard_manifest_path,
    }
    summary_path = output_root / "paper_outputs_summary.json"
    summary["paper_results_report_path"] = "paper_results_report.md"
    summary["paper_results_report_manifest_path"] = "paper_results_report_manifest.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_paper_results_report(output_root)
    readiness_requirements = (
        load_paper_output_requirements(args.readiness_requirements) if args.readiness_requirements else None
    )
    readiness_report = write_paper_readiness_report(output_root, requirements=readiness_requirements)
    summary["paper_readiness_report_path"] = "paper_readiness_report.json"
    summary["paper_readiness_decision"] = readiness_report["overall_decision"]
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_paper_results_report(output_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.require_paper_readiness and readiness_report["overall_decision"] != "pass":
        raise SystemExit(1)
    if args.require_experiment_coverage and coverage_report is None:
        raise SystemExit(1)
    if args.require_experiment_coverage and coverage_report and coverage_report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
