"""生成论文图表规格和图表数据。

该模块输出的是可审计的 figure spec JSON, 而不是直接渲染后的图片。
后续可以由 Matplotlib、Vega-Lite、网页前端或 LaTeX 流程消费这些规格。
"""

from __future__ import annotations

from typing import Any, Iterable

from main.analysis.aggregation import aggregate_decision_rows
from main.analysis.detection_curves import build_detection_roc_curve_table, build_score_histogram_table
from main.analysis.uncertainty import build_rate_confidence_interval_table
from main.analysis.standard_metrics import (
    aggregate_standard_watermark_metrics,
    build_attack_family_metrics_table,
    build_bit_recovery_table,
    build_quality_metrics_table,
)


def _figure_spec(
    *,
    figure_id: str,
    title: str,
    chart_type: str,
    data: list[dict[str, Any]],
    encodings: dict[str, Any],
    takeaway: str,
) -> dict[str, Any]:
    """构造统一图表规格, 让图表说明、数据和编码绑定在一起。"""
    return {
        "figure_id": figure_id,
        "title": title,
        "chart_type": chart_type,
        "takeaway": takeaway,
        "data": data,
        "encodings": encodings,
    }


def _main_performance_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """把主检测指标展开成长表, 适合 grouped bar 或 point chart。"""
    summaries = aggregate_decision_rows(rows)
    output_rows: list[dict[str, Any]] = []
    for method_name, summary in sorted(summaries.items()):
        for metric_name in ("tpr", "clean_fpr", "attacked_negative_fpr"):
            output_rows.append(
                {
                    "method_name": method_name,
                    "metric_name": metric_name,
                    "metric_value": summary[metric_name],
                }
            )
    return output_rows


def _rescue_ablation_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """提取 rescue 与消融贡献数据, 用于机制柱状图。"""
    summaries = aggregate_decision_rows(rows)
    output_rows: list[dict[str, Any]] = []
    for method_name, summary in sorted(summaries.items()):
        if not method_name.startswith("ceg"):
            continue
        output_rows.append(
            {
                "method_name": method_name,
                "positive_by_content_count": summary["positive_by_content_count"],
                "positive_by_geo_rescue_count": summary["positive_by_geo_rescue_count"],
                "rescue_eligible_event_count": summary["rescue_eligible_event_count"],
                "rescue_gain": summary["rescue_gain"],
            }
        )
    return output_rows


def _quality_tradeoff_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并检测性能与质量指标, 支持质量-鲁棒性权衡图。"""
    standard_metrics = aggregate_standard_watermark_metrics(rows)["by_method"]
    output_rows: list[dict[str, Any]] = []
    for method_name, summary in sorted(standard_metrics.items()):
        quality_metrics = summary["quality_metrics"]
        output_rows.append(
            {
                "method_name": method_name,
                "tpr": summary["tpr"],
                "clean_fpr": summary["clean_fpr"],
                "detection_auroc": summary["detection_auroc"],
                "bit_accuracy": summary["bit_accuracy"],
                "psnr": quality_metrics["psnr"]["mean"],
                "ssim": quality_metrics["ssim"]["mean"],
                "lpips": quality_metrics["lpips"]["mean"],
                "fid": quality_metrics["fid"]["mean"],
                "clip_score": quality_metrics["clip_score"]["mean"],
            }
        )
    return output_rows


def build_paper_figure_specs(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """从统一 records 生成论文图表规格集合。"""
    materialized = [dict(row) for row in rows]
    figures = [
        _figure_spec(
            figure_id="main_detection_comparison",
            title="主检测性能对比",
            chart_type="grouped_bar",
            data=_main_performance_rows(materialized),
            encodings={"x": "method_name", "y": "metric_value", "color": "metric_name"},
            takeaway="比较 CEG、内部消融和外部 baseline 的 TPR 与 FPR。",
        ),
        _figure_spec(
            figure_id="rescue_ablation_contribution",
            title="几何救回与消融贡献",
            chart_type="stacked_or_grouped_bar",
            data=_rescue_ablation_rows(materialized),
            encodings={"x": "method_name", "y": "rescue_gain", "detail": ["positive_by_content_count", "positive_by_geo_rescue_count"]},
            takeaway="显示 geometry rescue 相对 content-only 的独立贡献。",
        ),
        _figure_spec(
            figure_id="quality_detection_tradeoff",
            title="图像质量与检测性能权衡",
            chart_type="scatter_or_small_multiples",
            data=_quality_tradeoff_rows(materialized),
            encodings={"x": "psnr", "y": "tpr", "color": "method_name", "size": "bit_accuracy"},
            takeaway="展示水印检测性能与图像质量指标之间的折中关系。",
        ),
        _figure_spec(
            figure_id="attack_family_robustness",
            title="攻击家族鲁棒性分层",
            chart_type="heatmap_or_grouped_bar",
            data=build_attack_family_metrics_table(materialized),
            encodings={"x": "attack_family", "y": "method_name", "color": "tpr"},
            takeaway="按旋转、缩放、裁剪、噪声等攻击家族比较鲁棒性。",
        ),
        _figure_spec(
            figure_id="detection_roc_curves",
            title="检测 ROC 曲线",
            chart_type="line",
            data=build_detection_roc_curve_table(materialized),
            encodings={"x": "fpr", "y": "tpr", "color": "method_name", "detail": "threshold_value"},
            takeaway="展示各方法在阈值扫描下的 TPR-FPR 曲线, 支撑 AUROC 和 operating point 解读。",
        ),
        _figure_spec(
            figure_id="score_distribution_by_method",
            title="检测分数分布",
            chart_type="stacked_histogram",
            data=build_score_histogram_table(materialized),
            encodings={"x": "score_bin_lower", "y": "score_bin_count", "color": "label_name", "facet": "method_name"},
            takeaway="对比水印样本与负样本的检测分数分布, 用于解释阈值选择和分布重叠。",
        ),
        _figure_spec(
            figure_id="detection_confidence_intervals",
            title="检测率指标置信区间",
            chart_type="interval_bar",
            data=build_rate_confidence_interval_table(materialized),
            encodings={"x": "method_name", "y": "rate_value", "color": "metric_name", "y_lower": "ci_lower", "y_upper": "ci_upper"},
            takeaway="展示 TPR 与 FPR 估计值的 Wilson 95% 置信区间, 避免只报告点估计。",
        ),
        _figure_spec(
            figure_id="bit_recovery_comparison",
            title="Payload bit 恢复能力对比",
            chart_type="bar",
            data=build_bit_recovery_table(materialized),
            encodings={"x": "method_name", "y": "bit_accuracy"},
            takeaway="比较 CEG 与 baseline 的 bit-level 恢复质量。",
        ),
    ]
    return {
        "artifact_name": "paper_figure_specs.json",
        "figure_count": len(figures),
        "figures": figures,
        "supporting_tables": {
            "quality_metrics_summary.csv": build_quality_metrics_table(materialized),
            "bit_recovery_metrics.csv": build_bit_recovery_table(materialized),
            "attack_family_metrics.csv": build_attack_family_metrics_table(materialized),
        },
    }

