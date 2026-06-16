"""验证 active profile 配置覆盖 paper_main 与 paper_mechanism。"""

from __future__ import annotations

from pathlib import Path

import pytest

from main.methods.baselines import BASELINE_REGISTRY
from main.methods.ceg.ablations import CEG_ABLATIONS
from main.protocol.experiment import ACTIVE_PROFILES


@pytest.mark.quick
def test_all_active_profiles_have_config_files() -> None:
    """每个 active profile 都必须有对应配置文件。"""
    for profile in ACTIVE_PROFILES:
        assert Path("configs", f"{profile}.yaml").exists()


@pytest.mark.quick
def test_profile_configs_register_required_baselines_and_ablations() -> None:
    """配置文件必须覆盖外部 baseline 与 mechanism 消融版本。"""
    required_baselines = set(BASELINE_REGISTRY)
    for profile in ACTIVE_PROFILES:
        text = Path("configs", f"{profile}.yaml").read_text(encoding="utf-8")
        for baseline_id in required_baselines:
            assert baseline_id in text
        if "mechanism" in profile:
            for ablation_name in CEG_ABLATIONS:
                assert ablation_name in text
