"""验证 active profile 配置覆盖 paper_main 与 paper_mechanism。"""

from __future__ import annotations

from pathlib import Path

import pytest

from main.methods.baselines import BASELINE_REGISTRY
from main.methods.ceg.ablations import CEG_ABLATIONS
from main.protocol.experiment import ACTIVE_PROFILES
from experiments.formal_run_spec import load_formal_run_specs


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


@pytest.mark.quick
def test_formal_run_specs_define_paper_main_scales_and_resources() -> None:
    """正式运行规格应明确 probe / pilot / full 的规模、攻击、baseline 和 GPU 资源要求。"""

    specs = load_formal_run_specs("configs/formal_run_specs.json")
    assert {"paper_main_probe", "paper_main_pilot", "paper_main_full"}.issubset(specs)
    assert specs["paper_main_probe"].min_image_pair_count < specs["paper_main_pilot"].min_image_pair_count
    assert specs["paper_main_pilot"].min_image_pair_count < specs["paper_main_full"].min_image_pair_count
    assert specs["paper_main_full"].sd_model_id == "stabilityai/stable-diffusion-3.5-medium"
    assert specs["paper_main_full"].watermark_backend == "ceg_content_chain_embedding"
    assert set(specs["paper_main_full"].required_external_baselines) == set(BASELINE_REGISTRY)
    assert specs["paper_main_full"].min_gpu_vram_gb >= specs["paper_main_probe"].min_gpu_vram_gb
