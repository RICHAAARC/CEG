"""封装外部 baseline 命令执行并收集 observation 文件。

该模块用于 Tree-Ring、Gaussian Shading、Shallow Diffuse、Stable Signature DEE 等
外部实现的实验接入。它只规定命令执行和输出文件读取契约, 不把第三方算法实现
复制进 CEG 核心方法层。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess
from typing import Any, Sequence

from experiments.baseline_file_adapter import load_baseline_observation_rows
from main.methods.baselines import get_baseline_spec


@dataclass(frozen=True)
class BaselineCommandSpec:
    """描述一个外部 baseline 命令的最小运行契约。"""

    baseline_id: str
    command: tuple[str, ...]
    output_path: str
    working_directory: str | None = None
    timeout_seconds: int = 3600

    def to_dict(self) -> dict[str, Any]:
        """转为普通字典, 便于写入实验 manifest。"""
        return asdict(self)


@dataclass(frozen=True)
class BaselineCommandResult:
    """保存一次外部 baseline 命令的运行结果。"""

    baseline_id: str
    return_code: int
    output_path: str
    observation_count: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        """转为普通字典, 便于写入审计记录。"""
        return asdict(self)


def run_baseline_command(spec: BaselineCommandSpec) -> tuple[BaselineCommandResult, list[dict[str, Any]]]:
    """执行一个外部 baseline 命令并读取其 observation 输出。

    通用工程写法:
    - 命令必须由显式参数列表给出, 避免字符串 shell 拼接。
    - 输出文件必须由 spec.output_path 声明, 命令执行后再读取。

    项目特定写法:
    - baseline_id 必须出现在 CEG baseline registry 中。
    - observation rows 必须包含 event_id、baseline_id、score、threshold。
    """
    baseline = get_baseline_spec(spec.baseline_id)
    if not spec.command:
        raise ValueError("baseline command must be non-empty")
    completed = subprocess.run(
        list(spec.command),
        cwd=spec.working_directory,
        timeout=spec.timeout_seconds,
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        result = BaselineCommandResult(
            baseline_id=baseline.baseline_id,
            return_code=completed.returncode,
            output_path=spec.output_path,
            observation_count=0,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        return result, []
    rows = load_baseline_observation_rows(Path(spec.output_path))
    result = BaselineCommandResult(
        baseline_id=baseline.baseline_id,
        return_code=completed.returncode,
        output_path=spec.output_path,
        observation_count=len(rows),
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    return result, rows


def run_baseline_commands(specs: Sequence[BaselineCommandSpec]) -> tuple[list[BaselineCommandResult], list[dict[str, Any]]]:
    """执行多个 baseline 命令并合并 observation rows。"""
    results: list[BaselineCommandResult] = []
    all_rows: list[dict[str, Any]] = []
    for spec in specs:
        result, rows = run_baseline_command(spec)
        results.append(result)
        all_rows.extend(rows)
    return results, all_rows
