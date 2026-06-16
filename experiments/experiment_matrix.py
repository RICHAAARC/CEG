"""构建论文实验矩阵与覆盖率 manifest。

该模块只描述“应该运行哪些实验单元”, 不直接生成图像, 不调用第三方 baseline, 也不写正式结果。
这样做的主要原因是把实验设计和运行实现解耦: 论文需要的 split、攻击家族、方法、消融和 baseline 可以先被审计,
随后再由外部 runner 或集群任务系统逐项消费。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from main.methods.baselines import get_baseline_spec, list_baseline_specs
from main.methods.ceg.ablations import CEG_ABLATIONS
from main.protocol.experiment import ACTIVE_PROFILES, FORMAL_SPLITS


DEFAULT_ATTACK_FAMILIES = (
    "clean",
    "rotation",
    "scale",
    "crop",
    "gaussian_noise",
    "jpeg",
    "blur",
    "color_shift",
)
DEFAULT_ATTACK_LEVELS = ("none", "light", "medium", "strong")
DEFAULT_SAMPLE_ROLES = ("positive_source", "clean_negative", "attacked_negative")
DEFAULT_METHOD_GROUPS = ("ceg_main", "ceg_ablation", "external_baseline")


@dataclass(frozen=True)
class ExperimentAxis:
    """描述实验矩阵中的一个离散轴。

    该结构属于通用工程写法: 用显式轴声明替代散落在脚本中的循环常量, 便于审计覆盖率和后续复用。
    """

    axis_name: str
    values: tuple[str, ...]
    role: str

    def to_dict(self) -> dict[str, Any]:
        """转为普通字典, 便于 JSON manifest 保存。"""
        return asdict(self)


@dataclass(frozen=True)
class ExperimentCell:
    """表示一个可执行或可下发的实验单元。"""

    cell_id: str
    profile: str
    split: str
    method_group: str
    method_name: str
    sample_role: str
    attack_family: str
    attack_level: str
    attack_condition: str
    expected_artifact_family: str

    def to_dict(self) -> dict[str, Any]:
        """转为普通字典, 便于 JSON / JSONL 消费。"""
        return asdict(self)


def _tuple_from_config(config: dict[str, Any], key: str, default: Iterable[str]) -> tuple[str, ...]:
    """从配置中读取字符串序列, 缺省时使用内置论文矩阵。"""
    value = config.get(key, default)
    if not isinstance(value, list | tuple):
        raise TypeError(f"experiment matrix field {key} must be a list")
    output = tuple(str(item) for item in value)
    if not output:
        raise ValueError(f"experiment matrix field {key} must be non-empty")
    return output


def _method_names_for_group(method_group: str) -> tuple[str, ...]:
    """根据方法组展开具体方法名称。"""
    if method_group == "ceg_main":
        return ("ceg",)
    if method_group == "ceg_ablation":
        return tuple(f"ceg_{variant.lower().replace('-', '_')}" for variant in CEG_ABLATIONS)
    if method_group == "external_baseline":
        return tuple(spec.baseline_id for spec in list_baseline_specs())
    raise ValueError(f"unsupported method group: {method_group}")

def _attack_condition(attack_family: str, attack_level: str) -> str:
    """生成统一 attack_condition, 供 records 和图表分层复用。"""
    if attack_family == "clean" or attack_level == "none":
        return "clean_none"
    return f"{attack_family}_{attack_level}"


def build_default_experiment_axes() -> list[ExperimentAxis]:
    """返回论文默认实验矩阵轴。

    这一实现属于项目特定写法: 轴值来自 CEG 论文当前目标, 覆盖图像水印检测、攻击鲁棒性、消融和外部 baseline。
    """
    return [
        ExperimentAxis("profile", tuple(sorted(ACTIVE_PROFILES)), "protocol_profile"),
        ExperimentAxis("split", tuple(sorted(FORMAL_SPLITS)), "data_partition"),
        ExperimentAxis("method_group", DEFAULT_METHOD_GROUPS, "method_family"),
        ExperimentAxis("sample_role", DEFAULT_SAMPLE_ROLES, "label_family"),
        ExperimentAxis("attack_family", DEFAULT_ATTACK_FAMILIES, "robustness_family"),
        ExperimentAxis("attack_level", DEFAULT_ATTACK_LEVELS, "robustness_strength"),
    ]


def expand_experiment_matrix(config: dict[str, Any] | None = None) -> list[ExperimentCell]:
    """展开实验矩阵为单元列表。

    配置可覆盖 profiles、splits、sample_roles、attack_families、attack_levels 和 method_groups。
    返回值不包含真实样本路径, 因为样本清单应由数据准备流程另行绑定。
    """
    config = dict(config or {})
    profiles = _tuple_from_config(config, "profiles", sorted(ACTIVE_PROFILES))
    splits = _tuple_from_config(config, "splits", sorted(FORMAL_SPLITS))
    method_groups = _tuple_from_config(config, "method_groups", DEFAULT_METHOD_GROUPS)
    sample_roles = _tuple_from_config(config, "sample_roles", DEFAULT_SAMPLE_ROLES)
    attack_families = _tuple_from_config(config, "attack_families", DEFAULT_ATTACK_FAMILIES)
    attack_levels = _tuple_from_config(config, "attack_levels", DEFAULT_ATTACK_LEVELS)

    cells: list[ExperimentCell] = []
    for profile in profiles:
        if profile not in ACTIVE_PROFILES:
            raise ValueError(f"unsupported active profile in matrix: {profile}")
        for split in splits:
            if split not in FORMAL_SPLITS:
                raise ValueError(f"unsupported split in matrix: {split}")
            for method_group in method_groups:
                method_names = _method_names_for_group(method_group)
                for method_name in method_names:
                    if method_group == "external_baseline":
                        get_baseline_spec(method_name)
                    for sample_role in sample_roles:
                        for attack_family in attack_families:
                            for attack_level in attack_levels:
                                if attack_family == "clean" and attack_level != "none":
                                    continue
                                if attack_family != "clean" and attack_level == "none":
                                    continue
                                attack_condition = _attack_condition(attack_family, attack_level)
                                cell_id = "__".join(
                                    [
                                        profile,
                                        split,
                                        method_group,
                                        method_name,
                                        sample_role,
                                        attack_condition,
                                    ]
                                )
                                expected_family = (
                                    "ceg_event_records" if method_group == "ceg_ablation" else "baseline_observations"
                                )
                                cells.append(
                                    ExperimentCell(
                                        cell_id=cell_id,
                                        profile=profile,
                                        split=split,
                                        method_group=method_group,
                                        method_name=method_name,
                                        sample_role=sample_role,
                                        attack_family=attack_family,
                                        attack_level=attack_level,
                                        attack_condition=attack_condition,
                                        expected_artifact_family=expected_family,
                                    )
                                )
    return cells


def load_experiment_matrix_config(path: str | Path) -> dict[str, Any]:
    """读取 JSON 实验矩阵配置。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("experiment matrix config must contain an object")
    return dict(payload)


def build_experiment_matrix_manifest(cells: list[ExperimentCell]) -> dict[str, Any]:
    """构建实验矩阵 manifest, 用于审计覆盖范围。"""
    method_groups = sorted({cell.method_group for cell in cells})
    attack_families = sorted({cell.attack_family for cell in cells})
    sample_roles = sorted({cell.sample_role for cell in cells})
    return {
        "artifact_name": "experiment_matrix_manifest.json",
        "cell_count": len(cells),
        "method_groups": method_groups,
        "attack_families": attack_families,
        "sample_roles": sample_roles,
        "profiles": sorted({cell.profile for cell in cells}),
        "splits": sorted({cell.split for cell in cells}),
        "cells": [cell.to_dict() for cell in cells],
    }


def write_experiment_matrix(output_root: str | Path, cells: list[ExperimentCell]) -> dict[str, Any]:
    """写出实验矩阵 JSON 和 manifest。"""
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    manifest = build_experiment_matrix_manifest(cells)
    (output_path / "experiment_matrix.json").write_text(
        json.dumps([cell.to_dict() for cell in cells], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_path / "experiment_matrix_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
