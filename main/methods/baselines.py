"""定义外部对比 baseline 的干净注册表。

该模块只保存论文对比实验需要的 baseline 身份、职责和预期产物形状。
真实第三方实现应通过 `experiments/` 或外部适配器调用, 不能反向污染
`main/methods/ceg/` 的核心方法逻辑。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class BaselineSpec:
    """描述一个外部对比方法的最小可执行契约。"""

    baseline_id: str
    display_name: str
    method_family: str
    comparison_role: str
    required_record_fields: tuple[str, ...]
    required_artifacts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """转为普通字典, 便于写入 protocol manifest 或测试 fixture。"""
        return asdict(self)


COMMON_BASELINE_RECORD_FIELDS = (
    "event_id",
    "method_name",
    "split",
    "sample_role",
    "attack_family",
    "final_decision",
)


BASELINE_REGISTRY: dict[str, BaselineSpec] = {
    "tree_ring": BaselineSpec(
        baseline_id="tree_ring",
        display_name="Tree-Ring",
        method_family="diffusion_watermark_baseline",
        comparison_role="external_main_table",
        required_record_fields=COMMON_BASELINE_RECORD_FIELDS,
        required_artifacts=("baseline_event_records.jsonl", "baseline_metrics_summary.csv"),
    ),
    "gaussian_shading": BaselineSpec(
        baseline_id="gaussian_shading",
        display_name="Gaussian Shading",
        method_family="diffusion_watermark_baseline",
        comparison_role="external_main_table",
        required_record_fields=COMMON_BASELINE_RECORD_FIELDS,
        required_artifacts=("baseline_event_records.jsonl", "baseline_metrics_summary.csv"),
    ),
    "shallow_diffuse": BaselineSpec(
        baseline_id="shallow_diffuse",
        display_name="Shallow Diffuse",
        method_family="diffusion_watermark_baseline",
        comparison_role="external_main_table",
        required_record_fields=COMMON_BASELINE_RECORD_FIELDS,
        required_artifacts=("baseline_event_records.jsonl", "baseline_metrics_summary.csv"),
    ),
    "t2smark": BaselineSpec(
        baseline_id="t2smark",
        display_name="T2SMark",
        method_family="diffusion_watermark_baseline",
        comparison_role="external_main_table",
        required_record_fields=COMMON_BASELINE_RECORD_FIELDS,
        required_artifacts=("baseline_event_records.jsonl", "baseline_metrics_summary.csv"),
    ),

    "rivagan_invisible_watermark": BaselineSpec(
        baseline_id="rivagan_invisible_watermark",
        display_name="RivaGAN via invisible-watermark",
        method_family="image_watermark_baseline",
        comparison_role="external_supplementary_table",
        required_record_fields=COMMON_BASELINE_RECORD_FIELDS,
        required_artifacts=("baseline_event_records.jsonl", "baseline_metrics_summary.csv"),
    ),
    "wam": BaselineSpec(
        baseline_id="wam",
        display_name="WAM",
        method_family="image_watermark_baseline",
        comparison_role="external_supplementary_table",
        required_record_fields=COMMON_BASELINE_RECORD_FIELDS,
        required_artifacts=("baseline_event_records.jsonl", "baseline_metrics_summary.csv"),
    ),
    "trustmark": BaselineSpec(
        baseline_id="trustmark",
        display_name="TrustMark",
        method_family="image_watermark_baseline",
        comparison_role="external_supplementary_table",
        required_record_fields=COMMON_BASELINE_RECORD_FIELDS,
        required_artifacts=("baseline_event_records.jsonl", "baseline_metrics_summary.csv"),
    ),
}


BASELINE_ALIASES = {
    "tree-ring": "tree_ring",
    "treering": "tree_ring",
    "gaussian-shading": "gaussian_shading",
    "shallow-diffuse": "shallow_diffuse",
    "t2s-mark": "t2smark",
    "t2s_mark": "t2smark",
    "t2s mark": "t2smark",
    "rivagan": "rivagan_invisible_watermark",
    "riva-gan": "rivagan_invisible_watermark",
    "invisible-watermark-rivagan": "rivagan_invisible_watermark",
    "watermark-anything": "wam",
    "watermark_anything": "wam",
    "trust-mark": "trustmark",
}


def normalize_baseline_id(value: str) -> str:
    """将用户或配置中的 baseline 名称规范化为注册表主键。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("baseline id must be non-empty str")
    normalized = value.strip().lower().replace(" ", "_")
    return BASELINE_ALIASES.get(normalized, normalized)


def get_baseline_spec(value: str) -> BaselineSpec:
    """读取 baseline 契约, 未注册时 fail-fast。"""
    baseline_id = normalize_baseline_id(value)
    if baseline_id not in BASELINE_REGISTRY:
        raise KeyError(f"unsupported baseline: {value}")
    return BASELINE_REGISTRY[baseline_id]


def list_baseline_specs() -> tuple[BaselineSpec, ...]:
    """返回稳定排序后的 baseline 契约列表。"""
    return tuple(BASELINE_REGISTRY[key] for key in sorted(BASELINE_REGISTRY))
