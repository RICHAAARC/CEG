"""构建论文声明与受治理产物之间的审计映射。

该模块属于 artifact rebuild 层, 只读取已经由 records 重建出来的 artifact payload。
它不新增方法结论, 也不把临时文字声明伪装成正式结果; 它的作用是检查每一类论文可陈述结论是否有明确的表格、图表或指标产物支撑。
"""

from __future__ import annotations

from typing import Any, Iterable

REQUIRED_METHODS = (
    "ceg",
    "ceg_full",
    "ceg_content_only",
    "ceg_recover_then_content",
    "ceg_no_rescue",
    "ceg_no_attestation",
    "tree_ring",
    "gaussian_shading",
    "shallow_diffuse",
    "stable_signature_dee",
)

INTERNAL_METHODS = (
    "ceg",
    "ceg_full",
    "ceg_content_only",
    "ceg_recover_then_content",
    "ceg_no_rescue",
    "ceg_no_attestation",
)

EXTERNAL_BASELINES = (
    "tree_ring",
    "gaussian_shading",
    "shallow_diffuse",
    "stable_signature_dee",
)

REQUIRED_FIGURES = (
    "main_detection_comparison",
    "rescue_ablation_contribution",
    "quality_detection_tradeoff",
    "attack_family_robustness",
    "detection_roc_curves",
    "score_distribution_by_method",
    "detection_confidence_intervals",
    "bit_recovery_comparison",
)

CLAIM_CONTRACTS = (
    {
        "claim_id": "formal_detection_performance_supported",
        "claim_text": "formal final decision 的 TPR、clean FPR 和 attacked-negative FPR 可由受治理 records 重建。",
        "supporting_artifacts": ("formal_final_decision_metrics.json", "formal_main_table.csv"),
        "supporting_methods": REQUIRED_METHODS,
    },
    {
        "claim_id": "internal_ablation_comparison_supported",
        "claim_text": "CEG 主方法与内部机制消融之间的差异可由机制表和成对差值表支撑。",
        "supporting_artifacts": ("rescue_metrics_summary.csv", "method_pairwise_delta_table.csv"),
        "supporting_methods": INTERNAL_METHODS,
    },
    {
        "claim_id": "external_baseline_comparison_supported",
        "claim_text": "Tree-Ring、Gaussian Shading、Shallow Diffuse 和 Stable Signature DEE 外部 baseline 对比可由 baseline 表支撑。",
        "supporting_artifacts": ("baseline_comparison_table.csv", "standard_watermark_metrics.json"),
        "supporting_methods": EXTERNAL_BASELINES,
    },
    {
        "claim_id": "standard_watermark_metrics_supported",
        "claim_text": "图像水印标准评价指标、bit 恢复、质量指标和攻击族鲁棒性均有独立产物支撑。",
        "supporting_artifacts": (
            "standard_watermark_metrics.json",
            "quality_metrics_summary.csv",
            "bit_recovery_metrics.csv",
            "attack_family_metrics.csv",
        ),
        "supporting_methods": REQUIRED_METHODS,
    },
    {
        "claim_id": "detection_curve_and_uncertainty_supported",
        "claim_text": "检测曲线、score 分布、operating point 和置信区间可由表格产物复核。",
        "supporting_artifacts": (
            "detection_roc_curve.csv",
            "score_histogram_table.csv",
            "operating_point_table.csv",
            "rate_confidence_intervals.csv",
        ),
        "supporting_methods": REQUIRED_METHODS,
    },
    {
        "claim_id": "paper_figures_supported",
        "claim_text": "论文核心图表均由 paper_figure_specs.json 中的稳定 figure_id 定义。",
        "supporting_artifacts": ("paper_figure_specs.json",),
        "supporting_figures": REQUIRED_FIGURES,
    },
)


def _materialize_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """固化 records 列表, 并显式拒绝非 dict 行。"""
    materialized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("all rows must be dict")
        materialized.append(dict(row))
    return materialized


def _artifact_names(artifacts: dict[str, Any]) -> set[str]:
    """提取 artifact 字典中的产物名集合。"""
    return {str(name) for name in artifacts}


def _present_methods(rows: list[dict[str, Any]]) -> set[str]:
    """从 records 中提取已经覆盖的方法名。"""
    return {str(row.get("method_name")) for row in rows if row.get("method_name") is not None}


def _present_figure_ids(artifacts: dict[str, Any]) -> set[str]:
    """从 paper_figure_specs.json payload 中提取 figure_id 集合。"""
    payload = artifacts.get("paper_figure_specs.json")
    if not isinstance(payload, dict):
        return set()
    figures = payload.get("figures", [])
    if not isinstance(figures, list):
        return set()
    return {str(item.get("figure_id")) for item in figures if isinstance(item, dict) and item.get("figure_id")}


def _non_empty_artifact_names(artifacts: dict[str, Any]) -> set[str]:
    """判断 artifact payload 是否非空, 用于防止空表支撑论文声明。"""
    present: set[str] = set()
    for name, payload in artifacts.items():
        if isinstance(payload, dict) and payload:
            present.add(str(name))
        elif isinstance(payload, list) and payload:
            present.add(str(name))
        elif isinstance(payload, str) and payload.strip():
            present.add(str(name))
    return present


def _evaluate_claim(contract: dict[str, Any], rows: list[dict[str, Any]], artifacts: dict[str, Any]) -> dict[str, Any]:
    """评估单个 claim contract 是否已经有足够的受治理证据。"""
    artifact_names = _artifact_names(artifacts)
    non_empty_artifacts = _non_empty_artifact_names(artifacts)
    present_methods = _present_methods(rows)
    present_figures = _present_figure_ids(artifacts)

    required_artifacts = tuple(str(item) for item in contract.get("supporting_artifacts", ()))
    required_methods = tuple(str(item) for item in contract.get("supporting_methods", ()))
    required_figures = tuple(str(item) for item in contract.get("supporting_figures", ()))

    missing_artifacts = sorted(set(required_artifacts) - artifact_names)
    empty_artifacts = sorted(set(required_artifacts) - non_empty_artifacts - set(missing_artifacts))
    missing_methods = sorted(set(required_methods) - present_methods)
    missing_figures = sorted(set(required_figures) - present_figures)
    status = "fail" if missing_artifacts or empty_artifacts or missing_methods or missing_figures else "pass"

    return {
        "claim_id": str(contract["claim_id"]),
        "claim_text": str(contract["claim_text"]),
        "status": status,
        "supporting_artifacts": list(required_artifacts),
        "supporting_methods": list(required_methods),
        "supporting_figures": list(required_figures),
        "missing_artifacts": missing_artifacts,
        "empty_artifacts": empty_artifacts,
        "missing_methods": missing_methods,
        "missing_figures": missing_figures,
    }


def build_paper_claim_audit(rows: Iterable[dict[str, Any]], artifacts: dict[str, Any]) -> dict[str, Any]:
    """构建论文声明支撑关系审计报告。"""
    materialized = _materialize_rows(rows)
    claim_results = [_evaluate_claim(dict(contract), materialized, artifacts) for contract in CLAIM_CONTRACTS]
    fail_count = sum(1 for claim in claim_results if claim["status"] != "pass")
    return {
        "artifact_name": "paper_claim_audit.json",
        "overall_decision": "fail" if fail_count else "pass",
        "claim_count": len(claim_results),
        "supported_claim_count": len(claim_results) - fail_count,
        "failed_claim_count": fail_count,
        "claims": claim_results,
    }
