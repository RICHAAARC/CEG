"""验证真实 pilot 输入工作区脚手架."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_run_workspace import scaffold_pilot_run_workspace


def _write_checklist(path) -> None:
    """写入最小 checklist fixture, 用于测试工作区脚手架."""
    path.write_text(
        json.dumps(
            {
                "artifact_name": "pilot_readiness_checklist.json",
                "overall_decision": "not_ready_for_formal_pilot",
                "recommended_next_stage": "real_pilot_input_preparation",
                "checklist_items": [
                    {
                        "requirement_id": "dry_run_marker_absent::image_pairs",
                        "status": "gap",
                        "blocking_for_formal_pilot": True,
                        "next_action": "运行真实 SD / watermark backend.",
                        "evidence": {"field": "image_pairs"},
                    },
                    {
                        "requirement_id": "core_input_present::all",
                        "status": "pass",
                        "blocking_for_formal_pilot": False,
                        "next_action": "核心输入字段已齐备.",
                        "evidence": {},
                    },
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.quick
def test_scaffold_pilot_run_workspace_writes_draft_manifest_and_tasks(tmp_path) -> None:
    """工作区应写出目录、草稿 manifest 和待补齐真实输入任务."""
    checklist_path = tmp_path / "pilot_readiness_checklist.json"
    workspace_root = tmp_path / "pilot_workspace"
    _write_checklist(checklist_path)

    manifest = scaffold_pilot_run_workspace(
        checklist_path=checklist_path,
        output_root=workspace_root,
        run_id="pilot_real_inputs",
    )

    draft = json.loads((workspace_root / "pilot_input_manifest.draft.json").read_text(encoding="utf-8"))
    manifest_on_disk = json.loads((workspace_root / "pilot_run_workspace_manifest.json").read_text(encoding="utf-8"))

    assert manifest["workspace_status"] == "awaiting_real_pilot_inputs"
    assert manifest_on_disk["run_id"] == "pilot_real_inputs"
    assert draft["manifest_status"] == "draft_requires_real_inputs"
    assert draft["image_pairs"] == "inputs/image_pairs.json"
    assert (workspace_root / "inputs" / "images" / "clean").is_dir()
    assert (workspace_root / "inputs" / "images" / "watermarked").is_dir()
    assert manifest["required_real_inputs"][0]["requirement_id"] == "dry_run_marker_absent::image_pairs"


@pytest.mark.quick
def test_scaffold_pilot_run_workspace_cli(tmp_path) -> None:
    """CLI 应创建可填充的真实 pilot 输入工作区."""
    checklist_path = tmp_path / "pilot_readiness_checklist.json"
    workspace_root = tmp_path / "pilot_workspace"
    _write_checklist(checklist_path)

    subprocess.run(
        [
            sys.executable,
            "scripts/scaffold_pilot_run_workspace.py",
            "--checklist",
            str(checklist_path),
            "--out",
            str(workspace_root),
            "--run-id",
            "pilot_cli_workspace",
        ],
        cwd=".",
        check=True,
    )

    manifest = json.loads((workspace_root / "pilot_run_workspace_manifest.json").read_text(encoding="utf-8"))
    readme = (workspace_root / "README.md").read_text(encoding="utf-8")

    assert manifest["run_id"] == "pilot_cli_workspace"
    assert manifest["source_recommended_next_stage"] == "real_pilot_input_preparation"
    assert "不是正式论文结果包" in readme
