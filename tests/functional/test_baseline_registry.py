"""验证外部 baseline 注册表覆盖目标对比方法。"""

from __future__ import annotations

import pytest

from main.methods.baselines import get_baseline_spec, list_baseline_specs


@pytest.mark.quick
def test_required_external_baselines_are_registered() -> None:
    """论文外部对比至少应覆盖 Tree-Ring、Gaussian Shading、Shallow Diffuse 和 Stable Signature DEE。"""
    baseline_ids = {spec.baseline_id for spec in list_baseline_specs()}

    assert {
        "tree_ring",
        "gaussian_shading",
        "shallow_diffuse",
        "stable_signature_dee",
    } <= baseline_ids


@pytest.mark.quick
def test_baseline_alias_normalization_supports_paper_names() -> None:
    """baseline 注册表应接受论文中常用的显示名称或连字符写法。"""
    assert get_baseline_spec("Tree-Ring").baseline_id == "tree_ring"
    assert get_baseline_spec("Stable Signature").baseline_id == "stable_signature_dee"
