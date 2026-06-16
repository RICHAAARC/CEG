"""定义 CEG 论文实验协议的最小数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ACTIVE_PROFILES = frozenset(
    {
        "paper_main_probe",
        "paper_main_pilot",
        "paper_main_full",
        "paper_mechanism_geo_search",
        "paper_mechanism_quickcheck",
        "paper_mechanism_pilot",
    }
)

PAPER_MAIN_SAMPLE_ROLES = frozenset({"positive_source", "clean_negative"})
FORMAL_SPLITS = frozenset({"dev", "calibration", "test"})
MECHANISM_ABLATIONS = (
    "Full",
    "Content-only",
    "Recover-then-Content",
    "No-rescue",
    "No-attestation",
)


@dataclass(frozen=True)
class EventProtocolRecord:
    """表示一个可被 CEG 方法或 baseline 消费的事件级协议记录。"""

    event_id: str
    method_name: str
    split: str
    sample_role: str
    attack_family: str
    attack_condition: str
    is_watermarked: bool
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """转为普通字典, 用于 JSONL records、聚合器和测试 fixture。"""
        return asdict(self)


def validate_active_profile(profile: str) -> str:
    """校验 profile 是否属于 CEG clean project 的 active allowlist。"""
    if profile not in ACTIVE_PROFILES:
        raise ValueError(f"unsupported active profile: {profile}")
    return profile


def validate_paper_main_role(sample_role: str) -> str:
    """校验 paper_main 是否只使用 positive_source 与 clean_negative。"""
    if sample_role not in PAPER_MAIN_SAMPLE_ROLES:
        raise ValueError(f"unsupported paper_main sample role: {sample_role}")
    return sample_role


def validate_formal_split(split: str) -> str:
    """校验 split 是否属于 dev / calibration / test。"""
    if split not in FORMAL_SPLITS:
        raise ValueError(f"unsupported formal split: {split}")
    return split
