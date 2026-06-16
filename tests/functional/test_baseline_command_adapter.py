"""验证外部 baseline 命令封装。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.baseline_command_adapter import BaselineCommandSpec, run_baseline_command


@pytest.mark.quick
def test_run_baseline_command_collects_observation_rows(tmp_path) -> None:
    """外部 baseline 命令应写出 observation 文件并被统一读取。"""
    output_path = tmp_path / "tree_ring_rows.json"
    writer_script = (
        "import json, pathlib; "
        f"pathlib.Path(r'{output_path}').write_text("
        "json.dumps([{'event_id':'event_a','baseline_id':'tree_ring','score':0.7,'threshold':0.5}]),"
        "encoding='utf-8')"
    )
    spec = BaselineCommandSpec(
        baseline_id="tree_ring",
        command=(sys.executable, "-c", writer_script),
        output_path=str(output_path),
        timeout_seconds=30,
    )

    result, rows = run_baseline_command(spec)

    assert result.return_code == 0
    assert result.observation_count == 1
    assert rows[0]["baseline_id"] == "tree_ring"


@pytest.mark.quick
def test_run_baseline_command_reports_failure_without_rows(tmp_path) -> None:
    """外部 baseline 命令失败时应返回失败结果, 不伪造 observation。"""
    spec = BaselineCommandSpec(
        baseline_id="tree_ring",
        command=(sys.executable, "-c", "import sys; sys.exit(3)"),
        output_path=str(tmp_path / "missing.json"),
        timeout_seconds=30,
    )

    result, rows = run_baseline_command(spec)

    assert result.return_code == 3
    assert result.observation_count == 0
    assert rows == []
