"""审计论文实验矩阵与实际 records 的覆盖关系。

该模块只消费已经生成的实验矩阵和事件级 records, 不重新运行 CEG 判定, 也不调用第三方 baseline。
它的作用是把“论文所需的 split、攻击族、主方法、内部消融和外部 baseline 是否已经有结果”变成可机器检查的报告。
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from main.core.digest import build_stable_digest


def load_experiment_matrix_cells(path: str | Path) -> list[dict[str, Any]]:
    """读取由 build_experiment_matrix.py 导出的实验矩阵单元。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise TypeError("experiment matrix must contain a list")
    return [dict(item) for item in payload if isinstance(item, dict)]


def load_event_records(path: str | Path) -> list[dict[str, Any]]:
    """读取 build_paper_outputs.py 写出的 event_records.json。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise TypeError("event records must contain a list")
    return [dict(item) for item in payload if isinstance(item, dict)]


def _record_attack_condition(row: dict[str, Any]) -> str:
    """从 record 中读取稳定的攻击条件字段, 缺失时按攻击族回退。"""
    value = row.get("attack_condition")
    if value:
        return str(value)
    attack_family = str(row.get("attack_family") or "unknown_attack_family")
    return "clean_none" if attack_family == "clean" else attack_family


def _coverage_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    """构造矩阵覆盖匹配键。

    该键只使用 records 中真实存在的维度: split、method_name、sample_role 和 attack_condition。
    profile 是运行级配置, 不存放在每条 record 中, 因此 coverage audit 通过函数参数筛选矩阵 profile。
    """
    return (
        str(row.get("split") or "unknown_split"),
        str(row.get("method_name") or "unknown_method"),
        str(row.get("sample_role") or "unknown_sample_role"),
        _record_attack_condition(row),
    )


def _cell_coverage_key(cell: dict[str, Any]) -> tuple[str, str, str, str]:
    """构造实验矩阵单元的覆盖匹配键。"""
    return (
        str(cell.get("split") or "unknown_split"),
        str(cell.get("method_name") or "unknown_method"),
        str(cell.get("sample_role") or "unknown_sample_role"),
        str(cell.get("attack_condition") or "unknown_attack_condition"),
    )


def _summarize_axis(cells: list[dict[str, Any]], records: list[dict[str, Any]], axis_name: str) -> dict[str, Any]:
    """按单个轴统计 expected、observed 和 missing 值。"""
    expected_values = sorted({str(cell.get(axis_name)) for cell in cells if cell.get(axis_name) is not None})
    if axis_name == "attack_condition":
        observed_values = sorted({_record_attack_condition(row) for row in records})
    else:
        observed_values = sorted({str(row.get(axis_name)) for row in records if row.get(axis_name) is not None})
    missing_values = sorted(set(expected_values) - set(observed_values))
    return {
        "axis_name": axis_name,
        "expected_values": expected_values,
        "observed_values": observed_values,
        "missing_values": missing_values,
        "coverage_rate": (len(set(expected_values) & set(observed_values)) / len(expected_values)) if expected_values else 1.0,
    }


def build_experiment_coverage_report(
    records: Iterable[dict[str, Any]],
    matrix_cells: Iterable[dict[str, Any]],
    *,
    profile: str,
    max_examples: int = 50,
) -> dict[str, Any]:
    """构建实验矩阵覆盖报告。

    通用工程写法是先把预期矩阵和实际 records 投影到同一个稳定键空间, 再计算缺失和额外覆盖。
    项目特定写法在于覆盖轴被固定为图像水印论文需要的 split、method、sample_role 和 attack_condition。
    """
    materialized_records = [dict(row) for row in records]
    materialized_cells = [dict(cell) for cell in matrix_cells if str(cell.get("profile")) == profile]

    expected_by_key: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for cell in materialized_cells:
        expected_by_key[_cell_coverage_key(cell)].append(cell)

    observed_by_key: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in materialized_records:
        observed_by_key[_coverage_key(row)].append(row)

    expected_keys = set(expected_by_key)
    observed_keys = set(observed_by_key)
    missing_keys = sorted(expected_keys - observed_keys)
    unexpected_keys = sorted(observed_keys - expected_keys)
    covered_keys = sorted(expected_keys & observed_keys)

    method_groups = defaultdict(lambda: {"expected_cell_count": 0, "covered_cell_count": 0})
    for key, cells_for_key in expected_by_key.items():
        for cell in cells_for_key:
            group = str(cell.get("method_group") or "unknown_method_group")
            method_groups[group]["expected_cell_count"] += 1
            if key in observed_by_key:
                method_groups[group]["covered_cell_count"] += 1
    method_group_rows = []
    for group, summary in sorted(method_groups.items()):
        expected_count = int(summary["expected_cell_count"])
        covered_count = int(summary["covered_cell_count"])
        method_group_rows.append(
            {
                "method_group": group,
                "expected_cell_count": expected_count,
                "covered_cell_count": covered_count,
                "missing_cell_count": expected_count - covered_count,
                "coverage_rate": covered_count / expected_count if expected_count else 1.0,
            }
        )

    missing_examples = [
        {
            "split": key[0],
            "method_name": key[1],
            "sample_role": key[2],
            "attack_condition": key[3],
            "matrix_cell_ids": [str(cell.get("cell_id")) for cell in expected_by_key[key]],
        }
        for key in missing_keys[:max_examples]
    ]
    unexpected_examples = [
        {
            "split": key[0],
            "method_name": key[1],
            "sample_role": key[2],
            "attack_condition": key[3],
            "record_count": len(observed_by_key[key]),
        }
        for key in unexpected_keys[:max_examples]
    ]
    report = {
        "artifact_name": "paper_experiment_coverage_report.json",
        "profile": profile,
        "overall_decision": "pass" if not missing_keys else "fail",
        "expected_cell_count": sum(len(items) for items in expected_by_key.values()),
        "expected_key_count": len(expected_keys),
        "observed_record_count": len(materialized_records),
        "observed_key_count": len(observed_keys),
        "covered_key_count": len(covered_keys),
        "missing_key_count": len(missing_keys),
        "unexpected_key_count": len(unexpected_keys),
        "coverage_rate": len(covered_keys) / len(expected_keys) if expected_keys else 1.0,
        "axis_coverage": [
            _summarize_axis(materialized_cells, materialized_records, axis_name)
            for axis_name in ("split", "method_name", "sample_role", "attack_condition")
        ],
        "method_group_coverage": method_group_rows,
        "missing_examples": missing_examples,
        "unexpected_examples": unexpected_examples,
    }
    report["coverage_digest"] = build_stable_digest(
        {
            "profile": profile,
            "expected_keys": sorted(["::".join(key) for key in expected_keys]),
            "observed_keys": sorted(["::".join(key) for key in observed_keys]),
        }
    )
    return report
