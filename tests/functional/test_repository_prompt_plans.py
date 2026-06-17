"""校验仓库内置 prompt plan 的规模、split 和正式运行规格一致性。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_repository_prompt_plans import PROFILE_SPECS, build_all_prompt_plans


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.quick
def test_repository_prompt_plans_match_expected_counts() -> None:
    """确认三个论文 profile 的 prompt plan 已经落盘, 且规模满足固定 FPR 统计设计。"""

    manifest_path = ROOT / "prompts" / "prompt_plans" / "prompt_plan_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))

    assert set(manifest["profiles"]) == set(PROFILE_SPECS)
    assert manifest["profiles"]["paper_main_probe"]["prompt_count"] == 4
    assert manifest["profiles"]["paper_main_pilot"]["split_counts"] == {"calibration": 300, "test": 300}
    assert manifest["profiles"]["paper_main_full"]["split_counts"] == {"calibration": 3000, "test": 3000}
    assert manifest["profiles"]["paper_main_full"]["target_fpr"] == 0.001


@pytest.mark.quick
def test_prompt_plan_builder_is_reproducible(tmp_path: Path) -> None:
    """确认构造脚本可以从源文本重新生成相同规模的 plan, 避免手工 JSON 成为唯一来源。"""

    output_dir = tmp_path / "prompt_plans"
    build_all_prompt_plans(output_dir=output_dir)
    repository_manifest = json.loads(
        (ROOT / "prompts" / "prompt_plans" / "prompt_plan_manifest.json").read_text(encoding="utf-8-sig")
    )
    for profile, summary in repository_manifest["profiles"].items():
        output_path = ROOT / summary["prompt_plan_path"]
        regenerated_path = output_dir / f"{profile}_prompt_plan.json"
        original = json.loads(output_path.read_text(encoding="utf-8-sig"))
        regenerated = json.loads(regenerated_path.read_text(encoding="utf-8-sig"))
        assert regenerated == original


@pytest.mark.quick
def test_formal_run_specs_align_with_prompt_plan_targets() -> None:
    """确认正式运行规格中的推荐规模和目标 FPR 与仓库 prompt plan 保持一致。"""

    specs = json.loads((ROOT / "configs" / "formal_run_specs.json").read_text(encoding="utf-8-sig"))
    manifest = json.loads((ROOT / "prompts" / "prompt_plans" / "prompt_plan_manifest.json").read_text(encoding="utf-8-sig"))

    for profile, summary in manifest["profiles"].items():
        spec = specs["profiles"][profile]
        assert spec["recommended_image_pair_count"] == summary["prompt_count"]
        assert spec["target_fpr"] == summary["target_fpr"]
        assert spec["sd_model_id"] == summary["sd_model_id"]
        assert spec["watermark_backend"] == summary["watermark_backend"]
