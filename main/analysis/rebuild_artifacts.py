"""从事件 records 重建论文结果产物。

该模块属于产物重建层, 不实现 CEG 方法判定本身。它只消费已经生成的事件级 records,
产出可审计的 JSON / CSV / 图表规格结构, 从而保证论文表格、指标和图表可以由 records
重复生成, 而不是手工拼接。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from main.analysis.aggregation import aggregate_decision_rows
from main.analysis.claim_audit import build_paper_claim_audit
from main.analysis.detection_curves import build_detection_curve_artifacts
from main.analysis.figure_specs import build_paper_figure_specs
from main.analysis.fixed_fpr import build_fixed_fpr_artifacts
from main.analysis.standard_metrics import (
    aggregate_standard_watermark_metrics,
    build_attack_family_metrics_table,
    build_bit_recovery_table,
    build_quality_metrics_table,
)
from main.core.digest import build_stable_digest
from main.analysis.uncertainty import build_uncertainty_artifacts


PW02_ARTIFACT_NAMES = (
    "formal_final_decision_metrics.json",
    "content_score_distribution_audit.json",
    "content_threshold_degeneracy_report.json",
)

PW04_ARTIFACT_NAMES = (
    "formal_main_table.csv",
    "rescue_metrics_summary.csv",
    "baseline_comparison_table.csv",
    "method_group_comparison_table.csv",
)

PW05_STANDARD_METRIC_ARTIFACT_NAMES = (
    "standard_watermark_metrics.json",
    "quality_metrics_summary.csv",
    "bit_recovery_metrics.csv",
    "attack_family_metrics.csv",
)

PW06_FIGURE_ARTIFACT_NAMES = (
    "paper_figure_specs.json",
)

PW07_UNCERTAINTY_ARTIFACT_NAMES = (
    "rate_confidence_intervals.csv",
    "method_pairwise_delta_table.csv",
)

PW08_DETECTION_CURVE_ARTIFACT_NAMES = (
    "detection_roc_curve.csv",
    "score_histogram_table.csv",
    "operating_point_table.csv",
)

PW09_CLAIM_AUDIT_ARTIFACT_NAMES = (
    "paper_claim_audit.json",
)

PW10_FIXED_FPR_ARTIFACT_NAMES = (
    "fixed_fpr_threshold_table.csv",
    "tpr_at_fixed_fpr_table.csv",
    "attack_tpr_at_fixed_fpr_table.csv",
)


def _materialize_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """把可迭代 records 固化为列表, 并校验每一行都是字典。"""
    materialized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("all rows must be dict")
        materialized.append(row)
    return materialized


def _score_stats(values: list[float]) -> dict[str, Any]:
    """计算内容分数分布摘要, 缺失分数时显式返回 coverage 0。"""
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
    }


def build_content_score_distribution_audit(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """按 method / sample_role 汇总 content_score_raw 分布。"""
    materialized = _materialize_rows(rows)
    groups: dict[tuple[str, str], list[float]] = {}
    total_by_group: dict[tuple[str, str], int] = {}
    for row in materialized:
        key = (str(row.get("method_name") or "unknown_method"), str(row.get("sample_role") or "unknown_role"))
        total_by_group[key] = total_by_group.get(key, 0) + 1
        score = row.get("content_score_raw")
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            groups.setdefault(key, []).append(float(score))
    by_group: dict[str, dict[str, Any]] = {}
    for key, total_count in sorted(total_by_group.items()):
        values = groups.get(key, [])
        stats = _score_stats(values)
        stats["score_coverage_rate"] = len(values) / total_count if total_count else 0.0
        by_group[f"{key[0]}::{key[1]}"] = stats
    return {"artifact_name": "content_score_distribution_audit.json", "by_group": by_group}


def build_threshold_degeneracy_report(
    rows: Iterable[dict[str, Any]],
    *,
    content_thresholds: dict[str, float],
) -> dict[str, Any]:
    """检查 paper_main clean-side 阈值是否出现退化或正负重叠。"""
    materialized = _materialize_rows(rows)
    methods = sorted({str(row.get("method_name") or "unknown_method") for row in materialized})
    reports: dict[str, dict[str, Any]] = {}
    for method_name in methods:
        method_rows = [row for row in materialized if str(row.get("method_name") or "unknown_method") == method_name]
        positive_scores = [
            float(row["content_score_raw"])
            for row in method_rows
            if row.get("sample_role") == "positive_source" and isinstance(row.get("content_score_raw"), (int, float))
        ]
        clean_scores = [
            float(row["content_score_raw"])
            for row in method_rows
            if row.get("sample_role") == "clean_negative" and isinstance(row.get("content_score_raw"), (int, float))
        ]
        threshold = float(content_thresholds.get(method_name, 0.0))
        overlap = bool(positive_scores and clean_scores and min(positive_scores) <= max(clean_scores))
        degenerate = not clean_scores or not positive_scores or overlap
        if not clean_scores:
            reason = "clean_negative_scores_missing"
        elif not positive_scores:
            reason = "positive_scores_missing"
        elif overlap:
            reason = "positive_clean_score_overlap"
        else:
            reason = "none"
        reports[method_name] = {
            "content_threshold_value": threshold,
            "content_threshold_degenerate": degenerate,
            "content_threshold_degenerate_reason": reason,
            "score_distribution_overlap_indicator": overlap,
            "positive_score_min": min(positive_scores) if positive_scores else None,
            "clean_negative_score_max": max(clean_scores) if clean_scores else None,
        }
    return {"artifact_name": "content_threshold_degeneracy_report.json", "by_method": reports}


def build_formal_final_decision_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """重建 final-level 主指标摘要。"""
    return {
        "artifact_name": "formal_final_decision_metrics.json",
        "by_method": aggregate_decision_rows(rows),
    }


def build_pw02_artifacts(
    rows: Iterable[dict[str, Any]],
    *,
    content_thresholds: dict[str, float],
) -> dict[str, Any]:
    """构造 PW02 等价产物集合。"""
    materialized = _materialize_rows(rows)
    return {
        "formal_final_decision_metrics.json": build_formal_final_decision_metrics(materialized),
        "content_score_distribution_audit.json": build_content_score_distribution_audit(materialized),
        "content_threshold_degeneracy_report.json": build_threshold_degeneracy_report(
            materialized,
            content_thresholds=content_thresholds,
        ),
    }


def classify_method_group(method_name: str) -> dict[str, str]:
    """把方法名映射为论文对比组别, 便于区分主方法、内部消融和外部 baseline。

    这一实现属于项目特定写法: 它不改变任何检测算法, 只为论文表格和图表提供稳定分组语义。
    在其他项目中可复用的部分是“先生成统一 records, 再按方法身份附加分组标签”的 artifact 重建模式。
    """
    if method_name == "ceg":
        return {"method_group": "ceg_primary", "comparison_role": "proposed_method"}
    if method_name.startswith("ceg_"):
        return {"method_group": "ceg_internal_ablation", "comparison_role": "mechanism_ablation"}
    return {"method_group": "external_baseline", "comparison_role": "external_comparison"}


def build_pw04_tables(rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """构造 PW04 等价表格集合。"""
    summaries = aggregate_decision_rows(rows)
    formal_main_rows = []
    rescue_rows = []
    baseline_rows = []
    method_group_rows = []
    for method_name, summary in summaries.items():
        group_info = classify_method_group(method_name)
        formal_main_rows.append(
            {
                "method_name": method_name,
                "tpr": summary["tpr"],
                "clean_fpr": summary["clean_fpr"],
                "attacked_negative_fpr": summary["attacked_negative_fpr"],
                "final_positive_count": summary["final_positive_count"],
                "final_negative_count": summary["final_negative_count"],
            }
        )
        rescue_rows.append(
            {
                "method_name": method_name,
                "content_failed_subset_event_count": summary["content_failed_subset_event_count"],
                "rescue_eligible_event_count": summary["rescue_eligible_event_count"],
                "geo_rescue_applied_event_count": summary["geo_rescue_applied_event_count"],
                "positive_by_content_count": summary["positive_by_content_count"],
                "positive_by_geo_rescue_count": summary["positive_by_geo_rescue_count"],
                "rescue_gain": summary["rescue_gain"],
            }
        )
        baseline_rows.append(
            {
                "method_name": method_name,
                "event_count": summary["event_count"],
                "tpr": summary["tpr"],
                "clean_fpr": summary["clean_fpr"],
            }
        )
        method_group_rows.append(
            {
                "method_name": method_name,
                "method_group": group_info["method_group"],
                "comparison_role": group_info["comparison_role"],
                "event_count": summary["event_count"],
                "tpr": summary["tpr"],
                "clean_fpr": summary["clean_fpr"],
                "attacked_negative_fpr": summary["attacked_negative_fpr"],
                "rescue_gain": summary["rescue_gain"],
            }
        )
    return {
        "formal_main_table.csv": formal_main_rows,
        "rescue_metrics_summary.csv": rescue_rows,
        "baseline_comparison_table.csv": baseline_rows,
        "method_group_comparison_table.csv": method_group_rows,
    }


def build_standard_metric_artifacts(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """构造图像水印论文常用标准指标产物。"""
    materialized = _materialize_rows(rows)
    return {
        "standard_watermark_metrics.json": aggregate_standard_watermark_metrics(materialized),
        "quality_metrics_summary.csv": build_quality_metrics_table(materialized),
        "bit_recovery_metrics.csv": build_bit_recovery_table(materialized),
        "attack_family_metrics.csv": build_attack_family_metrics_table(materialized),
    }


def build_figure_artifacts(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """构造论文图表规格产物, 让图表可以由 records 可重复生成。"""
    materialized = _materialize_rows(rows)
    return {"paper_figure_specs.json": build_paper_figure_specs(materialized)}


def build_claim_audit_artifact(rows: Iterable[dict[str, Any]], artifacts: dict[str, Any]) -> dict[str, Any]:
    """构造 supported claims 到受治理产物的审计报告。"""
    materialized = _materialize_rows(rows)
    return {"paper_claim_audit.json": build_paper_claim_audit(materialized, artifacts)}


def build_all_paper_artifacts(
    rows: Iterable[dict[str, Any]],
    *,
    content_thresholds: dict[str, float],
) -> dict[str, Any]:
    """一次性构造论文所需的主指标、标准水印指标、机制表和图表规格。"""
    materialized = _materialize_rows(rows)
    artifacts = {
        **build_pw02_artifacts(materialized, content_thresholds=content_thresholds),
        **build_pw04_tables(materialized),
        **build_standard_metric_artifacts(materialized),
        **build_uncertainty_artifacts(materialized),
        **build_detection_curve_artifacts(materialized),
        **build_fixed_fpr_artifacts(materialized),
        **build_figure_artifacts(materialized),
    }
    artifacts.update(build_claim_audit_artifact(materialized, artifacts))
    return artifacts


def write_artifact_bundle(
    output_root: str | Path,
    artifacts: dict[str, Any],
    *,
    manifest_name: str = "artifact_manifest.json",
) -> dict[str, Any]:
    """将 JSON / CSV / JSONL 产物写入指定目录并生成 manifest。"""
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    written_paths: list[str] = []
    for artifact_name, payload in artifacts.items():
        target = output_path / artifact_name
        target.parent.mkdir(parents=True, exist_ok=True)
        if artifact_name.endswith(".json"):
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif artifact_name.endswith(".jsonl"):
            if not isinstance(payload, list):
                raise TypeError(f"jsonl artifact must be list: {artifact_name}")
            target.write_text(
                "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in payload),
                encoding="utf-8",
            )
        elif artifact_name.endswith(".csv"):
            if not isinstance(payload, list):
                raise TypeError(f"csv artifact must be list[dict]: {artifact_name}")
            fieldnames = sorted({key for row in payload if isinstance(row, dict) for key in row})
            with target.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for row in payload:
                    writer.writerow(row)
        else:
            raise ValueError(f"unsupported artifact extension: {artifact_name}")
        written_paths.append(target.name)
    manifest = {
        "manifest_name": manifest_name,
        "artifact_names": sorted(written_paths),
        "artifact_digest": build_stable_digest({name: artifacts[name] for name in sorted(artifacts)}),
    }
    (output_path / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest

