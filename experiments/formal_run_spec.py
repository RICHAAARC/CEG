"""校验 CEG 正式运行规格与端到端运行 manifest。

该模块属于 experiments 层, 用于把论文级运行要求显式化。它不运行 SD、不生成图像、
不计算检测指标, 只检查当前端到端结果是否满足所选 profile 的最小规模、攻击矩阵、
FPR、模型和外部 baseline 要求。

通用工程写法是把“正式运行规格”独立成数据配置, 再由验收脚本读取并校验。项目特定写法是
默认要求 Stable Diffusion 3.5 Medium、CEG 内容链水印和 fixed-FPR=0.01。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from main.core.digest import build_stable_digest


DEFAULT_FORMAL_RUN_SPEC_PATH = Path("configs/formal_run_specs.json")
REPORT_NAME = "formal_run_spec_validation_report.json"


@dataclass(frozen=True)
class FormalRunSpec:
    """表示一个正式运行 profile 的最小验收规格。"""

    profile: str
    min_image_pair_count: int
    required_splits: tuple[str, ...]
    required_attack_families: tuple[str, ...]
    target_fpr: float
    sd_model_id: str
    watermark_backend: str
    require_run_image_generation: bool
    require_evidence: bool
    require_image_examples: bool
    required_external_baselines: tuple[str, ...]
    min_gpu_vram_gb: float


def _read_json(path: Path) -> Any:
    """读取 UTF-8 或带 BOM 的 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8-sig"))


def _as_tuple(value: Any) -> tuple[str, ...]:
    """把配置中的字符串列表归一化为 tuple[str, ...]。"""

    if value is None:
        return ()
    if not isinstance(value, list):
        raise TypeError("formal run spec list field must be a list")
    return tuple(str(item) for item in value)


def load_formal_run_specs(path: str | Path = DEFAULT_FORMAL_RUN_SPEC_PATH) -> dict[str, FormalRunSpec]:
    """读取正式运行规格配置。"""

    payload = _read_json(Path(path))
    if not isinstance(payload, dict):
        raise TypeError("formal run spec file must contain an object")
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, dict):
        raise ValueError("formal run spec file missing profiles object")
    specs: dict[str, FormalRunSpec] = {}
    for profile, raw_spec in raw_profiles.items():
        if not isinstance(raw_spec, dict):
            raise TypeError(f"formal run spec for {profile} must be an object")
        specs[str(profile)] = FormalRunSpec(
            profile=str(profile),
            min_image_pair_count=int(raw_spec["min_image_pair_count"]),
            required_splits=_as_tuple(raw_spec.get("required_splits")),
            required_attack_families=_as_tuple(raw_spec.get("required_attack_families")),
            target_fpr=float(raw_spec["target_fpr"]),
            sd_model_id=str(raw_spec["sd_model_id"]),
            watermark_backend=str(raw_spec["watermark_backend"]),
            require_run_image_generation=bool(raw_spec.get("require_run_image_generation", True)),
            require_evidence=bool(raw_spec.get("require_evidence", False)),
            require_image_examples=bool(raw_spec.get("require_image_examples", False)),
            required_external_baselines=_as_tuple(raw_spec.get("required_external_baselines")),
            min_gpu_vram_gb=float(raw_spec.get("min_gpu_vram_gb", 0)),
        )
    return specs


def _command_value(command: list[Any], flag: str) -> str | None:
    """从显式 argv 中读取 flag 后面的值。"""

    parts = [str(item) for item in command]
    if flag not in parts:
        return None
    index = parts.index(flag)
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def _command_has_flag(command: list[Any], flag: str) -> bool:
    """判断显式 argv 中是否包含某个 flag。"""

    return flag in [str(item) for item in command]


def _extract_paper_pipeline_command(end_to_end_manifest: dict[str, Any]) -> list[Any]:
    """从端到端 manifest 中提取 paper pipeline argv。"""

    result = end_to_end_manifest.get("paper_pipeline_result")
    if not isinstance(result, dict):
        return []
    command = result.get("command")
    return list(command) if isinstance(command, list) else []


def _extract_image_generation_command(end_to_end_manifest: dict[str, Any]) -> list[Any]:
    """从端到端 manifest 中提取 image generation argv。"""

    result = end_to_end_manifest.get("image_generation_result")
    if not isinstance(result, dict):
        return []
    command = result.get("command")
    return list(command) if isinstance(command, list) else []


def _collect_image_pair_splits(image_pairs_path: Path) -> tuple[set[str], int, str | None]:
    """读取 image_pairs.json 中的 split 集合和样本数量。"""

    if not image_pairs_path.is_file():
        return set(), 0, "image_pairs_missing"
    try:
        payload = _read_json(image_pairs_path)
    except Exception as exc:  # pragma: no cover - 具体异常由 JSON / IO 决定
        return set(), 0, f"{type(exc).__name__}: {exc}"
    if not isinstance(payload, list):
        return set(), 0, "image_pairs_not_list"
    splits = {str(row.get("split")) for row in payload if isinstance(row, dict) and row.get("split")}
    return splits, len(payload), None


def validate_formal_run_against_spec(
    *,
    end_to_end_manifest: dict[str, Any],
    profile: str,
    spec_path: str | Path = DEFAULT_FORMAL_RUN_SPEC_PATH,
    allow_existing_image_generation: bool = False,
) -> dict[str, Any]:
    """校验一次端到端运行是否满足指定正式运行规格。"""

    specs = load_formal_run_specs(spec_path)
    if profile not in specs:
        raise ValueError(f"unknown formal run profile: {profile}")
    spec = specs[profile]
    checks: list[dict[str, Any]] = []

    paper_command = _extract_paper_pipeline_command(end_to_end_manifest)
    image_command = _extract_image_generation_command(end_to_end_manifest)
    image_pairs_path = Path(str(end_to_end_manifest.get("image_pairs") or ""))
    observed_splits, image_pair_count, image_pairs_error = _collect_image_pair_splits(image_pairs_path)
    observed_attack_families = set(
        str(item).strip()
        for item in (_command_value(paper_command, "--attack-families") or "").split(",")
        if str(item).strip()
    )
    observed_baseline_formal_claim = _command_has_flag(paper_command, "--baseline-formal-result-claim")
    observed_evidence_paths = [
        str(paper_command[index + 1])
        for index, value in enumerate(paper_command[:-1])
        if str(value) == "--baseline-evidence-path"
    ]
    observed_profile = _command_value(paper_command, "--profile")
    observed_target_fpr = _command_value(paper_command, "--target-fpr")
    observed_model_id = _command_value(image_command, "--sd-model-id")
    observed_watermark_backend = _command_value(image_command, "--watermark-backend")

    checks.append(
        {
            "check_name": "profile_matches_spec",
            "status": "pass" if observed_profile == spec.profile else "fail",
            "expected": spec.profile,
            "actual": observed_profile,
        }
    )
    checks.append(
        {
            "check_name": "target_fpr_matches_spec",
            "status": "pass" if observed_target_fpr is not None and abs(float(observed_target_fpr) - spec.target_fpr) < 1e-12 else "fail",
            "expected": spec.target_fpr,
            "actual": observed_target_fpr,
        }
    )
    checks.append(
        {
            "check_name": "image_pair_count_meets_minimum",
            "status": "pass" if image_pair_count >= spec.min_image_pair_count and image_pairs_error is None else "fail",
            "expected_min": spec.min_image_pair_count,
            "actual": image_pair_count,
            "image_pairs_error": image_pairs_error,
        }
    )
    missing_splits = sorted(set(spec.required_splits) - observed_splits)
    checks.append(
        {
            "check_name": "required_splits_present",
            "status": "pass" if not missing_splits else "fail",
            "expected": list(spec.required_splits),
            "actual": sorted(observed_splits),
            "missing": missing_splits,
        }
    )
    missing_attacks = sorted(set(spec.required_attack_families) - observed_attack_families)
    checks.append(
        {
            "check_name": "required_attack_families_present",
            "status": "pass" if not missing_attacks else "fail",
            "expected": list(spec.required_attack_families),
            "actual": sorted(observed_attack_families),
            "missing": missing_attacks,
        }
    )
    checks.append(
        {
            "check_name": "real_image_generation_requirement",
            "status": (
                "pass"
                if not spec.require_run_image_generation
                or end_to_end_manifest.get("run_image_generation") is True
                or allow_existing_image_generation
                else "fail"
            ),
            "expected_run_image_generation": spec.require_run_image_generation,
            "actual": end_to_end_manifest.get("run_image_generation"),
            "allow_existing_image_generation": allow_existing_image_generation,
        }
    )
    checks.append(
        {
            "check_name": "sd_model_matches_spec",
            "status": "pass" if observed_model_id == spec.sd_model_id or allow_existing_image_generation else "fail",
            "expected": spec.sd_model_id,
            "actual": observed_model_id,
            "allow_existing_image_generation": allow_existing_image_generation,
        }
    )
    checks.append(
        {
            "check_name": "watermark_backend_matches_spec",
            "status": "pass" if observed_watermark_backend == spec.watermark_backend or allow_existing_image_generation else "fail",
            "expected": spec.watermark_backend,
            "actual": observed_watermark_backend,
            "allow_existing_image_generation": allow_existing_image_generation,
        }
    )
    missing_baselines = sorted(set(spec.required_external_baselines) - set(_read_baseline_ids(end_to_end_manifest)))
    checks.append(
        {
            "check_name": "required_external_baselines_present",
            "status": "pass" if not missing_baselines else "fail",
            "expected": list(spec.required_external_baselines),
            "actual": sorted(_read_baseline_ids(end_to_end_manifest)),
            "missing": missing_baselines,
        }
    )
    checks.append(
        {
            "check_name": "baseline_evidence_requirement",
            "status": (
                "pass"
                if not spec.require_evidence
                or (observed_baseline_formal_claim and all(Path(path).is_file() for path in observed_evidence_paths))
                else "fail"
            ),
            "require_evidence": spec.require_evidence,
            "formal_claim_flag": observed_baseline_formal_claim,
            "evidence_paths": observed_evidence_paths,
        }
    )

    failing_checks = [check for check in checks if check["status"] != "pass"]
    return {
        "artifact_name": REPORT_NAME,
        "overall_decision": "pass" if not failing_checks else "fail",
        "profile": profile,
        "spec_path": str(Path(spec_path)),
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "failing_check_count": len(failing_checks),
            "image_pair_count": image_pair_count,
            "observed_splits": sorted(observed_splits),
            "observed_attack_families": sorted(observed_attack_families),
        },
        "spec_digest": build_stable_digest({"profile": spec.profile, "checks": checks}),
    }


def _read_baseline_ids(end_to_end_manifest: dict[str, Any]) -> tuple[str, ...]:
    """从 baseline_execution_manifest.json 读取实际 baseline id。"""

    paper_summary = end_to_end_manifest.get("paper_pipeline_summary")
    if not isinstance(paper_summary, dict) or not paper_summary.get("baseline_root"):
        return ()
    path = Path(str(paper_summary["baseline_root"])) / "baseline_execution_manifest.json"
    if not path.is_file():
        return ()
    try:
        payload = _read_json(path)
    except Exception:
        return ()
    if not isinstance(payload, dict) or not isinstance(payload.get("baseline_ids"), list):
        return ()
    return tuple(str(item) for item in payload["baseline_ids"])
