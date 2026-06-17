"""校验 Python editable install 的 setuptools 包发现配置。"""

from __future__ import annotations

from pathlib import Path
import tomllib

import pytest


@pytest.mark.constraint
def test_pyproject_limits_setuptools_package_discovery() -> None:
    """pyproject 必须显式限定包发现范围, 避免 prompts/configs 等数据目录被当作顶层包。"""

    payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    find_config = payload["tool"]["setuptools"]["packages"]["find"]

    assert find_config["where"] == ["."]
    assert set(find_config["include"]) == {"main*", "experiments*", "paper_workflow*", "tools*"}
    assert {"configs*", "docs*", "prompts*", "tests*"}.issubset(set(find_config["exclude"]))
    assert find_config["namespaces"] is True
