"""构建 P2 图像生成 GPU 交接清单。

该模块的作用是把已经通过的 P0 / P1 报告转换为一个可重复生成的 Colab GPU
执行清单。它不运行 SD 模型, 不生成图像, 也不写入任何密钥。这样做属于通用
工程写法: 对需要外部算力执行的阶段生成显式输入、输出、验收和安全边界。

项目特定写法是: 该清单固定对齐 CEG P2 图像生成输出契约, 包括
`prompt_plan.json`、`image_pairs.json` 和 image manifests。后续只有这些真实
GPU 产物通过接收门禁后, 才能进入 P3 attack。
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from experiments.image_generation_plan import REQUIRED_EXTERNAL_OUTPUTS
from experiments.pilot_image_generation_launch_plan import (
    IMAGE_GENERATION_COMMAND_PLAN_NAME,
    LAUNCH_PLAN_REPORT_NAME,
)
from experiments.pilot_p0_input_freeze import P0_INPUT_FREEZE_REPORT_NAME


P2_GPU_HANDOFF_DIR = Path("gpu_handoff") / "p2_image_generation"
P2_GPU_HANDOFF_CHECKLIST_NAME = "p2_image_generation_colab_execution_checklist.json"
P2_GPU_HANDOFF_RUNBOOK_NAME = "p2_image_generation_colab_runbook.md"
P2_OUTPUT_ACCEPTANCE_REPORT_NAME = "pilot_image_generation_output_acceptance_report.json"
WINDOWS_DRIVE_WORKSPACE_PREFIX = "D:\\content\\drive\\MyDrive\\CEG"
WINDOWS_DRIVE_WORKSPACE_PREFIX_ALT = "D:/content/drive/MyDrive/CEG"
COLAB_DRIVE_WORKSPACE_PREFIX = "/content/drive/MyDrive/CEG"
WINDOWS_REPO_PREFIX = "D:\\Code\\CEG"
WINDOWS_REPO_PREFIX_ALT = "D:/Code/CEG"
COLAB_REPO_PREFIX = "/content/CEG"


def _read_json(path: Path) -> dict[str, Any]:
    """读取 JSON 对象, 并在类型不匹配时给出明确错误。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """写出 UTF-8 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _report_status(path: Path) -> dict[str, Any]:
    """读取阶段报告的关键状态, 缺失或不可读时返回 fail。"""
    if not path.is_file():
        return {"path": str(path), "overall_decision": "fail", "reason": "missing_report"}
    try:
        payload = _read_json(path)
    except Exception as exc:  # pragma: no cover - 具体错误来自底层 JSON 或 IO
        return {"path": str(path), "overall_decision": "fail", "reason": f"unreadable_report: {exc}"}
    return {
        "path": str(path),
        "overall_decision": payload.get("overall_decision"),
        "recommended_next_stage": payload.get("recommended_next_stage"),
        "summary": payload.get("summary", {}),
    }


def _load_command_plan(path: Path) -> list[dict[str, Any]]:
    """读取 P1 物化出的图像生成命令计划。"""
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)]


def _to_colab_path(value: Any) -> Any:
    """把 Windows 本地路径转换为 Colab 可用路径。

    该转换只处理当前项目已知的工作区和仓库前缀, 不猜测其他路径。这样可以
    避免把任意字符串误改成路径, 同时让用户在 Colab 中能直接复制命令。
    """
    if not isinstance(value, str):
        return value
    normalized = value.replace("\\", "/")
    replacements = (
        (WINDOWS_DRIVE_WORKSPACE_PREFIX.replace("\\", "/"), COLAB_DRIVE_WORKSPACE_PREFIX),
        (WINDOWS_DRIVE_WORKSPACE_PREFIX_ALT, COLAB_DRIVE_WORKSPACE_PREFIX),
        (WINDOWS_REPO_PREFIX.replace("\\", "/"), COLAB_REPO_PREFIX),
        (WINDOWS_REPO_PREFIX_ALT, COLAB_REPO_PREFIX),
    )
    for source, target in replacements:
        if normalized.startswith(source):
            return target + normalized[len(source) :]
    return normalized


def _to_colab_command_plan(command_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 P1 生成的 Windows 命令计划转换为 Colab 命令计划。"""
    converted: list[dict[str, Any]] = []
    for row in command_plan:
        converted_row = dict(row)
        command = converted_row.get("command")
        if isinstance(command, list):
            converted_row["command"] = [_to_colab_path(part) for part in command]
        elif isinstance(command, str):
            converted_row["command"] = _to_colab_path(command)
        for field_name in ("output_root", "working_directory"):
            if field_name in converted_row:
                converted_row[field_name] = _to_colab_path(converted_row[field_name])
        converted.append(converted_row)
    return converted


def _command_to_shell(command: Any) -> str:
    """把 argv 形式命令渲染为便于 Colab 复制的 shell 字符串。"""
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command)


def _repo_relative_colab_path(value: str) -> str | None:
    """若 Colab 路径位于 `/content/CEG` 下, 返回仓库相对路径。"""
    normalized = value.replace("\\", "/")
    prefix = COLAB_REPO_PREFIX.rstrip("/") + "/"
    if normalized.startswith(prefix):
        return normalized[len(prefix) :]
    return None


def _python_entrypoint_from_command(command: Any) -> str | None:
    """从 Python argv 命令中提取入口脚本路径。"""
    if not isinstance(command, list) or len(command) < 2:
        return None
    executable = str(command[0]).lower()
    if executable not in {"python", "python3"} and not executable.endswith("/python"):
        return None
    entrypoint = str(command[1]).strip()
    return entrypoint or None



def _command_uses_backend_wrapper(command: Any) -> bool:
    """判断命令是否调用仓库提供的 P2 backend 包装入口。"""
    entrypoint = _python_entrypoint_from_command(command)
    if entrypoint is None:
        return False
    return Path(str(entrypoint).replace("\\", "/")).name == "run_pilot_image_generation_backend.py"


def _from_colab_path(value: str) -> str:
    """把已知 Colab 路径映射回本地 Windows 路径, 用于检查 MyDrive 草稿文件。"""
    normalized = value.replace("\\", "/")
    replacements = (
        (COLAB_DRIVE_WORKSPACE_PREFIX, WINDOWS_DRIVE_WORKSPACE_PREFIX_ALT),
        (COLAB_REPO_PREFIX, WINDOWS_REPO_PREFIX_ALT),
    )
    for source, target in replacements:
        if normalized.startswith(source):
            return target + normalized[len(source) :]
    return value


def _argument_after(command: list[Any], flag: str) -> str | None:
    """读取 argv 中某个 flag 后面的值。"""
    values = [str(part) for part in command]
    if flag not in values:
        return None
    index = values.index(flag)
    if index + 1 >= len(values):
        return None
    return values[index + 1]


def _external_backend_command_status(command: Any) -> str:
    """判断包装入口命令是否已经指向真实外部 backend 命令。

    该检查不会运行 backend, 只读取 argv 或 MyDrive JSON 草稿的结构。
    真实可用性仍必须在 Colab GPU 环境中执行后由 P2 接收门禁确认。
    """
    if not isinstance(command, list):
        return "required_before_execution"
    arguments = {str(part) for part in command}
    if "--external-command" in arguments or "--external-command-json" in arguments:
        return "provided_inline_unverified"
    file_value = _argument_after(command, "--external-command-json-file")
    if file_value is None:
        return "required_before_execution"
    local_path = Path(_from_colab_path(file_value))
    if not local_path.is_file():
        return "command_file_missing"
    try:
        payload = json.loads(local_path.read_text(encoding="utf-8-sig"))
    except Exception:  # pragma: no cover - 具体错误由 JSON / IO 决定
        return "command_file_unreadable"
    if isinstance(payload, dict) and "external_command" in payload:
        return "command_file_provided_unverified"
    if isinstance(payload, list):
        return "command_file_provided_unverified"
    if isinstance(payload, dict) and "external_command_placeholder" in payload:
        return "command_file_draft_placeholder"
    return "command_file_missing_external_command"

def _build_entrypoint_checks(*, repo_root: Path, colab_command_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """检查 Colab 命令中的仓库内 Python 入口是否存在。

    该检查只验证仓库内路径。外部 backend 路径可能由用户在 Colab 中挂载或安装,
    因此不能在本地证明存在, 只能作为需要用户确认的外部入口。
    """
    checks: list[dict[str, Any]] = []
    for index, row in enumerate(colab_command_plan):
        entrypoint = _python_entrypoint_from_command(row.get("command"))
        if entrypoint is None:
            checks.append(
                {
                    "command_index": index,
                    "status": "not_python_entrypoint_command",
                    "entrypoint": None,
                    "message": "该命令不是可解析的 python <script> 形式, 需要用户在 Colab 中确认。",
                }
            )
            continue
        relative = _repo_relative_colab_path(entrypoint)
        if relative is None:
            checks.append(
                {
                    "command_index": index,
                    "status": "external_entrypoint_unchecked",
                    "entrypoint": entrypoint,
                    "message": "入口不在 /content/CEG 下, 本地无法验证, 需要用户在 Colab 中确认。",
                }
            )
            continue
        local_path = repo_root / relative
        exists = local_path.is_file()
        command = row.get("command")
        uses_wrapper = _command_uses_backend_wrapper(command)
        external_backend_status = _external_backend_command_status(command) if uses_wrapper else "not_applicable"
        checks.append(
            {
                "command_index": index,
                "status": "repo_entrypoint_exists" if exists else "repo_entrypoint_missing",
                "entrypoint": entrypoint,
                "repo_relative_path": relative,
                "local_path": str(local_path),
                "uses_p2_backend_wrapper": uses_wrapper,
                "external_backend_command_status": external_backend_status,
                "message": (
                    "仓库内入口存在, Colab 中 clone 或上传仓库后可定位该脚本。"
                    if exists
                    else "仓库内不存在该入口。需要用户提供外部 backend 脚本, 或修改 image_generation_root / command_plan。"
                ),
            }
        )
    return checks


def _execution_warnings(entrypoint_checks: list[dict[str, Any]]) -> list[dict[str, str]]:
    """把入口检查结果转换为用户可读 warning。"""
    warnings: list[dict[str, str]] = []
    for check in entrypoint_checks:
        if check.get("status") in {"repo_entrypoint_missing", "external_entrypoint_unchecked", "not_python_entrypoint_command"}:
            warnings.append(
                {
                    "warning_type": str(check.get("status")),
                    "entrypoint": str(check.get("entrypoint")),
                    "message": str(check.get("message")),
                }
            )
        external_status = check.get("external_backend_command_status")
        if external_status == "required_before_execution":
            warnings.append(
                {
                    "warning_type": "external_backend_command_required",
                    "entrypoint": str(check.get("entrypoint")),
                    "message": (
                        "仓库内 P2 包装入口已经存在, 但命令计划尚未携带 --external-command-json-file、"
                        "--external-command-json 或 --external-command。正式执行前需要在 Colab 中追加真实 SD / watermark backend 命令。"
                    ),
                }
            )
        elif external_status in {
            "command_file_missing",
            "command_file_unreadable",
            "command_file_draft_placeholder",
            "command_file_missing_external_command",
        }:
            warnings.append(
                {
                    "warning_type": str(external_status),
                    "entrypoint": str(check.get("entrypoint")),
                    "message": "外部 backend 命令文件尚未替换为真实可执行 SD / watermark backend 命令。",
                }
            )
    return warnings


def _required_output_rows(output_root: Path) -> list[dict[str, str]]:
    """构造 P2 必需输出路径列表。"""
    rows = [
        {
            "relative_path": relative,
            "absolute_path": str(output_root / relative),
            "purpose": "P2 接收门禁的显式必需文件",
        }
        for relative in REQUIRED_EXTERNAL_OUTPUTS
    ]
    rows.extend(
        [
            {
                "relative_path": "clean/*",
                "absolute_path": str(output_root / "clean"),
                "purpose": "真实 clean 图像目录, 由 image_pairs.json 中 clean_image_path 或 reference_path 引用",
            },
            {
                "relative_path": "watermarked/*",
                "absolute_path": str(output_root / "watermarked"),
                "purpose": "真实 watermarked 图像目录, 由 image_pairs.json 中 watermarked_image_path 或 watermarked_path 引用",
            },
        ]
    )
    return rows


def build_p2_image_generation_gpu_handoff_checklist(
    *,
    workspace_root: str | Path,
    handoff_root: str | Path | None = None,
) -> dict[str, Any]:
    """构建 P2 Colab GPU 执行清单。

    该函数只读取 P0 / P1 报告和命令计划, 不执行外部命令。它的返回值用于告诉
    用户在 Colab 中需要确认哪些输入、运行哪些命令、回传哪些文件。
    """
    workspace = Path(workspace_root)
    handoff = Path(handoff_root) if handoff_root is not None else workspace / P2_GPU_HANDOFF_DIR
    p0_report = workspace / P0_INPUT_FREEZE_REPORT_NAME
    p1_report = workspace / LAUNCH_PLAN_REPORT_NAME
    command_plan_path = workspace / IMAGE_GENERATION_COMMAND_PLAN_NAME
    output_root = workspace / "inputs" / "images"
    p0_status = _report_status(p0_report)
    p1_status = _report_status(p1_report)
    command_plan = _load_command_plan(command_plan_path)
    colab_command_plan = _to_colab_command_plan(command_plan)
    repo_root = Path(__file__).resolve().parents[1]
    entrypoint_checks = _build_entrypoint_checks(repo_root=repo_root, colab_command_plan=colab_command_plan)
    execution_warnings = _execution_warnings(entrypoint_checks)
    blocking_items: list[dict[str, str]] = []
    if p0_status.get("overall_decision") != "pass":
        blocking_items.append({"gate": "p0_input_freeze", "reason": "p0_report_not_pass"})
    if p1_status.get("overall_decision") != "pass":
        blocking_items.append({"gate": "p1_image_generation_launch_plan", "reason": "p1_report_not_pass"})
    if not command_plan:
        blocking_items.append({"gate": "image_generation_command_plan", "reason": "missing_or_empty_command_plan"})

    return {
        "artifact_name": P2_GPU_HANDOFF_CHECKLIST_NAME,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(workspace),
        "handoff_root": str(handoff),
        "stage": "p2_image_generation_outputs",
        "overall_decision": "ready_for_user_colab_gpu_execution" if not blocking_items else "fail",
        "local_execution_status": "pause_required_no_local_gpu",
        "secret_handling": {
            "requires_huggingface_token": True,
            "allowed_environment_variables": ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
            "forbidden_storage": [
                "不要把 token 写入仓库文件",
                "不要把 token 写入 CSV",
                "不要把 token 写入 manifest",
                "不要把 token 打印到 notebook 输出或日志",
            ],
        },
        "preconditions": {
            "p0_input_freeze": p0_status,
            "p1_image_generation_launch_plan": p1_status,
            "command_plan_path": str(command_plan_path),
            "command_count": len(command_plan),
        },
        "colab_path_mapping": {
            "windows_workspace_root": str(workspace),
            "colab_workspace_root": "/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500",
            "output_root": "/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images",
            "windows_repo_root": "D:/Code/CEG",
            "colab_repo_root": COLAB_REPO_PREFIX,
        },
        "command_plan": command_plan,
        "colab_command_plan": colab_command_plan,
        "colab_shell_commands": [_command_to_shell(row.get("command", "")) for row in colab_command_plan],
        "entrypoint_checks": entrypoint_checks,
        "execution_warnings": execution_warnings,
        "required_outputs": _required_output_rows(output_root),
        "local_acceptance_commands": [
            (
                "python scripts/validate_pilot_image_generation_outputs.py "
                "--output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images "
                "--out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/"
                f"{P2_OUTPUT_ACCEPTANCE_REPORT_NAME} --require-pass"
            ),
            (
                "python scripts/build_pilot_stage_progress_summary.py "
                "--workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500"
            ),
        ],
        "colab_acceptance_commands": [
            (
                "python scripts/validate_pilot_image_generation_outputs.py "
                "--output-root /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images "
                "--out /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/"
                f"{P2_OUTPUT_ACCEPTANCE_REPORT_NAME} --require-pass"
            ),
            (
                "python scripts/build_pilot_stage_progress_summary.py "
                "--workspace /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500"
            ),
        ],
        "blocking_items": blocking_items,
        "notes": [
            "该清单不代表 P2 已完成, 只代表可以交给用户在 Colab GPU 环境执行。",
            "P2 正式证据必须来自真实 clean / watermarked 图像和 manifests。",
            "如果 Colab 中不使用 command_plan, 也必须产出 required_outputs 中列出的同名文件。",
        ],
    }


def render_p2_image_generation_gpu_handoff_runbook(checklist: dict[str, Any]) -> str:
    """把 P2 GPU 交接清单渲染为 Markdown runbook。"""
    lines = [
        "# P2 图像生成 Colab GPU 执行清单",
        "",
        "## 1. 当前结论",
        "",
        f"- 阶段: `{checklist['stage']}`",
        f"- 清单状态: `{checklist['overall_decision']}`",
        f"- 本地执行状态: `{checklist['local_execution_status']}`",
        "",
        "该文件只用于指导 Colab GPU 执行, 不包含 Hugging Face token, 也不表示 P2 已完成。",
        "",
        "## 2. 密钥边界",
        "",
        "- 允许在 Colab 环境变量中提供 `HF_TOKEN` 或 `HUGGING_FACE_HUB_TOKEN`。",
        "- 禁止把 token 写入仓库、CSV、manifest、Notebook 输出或日志。",
        "",
        "## 3. 前置门禁",
        "",
        "```text",
        f"P0 = {checklist['preconditions']['p0_input_freeze'].get('overall_decision')}",
        f"P1 = {checklist['preconditions']['p1_image_generation_launch_plan'].get('overall_decision')}",
        f"command_count = {checklist['preconditions']['command_count']}",
        "```",
        "",
        "## 4. Colab 路径映射",
        "",
        "```text",
        f"workspace = {checklist['colab_path_mapping']['colab_workspace_root']}",
        f"repo_root = {checklist['colab_path_mapping']['colab_repo_root']}",
        f"output_root = {checklist['colab_path_mapping']['output_root']}",
        "```",
        "",
        "## 5. Colab 可复制命令",
        "",
        "以下命令已经把 Windows 路径转换为 Colab 路径。若你在 Colab 中使用 Notebook 直接调度模块,",
        "也必须产出第 6 节列出的同名文件。",
        "",
        "```text",
    ]
    shell_commands = checklist.get("colab_shell_commands", [])
    if shell_commands:
        lines.extend(str(command) for command in shell_commands)
    else:
        lines.append("# 当前没有可复制命令, 请检查 image_generation_command_plan.json。")
    lines.extend(
        [
            "```",
            "",
            "## 6. 命令入口检查",
            "",
            "| 序号 | 状态 | 入口 | 说明 |",
            "|---:|---|---|---|",
        ]
    )
    for index, check in enumerate(checklist.get("entrypoint_checks", []), start=1):
        lines.append(
            "| {index} | `{status}` | `{entrypoint}` | {message} |".format(
                index=index,
                status=check.get("status", ""),
                entrypoint=check.get("entrypoint", ""),
                message=check.get("message", ""),
            )
        )
    lines.extend(
        [
            "",
            "如果状态为 `repo_entrypoint_missing`, 说明当前命令计划仍是外部 backend 模板,",
            "需要在 Colab 中提供对应脚本或改用真实图像生成 Notebook / backend, 但最终仍必须产出下一节列出的文件。",
            "",
            "## 7. 必须回传的 P2 输出",
        "",
        "| 序号 | 相对路径 | 用途 |",
        "|---:|---|---|",
        ]
    )
    for index, row in enumerate(checklist.get("required_outputs", []), start=1):
        lines.append(f"| {index} | `{row['relative_path']}` | {row['purpose']} |")
    lines.extend(
        [
            "",
            "## 8. Colab 自检命令",
            "",
            "这些命令可在 Colab 中执行, 用于确认 P2 输出已经满足接收门禁。",
            "",
            "```text",
        ]
    )
    lines.extend(str(command) for command in checklist.get("colab_acceptance_commands", []))
    lines.extend(
        [
            "```",
            "",
            "## 9. 回传后本地验收命令",
            "",
            "这些命令用于回到 Windows 本地后复核同一份 MyDrive 工作区。",
            "",
            "```text",
        ]
    )
    lines.extend(str(command) for command in checklist.get("local_acceptance_commands", []))
    lines.extend(["```", "", "## 10. 禁止事项", ""])
    lines.extend(
        [
            "1. 不能用 mock 图像替代真实 P2 图像。",
            "2. 不能跳过 `prompt_plan.json`、`image_pairs.json` 或 image manifests。",
            "3. 不能把 P3 attack 输出混入 P2 图像生成目录。",
            "4. 不能手工声明 P2 通过, 必须运行接收验收命令。",
            "",
        ]
    )
    return "\n".join(lines)


def write_p2_image_generation_gpu_handoff(
    *,
    workspace_root: str | Path,
    handoff_root: str | Path | None = None,
) -> dict[str, Any]:
    """写出 P2 GPU 交接 JSON 清单和 Markdown runbook。"""
    checklist = build_p2_image_generation_gpu_handoff_checklist(
        workspace_root=workspace_root,
        handoff_root=handoff_root,
    )
    handoff = Path(checklist["handoff_root"])
    _write_json(handoff / P2_GPU_HANDOFF_CHECKLIST_NAME, checklist)
    (handoff / P2_GPU_HANDOFF_RUNBOOK_NAME).write_text(
        render_p2_image_generation_gpu_handoff_runbook(checklist),
        encoding="utf-8",
    )
    return checklist
