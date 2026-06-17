"""图像生成 backend 命令文件治理。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

COMMAND_ARTIFACT_NAME = "image_generation_backend_command.draft.json"
VALIDATION_REPORT_NAME = "image_generation_backend_command_validation_report.json"

REQUIRED_OUTPUTS = (
    "prompt_plan.json",
    "clean/*",
    "watermarked/*",
    "image_pairs.json",
    "image_manifests/image_generation_manifest.json",
    "image_manifests/image_pair_manifest.json",
)


def read_json(path: str | Path) -> Any:
    """读取 JSON 文件, 支持带 BOM 的 UTF-8。"""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    """写出 UTF-8 JSON 文件。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_external_backend_command_template(*, workspace_root: str | Path) -> dict[str, Any]:
    """构造 Colab 可执行的真实图像生成 backend 命令。

    默认命令指向仓库内真实 SD 生成入口, 并通过 CEG 项目内原生水印原语执行 watermark。
    用户如需替换 watermark backend, 应改写 external_command 中的 watermark 参数, 而不是在 Notebook 中手写正式产物。
    """
    workspace = Path(workspace_root)
    prompt_plan = workspace / "inputs" / "prompts" / "prompt_plan.draft.json"
    output_root = workspace / "inputs" / "images"
    model_config = workspace / "configs" / "model_config.draft.json"
    return {
        "artifact_name": COMMAND_ARTIFACT_NAME,
        "manifest_status": "ready_for_colab_gpu_execution_unverified",
        "workspace_root": str(workspace),
        "prompt_source": "Google Drive workspace prompt_plan.draft.json",
        "hf_token_status": "defined_in_colab_environment_not_written_to_disk",
        "external_command": [
            "python",
            "/content/CEG/scripts/run_pilot_real_image_generation_backend.py",
            "--prompt-plan",
            str(prompt_plan).replace("\\", "/").replace("D:/content/drive/MyDrive/CEG", "/content/drive/MyDrive/CEG"),
            "--out",
            str(output_root).replace("\\", "/").replace("D:/content/drive/MyDrive/CEG", "/content/drive/MyDrive/CEG"),
            "--model-config",
            str(model_config).replace("\\", "/").replace("D:/content/drive/MyDrive/CEG", "/content/drive/MyDrive/CEG"),
            "--watermark-backend",
            "ceg_native_lsb",
            "--require-pass",
        ],
        "command_contract": {
            "value_type": "list[str]",
            "must_run_real_sd_backend": True,
            "must_run_real_watermark_backend": True,
            "must_not_call_external_project": True,
            "default_entrypoint": "scripts/run_pilot_real_image_generation_backend.py"
        },
        "required_outputs": list(REQUIRED_OUTPUTS),
        "instructions": [
            "在 Colab 中安装 torch、diffusers、transformers、accelerate 和 Pillow。",
            "默认命令会调用 /content/CEG/scripts/run_pilot_real_image_generation_backend.py。",
            "默认 watermark backend 为 CEG 仓库内 ceg_native_lsb, 不克隆也不调用其他项目。",
            "不要把 Hugging Face token 写入本文件、manifest、CSV、Notebook 输出或日志。",
            "真实 backend 必须写出 required_outputs 中列出的图像生成文件。",
        ],
    }


def _extract_command(payload: Any) -> tuple[list[str] | None, list[dict[str, Any]]]:
    """从命令文件 payload 中提取 argv, 同时返回阻断问题。"""
    issues: list[dict[str, Any]] = []
    raw_command: Any
    if isinstance(payload, list):
        raw_command = payload
    elif isinstance(payload, dict):
        if "external_command" in payload:
            raw_command = payload["external_command"]
        elif "external_command_placeholder" in payload:
            issues.append(
                {
                    "issue_type": "placeholder_not_replaced",
                    "field": "external_command_placeholder",
                    "message": "命令文件仍是草稿, 必须替换为 external_command。",
                }
            )
            raw_command = payload["external_command_placeholder"]
        else:
            issues.append({"issue_type": "missing_external_command_field"})
            raw_command = None
    else:
        issues.append({"issue_type": "payload_not_object_or_list"})
        raw_command = None

    if raw_command is None:
        return None, issues
    if not isinstance(raw_command, list) or not all(isinstance(item, str) for item in raw_command):
        issues.append({"issue_type": "external_command_must_be_string_list"})
        return None, issues
    if not raw_command:
        issues.append({"issue_type": "external_command_empty"})
        return None, issues
    return list(raw_command), issues


def _looks_like_secret(value: str) -> bool:
    """判断字符串是否像被误写入的密钥值。"""
    lowered = value.lower()
    return lowered.startswith("hf_") and len(value) > 10 or lowered.startswith("sk-") and len(value) > 10


def _validate_command_values(command: list[str]) -> list[dict[str, Any]]:
    """检查 argv 中是否仍包含 placeholder 或疑似密钥。"""
    issues: list[dict[str, Any]] = []
    for index, value in enumerate(command):
        lowered = value.lower()
        if "replace_with" in lowered or "placeholder" in lowered:
            issues.append({"issue_type": "placeholder_value_not_replaced", "argv_index": index, "value": value})
        if _looks_like_secret(value):
            issues.append({"issue_type": "possible_secret_written_to_command", "argv_index": index})
    return issues


def build_backend_command_validation_report(command_file: str | Path) -> dict[str, Any]:
    """构造外部 backend 命令文件校验报告。"""
    path = Path(command_file)
    issues: list[dict[str, Any]] = []
    payload: Any | None = None
    if not path.is_file():
        issues.append({"issue_type": "command_file_missing", "path": str(path)})
    else:
        try:
            payload = read_json(path)
        except Exception as exc:  # pragma: no cover - 具体错误由 JSON / IO 决定
            issues.append({"issue_type": "command_file_unreadable", "path": str(path), "error": str(exc)})
    command, extract_issues = _extract_command(payload) if payload is not None else (None, [])
    issues.extend(extract_issues)
    if command is not None:
        issues.extend(_validate_command_values(command))
    decision = "pass" if not issues else "fail"
    return {
        "artifact_name": VALIDATION_REPORT_NAME,
        "command_file": str(path),
        "overall_decision": decision,
        "recommended_next_stage": "run_image_generation_backend_in_colab" if decision == "pass" else "replace_external_backend_command",
        "external_command": command,
        "required_outputs": list(REQUIRED_OUTPUTS),
        "blocking_issues": issues,
        "summary": {
            "argv_count": len(command) if command else 0,
            "blocking_issue_count": len(issues),
        },
    }


def write_backend_command_validation_report(command_file: str | Path, out: str | Path) -> dict[str, Any]:
    """写出外部 backend 命令文件校验报告。"""
    report = build_backend_command_validation_report(command_file)
    write_json(out, report)
    return report


def apply_external_command_to_file(command_file: str | Path, external_command: list[str], out: str | Path | None = None) -> dict[str, Any]:
    """把真实外部 backend argv 写入命令文件。

    该函数只修改命令描述文件, 不运行模型。调用方仍需要随后执行校验和图像生成入口。
    """
    if not external_command or not all(isinstance(item, str) and item.strip() for item in external_command):
        raise ValueError("external_command must be a non-empty list[str]")
    source_path = Path(command_file)
    payload = read_json(source_path) if source_path.is_file() else {"artifact_name": COMMAND_ARTIFACT_NAME}
    if not isinstance(payload, dict):
        payload = {"artifact_name": COMMAND_ARTIFACT_NAME}
    payload.pop("external_command_placeholder", None)
    payload["external_command"] = list(external_command)
    payload["manifest_status"] = "ready_for_colab_gpu_execution_unverified"
    payload["execution_boundary"] = "command_written_but_not_executed"
    output_path = Path(out) if out is not None else source_path
    write_json(output_path, payload)
    return payload
