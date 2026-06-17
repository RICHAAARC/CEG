"""验证模板仓库的 harness 基础契约。"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.harness.run_all_audits import run_all_audits
from tools.harness.audits.audit_file_organization_contract import run_audit as run_file_organization_audit


@pytest.mark.constraint
def test_project_contract_exists() -> None:
    """项目契约必须存在, 作为所有修改前置依据。"""
    assert Path(".codex/project_contract.md").exists()


@pytest.mark.constraint
def test_harness_audits_pass_for_template() -> None:
    """模板仓库自身必须通过内置 harness 审计。"""
    summary = run_all_audits(Path.cwd())
    assert summary["overall_decision"] == "pass"


@pytest.mark.constraint
def test_local_ignored_outputs_directory_is_allowed(tmp_path: Path) -> None:
    """本地 outputs 目录可保存运行产物, 但不得被 git 跟踪或进入发布边界。"""

    outputs_root = Path("outputs")
    outputs_root.mkdir(exist_ok=True)
    try:
        (outputs_root / "local_runtime_log.txt").write_text("local output only\n", encoding="utf-8")
        report = run_file_organization_audit(Path.cwd())
        assert report["decision"] == "pass"
    finally:
        local_file = outputs_root / "local_runtime_log.txt"
        if local_file.exists():
            local_file.unlink()
        try:
            outputs_root.rmdir()
        except OSError:
            pass


@pytest.mark.constraint
def test_main_core_package_exists() -> None:
    """论文研究项目模板必须使用 main 作为核心包目录。"""
    assert Path("main/__init__.py").exists()
    assert not Path("src").exists()
