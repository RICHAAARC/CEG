"""Colab 冷启动执行 CEG 论文结果链路的轻量 helper。

Notebook 只调用本模块提供的入口; 正式 records、tables、figures、reports 和结果包仍由
`scripts/`、`experiments/` 和 `main/` 中的 repository modules 生成。这样可以避免 Notebook
成为唯一实现路径, 同时让无本地 GPU 的环境把重型运行放到 Colab 中完成。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


def is_colab_runtime() -> bool:
    """判断当前 Python 进程是否运行在 Google Colab 环境。"""
    return "COLAB_RELEASE_TAG" in os.environ or "google.colab" in sys.modules


def _probe_nvidia_smi() -> dict[str, Any]:
    """探测 nvidia-smi 是否可用, 供 Colab GPU 预检使用。"""
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "return_code": None, "stdout": "", "stderr": str(exc)}
    return {
        "available": completed.returncode == 0,
        "return_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _probe_torch_cuda() -> dict[str, Any]:
    """探测 torch.cuda 是否可用, 没有安装 torch 时返回显式状态。"""
    try:
        import torch  # type: ignore
    except Exception as exc:  # pragma: no cover - 依赖环境不同, 这里只做结构化记录
        return {"torch_imported": False, "cuda_available": False, "reason": str(exc)}
    return {
        "torch_imported": True,
        "cuda_available": bool(torch.cuda.is_available()),
        "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }




def build_colab_output_layout(workspace_root: str | Path) -> dict[str, str]:
    """返回 Colab 结果根目录下按结果类型划分的输出目录。

    该函数只定义路径布局, 不生成任何论文 records、tables、figures 或 reports。
    Notebook 和 helper 共享同一份布局, 可以避免下载包、外部 baseline、指标文件与
    论文结果包分散到多个不一致的位置。
    """
    workspace = Path(workspace_root).resolve()
    return {
        "drive_output_root": str(workspace),
        "workspace_root": str(workspace),
        "inputs_root": str(workspace / "inputs"),
        "source_inputs_root": str(workspace / "inputs"),
        "experiment_matrix_root": str(workspace / "experiment_matrix"),
        "paper_outputs_root": str(workspace / "paper_outputs"),
        "paper_results_package_root": str(workspace / "paper_results_package"),
        "colab_run_bundle_root": str(workspace / "colab_run_bundle"),
        "provided_results_root": str(workspace / "provided_results"),
        "external_image_generation_root": str(workspace / "external_image_generation"),
        "external_baselines_root": str(workspace / "external_baselines"),
        "external_metrics_root": str(workspace / "external_metrics"),
        "plans_root": str(workspace / "plans"),
        "basic_image_metrics_root": str(workspace / "basic_image_metrics"),
        "ceg_detection_root": str(workspace / "ceg_detection"),
        "image_attacks_root": str(workspace / "image_attacks"),
        "threshold_calibration_root": str(workspace / "threshold_calibration"),
        "acceptance_root": str(workspace / "acceptance"),
        "archives_root": str(workspace / "archives"),
    }


def build_colab_output_layout_manifest(workspace_root: str | Path) -> dict[str, Any]:
    """构造 Colab 结果类型目录 manifest。

    该 manifest 只描述每一类结果应该保存在哪里, 并记录当前目录是否存在与文件数量。
    它不会生成正式论文结果, 但可以让 Colab、bundle 和离线复核流程共同确认
    `/content/drive/MyDrive/CEG` 下的类型化落盘契约。
    """
    workspace = Path(workspace_root).resolve()
    layout = build_colab_output_layout(workspace)
    directory_specs = [
        ("source_inputs", "inputs_root", "输入、dry-run 输入和样本清单转换产物。"),
        ("experiment_matrix", "experiment_matrix_root", "实验矩阵和矩阵 manifest。"),
        ("paper_outputs", "paper_outputs_root", "由 records 和 manifests 重建的论文表格、图、报告与审计产物。"),
        ("paper_results_package", "paper_results_package_root", "可离线复核的论文结果包。"),
        ("colab_run_bundle", "colab_run_bundle_root", "Colab 运行级 provenance bundle。"),
        ("provided_results", "provided_results_root", "用户直接提供 baseline / metric 文件的受治理副本。"),
        ("external_image_generation", "external_image_generation_root", "真实 SD / watermark 图像生成命令计划、执行结果和输出契约报告。"),
        ("external_baselines", "external_baselines_root", "第三方 baseline 命令计划和执行结果。"),
        ("external_metrics", "external_metrics_root", "LPIPS、FID、CLIP score 等高级指标命令计划和执行结果。"),
        ("command_plans", "plans_root", "由模板物化出的外部命令计划。"),
        ("basic_image_metrics", "basic_image_metrics_root", "轻量 PSNR / SSIM 图像质量指标。"),
        ("ceg_detection", "ceg_detection_root", "CEG detection 事件、阈值和 producer manifest。"),
        ("image_attacks", "image_attacks_root", "攻击后图像、attack manifest 和 attack shard manifest。"),
        ("threshold_calibration", "threshold_calibration_root", "从 calibration 样本校准出的阈值和校准报告。"),
        ("acceptance", "acceptance_root", "最终验收 CLI 的结构化报告。"),
        ("archives", "archives_root", "可下载 zip 和 sidecar manifest。"),
    ]
    result_type_directories: list[dict[str, Any]] = []
    for result_type, layout_key, purpose in directory_specs:
        directory = Path(layout[layout_key])
        file_count = sum(1 for item in directory.rglob("*") if item.is_file()) if directory.exists() else 0
        result_type_directories.append(
            {
                "result_type": result_type,
                "layout_key": layout_key,
                "path": str(directory),
                "relative_path": directory.relative_to(workspace).as_posix(),
                "exists": directory.exists(),
                "file_count": file_count,
                "purpose": purpose,
            }
        )
    manifest = {
        "artifact_name": "colab_output_layout_manifest.json",
        "drive_output_root": layout["drive_output_root"],
        "workspace_root": layout["workspace_root"],
        "output_layout": layout,
        "result_type_directories": result_type_directories,
    }
    manifest["layout_digest"] = hashlib.sha256(
        json.dumps(result_type_directories, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return manifest


def write_colab_output_layout_manifest(workspace_root: str | Path) -> dict[str, Any]:
    """把 Colab 结果类型目录 manifest 写入 workspace 根目录。"""
    workspace = Path(workspace_root).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    manifest = build_colab_output_layout_manifest(workspace)
    (workspace / "colab_output_layout_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


FORMAL_EVENT_REQUIRED_FIELDS: tuple[str, ...] = (
    "event_id",
    "method_name",
    "split",
    "sample_role",
    "attack_family",
    "attack_condition",
    "is_watermarked",
    "payload",
)

FORMAL_SAMPLE_MANIFEST_REQUIRED_FIELDS: tuple[str, ...] = (
    "event_id",
    "split",
    "sample_role",
    "attack_family",
    "attack_condition",
    "is_watermarked",
    "content_score_raw",
    "attestation_score",
)

FORMAL_BASELINE_OBSERVATION_REQUIRED_FIELDS: tuple[str, ...] = (
    "event_id",
    "baseline_id",
    "score",
    "threshold",
)

FORMAL_METRIC_ROW_REQUIRED_ANY_OF: tuple[str, ...] = ("lpips", "fid", "clip_score")
FORMAL_IMAGE_PAIR_REQUIRED_FIELDS: tuple[str, ...] = ("reference_path", "watermarked_path")


def build_colab_formal_input_contract(workspace_root: str | Path) -> dict[str, Any]:
    """构造 Colab 正式论文运行的输入契约 manifest。

    该函数只声明正式运行需要哪些输入文件、最小字段和推荐落盘路径, 不生成正式
    records、tables、figures 或 reports。它的通用价值在于把 Notebook 配置项、
    repository scripts 和第三方 baseline / metric 脚本之间的接口显式化, 便于在
    Colab 冷启动前检查输入是否足以支撑论文级结果。
    """
    workspace = Path(workspace_root).resolve()
    layout = build_colab_output_layout(workspace)
    input_files = [
        {
            "role": "events",
            "recommended_relative_path": "inputs/events.json",
            "accepted_formats": ["json"],
            "required_fields": list(FORMAL_EVENT_REQUIRED_FIELDS),
            "optional_fields": ["payload.thresholds", "payload.content", "payload.geometry", "payload.attestation", "payload.standard_metrics"],
            "required_when": "USE_DRY_RUN_INPUTS=False and SAMPLE_MANIFEST_PATH is not provided",
            "consumed_by": ["scripts/build_paper_outputs.py"],
            "can_generate_from": "sample_manifest + thresholds via scripts/build_protocol_events_from_sample_manifest.py",
        },
        {
            "role": "thresholds",
            "recommended_relative_path": "inputs/thresholds.json",
            "accepted_formats": ["json_object"],
            "required_fields": ["ceg or method_name threshold keys"],
            "optional_fields": ["per-method content thresholds"],
            "required_when": "USE_DRY_RUN_INPUTS=False and CALIBRATE_THRESHOLDS=False",
            "consumed_by": ["scripts/build_paper_outputs.py", "scripts/build_protocol_events_from_sample_manifest.py"],
            "can_generate_from": "sample_manifest calibration split via scripts/calibrate_thresholds_from_sample_manifest.py",
        },
        {
            "role": "prompt_plan",
            "recommended_relative_path": "inputs/prompt_plan.json",
            "accepted_formats": ["json", "jsonl", "csv"],
            "required_fields": ["prompt_id", "prompt_text", "seed"],
            "optional_fields": ["event_id", "image_id", "model_id", "scheduler", "num_inference_steps", "guidance_scale", "split", "sample_role"],
            "required_when": "需要从 prompt 生成 clean / watermarked image manifests 时",
            "consumed_by": ["scripts/generate_mock_image_generation.py", "external SD / watermark backend"],
            "can_generate_from": "dry-run events via experiments.image_generation_backend.build_prompt_plan_from_events",
        },
        {
            "role": "sample_manifest",
            "recommended_relative_path": "inputs/sample_manifest.json",
            "accepted_formats": ["json", "jsonl", "csv"],
            "required_fields": list(FORMAL_SAMPLE_MANIFEST_REQUIRED_FIELDS),
            "optional_fields": [
                "registration_confidence",
                "anchor_inlier_ratio",
                "recovered_sync_consistency",
                "alignment_residual",
                "geometry_fail_reason",
                "reference_path",
                "watermarked_path",
                "bit_accuracy",
                "psnr",
                "ssim",
            ],
            "required_when": "需要由样本清单生成 events、image_pairs 或 calibration thresholds 时",
            "consumed_by": [
                "scripts/build_protocol_events_from_sample_manifest.py",
                "scripts/calibrate_thresholds_from_sample_manifest.py",
            ],
            "can_generate_from": None,
        },
        {
            "role": "baseline_observations",
            "recommended_relative_path": "provided_results/baseline_observations.json",
            "accepted_formats": ["json", "jsonl", "csv"],
            "required_fields": list(FORMAL_BASELINE_OBSERVATION_REQUIRED_FIELDS),
            "optional_fields": ["score_name", "higher_is_positive", "metadata", "metadata.bit_accuracy", "metadata.psnr", "metadata.ssim"],
            "required_when": "RUN_EXTERNAL_PLANS=False 的正式对比实验, 或第三方 baseline 已离线运行完成",
            "consumed_by": ["scripts/build_paper_outputs.py"],
            "can_generate_from": "external baseline command plan via scripts/run_baseline_plan.py",
        },
        {
            "role": "metric_rows",
            "recommended_relative_path": "provided_results/metric_rows.json",
            "accepted_formats": ["json", "jsonl", "csv"],
            "required_fields": ["event_id", "one of: " + ", ".join(FORMAL_METRIC_ROW_REQUIRED_ANY_OF)],
            "optional_fields": ["method_name", "baseline_id", "psnr", "ssim", "mse", "mae", "bit_accuracy"],
            "required_when": "正式图像水印标准指标需要 LPIPS / FID / CLIP score 等高级指标时",
            "consumed_by": ["scripts/build_paper_outputs.py"],
            "can_generate_from": "external metric command plan via scripts/run_metric_plan.py",
        },
        {
            "role": "image_pairs",
            "recommended_relative_path": "inputs/image_pairs.json",
            "accepted_formats": ["json", "jsonl", "csv"],
            "required_fields": list(FORMAL_IMAGE_PAIR_REQUIRED_FIELDS),
            "optional_fields": ["image_id", "event_id", "method_name", "split", "sample_role", "attack_family", "attack_condition"],
            "required_when": "COMPUTE_BASIC_IMAGE_METRICS=True",
            "consumed_by": ["scripts/compute_image_quality_metrics.py"],
            "can_generate_from": "sample_manifest rows containing reference_path and watermarked_path",
        },
    ]
    third_party_interfaces = [
        {
            "interface_id": "external_sd_watermark_image_generation",
            "expected_output": "prompt plan, image pairs and image manifests",
            "required_output_files": [
                "prompt_plan.json",
                "image_pairs.json",
                "image_manifests/image_generation_manifest.json",
                "image_manifests/image_pair_manifest.json",
            ],
            "template_config": "configs/external_image_generation_command_templates.json",
            "runner": "scripts/run_image_generation_plan.py",
            "notes": "真实 SD / watermark backend 在外部环境运行, CEG 只校验其输出是否满足图像 provenance 契约。",
        },
        {
            "interface_id": "external_baseline_run_ceg_eval",
            "expected_output": "baseline observation rows",
            "required_output_fields": list(FORMAL_BASELINE_OBSERVATION_REQUIRED_FIELDS),
            "template_config": "configs/baseline_command_templates.json",
            "runner": "scripts/run_baseline_plan.py",
            "notes": "第三方 baseline 算法本体不进入 CEG 核心层, 只需输出统一 observation 文件。",
        },
        {
            "interface_id": "external_advanced_metric_scripts",
            "expected_output": "metric rows",
            "required_output_fields": ["event_id", "one advanced metric field"],
            "required_any_metric_fields": list(FORMAL_METRIC_ROW_REQUIRED_ANY_OF),
            "template_config": "configs/external_metric_command_templates.json",
            "runner": "scripts/run_metric_plan.py",
            "notes": "LPIPS、FID 和 CLIP score 通常需要 GPU 或第三方模型依赖, 因此在 Colab 正式运行。",
        },
    ]
    acceptance_requirements = [
        "USE_DRY_RUN_INPUTS=False",
        "REQUIRE_EXPERIMENT_COVERAGE=True",
        "baseline_source_mode is provided_file or external_plan",
        "metric_source_mode is provided_file or external_plan",
        "strict paper_result_evidence passes without --allow-dry-run",
        "provided_file source mode requires provided_result_files_manifest_valid",
        "external_plan source mode requires strict run_colab_acceptance_checks with --require-external-command-results",
        "colab_formal_result_gap_report records ready_for_formal_claims before formal paper claims",
        "colab_paper_result_index production_trace_summary missing_trace_count=0",
    ]
    contract = {
        "artifact_name": "colab_formal_input_contract.json",
        "contract_version": "ceg_colab_formal_input_contract_v1",
        "drive_output_root": layout["drive_output_root"],
        "workspace_root": layout["workspace_root"],
        "input_files": input_files,
        "input_templates_manifest_path": str(Path(layout["inputs_root"]) / "formal_input_templates_manifest.json"),
        "third_party_command_interfaces": third_party_interfaces,
        "formal_acceptance_requirements": acceptance_requirements,
    }
    contract["contract_digest"] = hashlib.sha256(
        json.dumps(
            {
                "input_files": input_files,
                "third_party_command_interfaces": third_party_interfaces,
                "formal_acceptance_requirements": acceptance_requirements,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return contract


def write_colab_formal_input_contract(workspace_root: str | Path) -> dict[str, Any]:
    """把 Colab 正式输入契约 manifest 写入 workspace 根目录。"""
    workspace = Path(workspace_root).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    contract = build_colab_formal_input_contract(workspace)
    (workspace / "colab_formal_input_contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return contract


FORMAL_INPUT_TEMPLATE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "file_name": "events_template.json",
        "role": "events",
        "format": "json",
        "purpose": "填写真实实验事件行; 如果使用 sample_manifest 生成 events, 该模板仅作字段参考。",
        "payload": [
            {
                "event_id": "replace_with_real_event_id",
                "method_name": "ceg",
                "split": "test",
                "sample_role": "positive_source",
                "attack_family": "clean",
                "attack_condition": "none",
                "is_watermarked": True,
                "payload": {
                    "thresholds": {
                        "content_threshold": 0.5,
                        "attestation_threshold": 0.5,
                        "registration_confidence_min": 0.3,
                        "anchor_inlier_ratio_min": 0.5,
                        "recovered_sync_consistency_min": 0.55,
                        "rescue_delta_low": 0.05,
                    },
                    "content": {
                        "content_score_raw": 0.7,
                        "content_score_aligned": 0.7,
                        "content_fail_reason": "none",
                    },
                    "geometry": {
                        "registration_confidence": 0.8,
                        "anchor_inlier_ratio": 0.7,
                        "recovered_sync_consistency": 0.75,
                        "alignment_residual": 0.1,
                    },
                    "attestation": {"attestation_score": 0.9},
                    "standard_metrics": {"bit_accuracy": 0.98, "psnr": 35.0, "ssim": 0.95},
                },
            }
        ],
        "required_fields": list(FORMAL_EVENT_REQUIRED_FIELDS),
    },
    {
        "file_name": "thresholds_template.json",
        "role": "thresholds",
        "format": "json_object",
        "purpose": "填写方法名到 content threshold 的映射; 也可由 calibration split 自动生成。",
        "payload": {"ceg": 0.5, "Full": 0.5, "Content-only": 0.5},
        "required_fields": ["ceg or method_name threshold keys"],
    },
    {
        "file_name": "sample_manifest_template.json",
        "role": "sample_manifest",
        "format": "json",
        "purpose": "填写真实样本清单, 由仓库脚本转换为 events.json 和 image_pairs.json。",
        "payload": [
            {
                "event_id": "replace_with_real_event_id",
                "split": "test",
                "sample_role": "positive_source",
                "attack_family": "clean",
                "attack_condition": "none",
                "is_watermarked": True,
                "content_score_raw": 0.7,
                "attestation_score": 0.9,
                "registration_confidence": 0.8,
                "anchor_inlier_ratio": 0.7,
                "recovered_sync_consistency": 0.75,
                "alignment_residual": 0.1,
                "reference_path": "/content/drive/MyDrive/CEG/inputs/images/reference.png",
                "watermarked_path": "/content/drive/MyDrive/CEG/inputs/images/watermarked.png",
                "bit_accuracy": 0.98,
                "psnr": 35.0,
                "ssim": 0.95,
            }
        ],
        "required_fields": list(FORMAL_SAMPLE_MANIFEST_REQUIRED_FIELDS),
    },
    {
        "file_name": "baseline_observations_template.json",
        "role": "baseline_observations",
        "format": "json",
        "purpose": "填写第三方 baseline 输出, 供 build_paper_outputs.py 合并到对比表。",
        "payload": [
            {
                "event_id": "replace_with_real_event_id",
                "baseline_id": "tree_ring",
                "score": 0.7,
                "threshold": 0.5,
                "score_name": "baseline_score",
                "higher_is_positive": True,
                "metadata": {"bit_accuracy": 0.96, "psnr": 34.0, "ssim": 0.94},
            }
        ],
        "required_fields": list(FORMAL_BASELINE_OBSERVATION_REQUIRED_FIELDS),
    },
    {
        "file_name": "metric_rows_template.json",
        "role": "metric_rows",
        "format": "json",
        "purpose": "填写高级图像水印指标, 至少包含 LPIPS、FID 或 CLIP score 之一。",
        "payload": [
            {
                "event_id": "replace_with_real_event_id",
                "method_name": "ceg",
                "lpips": 0.05,
                "fid": 12.0,
                "clip_score": 0.31,
            }
        ],
        "required_fields": ["event_id", "one of: " + ", ".join(FORMAL_METRIC_ROW_REQUIRED_ANY_OF)],
    },
    {
        "file_name": "image_pairs_template.json",
        "role": "image_pairs",
        "format": "json",
        "purpose": "填写参考图像与水印图像配对, 供轻量 PSNR / SSIM 计算使用。",
        "payload": [
            {
                "image_id": "replace_with_real_image_id",
                "event_id": "replace_with_real_event_id",
                "method_name": "ceg",
                "reference_path": "/content/drive/MyDrive/CEG/inputs/images/reference.png",
                "watermarked_path": "/content/drive/MyDrive/CEG/inputs/images/watermarked.png",
            }
        ],
        "required_fields": list(FORMAL_IMAGE_PAIR_REQUIRED_FIELDS),
    },
)


def build_colab_formal_input_templates_manifest(workspace_root: str | Path) -> dict[str, Any]:
    """构造正式输入模板 manifest, 只描述将要写出的可填写模板。

    这些模板属于 Colab 冷启动的人机协作辅助文件, 不会被声明为正式实验结果,
    也不会替代真实 GPU baseline 或高级指标输出。
    """
    workspace = Path(workspace_root).resolve()
    layout = build_colab_output_layout(workspace)
    templates_root = Path(layout["inputs_root"]) / "formal_input_templates"
    templates = []
    for spec in FORMAL_INPUT_TEMPLATE_SPECS:
        path = templates_root / str(spec["file_name"])
        templates.append(
            {
                "role": spec["role"],
                "file_name": spec["file_name"],
                "format": spec["format"],
                "purpose": spec["purpose"],
                "required_fields": list(spec["required_fields"]),
                "path": str(path),
                "relative_path": path.relative_to(workspace).as_posix(),
                "exists": path.is_file(),
                "byte_count": path.stat().st_size if path.is_file() else 0,
                "sha256": _file_sha256(path) if path.is_file() else None,
            }
        )
    manifest = {
        "artifact_name": "formal_input_templates_manifest.json",
        "workspace_root": str(workspace),
        "templates_root": str(templates_root),
        "templates": templates,
        "template_count": len(templates),
        "template_roles": [str(spec["role"]) for spec in FORMAL_INPUT_TEMPLATE_SPECS],
        "usage_note": "将模板复制到 Notebook 配置的输入路径, 用真实实验值替换示例值, 然后先运行正式清单再构建论文结果。",
    }
    manifest["template_manifest_digest"] = hashlib.sha256(
        json.dumps(templates, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return manifest


def write_colab_formal_input_templates(workspace_root: str | Path) -> dict[str, Any]:
    """写出 Colab 正式输入模板和模板 manifest。

    该函数只生成可填写样例, 不生成正式 records、tables、figures 或 reports。
    Notebook 可以安全调用它来帮助用户准备真实输入文件。
    """
    workspace = Path(workspace_root).resolve()
    layout = build_colab_output_layout(workspace)
    templates_root = Path(layout["inputs_root"]) / "formal_input_templates"
    templates_root.mkdir(parents=True, exist_ok=True)
    for spec in FORMAL_INPUT_TEMPLATE_SPECS:
        path = templates_root / str(spec["file_name"])
        path.write_text(
            json.dumps(spec["payload"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    manifest = build_colab_formal_input_templates_manifest(workspace)
    manifest_path = Path(layout["inputs_root"]) / "formal_input_templates_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _runbook_json_summary(path: Path, keys: tuple[str, ...]) -> dict[str, Any]:
    """从 JSON 文件中提取 runbook 需要展示的少量字段。"""
    payload = _read_json_object(path) or {}
    return {key: payload.get(key) for key in keys}


def build_colab_formal_runbook(workspace_root: str | Path) -> str:
    """构造 Colab 正式运行说明书 Markdown。

    该说明书只汇总已经生成的契约、模板、清单、缺口报告和验收命令, 不重新计算
    records、tables、figures 或 reports。它的目的在于让 Colab 使用者能从冷启动
    明确知道下一步应准备哪些真实输入、运行哪些 cell、如何判断结果是否可用于论文声明。
    """
    workspace = Path(workspace_root).resolve()
    contract = _read_json_object(workspace / "colab_formal_input_contract.json") or build_colab_formal_input_contract(workspace)
    templates = _read_json_object(workspace / "inputs" / "formal_input_templates_manifest.json") or build_colab_formal_input_templates_manifest(workspace)
    checklist = _read_json_object(workspace / "colab_formal_run_checklist.json") or {}
    gap_report = _read_json_object(workspace / "colab_formal_result_gap_report.json") or {}
    acceptance_report = _read_json_object(workspace / "colab_acceptance_report.json") or {}
    archive_manifest = _read_json_object(workspace / "archives" / "colab_bundle_archive_manifest.json") or {}
    output_layout = build_colab_output_layout(workspace)

    input_lines = []
    for item in contract.get("input_files", []):
        if not isinstance(item, dict):
            continue
        input_lines.append(
            f"- `{item.get('role')}`: 推荐路径 `{item.get('recommended_relative_path')}`, "
            f"必需字段 `{', '.join(str(field) for field in item.get('required_fields', []))}`。"
        )
    if not input_lines:
        input_lines.append("- 未找到输入契约条目, 请先生成 `colab_formal_input_contract.json`。")

    template_lines = []
    for item in templates.get("templates", []):
        if not isinstance(item, dict):
            continue
        template_lines.append(f"- `{item.get('role')}`: `{item.get('relative_path')}`")
    if not template_lines:
        template_lines.append("- 未找到模板 manifest, 请先运行模板生成 cell。")

    blocking_gaps = gap_report.get("blocking_gap_requirements") if isinstance(gap_report.get("blocking_gap_requirements"), list) else []
    gap_lines = [f"- `{gap}`" for gap in blocking_gaps] or ["- 当前未生成缺口报告, 或缺口报告未列出阻断项。"]

    acceptance_commands = checklist.get("acceptance_commands") if isinstance(checklist.get("acceptance_commands"), dict) else {}
    command_lines = []
    for name, command in acceptance_commands.items():
        if isinstance(command, list):
            command_lines.append(f"- `{name}`: `{' '.join(str(part) for part in command)}`")
    offline_command = archive_manifest.get("offline_acceptance_command")
    if isinstance(offline_command, list):
        command_lines.append(f"- `offline_acceptance`: `{' '.join(str(part) for part in offline_command)}`")
    if not command_lines:
        command_lines.append("- 尚未生成 acceptance 命令, 请先运行正式清单 cell。")

    lines = [
        "# CEG Colab 正式运行说明书",
        "",
        "该说明书由 repository helper 生成, 只汇总输入契约、模板、运行清单、缺口报告和验收命令。",
        "它不生成正式 records、tables、figures 或 reports, 因此不能替代真实 GPU 实验。",
        "",
        "## 1. Drive 输出根目录",
        "",
        f"- workspace: `{workspace}`",
        f"- paper outputs: `{output_layout['paper_outputs_root']}`",
        f"- paper results package: `{output_layout['paper_results_package_root']}`",
        f"- colab run bundle: `{output_layout['colab_run_bundle_root']}`",
        f"- archives: `{output_layout['archives_root']}`",
        "",
        "## 2. 正式输入准备",
        "",
        *input_lines,
        "",
        "## 3. 可填写模板",
        "",
        *template_lines,
        "",
        "## 4. 正式运行前清单状态",
        "",
        f"- checklist decision: `{checklist.get('overall_decision')}`",
        f"- blocking issue count: `{checklist.get('blocking_issue_count')}`",
        f"- baseline source mode: `{checklist.get('baseline_source_mode')}`",
        f"- metric source mode: `{checklist.get('metric_source_mode')}`",
        "",
        "## 5. 当前正式结果缺口",
        "",
        f"- gap decision: `{gap_report.get('overall_decision')}`",
        f"- blocking gap count: `{gap_report.get('blocking_gap_count')}`",
        *gap_lines,
        "",
        "## 6. 验收命令",
        "",
        *command_lines,
        "",
        "## 7. 结果是否可用于论文声明",
        "",
        f"- acceptance decision: `{acceptance_report.get('overall_decision')}`",
        "- 只有在非 dry-run、实验矩阵覆盖通过、baseline / 高级指标来源证据按模式通过且严格 evidence / acceptance 均通过时, 才能支撑正式论文结果声明; `provided_file` 模式依赖 `provided_result_files_manifest.json`, `external_plan` 模式依赖 `--require-external-command-results`。",
    ]
    return "\n".join(lines) + "\n"


def write_colab_formal_runbook(workspace_root: str | Path) -> dict[str, Any]:
    """写出 Colab 正式运行说明书, 并返回可纳入 summary 的摘要。"""
    workspace = Path(workspace_root).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    runbook_path = workspace / "colab_formal_runbook.md"
    body = build_colab_formal_runbook(workspace)
    runbook_path.write_text(body, encoding="utf-8")
    return {
        "artifact_name": "colab_formal_runbook.md",
        "path": str(runbook_path),
        "relative_path": "colab_formal_runbook.md",
        "byte_count": runbook_path.stat().st_size,
        "sha256": _file_sha256(runbook_path),
    }


COLAB_PAPER_RESULT_INDEX_SPECS: tuple[dict[str, Any], ...] = (
    {
        "result_group": "core_governed_tables",
        "result_id": "formal_main_table",
        "relative_path": "paper_results_package/artifacts/formal_main_table.csv",
        "required_for_paper_outputs": True,
        "purpose": "论文主结果表, 汇总 CEG 主方法的核心检测与恢复表现。",
    },
    {
        "result_group": "core_governed_tables",
        "result_id": "formal_final_decision_metrics",
        "relative_path": "paper_results_package/artifacts/formal_final_decision_metrics.json",
        "required_for_paper_outputs": True,
        "purpose": "正式 final decision 指标 JSON, 作为主结果表和 claim audit 的事实来源。",
    },
    {
        "result_group": "core_governed_tables",
        "result_id": "content_score_distribution_audit",
        "relative_path": "paper_results_package/artifacts/content_score_distribution_audit.json",
        "required_for_paper_outputs": True,
        "purpose": "内容分数分布审计, 用于解释阈值附近样本和分数退化风险。",
    },
    {
        "result_group": "core_governed_tables",
        "result_id": "content_threshold_degeneracy_report",
        "relative_path": "paper_results_package/artifacts/content_threshold_degeneracy_report.json",
        "required_for_paper_outputs": True,
        "purpose": "内容阈值退化报告, 用于阻断不可解释或退化的正式阈值结果。",
    },
    {
        "result_group": "core_governed_tables",
        "result_id": "operating_point_table",
        "relative_path": "paper_results_package/artifacts/operating_point_table.csv",
        "required_for_paper_outputs": True,
        "purpose": "论文 operating point 表, 记录阈值和运行点。",
    },
    {
        "result_group": "core_governed_tables",
        "result_id": "rescue_metrics_summary",
        "relative_path": "paper_results_package/artifacts/rescue_metrics_summary.csv",
        "required_for_paper_outputs": True,
        "purpose": "几何恢复 rescue 指标汇总, 用于说明恢复链对主方法的贡献。",
    },
    {
        "result_group": "watermark_standard_metrics",
        "result_id": "standard_watermark_metrics",
        "relative_path": "paper_results_package/artifacts/standard_watermark_metrics.json",
        "required_for_paper_outputs": True,
        "purpose": "图像水印标准指标汇总, 包括质量和检测相关指标。",
    },
    {
        "result_group": "watermark_standard_metrics",
        "result_id": "quality_metrics_summary",
        "relative_path": "paper_results_package/artifacts/quality_metrics_summary.csv",
        "required_for_paper_outputs": True,
        "purpose": "PSNR、SSIM、LPIPS、FID、CLIP score 等质量指标的论文表格来源。",
    },
    {
        "result_group": "watermark_standard_metrics",
        "result_id": "bit_recovery_metrics",
        "relative_path": "paper_results_package/artifacts/bit_recovery_metrics.csv",
        "required_for_paper_outputs": True,
        "purpose": "水印 bit recovery 相关指标。",
    },
    {
        "result_group": "watermark_standard_metrics",
        "result_id": "attack_family_metrics",
        "relative_path": "paper_results_package/artifacts/attack_family_metrics.csv",
        "required_for_paper_outputs": True,
        "purpose": "按攻击族划分的检测和 bit recovery 指标。",
    },
    {
        "result_group": "watermark_standard_metrics",
        "result_id": "rate_confidence_intervals",
        "relative_path": "paper_results_package/artifacts/rate_confidence_intervals.csv",
        "required_for_paper_outputs": True,
        "purpose": "TPR、FPR、bit recovery 等比例指标的置信区间表。",
    },
    {
        "result_group": "watermark_standard_metrics",
        "result_id": "detection_roc_curve",
        "relative_path": "paper_results_package/artifacts/detection_roc_curve.csv",
        "required_for_paper_outputs": True,
        "purpose": "检测 ROC 曲线数据, 供论文图和 LaTeX 表复核。",
    },
    {
        "result_group": "watermark_standard_metrics",
        "result_id": "score_histogram_table",
        "relative_path": "paper_results_package/artifacts/score_histogram_table.csv",
        "required_for_paper_outputs": True,
        "purpose": "检测分数直方图数据, 供分数分布图复核。",
    },
    {
        "result_group": "watermark_standard_metrics",
        "result_id": "fixed_fpr_threshold_table",
        "relative_path": "paper_results_package/artifacts/fixed_fpr_threshold_table.csv",
        "required_for_paper_outputs": True,
        "purpose": "fixed-FPR 阈值校准表, 记录目标 FPR、校准阈值和校准集观测 FPR。",
    },
    {
        "result_group": "watermark_standard_metrics",
        "result_id": "tpr_at_fixed_fpr_table",
        "relative_path": "paper_results_package/artifacts/tpr_at_fixed_fpr_table.csv",
        "required_for_paper_outputs": True,
        "purpose": "TPR@FPR 主结果表, 用于论文在固定 FPR 下报告检测能力。",
    },
    {
        "result_group": "watermark_standard_metrics",
        "result_id": "attack_tpr_at_fixed_fpr_table",
        "relative_path": "paper_results_package/artifacts/attack_tpr_at_fixed_fpr_table.csv",
        "required_for_paper_outputs": True,
        "purpose": "攻击分组 TPR@FPR 表, 用于鲁棒性评价和 attack family 对比。",
    },
    {
        "result_group": "baseline_and_ablation",
        "result_id": "baseline_comparison_table",
        "relative_path": "paper_results_package/artifacts/baseline_comparison_table.csv",
        "required_for_paper_outputs": True,
        "purpose": "内部和外部 baseline 对比表。",
    },
    {
        "result_group": "baseline_and_ablation",
        "result_id": "method_group_comparison_table",
        "relative_path": "paper_results_package/artifacts/method_group_comparison_table.csv",
        "required_for_paper_outputs": True,
        "purpose": "CEG 主方法、内部消融和外部 baseline 的方法组对比表。",
    },
    {
        "result_group": "baseline_and_ablation",
        "result_id": "method_pairwise_delta_table",
        "relative_path": "paper_results_package/artifacts/method_pairwise_delta_table.csv",
        "required_for_paper_outputs": True,
        "purpose": "方法间差值和消融影响表。",
    },
    {
        "result_group": "figures",
        "result_id": "paper_figure_specs",
        "relative_path": "paper_results_package/artifacts/paper_figure_specs.json",
        "required_for_paper_outputs": True,
        "purpose": "可重复渲染论文图的图表规格。",
    },
    {
        "result_group": "figures",
        "result_id": "rendered_figure_manifest",
        "relative_path": "paper_results_package/rendered_figures/rendered_paper_figures_manifest.json",
        "required_for_paper_outputs": True,
        "purpose": "HTML / SVG 图表渲染 manifest。",
    },
    {
        "result_group": "figures",
        "result_id": "pdf_figure_manifest",
        "relative_path": "paper_results_package/pdf_figures/paper_figures_pdf_manifest.json",
        "required_for_paper_outputs": True,
        "purpose": "PDF 图表预览 manifest。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "paper_results_report",
        "relative_path": "paper_results_package/paper_results_report.md",
        "required_for_paper_outputs": True,
        "purpose": "论文结果 Markdown 报告。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_tables_manifest",
        "relative_path": "paper_results_package/latex_tables/latex_tables_manifest.json",
        "required_for_paper_outputs": True,
        "purpose": "LaTeX 表格导出 manifest。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_formal_main_table",
        "relative_path": "paper_results_package/latex_tables/formal_main_table.tex",
        "required_for_paper_outputs": True,
        "purpose": "论文主结果表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_rescue_metrics_summary",
        "relative_path": "paper_results_package/latex_tables/rescue_metrics_summary.tex",
        "required_for_paper_outputs": True,
        "purpose": "rescue 指标汇总表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_baseline_comparison_table",
        "relative_path": "paper_results_package/latex_tables/baseline_comparison_table.tex",
        "required_for_paper_outputs": True,
        "purpose": "baseline 对比表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_method_group_comparison_table",
        "relative_path": "paper_results_package/latex_tables/method_group_comparison_table.tex",
        "required_for_paper_outputs": True,
        "purpose": "方法组和消融对比表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_quality_metrics_summary",
        "relative_path": "paper_results_package/latex_tables/quality_metrics_summary.tex",
        "required_for_paper_outputs": True,
        "purpose": "质量指标表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_bit_recovery_metrics",
        "relative_path": "paper_results_package/latex_tables/bit_recovery_metrics.tex",
        "required_for_paper_outputs": True,
        "purpose": "bit recovery 指标表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_attack_family_metrics",
        "relative_path": "paper_results_package/latex_tables/attack_family_metrics.tex",
        "required_for_paper_outputs": True,
        "purpose": "攻击族鲁棒性指标表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_rate_confidence_intervals",
        "relative_path": "paper_results_package/latex_tables/rate_confidence_intervals.tex",
        "required_for_paper_outputs": True,
        "purpose": "比例指标置信区间表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_method_pairwise_delta_table",
        "relative_path": "paper_results_package/latex_tables/method_pairwise_delta_table.tex",
        "required_for_paper_outputs": True,
        "purpose": "方法成对差值表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_detection_roc_curve",
        "relative_path": "paper_results_package/latex_tables/detection_roc_curve.tex",
        "required_for_paper_outputs": True,
        "purpose": "检测 ROC 曲线数据表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_score_histogram_table",
        "relative_path": "paper_results_package/latex_tables/score_histogram_table.tex",
        "required_for_paper_outputs": True,
        "purpose": "分数直方图数据表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_operating_point_table",
        "relative_path": "paper_results_package/latex_tables/operating_point_table.tex",
        "required_for_paper_outputs": True,
        "purpose": "operating point 表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_fixed_fpr_threshold_table",
        "relative_path": "paper_results_package/latex_tables/fixed_fpr_threshold_table.tex",
        "required_for_paper_outputs": True,
        "purpose": "fixed-FPR 阈值校准表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_tpr_at_fixed_fpr_table",
        "relative_path": "paper_results_package/latex_tables/tpr_at_fixed_fpr_table.tex",
        "required_for_paper_outputs": True,
        "purpose": "TPR@FPR 主结果表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "latex_attack_tpr_at_fixed_fpr_table",
        "relative_path": "paper_results_package/latex_tables/attack_tpr_at_fixed_fpr_table.tex",
        "required_for_paper_outputs": True,
        "purpose": "攻击分组 TPR@FPR 表的 LaTeX 导出。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "paper_readiness_report",
        "relative_path": "paper_results_package/paper_readiness_report.json",
        "required_for_paper_outputs": True,
        "purpose": "论文产物 readiness 门禁报告。",
    },
    {
        "result_group": "paper_reports",
        "result_id": "paper_claim_audit",
        "relative_path": "paper_results_package/artifacts/paper_claim_audit.json",
        "required_for_paper_outputs": True,
        "purpose": "supported claims 到受治理产物的审计报告。",
    },
    {
        "result_group": "image_examples",
        "result_id": "image_generation_manifest",
        "relative_path": "paper_results_package/image_manifests/image_generation_manifest.json",
        "required_for_paper_outputs": True,
        "purpose": "图像生成 provenance manifest, 记录 prompt、seed、模型和图像来源字段。",
    },
    {
        "result_group": "image_examples",
        "result_id": "image_pair_manifest",
        "relative_path": "paper_results_package/image_manifests/image_pair_manifest.json",
        "required_for_paper_outputs": True,
        "purpose": "clean / watermarked / attacked 图像配对 manifest。",
    },
    {
        "result_group": "image_examples",
        "result_id": "image_example_manifest",
        "relative_path": "paper_results_package/image_examples/image_example_manifest.json",
        "required_for_paper_outputs": True,
        "purpose": "论文示例图 manifest, 记录示例图来源、角色、摘要和相对路径。",
    },
    {
        "result_group": "image_examples",
        "result_id": "attacked_image_manifest",
        "relative_path": "paper_results_package/image_manifests/attacked_image_manifest.json",
        "required_for_paper_outputs": True,
        "purpose": "攻击后图像 provenance manifest, 记录攻击族、攻击参数和 attacked image 路径。",
    },
    {
        "result_group": "image_examples",
        "result_id": "attack_shard_manifest",
        "relative_path": "paper_results_package/image_manifests/attack_shard_manifest.json",
        "required_for_paper_outputs": True,
        "purpose": "attack shard 执行 manifest, 记录 PW03 attack workflow 的输入、输出和摘要。",
    },
    {
        "result_group": "external_evidence",
        "result_id": "ceg_detection_execution_manifest",
        "relative_path": "ceg_detection/ceg_detection_execution_manifest.json",
        "required_for_paper_outputs": False,
        "purpose": "真实 CEG detector backend 或 dry-run detection producer 的执行摘要 manifest。",
    },
    {
        "result_group": "external_evidence",
        "result_id": "external_baseline_observations",
        "relative_path": "external_baselines/baseline_observations.json",
        "required_for_paper_outputs": False,
        "purpose": "Colab 运行外部 baseline 计划后产生的 baseline observation。",
    },
    {
        "result_group": "external_evidence",
        "result_id": "external_baseline_execution_manifest",
        "relative_path": "external_baselines/baseline_execution_manifest.json",
        "required_for_paper_outputs": False,
        "purpose": "外部 baseline pilot 或第三方 baseline 执行摘要 manifest。",
    },
    {
        "result_group": "external_evidence",
        "result_id": "external_metric_rows",
        "relative_path": "external_metrics/metric_rows.json",
        "required_for_paper_outputs": False,
        "purpose": "Colab 运行 LPIPS、FID、CLIP score 等高级指标计划后产生的 metric rows。",
    },
    {
        "result_group": "external_evidence",
        "result_id": "external_metric_execution_manifest",
        "relative_path": "external_metrics/metric_execution_manifest.json",
        "required_for_paper_outputs": False,
        "purpose": "外部高级指标或轻量质量指标 runner 的执行摘要 manifest。",
    },
    {
        "result_group": "external_evidence",
        "result_id": "provided_result_files_manifest",
        "relative_path": "provided_results/provided_result_files_manifest.json",
        "required_for_paper_outputs": False,
        "purpose": "用户直接提供 baseline / metric 结果文件时的副本摘要 manifest。",
    },
    {
        "result_group": "colab_delivery",
        "result_id": "paper_results_package_manifest",
        "relative_path": "paper_results_package/paper_results_package_manifest.json",
        "required_for_paper_outputs": True,
        "purpose": "论文结果包 manifest。",
    },
    {
        "result_group": "colab_delivery",
        "result_id": "colab_run_bundle_manifest",
        "relative_path": "colab_run_bundle/colab_run_bundle_manifest.json",
        "required_for_paper_outputs": False,
        "purpose": "Colab 运行级 bundle manifest。",
    },
    {
        "result_group": "colab_delivery",
        "result_id": "colab_formal_input_contract",
        "relative_path": "colab_formal_input_contract.json",
        "required_for_paper_outputs": False,
        "purpose": "Colab 正式实验输入契约 manifest, 声明 events、thresholds、baseline、metric rows 和第三方脚本接口。",
    },
    {
        "result_group": "colab_delivery",
        "result_id": "formal_input_templates_manifest",
        "relative_path": "inputs/formal_input_templates_manifest.json",
        "required_for_paper_outputs": False,
        "purpose": "Colab 正式实验输入模板 manifest, 指向可填写的 events、thresholds、sample manifest、baseline、metric rows 和 image pairs 模板。",
    },
    {
        "result_group": "colab_delivery",
        "result_id": "colab_formal_runbook",
        "relative_path": "colab_formal_runbook.md",
        "required_for_paper_outputs": False,
        "purpose": "Colab 正式运行说明书, 串联输入准备、模板、清单、缺口报告和验收命令。",
    },
    {
        "result_group": "colab_delivery",
        "result_id": "colab_bundle_archive",
        "relative_path": "archives/ceg_colab_run_bundle.zip",
        "required_for_paper_outputs": False,
        "purpose": "可下载的 Colab 运行级 zip bundle。",
    },
 )


COLAB_RESULT_GROUP_PRODUCTION_TRACES: dict[str, dict[str, tuple[str, ...]]] = {
    "core_governed_tables": {
        "producer_steps": (
            "scripts/build_paper_outputs.py",
            "main.analysis.rebuild_artifacts.rebuild_paper_artifacts",
            "scripts/export_paper_results_package.py",
        ),
        "required_inputs": (
            "event_records.json 或 sample_manifest + thresholds 生成的正式事件记录",
            "thresholds.json 或 calibrate_thresholds_from_sample_manifest.py 生成的阈值文件",
            "configs/paper_experiment_matrix.json 生成的实验矩阵",
        ),
        "validation_gates": (
            "scripts/validate_paper_outputs.py",
            "paper_readiness_report.json",
            "paper_result_evidence_report.json",
            "colab_paper_result_index semantic_check",
        ),
    },
    "watermark_standard_metrics": {
        "producer_steps": (
            "scripts/build_paper_outputs.py",
            "main.analysis.standard_metrics.aggregate_standard_watermark_metrics",
            "scripts/compute_image_quality_metrics.py 或 scripts/run_metric_plan.py",
            "scripts/export_paper_results_package.py",
        ),
        "required_inputs": (
            "governed event records",
            "metric_rows.json 或 provided_results/metric_rows.json",
            "image_pairs.json 或 sample_manifest 派生的 image pairs",
        ),
        "validation_gates": (
            "paper_readiness_report.json",
            "paper_result_evidence_report.json advanced_metrics_source_ready",
            "colab_paper_result_index semantic_check",
            "colab_paper_result_index semantic_check_summary",
        ),
    },
    "baseline_and_ablation": {
        "producer_steps": (
            "scripts/build_paper_outputs.py",
            "main.analysis.aggregation.build_baseline_comparison_table",
            "scripts/run_baseline_plan.py 或 copy_provided_result_files",
            "scripts/run_baseline_pilot_producer.py",
            "scripts/export_paper_results_package.py",
        ),
        "required_inputs": (
            "governed event records",
            "baseline_observations.json 或 provided_results/baseline_observations.json",
            "内部 CEG ablation / baseline 方法配置",
        ),
        "validation_gates": (
            "paper_experiment_coverage_report.json",
            "paper_readiness_report.json",
            "paper_result_evidence_report.json baseline_source_ready",
            "colab_paper_result_index semantic_check",
        ),
    },
    "figures": {
        "producer_steps": (
            "scripts/build_paper_outputs.py",
            "main.analysis.figure_specs.build_paper_figure_specs",
            "main.analysis.render_figures.write_rendered_figures",
            "main.analysis.pdf_figures.write_pdf_figure_preview",
            "scripts/export_paper_results_package.py",
        ),
        "required_inputs": (
            "paper_results_package/artifacts/*.csv",
            "paper_results_package/artifacts/standard_watermark_metrics.json",
            "paper_results_package/artifacts/paper_figure_specs.json",
        ),
        "validation_gates": (
            "paper_readiness_report.json rendered_figure_outputs_present",
            "paper_readiness_report.json pdf_figure_outputs_present",
            "colab_paper_result_index semantic_check",
        ),
    },
    "paper_reports": {
        "producer_steps": (
            "scripts/export_latex_tables.py",
            "scripts/export_paper_results_report.py",
            "scripts/validate_paper_outputs.py",
            "scripts/export_paper_results_package.py",
        ),
        "required_inputs": (
            "paper_results_package/artifacts/*.csv",
            "paper_results_package/artifacts/paper_claim_audit.json",
            "paper_results_package/paper_readiness_report.json",
            "paper_results_package/rendered_figures/rendered_paper_figures_manifest.json",
        ),
        "validation_gates": (
            "paper_readiness_report.json latex_table_outputs_present",
            "paper_readiness_report.json paper_results_report_present",
            "paper_result_evidence_report.json strict claims and readiness checks",
            "colab_paper_result_index semantic_check",
        ),
    },
    "image_examples": {
        "producer_steps": (
            "scripts/export_image_examples.py",
            "scripts/run_image_attack_workflow.py",
            "main.analysis.image_examples.export_image_example_package",
            "main.analysis.attack_images.run_attack_workflow",
            "scripts/export_paper_results_package.py",
        ),
        "required_inputs": (
            "image_pairs.json 或 sample_manifest 派生的 image pairs",
            "clean / watermarked / attacked image files",
        ),
        "validation_gates": (
            "paper_readiness_report.json image_manifests_and_examples_present",
            "colab_paper_result_index semantic_check",
        ),
    },
    "external_evidence": {
        "producer_steps": (
            "scripts/run_detection_plan.py",
            "scripts/run_ceg_detection_producer.py",
            "scripts/run_baseline_plan.py",
            "scripts/run_baseline_pilot_producer.py",
            "scripts/run_metric_plan.py",
            "copy_provided_result_files",
        ),
        "required_inputs": (
            "configs/baseline_command_templates.json",
            "configs/external_metric_command_templates.json",
            "用户提供的 baseline / metric 文件或第三方命令输出",
        ),
        "validation_gates": (
            "provided_result_files_manifest.json 摘要校验",
            "paper_result_evidence_report.json external source checks",
            "run_colab_acceptance_checks.py",
        ),
    },
    "colab_delivery": {
        "producer_steps": (
            "paper_workflow.colab_utils.cold_start.run_colab_cold_start_pipeline",
            "paper_workflow.colab_utils.cold_start.create_colab_bundle_archive",
            "scripts/validate_colab_run_bundle.py",
        ),
        "required_inputs": (
            "colab_command_plan.json",
            "colab_formal_run_checklist.json",
            "paper_results_package/",
            "paper_result_evidence_report.json",
        ),
        "validation_gates": (
            "colab_run_bundle_validation.json",
            "run_colab_acceptance_checks.py",
            "colab_paper_result_index_semantic_checks_passed",
        ),
    },
}


COLAB_RESULT_ID_PRODUCTION_TRACE_OVERRIDES: dict[str, dict[str, tuple[str, ...]]] = {
    "external_baseline_observations": {
        "producer_steps": ("scripts/run_baseline_plan.py", "scripts/run_baseline_pilot_producer.py"),
        "required_inputs": ("baseline command plan 或 detection_events.json", "governed event records"),
        "validation_gates": ("paper_result_evidence_report.json baseline_source_ready",),
    },
    "external_baseline_execution_manifest": {
        "producer_steps": ("scripts/run_baseline_plan.py", "scripts/run_baseline_pilot_producer.py"),
        "required_inputs": ("baseline command plan 或 detection_events.json", "baseline_observations.json"),
        "validation_gates": ("colab_run_bundle_validation.json",),
    },
    "external_metric_rows": {
        "producer_steps": ("scripts/run_metric_plan.py", "scripts/compute_image_quality_metrics.py"),
        "required_inputs": ("metric command plan", "image_pairs.json 或 sample_manifest"),
        "validation_gates": ("paper_result_evidence_report.json advanced_metrics_source_ready",),
    },
    "ceg_detection_execution_manifest": {
        "producer_steps": ("scripts/run_detection_plan.py", "scripts/run_ceg_detection_producer.py"),
        "required_inputs": ("image_pairs.json", "attacked_image_manifest.json 或 detection command plan"),
        "validation_gates": ("colab_run_bundle_validation.json",),
    },
    "external_metric_execution_manifest": {
        "producer_steps": ("scripts/run_metric_plan.py", "scripts/compute_image_quality_metrics.py"),
        "required_inputs": ("metric command plan 或 image_pairs.json", "metric_rows.json"),
        "validation_gates": ("colab_run_bundle_validation.json",),
    },
    "provided_result_files_manifest": {
        "producer_steps": ("copy_provided_result_files",),
        "required_inputs": ("用户提供的 baseline_observations.json", "用户提供的 metric_rows.json"),
        "validation_gates": ("provided_result_files_manifest.json sha256 摘要", "paper_result_evidence_report.json provided_file source checks"),
    },
    "paper_results_package_manifest": {
        "producer_steps": ("scripts/export_paper_results_package.py", "main.analysis.result_package.export_paper_results_package"),
        "required_inputs": ("paper_outputs/", "paper_readiness_report.json"),
        "validation_gates": ("paper_results_package_validation.json", "colab_run_bundle_validation.json"),
    },
    "colab_formal_input_contract": {
        "producer_steps": ("write_colab_formal_input_contract",),
        "required_inputs": ("Colab formal run configuration",),
        "validation_gates": ("colab_formal_run_checklist.json", "colab_formal_result_gap_report.json"),
    },
    "formal_input_templates_manifest": {
        "producer_steps": ("write_colab_formal_input_templates",),
        "required_inputs": ("Colab formal input contract",),
        "validation_gates": ("formal_input_templates_manifest.json template_digest",),
    },
    "colab_formal_runbook": {
        "producer_steps": ("write_colab_formal_runbook",),
        "required_inputs": ("colab_formal_run_checklist.json", "colab_paper_result_index.json", "colab_formal_result_gap_report.json"),
        "validation_gates": ("colab_formal_runbook_contains_acceptance_guidance",),
    },
    "colab_bundle_archive": {
        "producer_steps": ("create_colab_bundle_archive",),
        "required_inputs": ("colab_run_bundle/", "colab_run_bundle_manifest.json", "colab_run_bundle_validation.json"),
        "validation_gates": ("archive sha256", "offline_acceptance_command", "run_colab_acceptance_checks.py"),
    },
}


def _merge_trace_values(*value_groups: tuple[str, ...]) -> list[str]:
    """合并生产追踪字段, 保持顺序并去重, 便于结果索引稳定复现。"""
    merged: list[str] = []
    for values in value_groups:
        for value in values:
            if value not in merged:
                merged.append(value)
    return merged



def _build_colab_result_production_trace(spec: dict[str, Any]) -> dict[str, Any]:
    """根据结果组和 result_id 构造“如何生产与如何验收”的可审计追踪信息。"""
    group_trace = COLAB_RESULT_GROUP_PRODUCTION_TRACES.get(str(spec["result_group"]), {})
    override = COLAB_RESULT_ID_PRODUCTION_TRACE_OVERRIDES.get(str(spec["result_id"]), {})
    return {
        "producer_steps": _merge_trace_values(
            tuple(group_trace.get("producer_steps", ())),
            tuple(override.get("producer_steps", ())),
        ),
        "required_inputs": _merge_trace_values(
            tuple(group_trace.get("required_inputs", ())),
            tuple(override.get("required_inputs", ())),
        ),
        "validation_gates": _merge_trace_values(
            tuple(group_trace.get("validation_gates", ())),
            tuple(override.get("validation_gates", ())),
        ),
    }


COLAB_RESULT_QUALITY_METRIC_FIELDS: tuple[str, ...] = ("psnr", "ssim", "lpips", "fid", "clip_score")
COLAB_RESULT_REQUIRED_METHODS: tuple[str, ...] = (
    "ceg",
    "ceg_full",
    "ceg_content_only",
    "ceg_recover_then_content",
    "ceg_no_rescue",
    "ceg_no_attestation",
    "tree_ring",
    "gaussian_shading",
    "shallow_diffuse",
    "stable_signature_dee",
)
COLAB_RESULT_INTERNAL_ABLATION_METHODS: tuple[str, ...] = (
    "ceg_full",
    "ceg_content_only",
    "ceg_recover_then_content",
    "ceg_no_rescue",
    "ceg_no_attestation",
)
COLAB_RESULT_EXTERNAL_BASELINE_METHODS: tuple[str, ...] = (
    "tree_ring",
    "gaussian_shading",
    "shallow_diffuse",
    "stable_signature_dee",
)
COLAB_RESULT_PAIRWISE_METRIC_FIELDS: tuple[str, ...] = ("tpr", "clean_fpr", "attacked_negative_fpr")
COLAB_RESULT_STANDARD_METRIC_FIELDS: tuple[str, ...] = (
    "event_count",
    "tpr",
    "clean_fpr",
    "attacked_negative_fpr",
    "detection_auroc",
    "tpr_at_fpr_1_percent",
    "tpr_at_fpr_0_1_percent",
    "bit_accuracy",
    "bit_error_rate",
    "payload_recovery_rate",
)


COLAB_RESULT_SEMANTIC_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "formal_main_table": ("method_name", "tpr", "clean_fpr"),
    "operating_point_table": ("method_name", "operating_threshold", "tpr", "fpr"),
    "quality_metrics_summary": ("method_name", "metric_name", "metric_coverage_rate"),
    "bit_recovery_metrics": ("method_name", "bit_accuracy", "payload_recovery_rate"),
    "attack_family_metrics": ("method_name", "attack_family", "tpr", "bit_accuracy"),
    "rate_confidence_intervals": ("method_name", "metric_name", "rate_value", "ci_lower", "ci_upper"),
    "rescue_metrics_summary": ("method_name", "rescue_gain", "positive_by_geo_rescue_count"),
    "baseline_comparison_table": ("method_name", "event_count", "tpr", "clean_fpr"),
    "method_group_comparison_table": ("method_name", "method_group", "comparison_role", "event_count"),
    "method_pairwise_delta_table": ("reference_method", "method_name", "metric_name", "rate_delta"),
    "detection_roc_curve": ("method_name", "threshold_label", "tpr", "fpr"),
    "score_histogram_table": ("method_name", "label_name", "score_bin_lower", "score_bin_count"),
    "fixed_fpr_threshold_table": ("method_name", "target_fpr", "threshold_value", "calibration_observed_fpr"),
    "tpr_at_fixed_fpr_table": ("method_name", "target_fpr", "test_fpr_at_threshold", "tpr_at_fixed_fpr"),
    "attack_tpr_at_fixed_fpr_table": ("method_name", "target_fpr", "attack_family", "attack_tpr_at_fixed_fpr"),
}


def _read_csv_rows_for_result_index(path: Path) -> list[dict[str, Any]]:
    """读取 CSV 结果表, 仅用于 Colab 结果索引的轻量结构校验。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _semantic_check(status: str, reason: str, evidence: Any) -> dict[str, Any]:
    """构造单个论文结果内容结构检查条目。"""
    return {"status": status, "reason": reason, "evidence": evidence}


def _as_result_index_float(value: Any) -> float | None:
    """把结果索引校验读取到的字符串值转为 float, 用于判断数值单元是否可复核。"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check_csv_result_semantics(path: Path, required_fields: tuple[str, ...]) -> dict[str, Any]:
    """检查 CSV 论文结果表是否非空且包含必需字段。"""
    try:
        rows = _read_csv_rows_for_result_index(path)
    except Exception as exc:
        return _semantic_check("fail", "csv_parse_failed", str(exc))
    fieldnames = set(rows[0].keys()) if rows else set()
    missing_fields = [field for field in required_fields if field not in fieldnames]
    if not rows:
        return _semantic_check("fail", "csv_rows_empty", {"required_fields": list(required_fields)})
    if missing_fields:
        return _semantic_check("fail", "csv_required_fields_missing", {"missing_fields": missing_fields, "fieldnames": sorted(fieldnames)})
    return _semantic_check("pass", "csv_required_fields_present", {"row_count": len(rows), "required_fields": list(required_fields)})


def _check_method_rows_semantics(
    rows: list[dict[str, Any]],
    *,
    required_methods: tuple[str, ...],
    numeric_fields: tuple[str, ...],
    reason: str,
) -> dict[str, Any]:
    """检查方法级 CSV 行覆盖。

    该实现属于通用工程写法: 任何以 `method_name` 为主键的结果表都可以复用该检查。
    它只验证现有表格是否包含必需方法和可解析数值, 不会替代正式统计计算。
    """
    by_method = {str(row.get("method_name")): row for row in rows}
    violations: list[dict[str, Any]] = []
    for method_name in required_methods:
        row = by_method.get(method_name)
        if row is None:
            violations.append({"method_name": method_name, "reason": "missing_method_row"})
            continue
        for field in numeric_fields:
            if _as_result_index_float(row.get(field)) is None:
                violations.append({"method_name": method_name, "field": field, "reason": "missing_or_invalid_numeric_value"})
    if violations:
        return _semantic_check("fail", "required_method_rows_incomplete", {"violations": violations[:50], "violation_count": len(violations)})
    return _semantic_check(
        "pass",
        reason,
        {"required_methods": list(required_methods), "numeric_fields": list(numeric_fields), "row_count": len(rows)},
    )


def _check_baseline_comparison_semantics(path: Path) -> dict[str, Any]:
    """检查 baseline 对比表是否同时覆盖 CEG 内部方法和外部 baseline 方法。"""
    base_check = _check_csv_result_semantics(path, COLAB_RESULT_SEMANTIC_REQUIRED_FIELDS["baseline_comparison_table"])
    if base_check["status"] != "pass":
        return base_check
    rows = _read_csv_rows_for_result_index(path)
    return _check_method_rows_semantics(
        rows,
        required_methods=COLAB_RESULT_REQUIRED_METHODS,
        numeric_fields=("event_count", "tpr", "clean_fpr"),
        reason="baseline_comparison_methods_cover_internal_and_external",
    )


def _check_method_group_comparison_semantics(path: Path) -> dict[str, Any]:
    """检查方法组对比表是否保留主方法、内部消融和外部 baseline 的角色语义。"""
    base_check = _check_csv_result_semantics(path, COLAB_RESULT_SEMANTIC_REQUIRED_FIELDS["method_group_comparison_table"])
    if base_check["status"] != "pass":
        return base_check
    rows = _read_csv_rows_for_result_index(path)
    method_check = _check_method_rows_semantics(
        rows,
        required_methods=COLAB_RESULT_REQUIRED_METHODS,
        numeric_fields=("event_count", "tpr", "clean_fpr"),
        reason="method_group_rows_cover_required_methods",
    )
    if method_check["status"] != "pass":
        return method_check
    by_method = {str(row.get("method_name")): row for row in rows}
    expected_roles = {
        "ceg": ("ceg_primary", "proposed_method"),
        **{method_name: ("ceg_internal_ablation", "mechanism_ablation") for method_name in COLAB_RESULT_INTERNAL_ABLATION_METHODS},
        **{method_name: ("external_baseline", "external_comparison") for method_name in COLAB_RESULT_EXTERNAL_BASELINE_METHODS},
    }
    violations: list[dict[str, Any]] = []
    for method_name, (expected_group, expected_role) in expected_roles.items():
        row = by_method.get(method_name, {})
        if row.get("method_group") != expected_group or row.get("comparison_role") != expected_role:
            violations.append(
                {
                    "method_name": method_name,
                    "reason": "method_group_or_role_mismatch",
                    "expected_method_group": expected_group,
                    "actual_method_group": row.get("method_group"),
                    "expected_comparison_role": expected_role,
                    "actual_comparison_role": row.get("comparison_role"),
                }
            )
    if violations:
        return _semantic_check("fail", "method_group_roles_mismatch", {"violations": violations[:50], "violation_count": len(violations)})
    return _semantic_check("pass", "method_group_roles_cover_proposed_ablation_and_external", {"required_roles": expected_roles})


def _check_method_pairwise_delta_semantics(path: Path) -> dict[str, Any]:
    """检查成对差值表是否包含以 CEG 为参考的内部消融和外部 baseline 指标差值。"""
    base_check = _check_csv_result_semantics(path, COLAB_RESULT_SEMANTIC_REQUIRED_FIELDS["method_pairwise_delta_table"])
    if base_check["status"] != "pass":
        return base_check
    rows = _read_csv_rows_for_result_index(path)
    observed_pairs = {
        (str(row.get("reference_method")), str(row.get("method_name")), str(row.get("metric_name")))
        for row in rows
    }
    violations: list[dict[str, Any]] = []
    for method_name in (method for method in COLAB_RESULT_REQUIRED_METHODS if method != "ceg"):
        for metric_name in COLAB_RESULT_PAIRWISE_METRIC_FIELDS:
            if ("ceg", method_name, metric_name) not in observed_pairs:
                violations.append(
                    {
                        "reference_method": "ceg",
                        "method_name": method_name,
                        "metric_name": metric_name,
                        "reason": "missing_pairwise_delta_row",
                    }
                )
    if violations:
        return _semantic_check("fail", "pairwise_delta_rows_incomplete", {"violations": violations[:50], "violation_count": len(violations)})
    return _semantic_check(
        "pass",
        "pairwise_delta_rows_cover_ablation_and_external_methods",
        {
            "reference_method": "ceg",
            "compared_methods": [method for method in COLAB_RESULT_REQUIRED_METHODS if method != "ceg"],
            "metric_names": list(COLAB_RESULT_PAIRWISE_METRIC_FIELDS),
        },
    )


def _check_standard_watermark_metrics_semantics(path: Path) -> dict[str, Any]:
    """检查标准水印指标 JSON 是否包含方法级指标和质量指标槽位。"""
    payload = _read_json_object(path)
    if not isinstance(payload, dict):
        return _semantic_check("fail", "json_object_missing_or_invalid", str(path))
    by_method = payload.get("by_method")
    if not isinstance(by_method, dict) or not by_method:
        return _semantic_check("fail", "by_method_missing_or_empty", {"artifact_name": payload.get("artifact_name")})
    missing_methods = [method_name for method_name in COLAB_RESULT_REQUIRED_METHODS if method_name not in by_method]
    if missing_methods:
        return _semantic_check("fail", "required_methods_missing_from_standard_metrics", {"missing_methods": missing_methods})
    missing_quality_metrics: dict[str, list[str]] = {}
    missing_standard_metric_fields: dict[str, list[str]] = {}
    for method_name, summary in by_method.items():
        standard_missing = [
            field
            for field in COLAB_RESULT_STANDARD_METRIC_FIELDS
            if not isinstance(summary, dict) or summary.get(field) is None or summary.get(field) == ""
        ]
        if standard_missing:
            missing_standard_metric_fields[str(method_name)] = standard_missing
        quality_metrics = summary.get("quality_metrics") if isinstance(summary, dict) else None
        metric_names = set(quality_metrics.keys()) if isinstance(quality_metrics, dict) else set()
        missing = [field for field in COLAB_RESULT_QUALITY_METRIC_FIELDS if field not in metric_names]
        if missing:
            missing_quality_metrics[str(method_name)] = missing
    if missing_standard_metric_fields:
        return _semantic_check("fail", "standard_metric_fields_missing", missing_standard_metric_fields)
    if missing_quality_metrics:
        return _semantic_check("fail", "quality_metric_slots_missing", missing_quality_metrics)
    return _semantic_check(
        "pass",
        "standard_watermark_metrics_cover_required_methods_and_fields",
        {
            "method_count": len(by_method),
            "required_methods": list(COLAB_RESULT_REQUIRED_METHODS),
            "standard_metric_fields": list(COLAB_RESULT_STANDARD_METRIC_FIELDS),
            "quality_metric_fields": list(COLAB_RESULT_QUALITY_METRIC_FIELDS),
        },
    )


def _check_quality_metrics_summary_semantics(path: Path) -> dict[str, Any]:
    """检查质量指标长表是否覆盖标准图像水印质量指标名称。"""
    base_check = _check_csv_result_semantics(path, COLAB_RESULT_SEMANTIC_REQUIRED_FIELDS["quality_metrics_summary"])
    if base_check["status"] != "pass":
        return base_check
    rows = _read_csv_rows_for_result_index(path)
    metric_names = {str(row.get("metric_name")) for row in rows}
    missing = [field for field in COLAB_RESULT_QUALITY_METRIC_FIELDS if field not in metric_names]
    if missing:
        return _semantic_check("fail", "quality_metric_rows_missing", {"missing_metric_names": missing, "metric_names": sorted(metric_names)})
    return _semantic_check("pass", "quality_metric_rows_cover_standard_fields", {"row_count": len(rows), "quality_metric_fields": list(COLAB_RESULT_QUALITY_METRIC_FIELDS)})


def _check_paper_figure_specs_semantics(path: Path) -> dict[str, Any]:
    """检查论文图表规格 JSON 是否包含可渲染图表条目。"""
    payload = _read_json_object(path)
    figures = payload.get("figures") if isinstance(payload, dict) else None
    if not isinstance(figures, list) or not figures:
        return _semantic_check("fail", "figure_specs_missing_or_empty", {"artifact_name": payload.get("artifact_name") if isinstance(payload, dict) else None})
    figure_ids = [item.get("figure_id") for item in figures if isinstance(item, dict)]
    if not all(figure_ids):
        return _semantic_check("fail", "figure_id_missing", {"figure_ids": figure_ids})
    return _semantic_check("pass", "figure_specs_shape_valid", {"figure_count": len(figures), "figure_ids": figure_ids})


def _check_json_object_result_semantics(path: Path) -> dict[str, Any]:
    """检查 JSON 结果文件是否是非空对象。

    该检查适用于正式指标和审计报告类产物。它不解释具体统计含义, 只保证 Colab 索引中的
    必需 JSON 不是空文件、数组或无法复核的碎片内容。
    """
    payload = _read_json_object(path)
    if not isinstance(payload, dict) or not payload:
        return _semantic_check("fail", "json_object_missing_or_empty", {"path": str(path)})
    return _semantic_check("pass", "json_object_non_empty", {"top_level_keys": sorted(str(key) for key in payload.keys())})


def _check_latex_table_semantics(path: Path) -> dict[str, Any]:
    """检查 LaTeX 表格导出是否包含基本 tabular 结构。

    这是面向论文交付的轻量结构检查, 不重新排版 PDF, 只确认每个必需 `.tex` 表不是空占位文件。
    """
    body = path.read_text(encoding="utf-8-sig")
    required_markers = ("\\begin{tabular}", "\\end{tabular}")
    missing = [marker for marker in required_markers if marker not in body]
    if missing:
        return _semantic_check("fail", "latex_table_markers_missing", {"missing_markers": missing, "byte_count": path.stat().st_size})
    return _semantic_check("pass", "latex_table_tabular_present", {"byte_count": path.stat().st_size})


def _check_manifest_list_semantics(path: Path, list_field: str) -> dict[str, Any]:
    """检查交付 manifest 是否包含非空文件条目列表。"""
    payload = _read_json_object(path)
    items = payload.get(list_field) if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return _semantic_check("fail", "manifest_list_missing_or_empty", {"list_field": list_field, "artifact_name": payload.get("artifact_name") if isinstance(payload, dict) else None})
    return _semantic_check("pass", "manifest_list_non_empty", {"list_field": list_field, "item_count": len(items)})


def _check_paper_results_report_semantics(path: Path) -> dict[str, Any]:
    """检查 Markdown 论文结果报告是否包含基本章节。"""
    body = path.read_text(encoding="utf-8-sig")
    required_markers = ("#", "核心表格", "图表")
    missing = [marker for marker in required_markers if marker not in body]
    if missing:
        return _semantic_check("fail", "report_required_markers_missing", {"missing_markers": missing})
    return _semantic_check("pass", "report_markers_present", {"byte_count": path.stat().st_size})


def _check_colab_result_semantics(result_id: str, path: Path) -> dict[str, Any]:
    """按 result_id 对关键论文结果文件做轻量内容结构校验。"""
    if not path.is_file():
        return {"status": "not_checked", "reason": "file_missing", "checks": []}
    if result_id == "standard_watermark_metrics":
        checks = [_check_standard_watermark_metrics_semantics(path)]
    elif result_id == "quality_metrics_summary":
        checks = [_check_quality_metrics_summary_semantics(path)]
    elif result_id == "baseline_comparison_table":
        checks = [_check_baseline_comparison_semantics(path)]
    elif result_id == "method_group_comparison_table":
        checks = [_check_method_group_comparison_semantics(path)]
    elif result_id == "method_pairwise_delta_table":
        checks = [_check_method_pairwise_delta_semantics(path)]
    elif result_id == "paper_figure_specs":
        checks = [_check_paper_figure_specs_semantics(path)]
    elif result_id in COLAB_RESULT_SEMANTIC_REQUIRED_FIELDS:
        checks = [_check_csv_result_semantics(path, COLAB_RESULT_SEMANTIC_REQUIRED_FIELDS[result_id])]
    elif result_id in {
        "formal_final_decision_metrics",
        "content_score_distribution_audit",
        "content_threshold_degeneracy_report",
        "attacked_image_manifest",
        "attack_shard_manifest",
    }:
        checks = [_check_json_object_result_semantics(path)]
    elif result_id == "rendered_figure_manifest":
        checks = [_check_manifest_list_semantics(path, "rendered_figures")]
    elif result_id == "latex_tables_manifest":
        checks = [_check_manifest_list_semantics(path, "latex_tables")]
    elif result_id.startswith("latex_"):
        checks = [_check_latex_table_semantics(path)]
    elif result_id == "pdf_figure_manifest":
        checks = [_semantic_check("pass", "pdf_manifest_present", {"byte_count": path.stat().st_size})]
    elif result_id == "paper_results_report":
        checks = [_check_paper_results_report_semantics(path)]
    else:
        return {"status": "not_checked", "reason": "no_semantic_rule", "checks": []}
    fail_count = sum(1 for item in checks if item.get("status") != "pass")
    return {"status": "fail" if fail_count else "pass", "reason": "semantic_checks_failed" if fail_count else "semantic_checks_passed", "checks": checks}


def build_colab_paper_result_index(workspace_root: str | Path) -> dict[str, Any]:
    """构造 Colab 论文结果索引 manifest。

    该索引把“论文所需结果图表、标准指标、baseline、消融和交付件”映射到 Drive
    workspace 中的具体文件路径。它只读取现有产物并记录摘要, 不重新计算指标, 因此属于
    Notebook 交付和离线复核层, 不会替代正式 artifact rebuild 逻辑。
    """
    workspace = Path(workspace_root).resolve()
    layout = build_colab_output_layout(workspace)
    indexed_results: list[dict[str, Any]] = []
    for spec in COLAB_PAPER_RESULT_INDEX_SPECS:
        relative = str(spec["relative_path"])
        path = workspace / relative
        entry = {
            "result_group": spec["result_group"],
            "result_id": spec["result_id"],
            "relative_path": relative,
            "path": str(path),
            "exists": path.is_file(),
            "required_for_paper_outputs": bool(spec["required_for_paper_outputs"]),
            "purpose": spec["purpose"],
            "production_trace": _build_colab_result_production_trace(spec),
        }
        if path.is_file():
            entry["byte_count"] = path.stat().st_size
            entry["sha256"] = _file_sha256(path)
            entry["semantic_check"] = _check_colab_result_semantics(str(spec["result_id"]), path)
        else:
            entry["semantic_check"] = {"status": "not_checked", "reason": "file_missing", "checks": []}
        indexed_results.append(entry)

    required_missing = [
        item["relative_path"]
        for item in indexed_results
        if item["required_for_paper_outputs"] and not item["exists"]
    ]
    groups: dict[str, dict[str, Any]] = {}
    for item in indexed_results:
        group = groups.setdefault(
            str(item["result_group"]),
            {
                "result_group": item["result_group"],
                "total": 0,
                "present": 0,
                "required_total": 0,
                "required_present": 0,
                "missing_required_results": [],
            },
        )
        group["total"] += 1
        group["present"] += int(bool(item["exists"]))
        group["required_total"] += int(bool(item["required_for_paper_outputs"]))
        group["required_present"] += int(bool(item["required_for_paper_outputs"] and item["exists"]))
        if item["required_for_paper_outputs"] and not item["exists"]:
            group["missing_required_results"].append(item["result_id"])
    for group in groups.values():
        if group["required_total"] == 0:
            group["overall_decision"] = "not_required"
        else:
            group["overall_decision"] = "pass" if not group["missing_required_results"] else "fail"
    result_group_summary = sorted(groups.values(), key=lambda item: str(item["result_group"]))
    required_result_group_summary = [item for item in result_group_summary if item["required_total"] > 0]
    required_group_failures = [item["result_group"] for item in required_result_group_summary if item["overall_decision"] != "pass"]
    semantic_checkable_results = [item for item in indexed_results if item.get("semantic_check", {}).get("status") in {"pass", "fail"}]
    semantic_check_failures = [
        item["result_id"]
        for item in indexed_results
        if item["required_for_paper_outputs"] and item.get("semantic_check", {}).get("status") == "fail"
    ]
    semantic_check_summary = {
        "checkable_total": len(semantic_checkable_results),
        "pass_count": sum(1 for item in semantic_checkable_results if item.get("semantic_check", {}).get("status") == "pass"),
        "fail_count": len(semantic_check_failures),
        "required_failures": semantic_check_failures,
    }
    missing_trace_result_ids = [
        str(item["result_id"])
        for item in indexed_results
        if not item.get("production_trace", {}).get("producer_steps")
        or not item.get("production_trace", {}).get("validation_gates")
    ]
    production_trace_summary = {
        "traceable_total": len(indexed_results) - len(missing_trace_result_ids),
        "missing_trace_count": len(missing_trace_result_ids),
        "missing_trace_result_ids": missing_trace_result_ids,
    }
    manifest = {
        "artifact_name": "colab_paper_result_index.json",
        "overall_decision": "fail" if (required_missing or required_group_failures or semantic_check_failures) else "pass",
        "drive_output_root": layout["drive_output_root"],
        "workspace_root": layout["workspace_root"],
        "output_layout_manifest_path": str(workspace / "colab_output_layout_manifest.json"),
        "indexed_results": indexed_results,
        "result_group_summary": result_group_summary,
        "required_result_group_summary": required_result_group_summary,
        "required_result_group_count": len(required_result_group_summary),
        "required_result_group_pass_count": sum(1 for item in required_result_group_summary if item["overall_decision"] == "pass"),
        "required_result_group_failures": required_group_failures,
        "semantic_check_summary": semantic_check_summary,
        "semantic_check_failures": semantic_check_failures,
        "production_trace_summary": production_trace_summary,
        "required_missing": required_missing,
        "required_total": sum(1 for item in indexed_results if item["required_for_paper_outputs"]),
        "required_present": sum(1 for item in indexed_results if item["required_for_paper_outputs"] and item["exists"]),
    }
    manifest["result_index_digest"] = hashlib.sha256(
        json.dumps(indexed_results, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return manifest


def write_colab_paper_result_index(workspace_root: str | Path) -> dict[str, Any]:
    """把 Colab 论文结果索引写入 workspace 根目录。"""
    workspace = Path(workspace_root).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    manifest = build_colab_paper_result_index(workspace)
    (workspace / "colab_paper_result_index.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _read_json_object(path: Path) -> dict[str, Any] | None:
    """读取 JSON 对象文件, 文件缺失或结构不符时返回 None。"""
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _formal_gap_check(
    requirement: str,
    status: str,
    severity: str,
    message: str,
    evidence: Any,
) -> dict[str, Any]:
    """构造正式论文结果缺口报告中的单个检查项。"""
    return {
        "requirement": requirement,
        "status": status,
        "severity": severity,
        "message": message,
        "evidence": evidence,
    }


def build_colab_formal_result_gap_report(
    workspace_root: str | Path,
    *,
    acceptance_report_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造 Colab 正式论文结果缺口报告。

    该报告只读取 Colab workspace 中已经生成的 checklist、result index、evidence report、
    coverage report 和外部命令 provenance, 用于解释当前运行距离“可支撑正式论文结果声明”
    还缺哪些证据。它不重新生成 records、tables、figures 或 metrics。
    `acceptance_report_override` 用于 acceptance CLI 在报告尚未写回 bundle 时复核最终验收状态。
    """
    workspace = Path(workspace_root).resolve()
    checklist = _read_json_object(workspace / "colab_formal_run_checklist.json") or {}
    result_index = _read_json_object(workspace / "colab_paper_result_index.json") or {}
    evidence_report = _read_json_object(workspace / "paper_result_evidence_report.json") or {}
    acceptance_report = acceptance_report_override if isinstance(acceptance_report_override, dict) else _read_json_object(workspace / "colab_acceptance_report.json") or {}
    coverage_report = _read_json_object(
        workspace / "paper_results_package" / "artifacts" / "paper_experiment_coverage_report.json"
    ) or {}

    checklist_present = bool(checklist)
    use_dry_run = bool(checklist.get("use_dry_run_inputs"))
    run_external_plans = bool(checklist.get("run_external_plans"))
    require_experiment_coverage = bool(checklist.get("require_experiment_coverage"))
    baseline_source_mode = str(checklist.get("baseline_source_mode") or "missing")
    metric_source_mode = str(checklist.get("metric_source_mode") or "missing")
    gpu_readiness = checklist.get("gpu_readiness") if isinstance(checklist.get("gpu_readiness"), dict) else {}

    checks: list[dict[str, Any]] = []
    checks.append(
        _formal_gap_check(
            "non_dry_run_inputs_used",
            "pass" if (checklist_present and not use_dry_run) else "fail",
            "blocking",
            "正式论文结果必须来自非 dry-run 输入。",
            {"checklist_present": checklist_present, "use_dry_run_inputs": use_dry_run},
        )
    )
    checklist_passed = checklist.get("overall_decision") == "pass" and int(checklist.get("blocking_issue_count", 0) or 0) == 0
    checks.append(
        _formal_gap_check(
            "formal_run_checklist_passed",
            "pass" if checklist_passed else "fail",
            "blocking",
            "正式运行清单必须通过, 且 blocking_issue_count 必须为 0。",
            {
                "overall_decision": checklist.get("overall_decision"),
                "blocking_issue_count": checklist.get("blocking_issue_count"),
                "issue_ids": [item.get("issue_id") for item in checklist.get("issues", []) if isinstance(item, dict)],
            },
        )
    )
    result_group_failures = result_index.get("required_result_group_failures")
    semantic_check_summary = result_index.get("semantic_check_summary") if isinstance(result_index.get("semantic_check_summary"), dict) else {}
    semantic_check_failures = result_index.get("semantic_check_failures")
    production_trace_summary = result_index.get("production_trace_summary") if isinstance(result_index.get("production_trace_summary"), dict) else {}
    production_trace_missing_ids = production_trace_summary.get("missing_trace_result_ids")
    index_complete = (
        result_index.get("overall_decision") == "pass"
        and not result_index.get("required_missing")
        and isinstance(result_group_failures, list)
        and not result_group_failures
        and isinstance(semantic_check_failures, list)
        and not semantic_check_failures
        and int(semantic_check_summary.get("fail_count", -1)) == 0
    )
    checks.append(
        _formal_gap_check(
            "paper_result_index_complete",
            "pass" if index_complete else "fail",
            "blocking",
            "论文结果索引中的必需表格、图表、指标和报告必须全部存在, 且关键结果内容结构必须通过。",
            {
                "overall_decision": result_index.get("overall_decision"),
                "required_missing": result_index.get("required_missing"),
                "required_present": result_index.get("required_present"),
                "required_total": result_index.get("required_total"),
                "required_result_group_failures": result_group_failures,
                "required_result_group_summary": result_index.get("required_result_group_summary"),
                "semantic_check_summary": semantic_check_summary,
                "semantic_check_failures": semantic_check_failures,
            },
        )
    )
    production_trace_complete = (
        isinstance(production_trace_missing_ids, list)
        and not production_trace_missing_ids
        and int(production_trace_summary.get("missing_trace_count", -1)) == 0
    )
    checks.append(
        _formal_gap_check(
            "paper_result_index_production_trace_complete",
            "pass" if production_trace_complete else "fail",
            "blocking",
            "论文结果索引中的每个 result_id 必须说明生成步骤、上游输入和验收门禁。",
            {
                "production_trace_summary": production_trace_summary,
                "missing_trace_result_ids": production_trace_missing_ids,
            },
        )
    )
    coverage_passed = require_experiment_coverage and coverage_report.get("overall_decision") == "pass"
    checks.append(
        _formal_gap_check(
            "experiment_matrix_coverage_enforced",
            "pass" if coverage_passed else "fail",
            "blocking",
            "正式论文结果必须开启并通过实验矩阵覆盖率门禁。",
            {
                "require_experiment_coverage": require_experiment_coverage,
                "coverage_decision": coverage_report.get("overall_decision"),
            },
        )
    )
    baseline_ready = baseline_source_mode in {"provided_file", "external_plan"}
    checks.append(
        _formal_gap_check(
            "external_baseline_source_ready",
            "pass" if baseline_ready else "fail",
            "blocking",
            "正式论文对比需要外部 baseline observation 文件或可执行外部 baseline 计划。",
            {"baseline_source_mode": baseline_source_mode},
        )
    )
    metric_ready = metric_source_mode in {"provided_file", "external_plan"}
    checks.append(
        _formal_gap_check(
            "advanced_metric_source_ready",
            "pass" if metric_ready else "fail",
            "blocking",
            "正式论文质量指标需要 LPIPS、FID 或 CLIP score 等高级指标来源。",
            {"metric_source_mode": metric_source_mode},
        )
    )

    gpu_required = bool(gpu_readiness.get("checked_for_formal_external_plans"))
    gpu_available = bool(gpu_readiness.get("gpu_available"))
    checks.append(
        _formal_gap_check(
            "gpu_runtime_ready_for_external_plans",
            "pass" if (not gpu_required or gpu_available) else "fail",
            "blocking" if gpu_required else "informational",
            "启用正式外部 baseline / metric 计划时应检测到 GPU runtime, 除非已显式放宽。",
            {"gpu_required": gpu_required, "gpu_available": gpu_available, "gpu_readiness": gpu_readiness},
        )
    )

    result_source_modes = {baseline_source_mode, metric_source_mode}
    external_plan_selected = "external_plan" in result_source_modes
    provided_file_selected = "provided_file" in result_source_modes
    external_command_files = {
        "baseline_command_results": workspace / "external_baselines" / "baseline_command_results.json",
        "baseline_observations": workspace / "external_baselines" / "baseline_observations.json",
        "metric_command_results": workspace / "external_metrics" / "metric_command_results.json",
        "metric_rows": workspace / "external_metrics" / "metric_rows.json",
    }
    missing_external_files = [name for name, path in external_command_files.items() if not path.is_file()]
    external_files_required = external_plan_selected and not use_dry_run
    checks.append(
        _formal_gap_check(
            "external_command_result_files_present",
            "pass" if (not external_files_required or not missing_external_files) else "fail",
            "blocking" if external_files_required else "informational",
            "启用正式外部计划时, baseline 与高级指标命令结果文件必须存在。",
            {
                "run_external_plans": run_external_plans,
                "external_files_required": external_files_required,
                "missing_external_files": missing_external_files,
            },
        )
    )

    provided_manifest_required = provided_file_selected
    provided_manifest = _read_json_object(workspace / "provided_results" / "provided_result_files_manifest.json")
    provided_manifest_passed = isinstance(provided_manifest, dict) and provided_manifest.get("overall_decision") == "pass"
    checks.append(
        _formal_gap_check(
            "provided_result_files_manifest_ready",
            "pass" if (not provided_manifest_required or provided_manifest_passed) else "fail",
            "blocking" if provided_manifest_required else "informational",
            "使用直接提供结果文件时, 必须存在通过的 provided_results manifest。",
            {
                "provided_manifest_required": provided_manifest_required,
                "provided_manifest_decision": provided_manifest.get("overall_decision") if isinstance(provided_manifest, dict) else None,
            },
        )
    )

    evidence_external_plan_ok = (not external_plan_selected) or evidence_report.get("require_external_command_results") is True
    evidence_provided_file_ok = (not provided_file_selected) or provided_manifest_passed
    evidence_formal_passed = (
        evidence_report.get("overall_decision") == "pass"
        and evidence_report.get("allow_dry_run") is False
        and evidence_report.get("require_experiment_coverage") is True
        and evidence_external_plan_ok
        and evidence_provided_file_ok
    )
    checks.append(
        _formal_gap_check(
            "strict_paper_result_evidence_passed",
            "pass" if evidence_formal_passed else "fail",
            "blocking",
            "正式 evidence 报告必须在不允许 dry-run、要求实验覆盖、要求外部命令结果的模式下通过。",
            {
                "overall_decision": evidence_report.get("overall_decision"),
                "allow_dry_run": evidence_report.get("allow_dry_run"),
                "require_experiment_coverage": evidence_report.get("require_experiment_coverage"),
                "require_external_command_results": evidence_report.get("require_external_command_results"),
                "external_plan_selected": external_plan_selected,
                "provided_file_selected": provided_file_selected,
                "provided_manifest_passed": provided_manifest_passed,
            },
        )
    )

    acceptance_external_plan_ok = (not external_plan_selected) or acceptance_report.get("require_external_command_results") is True
    acceptance_provided_file_ok = (not provided_file_selected) or provided_manifest_passed
    acceptance_strict = (
        acceptance_report.get("overall_decision") == "pass"
        and acceptance_report.get("allow_dry_run") is False
        and acceptance_report.get("require_experiment_coverage") is True
        and acceptance_external_plan_ok
        and acceptance_provided_file_ok
    )
    checks.append(
        _formal_gap_check(
            "strict_colab_acceptance_passed",
            "pass" if acceptance_strict else "fail",
            "blocking",
            "最终 Colab acceptance 必须在正式严格参数下通过。",
            {
                "overall_decision": acceptance_report.get("overall_decision"),
                "allow_dry_run": acceptance_report.get("allow_dry_run"),
                "require_experiment_coverage": acceptance_report.get("require_experiment_coverage"),
                "require_external_command_results": acceptance_report.get("require_external_command_results"),
                "report_decisions": acceptance_report.get("report_decisions"),
                "external_plan_selected": external_plan_selected,
                "provided_file_selected": provided_file_selected,
                "provided_manifest_passed": provided_manifest_passed,
            },
        )
    )

    blocking_gaps = [item for item in checks if item["severity"] == "blocking" and item["status"] != "pass"]
    return {
        "artifact_name": "colab_formal_result_gap_report.json",
        "overall_decision": "ready_for_formal_claims" if not blocking_gaps else "not_ready_for_formal_claims",
        "workspace_root": str(workspace),
        "blocking_gap_count": len(blocking_gaps),
        "blocking_gap_requirements": [item["requirement"] for item in blocking_gaps],
        "checks": checks,
    }


def write_colab_formal_result_gap_report(workspace_root: str | Path) -> dict[str, Any]:
    """写出 Colab 正式论文结果缺口报告。"""
    workspace = Path(workspace_root).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    report = build_colab_formal_result_gap_report(workspace)
    (workspace / "colab_formal_result_gap_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _file_sha256(path: Path) -> str:
    """计算单个文件的 SHA-256 摘要, 用于 Colab 运行包审计。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_file_with_parents(source_root: Path, target_root: Path, relative: str) -> dict[str, Any] | None:
    """复制一个相对路径文件并返回 manifest 条目, 文件不存在时返回 None。"""
    source_path = source_root / relative
    if not source_path.is_file():
        return None
    target_path = target_root / relative
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    return {
        "relative_path": relative.replace("\\", "/"),
        "byte_count": source_path.stat().st_size,
        "sha256": _file_sha256(source_path),
    }


def _copy_tree_files(source_root: Path, target_root: Path, relative_root: str) -> list[dict[str, Any]]:
    """复制一个目录下的所有文件并返回 manifest 条目。"""
    source_dir = source_root / relative_root
    if not source_dir.exists():
        return []
    entries: list[dict[str, Any]] = []
    for source_path in sorted(path for path in source_dir.rglob("*") if path.is_file()):
        relative = source_path.relative_to(source_root).as_posix()
        item = _copy_file_with_parents(source_root, target_root, relative)
        if item is not None:
            entries.append(item)
    return entries


def copy_provided_result_files(command_plan: dict[str, Any]) -> dict[str, Any]:
    """把用户直接提供的 baseline / metric 结果文件复制到 workspace 内的受治理位置。

    该函数属于 Colab provenance 工程层, 不解析或重算指标。它的作用是确保后续
    `build_paper_outputs.py` 消费的是 bundle 可携带、可校验摘要的文件副本, 从而让离线复核者不依赖
    Colab 会话外部路径。
    """
    copy_plan = list(command_plan.get("provided_result_copy_plan", []))
    workspace = Path(str(command_plan["workspace_root"]))
    provided_root = Path(str(command_plan.get("provided_results_root", workspace / "provided_results")))
    copied_files: list[dict[str, Any]] = []
    missing_sources: list[dict[str, str]] = []
    for item in copy_plan:
        if not isinstance(item, dict):
            continue
        source_path = Path(str(item.get("source_path", ""))).resolve()
        target_path = Path(str(item.get("target_path", ""))).resolve()
        role = str(item.get("role", "unknown"))
        if not source_path.is_file():
            missing_sources.append({"role": role, "source_path": str(source_path), "reason": "missing"})
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path != target_path:
            shutil.copy2(source_path, target_path)
        copied_files.append(
            {
                "role": role,
                "source_path": str(source_path),
                "target_path": str(target_path),
                "relative_target_path": target_path.relative_to(workspace).as_posix(),
                "byte_count": target_path.stat().st_size,
                "sha256": _file_sha256(target_path),
            }
        )
    manifest = {
        "artifact_name": "provided_result_files_manifest.json",
        "overall_decision": "fail" if missing_sources else "pass",
        "workspace_root": str(workspace),
        "provided_results_root": str(provided_root),
        "copied_files": copied_files,
        "missing_sources": missing_sources,
        "copied_file_count": len(copied_files),
    }
    if copy_plan or provided_root.exists():
        provided_root.mkdir(parents=True, exist_ok=True)
        (provided_root / "provided_result_files_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return manifest




def _pass_check(requirement: str, evidence: Any) -> dict[str, Any]:
    """构造通过的 Colab bundle 校验项。"""
    return {"requirement": requirement, "status": "pass", "evidence": evidence}


def _fail_check(requirement: str, evidence: Any) -> dict[str, Any]:
    """构造失败的 Colab bundle 校验项。"""
    return {"requirement": requirement, "status": "fail", "evidence": evidence}


def validate_colab_run_bundle(bundle_root: str | Path) -> dict[str, Any]:
    """校验 Colab 运行级 bundle 的 manifest 摘要与核心证据文件。"""
    root = Path(bundle_root)
    manifest_path = root / "colab_run_bundle_manifest.json"
    checks: list[dict[str, Any]] = []
    if not manifest_path.exists():
        return {
            "artifact_name": "colab_run_bundle_validation.json",
            "overall_decision": "fail",
            "checks": [_fail_check("colab_run_bundle_manifest_present", "missing")],
            "summary": {"total": 1, "fail_count": 1, "pass_count": 0},
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return {
            "artifact_name": "colab_run_bundle_validation.json",
            "overall_decision": "fail",
            "checks": [_fail_check("colab_run_bundle_manifest_parseable", str(exc))],
            "summary": {"total": 1, "fail_count": 1, "pass_count": 0},
        }
    checks.append(_pass_check("colab_run_bundle_manifest_present", "colab_run_bundle_manifest.json"))
    required_files = (
        "colab_cold_start_summary.json",
        "colab_input_manifest.json",
        "colab_output_layout_manifest.json",
        "colab_formal_input_contract.json",
        "inputs/formal_input_templates_manifest.json",
        "colab_formal_runbook.md",
        "colab_paper_result_index.json",
        "colab_formal_result_gap_report.json",
        "archives/colab_bundle_archive_manifest.json",
        "experiment_matrix/experiment_matrix.json",
        "experiment_matrix/experiment_matrix_manifest.json",
        "paper_results_package/paper_results_package_manifest.json",
        "paper_results_package/paper_results_package_validation.json",
    )
    missing_required = [relative for relative in required_files if not (root / relative).is_file()]
    checks.append(
        _fail_check("colab_run_bundle_core_files_present", missing_required)
        if missing_required
        else _pass_check("colab_run_bundle_core_files_present", list(required_files))
    )
    runbook_path = root / "colab_formal_runbook.md"
    if runbook_path.is_file():
        runbook_body = runbook_path.read_text(encoding="utf-8-sig")
        runbook_guidance = {
            "contains_acceptance_section": "验收命令" in runbook_body or "楠屾敹鍛戒护" in runbook_body,
            "contains_acceptance_cli": "run_colab_acceptance_checks.py" in runbook_body,
        }
        checks.append(
            _pass_check("colab_formal_runbook_contains_acceptance_guidance", runbook_guidance)
            if all(runbook_guidance.values())
            else _fail_check("colab_formal_runbook_contains_acceptance_guidance", runbook_guidance)
        )
    else:
        checks.append(_fail_check("colab_formal_runbook_contains_acceptance_guidance", "missing"))
    archive_sidecar_path = root / "archives" / "colab_bundle_archive_manifest.json"
    if archive_sidecar_path.is_file():
        try:
            archive_sidecar_payload = json.loads(archive_sidecar_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            checks.append(_fail_check("embedded_colab_archive_sidecar_parseable", str(exc)))
        else:
            offline_command = archive_sidecar_payload.get("offline_acceptance_command") if isinstance(archive_sidecar_payload, dict) else None
            sidecar_summary = {
                "artifact_name": archive_sidecar_payload.get("artifact_name") if isinstance(archive_sidecar_payload, dict) else None,
                "archive_manifest_stage": archive_sidecar_payload.get("archive_manifest_stage") if isinstance(archive_sidecar_payload, dict) else None,
                "archive_name": archive_sidecar_payload.get("archive_name") if isinstance(archive_sidecar_payload, dict) else None,
                "offline_acceptance_command": offline_command,
            }
            offline_command_text = " ".join(str(part) for part in offline_command) if isinstance(offline_command, list) else ""
            sidecar_valid = (
                isinstance(archive_sidecar_payload, dict)
                and archive_sidecar_payload.get("artifact_name") == "colab_bundle_archive_manifest.json"
                and archive_sidecar_payload.get("archive_manifest_stage") == "pre_archive_sidecar"
                and archive_sidecar_payload.get("archive_name") == "ceg_colab_run_bundle.zip"
                and isinstance(offline_command, list)
                and "scripts/run_colab_acceptance_checks.py" in offline_command_text
                and "path/to/ceg_colab_run_bundle.zip" in offline_command
            )
            checks.append(
                _pass_check("embedded_colab_archive_sidecar_parseable", sidecar_summary)
                if sidecar_valid
                else _fail_check("embedded_colab_archive_sidecar_parseable", sidecar_summary)
            )
    else:
        checks.append(_fail_check("embedded_colab_archive_sidecar_parseable", "missing"))
    result_index_path = root / "colab_paper_result_index.json"
    if result_index_path.is_file():
        try:
            result_index_payload = json.loads(result_index_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            checks.append(_fail_check("colab_paper_result_index_semantic_checks_passed", str(exc)))
            checks.append(_fail_check("colab_paper_result_index_production_trace_complete", str(exc)))
        else:
            semantic_summary = result_index_payload.get("semantic_check_summary") if isinstance(result_index_payload, dict) else None
            semantic_failures = result_index_payload.get("semantic_check_failures") if isinstance(result_index_payload, dict) else None
            group_failures = result_index_payload.get("required_result_group_failures") if isinstance(result_index_payload, dict) else None
            production_trace_summary = result_index_payload.get("production_trace_summary") if isinstance(result_index_payload, dict) else None
            index_summary = {
                "overall_decision": result_index_payload.get("overall_decision") if isinstance(result_index_payload, dict) else None,
                "required_missing": result_index_payload.get("required_missing") if isinstance(result_index_payload, dict) else None,
                "required_result_group_failures": group_failures,
                "semantic_check_summary": semantic_summary,
                "semantic_check_failures": semantic_failures,
                "production_trace_summary": production_trace_summary,
            }
            semantic_ok = (
                isinstance(result_index_payload, dict)
                and result_index_payload.get("overall_decision") == "pass"
                and not result_index_payload.get("required_missing")
                and isinstance(group_failures, list)
                and not group_failures
                and isinstance(semantic_summary, dict)
                and int(semantic_summary.get("fail_count", -1)) == 0
                and isinstance(semantic_failures, list)
                and not semantic_failures
            )
            production_trace_ok = (
                isinstance(result_index_payload, dict)
                and isinstance(production_trace_summary, dict)
                and int(production_trace_summary.get("missing_trace_count", -1)) == 0
                and isinstance(production_trace_summary.get("missing_trace_result_ids"), list)
                and not production_trace_summary.get("missing_trace_result_ids")
            )
            checks.append(
                _pass_check("colab_paper_result_index_semantic_checks_passed", index_summary)
                if semantic_ok
                else _fail_check("colab_paper_result_index_semantic_checks_passed", index_summary)
            )
            checks.append(
                _pass_check("colab_paper_result_index_production_trace_complete", index_summary)
                if production_trace_ok
                else _fail_check("colab_paper_result_index_production_trace_complete", index_summary)
            )
    else:
        checks.append(_fail_check("colab_paper_result_index_semantic_checks_passed", "missing"))
        checks.append(_fail_check("colab_paper_result_index_production_trace_complete", "missing"))
    provenance_files = (
        "colab_formal_run_checklist.json",
        "paper_result_evidence_report.json",
    )
    missing_provenance = [relative for relative in provenance_files if not (root / relative).is_file()]
    checks.append(
        _fail_check("colab_run_bundle_formal_provenance_files_present", missing_provenance)
        if missing_provenance
        else _pass_check("colab_run_bundle_formal_provenance_files_present", list(provenance_files))
    )
    malformed_provenance: list[dict[str, str]] = []
    provenance_payloads: dict[str, dict[str, Any]] = {}
    for relative in provenance_files:
        path = root / relative
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            malformed_provenance.append({"relative_path": relative, "reason": str(exc)})
            continue
        if not isinstance(payload, dict) or not payload.get("artifact_name") or "overall_decision" not in payload:
            malformed_provenance.append({"relative_path": relative, "reason": "missing_artifact_name_or_overall_decision"})
            continue
        provenance_payloads[relative] = payload
    checks.append(
        _fail_check("colab_run_bundle_formal_provenance_parseable", malformed_provenance)
        if malformed_provenance
        else _pass_check("colab_run_bundle_formal_provenance_parseable", list(provenance_files))
    )
    evidence_payload = provenance_payloads.get("paper_result_evidence_report.json")
    if evidence_payload is None:
        checks.append(_fail_check("embedded_paper_result_evidence_report_passed", "missing_or_malformed"))
    else:
        evidence_summary = {
            "overall_decision": evidence_payload.get("overall_decision"),
            "target_kind": evidence_payload.get("target_kind"),
        }
        checks.append(
            _pass_check("embedded_paper_result_evidence_report_passed", evidence_summary)
            if evidence_payload.get("overall_decision") == "pass"
            else _fail_check("embedded_paper_result_evidence_report_passed", evidence_summary)
        )
        checks.append(
            _pass_check("embedded_paper_result_evidence_targets_colab_bundle", evidence_summary)
            if evidence_payload.get("target_kind") == "colab_run_bundle"
            else _fail_check("embedded_paper_result_evidence_targets_colab_bundle", evidence_summary)
        )
    acceptance_report_path = root / "colab_acceptance_report.json"
    if acceptance_report_path.is_file():
        try:
            acceptance_payload = json.loads(acceptance_report_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            checks.append(_fail_check("embedded_colab_acceptance_report_parseable", str(exc)))
        else:
            acceptance_summary = {
                "artifact_name": acceptance_payload.get("artifact_name") if isinstance(acceptance_payload, dict) else None,
                "overall_decision": acceptance_payload.get("overall_decision") if isinstance(acceptance_payload, dict) else None,
                "report_decisions": acceptance_payload.get("report_decisions") if isinstance(acceptance_payload, dict) else None,
                "blocking_report_decisions": acceptance_payload.get("blocking_report_decisions") if isinstance(acceptance_payload, dict) else None,
                "formal_result_gap_decision": acceptance_payload.get("formal_result_gap_decision") if isinstance(acceptance_payload, dict) else None,
                "formal_result_gap_decision_mode": acceptance_payload.get("formal_result_gap_decision_mode") if isinstance(acceptance_payload, dict) else None,
            }
            report_decisions = acceptance_payload.get("report_decisions", {}) if isinstance(acceptance_payload, dict) else {}
            blocking_report_decisions = acceptance_payload.get("blocking_report_decisions", {}) if isinstance(acceptance_payload, dict) else {}
            acceptance_valid = (
                isinstance(acceptance_payload, dict)
                and acceptance_payload.get("artifact_name") == "colab_acceptance_report.json"
                and acceptance_payload.get("overall_decision") in {"pass", "fail"}
                and isinstance(report_decisions, dict)
                and isinstance(blocking_report_decisions, dict)
                and "colab_run_bundle_validation" in report_decisions
                and "paper_result_evidence" in report_decisions
                and "formal_result_gap" in report_decisions
                and "colab_run_bundle_validation" in blocking_report_decisions
                and "paper_result_evidence" in blocking_report_decisions
                and acceptance_payload.get("formal_result_gap_decision") == report_decisions.get("formal_result_gap")
                and acceptance_payload.get("formal_result_gap_decision_mode") == "post_acceptance_override"
            )
            checks.append(
                _pass_check("embedded_colab_acceptance_report_parseable", acceptance_summary)
                if acceptance_valid
                else _fail_check("embedded_colab_acceptance_report_parseable", acceptance_summary)
            )
    else:
        checks.append(_pass_check("embedded_colab_acceptance_report_optional_before_final_acceptance", "missing"))
    mismatches: list[dict[str, str]] = []
    file_entries = manifest.get("files", []) if isinstance(manifest, dict) else []
    for entry in file_entries:
        if not isinstance(entry, dict):
            mismatches.append({"relative_path": "unknown", "reason": "file_entry_not_object"})
            continue
        relative = str(entry.get("relative_path"))
        path = root / relative
        if not path.is_file():
            mismatches.append({"relative_path": relative, "reason": "missing"})
            continue
        if path.stat().st_size != int(entry.get("byte_count", -1)) or _file_sha256(path) != entry.get("sha256"):
            mismatches.append({"relative_path": relative, "reason": "digest_or_size_mismatch"})
    checks.append(
        _fail_check("colab_run_bundle_files_match_manifest", mismatches)
        if mismatches
        else _pass_check("colab_run_bundle_files_match_manifest", len(file_entries))
    )
    package_validation_path = root / "paper_results_package" / "paper_results_package_validation.json"
    if package_validation_path.exists():
        package_validation = json.loads(package_validation_path.read_text(encoding="utf-8-sig"))
        package_decision = package_validation.get("overall_decision") if isinstance(package_validation, dict) else None
        checks.append(
            _pass_check("embedded_paper_results_package_validation_passed", package_decision)
            if package_decision == "pass"
            else _fail_check("embedded_paper_results_package_validation_passed", package_decision)
        )
    else:
        checks.append(_fail_check("embedded_paper_results_package_validation_passed", "missing"))
    fail_count = sum(1 for check in checks if check["status"] != "pass")
    return {
        "artifact_name": "colab_run_bundle_validation.json",
        "overall_decision": "fail" if fail_count else "pass",
        "checks": checks,
        "summary": {"total": len(checks), "fail_count": fail_count, "pass_count": len(checks) - fail_count},
    }

def export_colab_run_bundle(workspace_root: str | Path, bundle_root: str | Path | None = None) -> dict[str, Any]:
    """导出 Colab 运行级 bundle。

    该 bundle 与论文结果包不同: 它除了包含 `paper_results_package/` 之外, 还收集 Colab 环境、命令计划、
    输入清单、实验矩阵、样本转换、阈值校准以及外部命令执行摘要, 便于复现实验运行过程。
    """
    workspace = Path(workspace_root).resolve()
    target = Path(bundle_root).resolve() if bundle_root else workspace / "colab_run_bundle"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    write_colab_output_layout_manifest(workspace)
    write_colab_formal_input_contract(workspace)
    write_colab_formal_input_templates(workspace)
    write_colab_paper_result_index(workspace)
    write_colab_formal_result_gap_report(workspace)
    write_colab_formal_runbook(workspace)
    file_entries: list[dict[str, Any]] = []
    missing_optional: list[str] = []

    for relative in (
        "colab_cold_start_summary.json",
        "colab_formal_run_checklist.json",
        "paper_result_evidence_report.json",
        "colab_acceptance_report.json",
        "colab_input_manifest.json",
        "colab_output_layout_manifest.json",
        "colab_formal_input_contract.json",
        "inputs/formal_input_templates_manifest.json",
        "colab_formal_runbook.md",
        "colab_paper_result_index.json",
        "colab_formal_result_gap_report.json",
        "archives/colab_bundle_archive_manifest.json",
        "acceptance/colab_run_bundle_validation_cli.json",
        "acceptance/paper_result_evidence_cli.json",
        "inputs/paper_dry_run_inputs_manifest.json",
        "inputs/sample_event_build_manifest.json",
        "inputs/prompt_plan.json",
        "inputs/mock_image_generation_backend_manifest.json",
        "inputs/image_manifests/image_generation_manifest.json",
        "inputs/image_manifests/image_pair_manifest.json",
        "inputs/image_pairs.json",
        "image_attacks/image_manifests/attacked_image_manifest.json",
        "image_attacks/image_manifests/attack_shard_manifest.json",
        "image_attacks/image_pairs_attacked.json",
        "ceg_detection/detection_events.json",
        "ceg_detection/detection_thresholds.json",
        "ceg_detection/ceg_detection_producer_manifest.json",
        "ceg_detection/ceg_detection_command_plan_manifest.json",
        "ceg_detection/ceg_detection_command_results.json",
        "ceg_detection/ceg_detection_execution_manifest.json",
        "threshold_calibration/thresholds.json",
        "threshold_calibration/threshold_calibration_report.json",
        "basic_image_metrics/metric_execution_manifest.json",
        "basic_image_metrics/metric_rows.json",
        "provided_results/provided_result_files_manifest.json",
        "provided_results/baseline_observations.json",
        "provided_results/metric_rows.json",
        "plans/image_generation_command_plan.json",
        "plans/detection_command_plan.json",
        "plans/baseline_command_plan.json",
        "plans/metric_command_plan.json",
        "external_image_generation/image_generation_command_plan_manifest.json",
        "external_image_generation/image_generation_command_results.json",
        "external_baselines/baseline_command_plan_manifest.json",
        "external_baselines/baseline_command_results.json",
        "external_baselines/baseline_execution_manifest.json",
        "external_baselines/baseline_observations.json",
        "external_metrics/metric_command_plan_manifest.json",
        "external_metrics/metric_command_results.json",
        "external_metrics/metric_execution_manifest.json",
        "external_metrics/metric_rows.json",
    ):
        item = _copy_file_with_parents(workspace, target, relative)
        if item is None:
            missing_optional.append(relative)
        else:
            file_entries.append(item)

    for relative_root in ("inputs/formal_input_templates", "experiment_matrix", "paper_results_package"):
        copied = _copy_tree_files(workspace, target, relative_root)
        if not copied:
            missing_optional.append(f"{relative_root}/")
        file_entries.extend(copied)

    manifest_payload = {
        "artifact_name": "colab_run_bundle_manifest.json",
        "workspace_root": str(workspace),
        "bundle_root": str(target),
        "file_count": len(file_entries),
        "copied_files": [entry["relative_path"] for entry in file_entries],
        "missing_optional": missing_optional,
        "bundle_digest": "",
        "files": file_entries,
    }
    manifest_payload["bundle_digest"] = hashlib.sha256(
        json.dumps(file_entries, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    (target / "colab_run_bundle_manifest.json").write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    validation = validate_colab_run_bundle(target)
    (target / "colab_run_bundle_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_payload["validation_decision"] = validation["overall_decision"]
    return manifest_payload

def _build_colab_archive_manifest_base(
    workspace: Path,
    target_bundle: Path,
    final_archive_path: Path,
    *,
    allow_dry_run: bool,
    require_experiment_coverage: bool,
    require_external_command_results: bool,
) -> dict[str, Any]:
    """构造归档 sidecar 的基础 manifest, 供 zip 内外使用同一份验收命令语义。"""
    output_layout = build_colab_output_layout(workspace)
    colab_acceptance_command = [
        sys.executable,
        "scripts/run_colab_acceptance_checks.py",
        "--bundle",
        str(final_archive_path),
        "--require-pass",
    ]
    offline_acceptance_command = [
        sys.executable,
        "scripts/run_colab_acceptance_checks.py",
        "--bundle",
        f"path/to/{final_archive_path.name}",
        "--require-pass",
    ]
    for command in (colab_acceptance_command, offline_acceptance_command):
        if allow_dry_run:
            command.insert(-1, "--allow-dry-run")
        if not require_experiment_coverage:
            command.insert(-1, "--allow-missing-experiment-coverage")
        if require_external_command_results:
            command.insert(-1, "--require-external-command-results")

    return {
        "artifact_name": "colab_bundle_archive_manifest.json",
        "archive_manifest_stage": "pre_archive_sidecar",
        "workspace_root": str(workspace),
        "drive_output_root": output_layout["drive_output_root"],
        "archives_root": str(final_archive_path.parent),
        "bundle_root": str(target_bundle),
        "archive_path": str(final_archive_path),
        "archive_manifest_path": str(final_archive_path.parent / "colab_bundle_archive_manifest.json"),
        "output_layout_manifest_path": str(workspace / "colab_output_layout_manifest.json"),
        "formal_input_contract_path": str(workspace / "colab_formal_input_contract.json"),
        "formal_input_templates_manifest_path": str(workspace / "inputs" / "formal_input_templates_manifest.json"),
        "formal_runbook_path": str(workspace / "colab_formal_runbook.md"),
        "paper_result_index_path": str(workspace / "colab_paper_result_index.json"),
        "formal_result_gap_report_path": str(workspace / "colab_formal_result_gap_report.json"),
        "archive_name": final_archive_path.name,
        "allow_dry_run": allow_dry_run,
        "require_experiment_coverage": require_experiment_coverage,
        "require_external_command_results": require_external_command_results,
        "colab_acceptance_command": colab_acceptance_command,
        "offline_acceptance_command": offline_acceptance_command,
    }


def create_colab_bundle_archive(
    workspace_root: str | Path,
    *,
    bundle_root: str | Path | None = None,
    archive_path: str | Path | None = None,
    allow_dry_run: bool = False,
    require_experiment_coverage: bool = True,
    require_external_command_results: bool = False,
) -> dict[str, Any]:
    """创建可下载的 Colab bundle zip, 并写出 archive manifest。

    该函数只读取已经生成的 `colab_run_bundle/`, 或先调用 `export_colab_run_bundle` 刷新 bundle manifest。
    它不生成正式 records、tables、figures 或 reports, 因此可安全作为 Notebook 下载出口复用。
    """
    workspace = Path(workspace_root).resolve()
    output_layout = build_colab_output_layout(workspace)
    target_bundle = Path(bundle_root).resolve() if bundle_root else Path(output_layout["colab_run_bundle_root"])
    archives_root = Path(output_layout["archives_root"])
    archives_root.mkdir(parents=True, exist_ok=True)
    requested_archive = Path(archive_path).resolve() if archive_path else archives_root / "ceg_colab_run_bundle.zip"
    requested_archive.parent.mkdir(parents=True, exist_ok=True)
    archive_base = requested_archive.with_suffix("") if requested_archive.suffix.lower() == ".zip" else requested_archive
    final_archive_path = archive_base.with_suffix(".zip").resolve()
    archive_manifest_path = final_archive_path.parent / "colab_bundle_archive_manifest.json"

    archive_manifest_base = _build_colab_archive_manifest_base(
        workspace,
        target_bundle,
        final_archive_path,
        allow_dry_run=allow_dry_run,
        require_experiment_coverage=require_experiment_coverage,
        require_external_command_results=require_external_command_results,
    )
    archive_manifest_path.write_text(
        json.dumps(archive_manifest_base, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    bundle_manifest = export_colab_run_bundle(workspace, target_bundle)
    if final_archive_path.exists():
        final_archive_path.unlink()
    created_archive = Path(shutil.make_archive(str(archive_base), "zip", root_dir=target_bundle)).resolve()
    archive_bytes = created_archive.read_bytes()
    archive_manifest = {
        **archive_manifest_base,
        "archive_path": str(created_archive),
        "archive_manifest_path": str(archive_manifest_path),
        "archive_name": created_archive.name,
        "archive_manifest_stage": "post_archive_sidecar",
        "archive_size_bytes": created_archive.stat().st_size,
        "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "bundle_file_count": bundle_manifest["file_count"],
        "bundle_digest": bundle_manifest["bundle_digest"],
        "bundle_validation_decision": bundle_manifest.get("validation_decision"),
    }
    archive_manifest_path.write_text(
        json.dumps(archive_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_colab_output_layout_manifest(workspace)
    write_colab_formal_input_contract(workspace)
    write_colab_formal_input_templates(workspace)
    write_colab_paper_result_index(workspace)
    write_colab_formal_result_gap_report(workspace)
    write_colab_formal_runbook(workspace)
    return archive_manifest


def build_colab_environment_summary(repo_root: str | Path) -> dict[str, Any]:
    """返回 Notebook 可展示的运行环境摘要。"""
    root = Path(repo_root)
    return {
        "artifact_name": "colab_environment_summary.json",
        "is_colab_runtime": is_colab_runtime(),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "repo_root": str(root.resolve()),
        "repo_root_exists": root.exists(),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "nvidia_smi": _probe_nvidia_smi(),
        "torch_cuda": _probe_torch_cuda(),
    }


def _environment_has_gpu(environment_summary: dict[str, Any]) -> bool:
    """根据环境摘要判断当前运行时是否已经分配 GPU。"""
    nvidia_smi = environment_summary.get("nvidia_smi")
    torch_cuda = environment_summary.get("torch_cuda")
    nvidia_available = isinstance(nvidia_smi, dict) and bool(nvidia_smi.get("available"))
    torch_available = isinstance(torch_cuda, dict) and bool(torch_cuda.get("cuda_available"))
    return nvidia_available or torch_available


def run_command(command: list[str], *, cwd: str | Path, timeout_seconds: int | None = None) -> dict[str, Any]:
    """执行一个子命令并返回结构化结果, 供 Notebook 直接显示和审计。"""
    completed = subprocess.run(
        command,
        cwd=Path(cwd),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "command": command,
        "working_directory": str(Path(cwd).resolve()),
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _optional_path(path: str | Path | None) -> Path | None:
    """把可选路径标准化为绝对路径。"""
    return Path(path).resolve() if path else None


def _build_external_plan_steps(
    root: Path,
    workspace: Path,
    *,
    run_external_plans: bool,
    baseline_plan_path: str | Path | None,
    metric_plan_path: str | Path | None,
    baseline_root: str | Path | None,
    metric_root: str | Path | None,
    events_path: Path,
    image_pairs_path: str | Path | None,
    reference_image_root: str | Path | None,
    generated_image_root: str | Path | None,
    image_prompt_rows_path: str | Path | None,
) -> dict[str, Any]:
    """构造外部 baseline 与高级指标命令计划步骤。"""
    plans_root = workspace / "plans"
    baseline_output_root = workspace / "external_baselines"
    metric_output_root = workspace / "external_metrics"
    materialize_baseline_command: list[str] = []
    materialize_metric_command: list[str] = []
    baseline_execution_command: list[str] = []
    metric_execution_command: list[str] = []
    effective_baseline_plan = _optional_path(baseline_plan_path)
    effective_metric_plan = _optional_path(metric_plan_path)

    if run_external_plans:
        if effective_baseline_plan is None:
            if baseline_root is None:
                raise ValueError("baseline_root or baseline_plan_path is required when run_external_plans is True")
            effective_baseline_plan = plans_root / "baseline_command_plan.json"
            materialize_baseline_command = [
                sys.executable,
                str(root / "scripts" / "materialize_command_templates.py"),
                "--templates",
                str(root / "configs" / "baseline_command_templates.json"),
                "--kind",
                "baseline",
                "--out",
                str(effective_baseline_plan),
                "--var",
                f"baseline_root={Path(baseline_root).resolve()}",
                "--var",
                f"events_path={events_path}",
                "--var",
                f"output_root={baseline_output_root}",
            ]
        baseline_execution_command = [
            sys.executable,
            str(root / "scripts" / "run_baseline_plan.py"),
            "--plan",
            str(effective_baseline_plan),
            "--out",
            str(baseline_output_root),
        ]

        if effective_metric_plan is None:
            if metric_root is None:
                raise ValueError("metric_root or metric_plan_path is required when run_external_plans is True")
            effective_metric_plan = plans_root / "metric_command_plan.json"
            materialize_metric_command = [
                sys.executable,
                str(root / "scripts" / "materialize_command_templates.py"),
                "--templates",
                str(root / "configs" / "external_metric_command_templates.json"),
                "--kind",
                "metric",
                "--out",
                str(effective_metric_plan),
                "--var",
                f"metric_root={Path(metric_root).resolve()}",
                "--var",
                f"image_pairs_path={Path(image_pairs_path).resolve() if image_pairs_path else ''}",
                "--var",
                f"reference_image_root={Path(reference_image_root).resolve() if reference_image_root else ''}",
                "--var",
                f"generated_image_root={Path(generated_image_root).resolve() if generated_image_root else ''}",
                "--var",
                f"image_prompt_rows_path={Path(image_prompt_rows_path).resolve() if image_prompt_rows_path else ''}",
                "--var",
                f"output_root={metric_output_root}",
            ]
        metric_execution_command = [
            sys.executable,
            str(root / "scripts" / "run_metric_plan.py"),
            "--plan",
            str(effective_metric_plan),
            "--out",
            str(metric_output_root),
        ]

    return {
        "plans_root": str(plans_root),
        "baseline_output_root": str(baseline_output_root),
        "metric_output_root": str(metric_output_root),
        "baseline_plan_path": str(effective_baseline_plan) if effective_baseline_plan else None,
        "metric_plan_path": str(effective_metric_plan) if effective_metric_plan else None,
        "materialize_baseline_command": materialize_baseline_command,
        "baseline_execution_command": baseline_execution_command,
        "materialize_metric_command": materialize_metric_command,
        "metric_execution_command": metric_execution_command,
        "baseline_observations_path": str(baseline_output_root / "baseline_observations.json") if run_external_plans else None,
        "baseline_execution_manifest_path": str(baseline_output_root / "baseline_execution_manifest.json") if run_external_plans else None,
        "metric_rows_path": str(metric_output_root / "metric_rows.json") if run_external_plans else None,
        "metric_execution_manifest_path": str(metric_output_root / "metric_execution_manifest.json") if run_external_plans else None,
    }


def build_colab_command_plan(
    repo_root: str | Path,
    workspace_root: str | Path,
    *,
    profile: str = "paper_main_probe",
    repetitions: int = 1,
    use_dry_run_inputs: bool = True,
    run_external_plans: bool = False,
    require_experiment_coverage: bool = False,
    events_path: str | Path | None = None,
    thresholds_path: str | Path | None = None,
    sample_manifest_path: str | Path | None = None,
    compute_basic_image_metrics: bool = False,
    calibrate_thresholds: bool = False,
    threshold_target_fpr: float = 0.01,
    threshold_calibration_split: str = "calibration",
    baseline_observations_path: str | Path | None = None,
    metric_rows_path: str | Path | None = None,
    baseline_plan_path: str | Path | None = None,
    metric_plan_path: str | Path | None = None,
    baseline_root: str | Path | None = None,
    metric_root: str | Path | None = None,
    image_pairs_path: str | Path | None = None,
    reference_image_root: str | Path | None = None,
    generated_image_root: str | Path | None = None,
    image_prompt_rows_path: str | Path | None = None,
) -> dict[str, Any]:
    """构造 Colab 端从输入到结果包的命令计划。"""
    root = Path(repo_root).resolve()
    workspace = Path(workspace_root).resolve()
    output_layout = build_colab_output_layout(workspace)
    inputs_root = Path(output_layout["inputs_root"])
    paper_outputs_root = Path(output_layout["paper_outputs_root"])
    package_root = Path(output_layout["paper_results_package_root"])
    matrix_root = Path(output_layout["experiment_matrix_root"])
    experiment_matrix_path = matrix_root / "experiment_matrix.json"
    basic_metric_root = Path(output_layout["basic_image_metrics_root"])
    provided_results_root = Path(output_layout["provided_results_root"])
    threshold_root = Path(output_layout["threshold_calibration_root"])
    attack_root = Path(output_layout["image_attacks_root"])
    generated_image_pairs_path = inputs_root / "image_pairs.json"
    basic_metric_rows_path = basic_metric_root / "metric_rows.json"
    basic_metric_execution_manifest_path = basic_metric_root / "metric_execution_manifest.json"
    calibrated_thresholds_path = threshold_root / "thresholds.json"
    attacked_image_manifest_path = attack_root / "image_manifests" / "attacked_image_manifest.json"
    attack_shard_manifest_path = attack_root / "image_manifests" / "attack_shard_manifest.json"

    basic_metric_command: list[str] = []
    threshold_calibration_command: list[str] = []
    provided_result_copy_plan: list[dict[str, str]] = []
    if use_dry_run_inputs:
        effective_events_path = inputs_root / "events.json"
        effective_thresholds_path = inputs_root / "thresholds.json"
        effective_baseline_path = inputs_root / "baseline_observations.json"
        effective_metric_rows_path = inputs_root / "metric_rows.json"
        effective_image_pairs_path = generated_image_pairs_path
        prepare_command = [
            sys.executable,
            str(root / "scripts" / "build_paper_dry_run_inputs.py"),
            "--out",
            str(inputs_root),
            "--repetitions",
            str(repetitions),
        ]
    else:
        if events_path is None and sample_manifest_path is None:
            raise ValueError("events_path or sample_manifest_path is required when use_dry_run_inputs is False")
        if thresholds_path is None:
            if not calibrate_thresholds or sample_manifest_path is None:
                raise ValueError("thresholds_path is required unless calibrate_thresholds=True with sample_manifest_path")
            effective_thresholds_path = calibrated_thresholds_path
            threshold_calibration_command = [
                sys.executable,
                str(root / "scripts" / "calibrate_thresholds_from_sample_manifest.py"),
                "--samples",
                str(Path(sample_manifest_path).resolve()),
                "--out",
                str(threshold_root),
                "--target-fpr",
                str(threshold_target_fpr),
                "--calibration-split",
                threshold_calibration_split,
            ]
        else:
            effective_thresholds_path = Path(thresholds_path).resolve()
        if sample_manifest_path is not None and events_path is None:
            effective_events_path = inputs_root / "events.json"
            effective_image_pairs_path = generated_image_pairs_path
            prepare_command = [
                sys.executable,
                str(root / "scripts" / "build_protocol_events_from_sample_manifest.py"),
                "--samples",
                str(Path(sample_manifest_path).resolve()),
                "--thresholds",
                str(effective_thresholds_path),
                "--out",
                str(inputs_root),
            ]
        else:
            effective_events_path = Path(str(events_path)).resolve()
            effective_image_pairs_path = _optional_path(image_pairs_path) or generated_image_pairs_path
            prepare_command = []
        effective_baseline_path = _optional_path(baseline_observations_path)
        effective_metric_rows_path = _optional_path(metric_rows_path)
        if effective_baseline_path is not None and not run_external_plans:
            provided_baseline_path = provided_results_root / "baseline_observations.json"
            provided_result_copy_plan.append(
                {
                    "role": "baseline_observations",
                    "source_path": str(effective_baseline_path),
                    "target_path": str(provided_baseline_path),
                }
            )
            effective_baseline_path = provided_baseline_path
        if effective_metric_rows_path is not None and not run_external_plans:
            provided_metric_rows_path = provided_results_root / "metric_rows.json"
            provided_result_copy_plan.append(
                {
                    "role": "metric_rows",
                    "source_path": str(effective_metric_rows_path),
                    "target_path": str(provided_metric_rows_path),
                }
            )
            effective_metric_rows_path = provided_metric_rows_path
        if compute_basic_image_metrics and effective_metric_rows_path is None:
            if sample_manifest_path is None and image_pairs_path is None:
                raise ValueError("image_pairs_path or sample_manifest_path is required when compute_basic_image_metrics is True")
            basic_metric_command = [
                sys.executable,
                str(root / "scripts" / "compute_image_quality_metrics.py"),
                "--pairs",
                str(effective_image_pairs_path),
                "--out",
                str(basic_metric_rows_path),
                "--manifest",
                str(basic_metric_execution_manifest_path),
            ]
            effective_metric_rows_path = basic_metric_rows_path

    matrix_command = [
        sys.executable,
        str(root / "scripts" / "build_experiment_matrix.py"),
        "--config",
        str(root / "configs" / "paper_experiment_matrix.json"),
        "--out",
        str(matrix_root),
    ]

    external_steps = _build_external_plan_steps(
        root,
        workspace,
        run_external_plans=run_external_plans,
        baseline_plan_path=baseline_plan_path,
        metric_plan_path=metric_plan_path,
        baseline_root=baseline_root,
        metric_root=metric_root,
        events_path=effective_events_path,
        image_pairs_path=image_pairs_path or effective_image_pairs_path,
        reference_image_root=reference_image_root,
        generated_image_root=generated_image_root,
        image_prompt_rows_path=image_prompt_rows_path,
    )
    if run_external_plans:
        effective_baseline_path = Path(str(external_steps["baseline_observations_path"])).resolve()
        effective_metric_rows_path = Path(str(external_steps["metric_rows_path"])).resolve()

    attack_command = [
        sys.executable,
        str(root / "scripts" / "run_image_attack_workflow.py"),
        "--image-pairs",
        str(effective_image_pairs_path),
        "--out",
        str(attack_root),
        "--attack-families",
        "brightness_contrast",
    ]

    build_command = [
        sys.executable,
        str(root / "scripts" / "build_paper_outputs.py"),
        "--events",
        str(effective_events_path),
        "--thresholds",
        str(effective_thresholds_path),
        "--profile",
        profile,
        "--out",
        str(paper_outputs_root),
        "--require-paper-readiness",
    ]
    build_command.extend(["--experiment-matrix", str(experiment_matrix_path)])
    if require_experiment_coverage:
        build_command.append("--require-experiment-coverage")
    if effective_baseline_path is not None:
        build_command.extend(["--baseline-observations", str(effective_baseline_path)])
    if run_external_plans and external_steps.get("baseline_execution_manifest_path"):
        build_command.extend(["--baseline-execution-manifest", str(external_steps["baseline_execution_manifest_path"])])
    if effective_metric_rows_path is not None:
        build_command.extend(["--metric-rows", str(effective_metric_rows_path)])
    if run_external_plans and external_steps.get("metric_execution_manifest_path"):
        build_command.extend(["--metric-execution-manifest", str(external_steps["metric_execution_manifest_path"])])
    elif basic_metric_command:
        build_command.extend(["--metric-execution-manifest", str(basic_metric_execution_manifest_path)])
    if effective_image_pairs_path is not None:
        build_command.extend(["--image-pairs", str(effective_image_pairs_path)])
    build_command.extend(["--attacked-image-manifest", str(attacked_image_manifest_path)])
    build_command.extend(["--attack-shard-manifest", str(attack_shard_manifest_path)])

    package_command = [
        sys.executable,
        str(root / "scripts" / "export_paper_results_package.py"),
        "--source-output-root",
        str(paper_outputs_root),
        "--package-root",
        str(package_root),
    ]
    return {
        "artifact_name": "colab_command_plan.json",
        "repo_root": str(root),
        "workspace_root": str(workspace),
        "drive_output_root": output_layout["drive_output_root"],
        "output_layout": output_layout,
        "archives_root": output_layout["archives_root"],
        "profile": profile,
        "use_dry_run_inputs": use_dry_run_inputs,
        "run_external_plans": run_external_plans,
        "inputs_root": str(inputs_root),
        "paper_outputs_root": str(paper_outputs_root),
        "package_root": str(package_root),
        "matrix_root": str(matrix_root),
        "experiment_matrix_path": str(experiment_matrix_path),
        "require_experiment_coverage": require_experiment_coverage,
        "sample_manifest_path": str(Path(sample_manifest_path).resolve()) if sample_manifest_path else None,
        "compute_basic_image_metrics": compute_basic_image_metrics,
        "calibrate_thresholds": calibrate_thresholds,
        "threshold_target_fpr": threshold_target_fpr,
        "threshold_calibration_split": threshold_calibration_split,
        "threshold_root": str(threshold_root),
        "calibrated_thresholds_path": str(calibrated_thresholds_path),
        "attack_root": str(attack_root),
        "attacked_image_manifest_path": str(attacked_image_manifest_path),
        "attack_shard_manifest_path": str(attack_shard_manifest_path),
        "basic_metric_root": str(basic_metric_root),
        "provided_results_root": str(provided_results_root),
        "provided_result_copy_plan": provided_result_copy_plan,
        "generated_image_pairs_path": str(effective_image_pairs_path),
        "basic_metric_rows_path": str(basic_metric_rows_path),
        "basic_metric_execution_manifest_path": str(basic_metric_execution_manifest_path),
        "matrix_command": matrix_command,
        "threshold_calibration_command": threshold_calibration_command,
        "prepare_command": prepare_command,
        "basic_metric_command": basic_metric_command,
        "attack_command": attack_command,
        "external_plan_steps": external_steps,
        "build_command": build_command,
        "package_command": package_command,
    }


def build_colab_input_manifest(command_plan: dict[str, Any]) -> dict[str, Any]:
    """根据命令计划生成输入路径和输出契约清单。"""
    build_command = list(command_plan.get("build_command", []))
    path_flags = {"--events", "--thresholds", "--baseline-observations", "--baseline-execution-manifest", "--metric-rows", "--metric-execution-manifest", "--image-pairs", "--experiment-matrix", "--attacked-image-manifest", "--attack-shard-manifest"}
    input_paths = []
    for index, part in enumerate(build_command[:-1]):
        if part in path_flags:
            candidate = Path(str(build_command[index + 1]))
            input_paths.append({"role": part.lstrip("-"), "path": str(candidate), "exists": candidate.exists()})

    source_input_paths = []
    for item in command_plan.get("provided_result_copy_plan", []):
        if not isinstance(item, dict):
            continue
        source_candidate = Path(str(item.get("source_path", "")))
        source_input_paths.append(
            {
                "role": f"provided_result:{item.get('role', 'unknown')}",
                "path": str(source_candidate),
                "exists": source_candidate.exists(),
            }
        )
    for command_name, flags in {
        "threshold_calibration_command": {"--samples"},
        "prepare_command": {"--samples", "--thresholds"},
        "basic_metric_command": {"--pairs"},
        "attack_command": {"--image-pairs"},
    }.items():
        command = list(command_plan.get(command_name, []))
        for index, part in enumerate(command[:-1]):
            if part in flags:
                candidate = Path(str(command[index + 1]))
                source_input_paths.append(
                    {
                        "role": f"{command_name}:{part.lstrip('-')}",
                        "path": str(candidate),
                        "exists": candidate.exists(),
                    }
                )

    package_root = Path(str(command_plan["package_root"]))
    preflight_outputs = [
        str(Path(str(command_plan["matrix_root"])) / "experiment_matrix.json"),
        str(Path(str(command_plan["matrix_root"])) / "experiment_matrix_manifest.json"),
    ]
    if command_plan.get("threshold_calibration_command"):
        preflight_outputs.append(str(Path(str(command_plan["threshold_root"])) / "thresholds.json"))
        preflight_outputs.append(str(Path(str(command_plan["threshold_root"])) / "threshold_calibration_report.json"))
    if command_plan.get("prepare_command"):
        preflight_outputs.append(str(Path(str(command_plan["inputs_root"])) / "events.json"))
        if command_plan.get("use_dry_run_inputs"):
            inputs_root = Path(str(command_plan["inputs_root"]))
            preflight_outputs.append(str(inputs_root / "prompt_plan.json"))
            preflight_outputs.append(str(inputs_root / "mock_image_generation_backend_manifest.json"))
            preflight_outputs.append(str(inputs_root / "image_manifests" / "image_generation_manifest.json"))
            preflight_outputs.append(str(inputs_root / "image_manifests" / "image_pair_manifest.json"))
        if not command_plan.get("use_dry_run_inputs"):
            preflight_outputs.append(str(Path(str(command_plan["inputs_root"])) / "sample_event_build_manifest.json"))
    if command_plan.get("basic_metric_command"):
        preflight_outputs.append(str(command_plan["basic_metric_rows_path"]))
        preflight_outputs.append(str(command_plan["basic_metric_execution_manifest_path"]))
    if command_plan.get("attack_command"):
        preflight_outputs.append(str(command_plan["attacked_image_manifest_path"]))
        preflight_outputs.append(str(command_plan["attack_shard_manifest_path"]))
        preflight_outputs.append(str(Path(str(command_plan["attack_root"])) / "image_pairs_attacked.json"))
    if command_plan.get("provided_result_copy_plan"):
        provided_root = Path(str(command_plan["provided_results_root"]))
        preflight_outputs.append(str(provided_root / "provided_result_files_manifest.json"))
        for item in command_plan.get("provided_result_copy_plan", []):
            if isinstance(item, dict) and item.get("target_path"):
                preflight_outputs.append(str(Path(str(item["target_path"]))))
    expected_outputs = [
        str(package_root / "paper_results_package_manifest.json"),
        str(package_root / "paper_results_package_validation.json"),
        str(package_root / "artifacts" / "paper_claim_audit.json"),
        str(package_root / "artifacts" / "paper_experiment_coverage_report.json"),
        str(package_root / "paper_results_report.md"),
    ]
    generated_paths = set(preflight_outputs)
    generated_paths.add(str(Path(str(command_plan.get("experiment_matrix_path", "")))))
    if command_plan.get("generated_image_pairs_path"):
        generated_paths.add(str(Path(str(command_plan["generated_image_pairs_path"]))))
    if command_plan.get("threshold_calibration_command"):
        generated_paths.add(str(Path(str(command_plan["threshold_root"])) / "thresholds.json"))
    if command_plan.get("use_dry_run_inputs"):
        generated_paths.update(
            str(Path(str(command_plan["inputs_root"])) / name)
            for name in (
                "events.json",
                "thresholds.json",
                "baseline_observations.json",
                "metric_rows.json",
                "prompt_plan.json",
                "mock_image_generation_backend_manifest.json",
                "image_manifests/image_generation_manifest.json",
                "image_manifests/image_pair_manifest.json",
            )
        )
    if command_plan.get("run_external_plans"):
        external_steps = command_plan.get("external_plan_steps", {})
        for key in ("baseline_observations_path", "baseline_execution_manifest_path", "metric_rows_path", "metric_execution_manifest_path"):
            if external_steps.get(key):
                generated_paths.add(str(Path(str(external_steps[key]))))
    if command_plan.get("basic_metric_command"):
        generated_paths.add(str(Path(str(command_plan["basic_metric_rows_path"]))))
        generated_paths.add(str(Path(str(command_plan["basic_metric_execution_manifest_path"]))))
    if command_plan.get("attack_command"):
        generated_paths.add(str(Path(str(command_plan["attacked_image_manifest_path"]))))
        generated_paths.add(str(Path(str(command_plan["attack_shard_manifest_path"]))))
        generated_paths.add(str(Path(str(command_plan["attack_root"])) / "image_pairs_attacked.json"))
    if command_plan.get("provided_result_copy_plan"):
        generated_paths.add(str(Path(str(command_plan["provided_results_root"])) / "provided_result_files_manifest.json"))
        for item in command_plan.get("provided_result_copy_plan", []):
            if isinstance(item, dict) and item.get("target_path"):
                generated_paths.add(str(Path(str(item["target_path"]))))

    missing_required_inputs = []
    for item in [*input_paths, *source_input_paths]:
        if item["exists"]:
            continue
        if item["path"] in generated_paths:
            continue
        if item["role"] in {"events", "thresholds"} or item["role"].startswith("prepare_command:") or item["role"].startswith("basic_metric_command:") or item["role"].startswith("attack_command:"):
            missing_required_inputs.append(item)
    return {
        "artifact_name": "colab_input_manifest.json",
        "input_paths": input_paths,
        "source_input_paths": source_input_paths,
        "preflight_outputs": preflight_outputs,
        "expected_outputs": expected_outputs,
        "missing_required_inputs": missing_required_inputs,
    }


def _issue(issue_id: str, severity: str, message: str, evidence: Any) -> dict[str, Any]:
    """构造 Colab 正式运行清单中的问题项。"""
    return {"issue_id": issue_id, "severity": severity, "message": message, "evidence": evidence}


def _command_value(spec: Any, name: str, default: Any = None) -> Any:
    """从 dataclass 或 dict 命令计划行中读取字段。"""
    if isinstance(spec, dict):
        return spec.get(name, default)
    return getattr(spec, name, default)


def _looks_like_executable_script(part: str) -> bool:
    """判断命令参数是否像需要预先存在的第三方脚本文件。"""
    if part.startswith("-"):
        return False
    path = Path(part)
    return path.suffix in {".py", ".sh", ".bash"} and (path.is_absolute() or "/" in part or "\\" in part)


def _inspect_external_specs(specs: list[Any], *, plan_kind: str) -> dict[str, Any]:
    """检查外部命令计划中的脚本文件和工作目录是否已经存在。"""
    violations: list[dict[str, Any]] = []
    for index, spec in enumerate(specs):
        command = [str(part) for part in (_command_value(spec, "command", ()) or ())]
        working_directory = _command_value(spec, "working_directory")
        template_id = _command_value(spec, "baseline_id") or _command_value(spec, "metric_name") or _command_value(spec, "template_id") or f"row_{index}"
        if working_directory and not Path(str(working_directory)).exists():
            violations.append(
                {
                    "plan_kind": plan_kind,
                    "template_id": str(template_id),
                    "reason": "working_directory_missing",
                    "path": str(working_directory),
                }
            )
        for part in command:
            if _looks_like_executable_script(part) and not Path(part).is_file():
                violations.append(
                    {
                        "plan_kind": plan_kind,
                        "template_id": str(template_id),
                        "reason": "script_missing",
                        "path": part,
                    }
                )
    return {"plan_kind": plan_kind, "command_count": len(specs), "violations": violations}


def _flag_value(command: list[Any], flag: str) -> str | None:
    """从 argv 列表中读取某个 flag 后面的取值。"""
    parts = [str(part) for part in command]
    for index, part in enumerate(parts[:-1]):
        if part == flag:
            return parts[index + 1]
    return None


def _build_external_plan_preflight(
    root: Path,
    command_plan: dict[str, Any] | None,
    *,
    run_external_plans: bool,
    baseline_plan_path: str | Path | None,
    metric_plan_path: str | Path | None,
    baseline_root: str | Path | None,
    metric_root: str | Path | None,
    image_pairs_path: str | Path | None,
    reference_image_root: str | Path | None,
    generated_image_root: str | Path | None,
    image_prompt_rows_path: str | Path | None,
) -> dict[str, Any]:
    """物化或读取外部计划, 并在正式运行前预检第三方脚本和工作目录。"""
    if not run_external_plans:
        return {"status": "not_required", "checks": [], "violation_count": 0}
    if command_plan is None:
        return {"status": "fail", "checks": [], "violation_count": 1, "reason": "command_plan_missing"}

    from experiments.baseline_plan import load_baseline_command_plan
    from experiments.command_templates import materialize_baseline_command_plan, materialize_metric_command_plan
    from experiments.metric_plan import load_metric_command_plan

    external_steps = command_plan.get("external_plan_steps", {}) if isinstance(command_plan, dict) else {}
    build_command = list(command_plan.get("build_command", [])) if isinstance(command_plan, dict) else []
    events_path = _flag_value(build_command, "--events") or ""
    baseline_output_root = str(external_steps.get("baseline_output_root") or Path(str(command_plan.get("workspace_root", "."))) / "external_baselines")
    metric_output_root = str(external_steps.get("metric_output_root") or Path(str(command_plan.get("workspace_root", "."))) / "external_metrics")

    checks: list[dict[str, Any]] = []
    load_failures: list[dict[str, Any]] = []
    try:
        if baseline_plan_path:
            baseline_specs = load_baseline_command_plan(Path(baseline_plan_path))
        else:
            baseline_specs = materialize_baseline_command_plan(
                root / "configs" / "baseline_command_templates.json",
                {
                    "baseline_root": str(Path(str(baseline_root)).resolve()),
                    "events_path": events_path,
                    "output_root": baseline_output_root,
                },
            )
        checks.append(_inspect_external_specs(list(baseline_specs), plan_kind="baseline"))
    except Exception as exc:
        load_failures.append({"plan_kind": "baseline", "reason": "plan_load_or_materialize_failed", "error": str(exc)})

    try:
        if metric_plan_path:
            metric_specs = load_metric_command_plan(metric_plan_path)
        else:
            metric_specs = materialize_metric_command_plan(
                root / "configs" / "external_metric_command_templates.json",
                {
                    "metric_root": str(Path(str(metric_root)).resolve()),
                    "image_pairs_path": str(Path(image_pairs_path).resolve()) if image_pairs_path else "",
                    "reference_image_root": str(Path(reference_image_root).resolve()) if reference_image_root else "",
                    "generated_image_root": str(Path(generated_image_root).resolve()) if generated_image_root else "",
                    "image_prompt_rows_path": str(Path(image_prompt_rows_path).resolve()) if image_prompt_rows_path else "",
                    "output_root": metric_output_root,
                },
            )
        checks.append(_inspect_external_specs(list(metric_specs), plan_kind="metric"))
    except Exception as exc:
        load_failures.append({"plan_kind": "metric", "reason": "plan_load_or_materialize_failed", "error": str(exc)})

    violations = [violation for check in checks for violation in check.get("violations", [])]
    violation_count = len(violations) + len(load_failures)
    return {
        "status": "fail" if violation_count else "pass",
        "checks": checks,
        "load_failures": load_failures,
        "violation_count": violation_count,
    }


ADVANCED_METRIC_FIELDS = {"lpips", "fid", "clip_score"}


def _load_rows_for_formal_input_preflight(path: str | Path) -> list[dict[str, Any]]:
    """读取 JSON / JSONL / CSV 行文件, 供正式输入预检复用。

    该函数只做轻量结构读取, 不运行模型, 不生成正式论文记录。它用于在 Colab 正式运行前尽早发现
    events、sample manifest 或 image pairs 文件格式错误, 避免长时间 GPU 任务结束后才失败。
    """
    input_path = Path(path)
    if input_path.suffix == ".jsonl":
        return [json.loads(line) for line in input_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if input_path.suffix == ".json":
        payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            raise TypeError("formal row JSON must contain a list")
        return [dict(row) for row in payload]
    if input_path.suffix == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"unsupported formal row file extension: {input_path.suffix}")


def _missing_required_fields(rows: list[dict[str, Any]], required_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    """返回正式输入行中缺失必需字段的轻量摘要。

    只记录行号和字段名, 不复制完整样本内容, 这样可以把预检结果安全写入 checklist 和 bundle。
    """
    missing_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        missing_fields = [
            field
            for field in required_fields
            if field not in row or row.get(field) is None or (isinstance(row.get(field), str) and str(row.get(field)).strip() == "")
        ]
        if missing_fields:
            missing_rows.append({"row_index": row_index, "missing_fields": missing_fields})
    return missing_rows


def _build_formal_input_source_preflight(
    *,
    events_path: str | Path | None,
    thresholds_path: str | Path | None,
    sample_manifest_path: str | Path | None,
    image_pairs_path: str | Path | None,
) -> dict[str, Any]:
    """预检正式 Colab 输入源的结构是否满足后续 repository scripts 的最低要求。

    该预检属于通用工程写法: 在执行昂贵任务前先检查输入结构。项目特定部分在于它复用 CEG
    的事件字段、样本清单字段和图像配对字段契约, 并把检查结果写入正式运行 checklist。
    """
    checks: list[dict[str, Any]] = []

    if events_path is not None:
        event_check: dict[str, Any] = {
            "file_kind": "events",
            "path": str(Path(events_path)),
            "status": "pass",
            "row_count": 0,
            "violations": [],
        }
        try:
            event_rows = _load_rows_for_formal_input_preflight(events_path)
            event_check["row_count"] = len(event_rows)
            if not event_rows:
                event_check["violations"].append({"reason": "empty_events"})
            missing_rows = _missing_required_fields(event_rows, FORMAL_EVENT_REQUIRED_FIELDS)
            if missing_rows:
                event_check["violations"].append({"reason": "missing_event_required_fields", "rows": missing_rows[:10]})
            payload_violations = [
                {"row_index": index, "reason": "payload_not_object"}
                for index, row in enumerate(event_rows)
                if not isinstance(row.get("payload"), dict)
            ]
            if payload_violations:
                event_check["violations"].append({"reason": "event_payload_not_object", "rows": payload_violations[:10]})
        except Exception as exc:
            event_check["violations"].append({"reason": "events_file_load_failed", "error": str(exc)})
        if event_check["violations"]:
            event_check["status"] = "fail"
        checks.append(event_check)

    if thresholds_path is not None:
        threshold_check: dict[str, Any] = {
            "file_kind": "thresholds",
            "path": str(Path(thresholds_path)),
            "status": "pass",
            "threshold_count": 0,
            "violations": [],
        }
        try:
            from experiments.sample_manifest import load_threshold_map

            threshold_map = load_threshold_map(thresholds_path)
            threshold_check["threshold_count"] = len(threshold_map)
            if not threshold_map:
                threshold_check["violations"].append({"reason": "empty_threshold_map"})
        except Exception as exc:
            threshold_check["violations"].append({"reason": "threshold_file_load_failed", "error": str(exc)})
        if threshold_check["violations"]:
            threshold_check["status"] = "fail"
        checks.append(threshold_check)

    if sample_manifest_path is not None:
        sample_check: dict[str, Any] = {
            "file_kind": "sample_manifest",
            "path": str(Path(sample_manifest_path)),
            "status": "pass",
            "row_count": 0,
            "splits": [],
            "sample_roles": [],
            "violations": [],
        }
        try:
            from experiments.sample_manifest import load_sample_manifest

            sample_rows = load_sample_manifest(sample_manifest_path)
            sample_check["row_count"] = len(sample_rows)
            sample_check["splits"] = sorted({str(row.get("split")) for row in sample_rows if row.get("split") not in {None, ""}})
            sample_check["sample_roles"] = sorted({str(row.get("sample_role")) for row in sample_rows if row.get("sample_role") not in {None, ""}})
            if not sample_rows:
                sample_check["violations"].append({"reason": "empty_sample_manifest"})
            missing_rows = _missing_required_fields(sample_rows, FORMAL_SAMPLE_MANIFEST_REQUIRED_FIELDS)
            if missing_rows:
                sample_check["violations"].append({"reason": "missing_sample_required_fields", "rows": missing_rows[:10]})
        except Exception as exc:
            sample_check["violations"].append({"reason": "sample_manifest_load_failed", "error": str(exc)})
        if sample_check["violations"]:
            sample_check["status"] = "fail"
        checks.append(sample_check)

    if image_pairs_path is not None:
        image_pair_check: dict[str, Any] = {
            "file_kind": "image_pairs",
            "path": str(Path(image_pairs_path)),
            "status": "pass",
            "row_count": 0,
            "violations": [],
        }
        try:
            image_pair_rows = _load_rows_for_formal_input_preflight(image_pairs_path)
            image_pair_check["row_count"] = len(image_pair_rows)
            if not image_pair_rows:
                image_pair_check["violations"].append({"reason": "empty_image_pairs"})
            missing_rows = _missing_required_fields(image_pair_rows, FORMAL_IMAGE_PAIR_REQUIRED_FIELDS)
            if missing_rows:
                image_pair_check["violations"].append({"reason": "missing_image_pair_required_fields", "rows": missing_rows[:10]})
        except Exception as exc:
            image_pair_check["violations"].append({"reason": "image_pairs_file_load_failed", "error": str(exc)})
        if image_pair_check["violations"]:
            image_pair_check["status"] = "fail"
        checks.append(image_pair_check)

    violation_count = sum(len(check.get("violations", [])) for check in checks)
    return {
        "artifact_name": "formal_input_source_preflight",
        "status": "not_required" if not checks else ("fail" if violation_count else "pass"),
        "checks": checks,
        "violation_count": violation_count,
    }


def _build_provided_result_file_preflight(
    *,
    baseline_observations_path: str | Path | None,
    metric_rows_path: str | Path | None,
) -> dict[str, Any]:
    """预检用户直接提供的 baseline 和高级指标文件是否符合正式适配器契约。

    该函数只读取轻量 JSON / JSONL / CSV 结果文件, 不运行模型, 也不生成正式 records。
    它复用 experiments 中的正式文件适配器, 这样 Notebook 清单与后续 artifact rebuild 使用同一套结构规则。
    """
    checks: list[dict[str, Any]] = []

    if baseline_observations_path is not None:
        baseline_check: dict[str, Any] = {
            "file_kind": "baseline_observations",
            "path": str(Path(baseline_observations_path)),
            "status": "pass",
            "row_count": 0,
            "baseline_ids": [],
            "violations": [],
        }
        try:
            from experiments.baseline_file_adapter import load_baseline_observation_rows

            baseline_rows = load_baseline_observation_rows(baseline_observations_path)
            baseline_ids = sorted({str(row.get("baseline_id")) for row in baseline_rows if row.get("baseline_id") not in {None, ""}})
            baseline_check["row_count"] = len(baseline_rows)
            baseline_check["baseline_ids"] = baseline_ids
            if not baseline_rows:
                baseline_check["violations"].append({"reason": "empty_baseline_observations"})
            if not baseline_ids:
                baseline_check["violations"].append({"reason": "missing_baseline_ids"})
        except Exception as exc:
            baseline_check["violations"].append({"reason": "baseline_file_load_failed", "error": str(exc)})
        if baseline_check["violations"]:
            baseline_check["status"] = "fail"
        checks.append(baseline_check)

    if metric_rows_path is not None:
        metric_check: dict[str, Any] = {
            "file_kind": "metric_rows",
            "path": str(Path(metric_rows_path)),
            "status": "pass",
            "row_count": 0,
            "metric_fields": [],
            "advanced_metric_fields": [],
            "violations": [],
        }
        try:
            from experiments.metric_file_adapter import load_metric_rows

            metric_rows = load_metric_rows(metric_rows_path)
            metric_fields = sorted(
                {
                    key
                    for row in metric_rows
                    for key in row
                    if key not in {"event_id", "method_name", "baseline_id"}
                }
            )
            advanced_metric_fields = sorted(set(metric_fields) & ADVANCED_METRIC_FIELDS)
            metric_check["row_count"] = len(metric_rows)
            metric_check["metric_fields"] = metric_fields
            metric_check["advanced_metric_fields"] = advanced_metric_fields
            if not metric_rows:
                metric_check["violations"].append({"reason": "empty_metric_rows"})
            if not advanced_metric_fields:
                metric_check["violations"].append(
                    {
                        "reason": "advanced_metric_fields_missing",
                        "required_any_of": sorted(ADVANCED_METRIC_FIELDS),
                    }
                )
        except Exception as exc:
            metric_check["violations"].append({"reason": "metric_file_load_failed", "error": str(exc)})
        if metric_check["violations"]:
            metric_check["status"] = "fail"
        checks.append(metric_check)

    violation_count = sum(len(check.get("violations", [])) for check in checks)
    return {
        "status": "not_required" if not checks else ("fail" if violation_count else "pass"),
        "checks": checks,
        "violation_count": violation_count,
    }


def build_colab_formal_run_checklist(
    repo_root: str | Path,
    workspace_root: str | Path,
    *,
    profile: str = "paper_main_full",
    use_dry_run_inputs: bool = False,
    run_external_plans: bool = False,
    require_gpu_for_external_plans: bool = True,
    require_experiment_coverage: bool = True,
    events_path: str | Path | None = None,
    thresholds_path: str | Path | None = None,
    sample_manifest_path: str | Path | None = None,
    compute_basic_image_metrics: bool = False,
    calibrate_thresholds: bool = False,
    threshold_target_fpr: float = 0.01,
    threshold_calibration_split: str = "calibration",
    baseline_observations_path: str | Path | None = None,
    metric_rows_path: str | Path | None = None,
    baseline_plan_path: str | Path | None = None,
    metric_plan_path: str | Path | None = None,
    baseline_root: str | Path | None = None,
    metric_root: str | Path | None = None,
    image_pairs_path: str | Path | None = None,
    reference_image_root: str | Path | None = None,
    generated_image_root: str | Path | None = None,
    image_prompt_rows_path: str | Path | None = None,
) -> dict[str, Any]:
    """生成 Colab 正式实验从冷启动到论文结果的运行清单。

    该函数只构造命令计划、输入检查、外部结果来源模式和验收命令, 不运行 GPU 任务。
    它的主要用途是在 Notebook 执行正式实验前, 让使用者确认是否已经提供真实样本、阈值、baseline 和高级指标来源。
    """
    root = Path(repo_root).resolve()
    workspace = Path(workspace_root).resolve()
    output_layout = build_colab_output_layout(workspace)
    issues: list[dict[str, Any]] = []
    environment_summary = build_colab_environment_summary(root)
    gpu_available = _environment_has_gpu(environment_summary)
    gpu_readiness = {
        "required_for_external_plans": require_gpu_for_external_plans,
        "gpu_available": gpu_available,
        "checked_for_formal_external_plans": bool(run_external_plans and not use_dry_run_inputs),
    }
    if run_external_plans and not use_dry_run_inputs and require_gpu_for_external_plans and not gpu_available:
        issues.append(
            _issue(
                "gpu_runtime_unavailable_for_external_plans",
                "blocking",
                "正式外部 baseline 或高级指标计划需要 Colab GPU 运行时。请在 Colab 中启用 GPU 后重新生成运行清单。",
                gpu_readiness,
            )
        )

    if use_dry_run_inputs:
        issues.append(
            _issue(
                "dry_run_inputs_enabled",
                "blocking",
                "正式论文结果不能使用 dry-run 输入。",
                {"use_dry_run_inputs": use_dry_run_inputs},
            )
        )
    if not require_experiment_coverage:
        issues.append(
            _issue(
                "experiment_coverage_not_required",
                "blocking",
                "正式论文结果必须把实验矩阵覆盖率作为门禁。",
                {"require_experiment_coverage": require_experiment_coverage},
            )
        )
    if events_path is None and sample_manifest_path is None:
        issues.append(
            _issue(
                "formal_event_source_missing",
                "blocking",
                "正式实验需要 events.json 或 sample_manifest_path 作为事件来源。",
                {"events_path": events_path, "sample_manifest_path": sample_manifest_path},
            )
        )
    if thresholds_path is None and not (calibrate_thresholds and sample_manifest_path is not None):
        issues.append(
            _issue(
                "formal_threshold_source_missing",
                "blocking",
                "正式实验需要 thresholds.json, 或使用 calibration split 从样本清单校准阈值。",
                {"thresholds_path": thresholds_path, "calibrate_thresholds": calibrate_thresholds},
            )
        )

    formal_input_source_preflight = _build_formal_input_source_preflight(
        events_path=events_path if events_path is not None else None,
        thresholds_path=thresholds_path if thresholds_path is not None else None,
        sample_manifest_path=sample_manifest_path if sample_manifest_path is not None else None,
        image_pairs_path=image_pairs_path if image_pairs_path is not None else None,
    )
    if formal_input_source_preflight.get("status") == "fail":
        issues.append(
            _issue(
                "formal_input_source_preflight_failed",
                "blocking",
                "正式输入源文件未通过结构预检。请优先修复 events、thresholds、sample manifest 或 image pairs 文件, 再启动正式论文实验。",
                formal_input_source_preflight,
            )
        )

    baseline_source_mode = "external_plan" if run_external_plans else ("provided_file" if baseline_observations_path else "missing")
    metric_source_mode = "external_plan" if run_external_plans else ("provided_file" if metric_rows_path else "missing")
    if baseline_source_mode == "missing":
        issues.append(
            _issue(
                "external_baseline_source_missing",
                "blocking",
                "正式论文对比需要外部 baseline observation 文件或可执行外部 baseline 计划。",
                {"run_external_plans": run_external_plans, "baseline_observations_path": baseline_observations_path},
            )
        )
    if metric_source_mode == "missing":
        issues.append(
            _issue(
                "advanced_metric_source_missing",
                "blocking",
                "正式论文质量指标需要 LPIPS/FID/CLIP score 等高级指标文件或可执行外部 metric 计划。",
                {"run_external_plans": run_external_plans, "metric_rows_path": metric_rows_path},
            )
        )

    provided_result_file_preflight = _build_provided_result_file_preflight(
        baseline_observations_path=baseline_observations_path if baseline_source_mode == "provided_file" else None,
        metric_rows_path=metric_rows_path if metric_source_mode == "provided_file" else None,
    )
    if provided_result_file_preflight.get("status") == "fail":
        issues.append(
            _issue(
                "provided_result_file_preflight_failed",
                "blocking",
                "直接提供的 baseline observation 或高级指标文件不能通过正式适配器结构预检。",
                provided_result_file_preflight,
            )
        )
    if run_external_plans and baseline_plan_path is None and baseline_root is None:
        issues.append(
            _issue(
                "baseline_plan_materialization_source_missing",
                "blocking",
                "启用外部 baseline 计划时, 需要 baseline_plan_path 或 baseline_root。",
                {"baseline_plan_path": baseline_plan_path, "baseline_root": baseline_root},
            )
        )
    if run_external_plans and metric_plan_path is None and metric_root is None:
        issues.append(
            _issue(
                "metric_plan_materialization_source_missing",
                "blocking",
                "启用外部 metric 计划时, 需要 metric_plan_path 或 metric_root。",
                {"metric_plan_path": metric_plan_path, "metric_root": metric_root},
            )
        )

    command_plan: dict[str, Any] | None = None
    input_manifest: dict[str, Any] | None = None
    external_plan_preflight: dict[str, Any] = {"status": "not_started", "checks": [], "violation_count": 0}
    try:
        command_plan = build_colab_command_plan(
            root,
            workspace,
            profile=profile,
            use_dry_run_inputs=use_dry_run_inputs,
            run_external_plans=run_external_plans,
            require_experiment_coverage=require_experiment_coverage,
            events_path=events_path,
            thresholds_path=thresholds_path,
            sample_manifest_path=sample_manifest_path,
            compute_basic_image_metrics=compute_basic_image_metrics,
            calibrate_thresholds=calibrate_thresholds,
            threshold_target_fpr=threshold_target_fpr,
            threshold_calibration_split=threshold_calibration_split,
            baseline_observations_path=baseline_observations_path,
            metric_rows_path=metric_rows_path,
            baseline_plan_path=baseline_plan_path,
            metric_plan_path=metric_plan_path,
            baseline_root=baseline_root,
            metric_root=metric_root,
            image_pairs_path=image_pairs_path,
            reference_image_root=reference_image_root,
            generated_image_root=generated_image_root,
            image_prompt_rows_path=image_prompt_rows_path,
        )
        input_manifest = build_colab_input_manifest(command_plan)
        for missing in input_manifest.get("missing_required_inputs", []):
            issues.append(
                _issue(
                    "required_input_path_missing",
                    "blocking",
                    "正式运行清单中的必需输入路径当前不可用。",
                    missing,
                )
            )
        external_plan_preflight = _build_external_plan_preflight(
            root,
            command_plan,
            run_external_plans=run_external_plans,
            baseline_plan_path=baseline_plan_path,
            metric_plan_path=metric_plan_path,
            baseline_root=baseline_root,
            metric_root=metric_root,
            image_pairs_path=image_pairs_path,
            reference_image_root=reference_image_root,
            generated_image_root=generated_image_root,
            image_prompt_rows_path=image_prompt_rows_path,
        )
        if external_plan_preflight.get("status") == "fail":
            issues.append(
                _issue(
                    "external_command_plan_preflight_failed",
                    "blocking",
                    "外部 baseline 或高级指标命令计划中的第三方脚本 / 工作目录缺失。",
                    external_plan_preflight,
                )
            )
    except Exception as exc:
        issues.append(
            _issue(
                "command_plan_build_failed",
                "blocking",
                "无法构造 Colab 正式运行命令计划。",
                str(exc),
            )
        )

    evidence_command = [
        sys.executable,
        str(root / "scripts" / "validate_paper_result_evidence.py"),
        "--target",
        str(workspace / "colab_run_bundle"),
        "--require-pass",
    ]
    acceptance_command = [
        sys.executable,
        str(root / "scripts" / "run_colab_acceptance_checks.py"),
        "--bundle",
        str(workspace / "colab_run_bundle"),
        "--require-pass",
    ]
    if use_dry_run_inputs:
        acceptance_command.insert(-1, "--allow-dry-run")
    if not require_experiment_coverage:
        acceptance_command.insert(-1, "--allow-missing-experiment-coverage")
    if run_external_plans:
        evidence_command.insert(-1, "--require-external-command-results")
        acceptance_command.insert(-1, "--require-external-command-results")

    blocking_issues = [issue for issue in issues if issue.get("severity") == "blocking"]
    return {
        "artifact_name": "colab_formal_run_checklist.json",
        "overall_decision": "fail" if blocking_issues else "pass",
        "repo_root": str(root),
        "workspace_root": str(workspace),
        "drive_output_root": output_layout["drive_output_root"],
        "output_layout": output_layout,
        "profile": profile,
        "use_dry_run_inputs": use_dry_run_inputs,
        "run_external_plans": run_external_plans,
        "require_gpu_for_external_plans": require_gpu_for_external_plans,
        "gpu_readiness": gpu_readiness,
        "environment_summary": environment_summary,
        "require_experiment_coverage": require_experiment_coverage,
        "baseline_source_mode": baseline_source_mode,
        "metric_source_mode": metric_source_mode,
        "compute_basic_image_metrics": compute_basic_image_metrics,
        "calibrate_thresholds": calibrate_thresholds,
        "formal_input_source_preflight": formal_input_source_preflight,
        "formal_input_source_violation_count": int(formal_input_source_preflight.get("violation_count", 0)),
        "provided_result_file_preflight": provided_result_file_preflight,
        "provided_result_file_violation_count": int(provided_result_file_preflight.get("violation_count", 0)),
        "external_plan_preflight": external_plan_preflight,
        "external_command_plan_violation_count": int(external_plan_preflight.get("violation_count", 0)),
        "issues": issues,
        "blocking_issue_count": len(blocking_issues),
        "command_plan": command_plan,
        "input_manifest": input_manifest,
        "acceptance_commands": {
            "validate_colab_run_bundle": [
                sys.executable,
                str(root / "scripts" / "validate_colab_run_bundle.py"),
                "--bundle",
                str(workspace / "colab_run_bundle"),
                "--require-pass",
            ],
            "validate_paper_result_evidence": evidence_command,
            "run_colab_acceptance_checks": acceptance_command,
        },
    }


def run_colab_acceptance_checks(
    repo_root: str | Path,
    workspace_root: str | Path,
    *,
    allow_dry_run: bool = False,
    require_experiment_coverage: bool = True,
    require_external_command_results: bool = False,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """运行 Colab bundle 的最终验收命令并写出结构化 acceptance report。

    该函数属于 Notebook 交付后的验收层, 只调用仓库已有 CLI 读取并校验已生成的 bundle。
    它不重新生成 records、tables、figures 或 reports, 因此不会把 Notebook 变成正式协议逻辑的唯一实现。
    """
    root = Path(repo_root).resolve()
    workspace = Path(workspace_root).resolve()
    output_layout = build_colab_output_layout(workspace)
    bundle_root = Path(output_layout["colab_run_bundle_root"])
    acceptance_root = Path(output_layout["acceptance_root"])
    acceptance_root.mkdir(parents=True, exist_ok=True)

    bundle_validation_command = [
        sys.executable,
        str(root / "scripts" / "validate_colab_run_bundle.py"),
        "--bundle",
        str(bundle_root),
        "--out",
        str(acceptance_root / "colab_run_bundle_validation_cli.json"),
        "--require-pass",
    ]
    evidence_command = [
        sys.executable,
        str(root / "scripts" / "validate_paper_result_evidence.py"),
        "--target",
        str(bundle_root),
        "--out",
        str(acceptance_root / "paper_result_evidence_cli.json"),
        "--require-pass",
    ]
    if allow_dry_run:
        evidence_command.insert(-1, "--allow-dry-run")
    if not require_experiment_coverage:
        evidence_command.insert(-1, "--allow-missing-experiment-coverage")
    if require_external_command_results:
        evidence_command.insert(-1, "--require-external-command-results")

    command_results = [
        run_command(bundle_validation_command, cwd=root, timeout_seconds=timeout_seconds),
        run_command(evidence_command, cwd=root, timeout_seconds=timeout_seconds),
    ]
    parsed_reports: dict[str, Any] = {}
    for name, report_path in {
        "colab_run_bundle_validation": acceptance_root / "colab_run_bundle_validation_cli.json",
        "paper_result_evidence": acceptance_root / "paper_result_evidence_cli.json",
    }.items():
        if report_path.is_file():
            try:
                parsed_reports[name] = json.loads(report_path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError as exc:
                parsed_reports[name] = {"overall_decision": "fail", "parse_error": str(exc)}
        else:
            parsed_reports[name] = {"overall_decision": "fail", "reason": "missing_report"}

    formal_gap_report_path = bundle_root / "colab_formal_result_gap_report.json"
    parsed_reports["formal_result_gap"] = _read_json_object(formal_gap_report_path) or {
        "overall_decision": "fail",
        "reason": "missing_or_malformed_report",
    }

    report_decisions = {name: payload.get("overall_decision") for name, payload in parsed_reports.items()}
    blocking_report_names = ("colab_run_bundle_validation", "paper_result_evidence")
    blocking_report_decisions = {name: report_decisions.get(name) for name in blocking_report_names}
    all_commands_passed = all(item.get("return_code") == 0 for item in command_results)
    all_blocking_reports_passed = all(decision == "pass" for decision in blocking_report_decisions.values())
    acceptance_report = {
        "artifact_name": "colab_acceptance_report.json",
        "overall_decision": "pass" if all_commands_passed and all_blocking_reports_passed else "fail",
        "drive_output_root": output_layout["drive_output_root"],
        "bundle_root": str(bundle_root),
        "acceptance_root": str(acceptance_root),
        "allow_dry_run": allow_dry_run,
        "require_experiment_coverage": require_experiment_coverage,
        "require_external_command_results": require_external_command_results,
        "report_decisions": report_decisions,
        "blocking_report_decisions": blocking_report_decisions,
        "formal_result_gap_decision": report_decisions.get("formal_result_gap"),
        "formal_result_gap_decision_mode": "post_acceptance_override",
        "command_results": command_results,
        "report_paths": {
            "colab_run_bundle_validation": str(acceptance_root / "colab_run_bundle_validation_cli.json"),
            "paper_result_evidence": str(acceptance_root / "paper_result_evidence_cli.json"),
            "formal_result_gap": str(formal_gap_report_path),
        },
    }
    post_acceptance_gap_report = build_colab_formal_result_gap_report(
        bundle_root,
        acceptance_report_override=acceptance_report,
    )
    report_decisions["formal_result_gap"] = post_acceptance_gap_report.get("overall_decision")
    acceptance_report["report_decisions"] = report_decisions
    acceptance_report["formal_result_gap_decision"] = report_decisions.get("formal_result_gap")
    acceptance_report["formal_result_gap_blocking_gap_requirements"] = post_acceptance_gap_report.get("blocking_gap_requirements")
    (workspace / "colab_acceptance_report.json").write_text(
        json.dumps(acceptance_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return acceptance_report


def write_colab_formal_run_checklist(
    output_path: str | Path,
    repo_root: str | Path,
    workspace_root: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """写出 Colab 正式实验运行清单 JSON。"""
    checklist = build_colab_formal_run_checklist(repo_root, workspace_root, **kwargs)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(checklist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return checklist


def run_colab_cold_start_pipeline(
    repo_root: str | Path,
    workspace_root: str | Path,
    *,
    profile: str = "paper_main_probe",
    repetitions: int = 1,
    use_dry_run_inputs: bool = True,
    run_external_plans: bool = False,
    require_gpu_for_external_plans: bool = True,
    require_experiment_coverage: bool = False,
    events_path: str | Path | None = None,
    thresholds_path: str | Path | None = None,
    sample_manifest_path: str | Path | None = None,
    compute_basic_image_metrics: bool = False,
    calibrate_thresholds: bool = False,
    threshold_target_fpr: float = 0.01,
    threshold_calibration_split: str = "calibration",
    baseline_observations_path: str | Path | None = None,
    metric_rows_path: str | Path | None = None,
    baseline_plan_path: str | Path | None = None,
    metric_plan_path: str | Path | None = None,
    baseline_root: str | Path | None = None,
    metric_root: str | Path | None = None,
    image_pairs_path: str | Path | None = None,
    reference_image_root: str | Path | None = None,
    generated_image_root: str | Path | None = None,
    image_prompt_rows_path: str | Path | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """在 Colab 或本地临时环境中运行完整论文结果链路。"""
    workspace = Path(workspace_root).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    formal_run_checklist = write_colab_formal_run_checklist(
        workspace / "colab_formal_run_checklist.json",
        repo_root,
        workspace_root,
        profile=profile,
        use_dry_run_inputs=use_dry_run_inputs,
        run_external_plans=run_external_plans,
        require_gpu_for_external_plans=require_gpu_for_external_plans,
        require_experiment_coverage=require_experiment_coverage,
        events_path=events_path,
        thresholds_path=thresholds_path,
        sample_manifest_path=sample_manifest_path,
        compute_basic_image_metrics=compute_basic_image_metrics,
        calibrate_thresholds=calibrate_thresholds,
        threshold_target_fpr=threshold_target_fpr,
        threshold_calibration_split=threshold_calibration_split,
        baseline_observations_path=baseline_observations_path,
        metric_rows_path=metric_rows_path,
        baseline_plan_path=baseline_plan_path,
        metric_plan_path=metric_plan_path,
        baseline_root=baseline_root,
        metric_root=metric_root,
        image_pairs_path=image_pairs_path,
        reference_image_root=reference_image_root,
        generated_image_root=generated_image_root,
        image_prompt_rows_path=image_prompt_rows_path,
    )
    plan = build_colab_command_plan(
        repo_root,
        workspace_root,
        profile=profile,
        repetitions=repetitions,
        use_dry_run_inputs=use_dry_run_inputs,
        run_external_plans=run_external_plans,
        require_experiment_coverage=require_experiment_coverage,
        events_path=events_path,
        thresholds_path=thresholds_path,
        sample_manifest_path=sample_manifest_path,
        compute_basic_image_metrics=compute_basic_image_metrics,
        calibrate_thresholds=calibrate_thresholds,
        threshold_target_fpr=threshold_target_fpr,
        threshold_calibration_split=threshold_calibration_split,
        baseline_observations_path=baseline_observations_path,
        metric_rows_path=metric_rows_path,
        baseline_plan_path=baseline_plan_path,
        metric_plan_path=metric_plan_path,
        baseline_root=baseline_root,
        metric_root=metric_root,
        image_pairs_path=image_pairs_path,
        reference_image_root=reference_image_root,
        generated_image_root=generated_image_root,
        image_prompt_rows_path=image_prompt_rows_path,
    )
    workspace = Path(plan["workspace_root"])
    output_layout_manifest = write_colab_output_layout_manifest(workspace)
    formal_input_contract = write_colab_formal_input_contract(workspace)
    formal_input_templates_manifest = write_colab_formal_input_templates(workspace)
    input_manifest = build_colab_input_manifest(plan)
    (workspace / "colab_input_manifest.json").write_text(
        json.dumps(input_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    provided_result_files_manifest = copy_provided_result_files(plan)
    results = []
    if plan["matrix_command"]:
        results.append(run_command(plan["matrix_command"], cwd=plan["repo_root"], timeout_seconds=timeout_seconds))
    if all(item["return_code"] == 0 for item in results) and plan.get("threshold_calibration_command"):
        results.append(run_command(plan["threshold_calibration_command"], cwd=plan["repo_root"], timeout_seconds=timeout_seconds))
    if all(item["return_code"] == 0 for item in results) and plan["prepare_command"]:
        results.append(run_command(plan["prepare_command"], cwd=plan["repo_root"], timeout_seconds=timeout_seconds))
    if all(item["return_code"] == 0 for item in results) and plan.get("basic_metric_command"):
        results.append(run_command(plan["basic_metric_command"], cwd=plan["repo_root"], timeout_seconds=timeout_seconds))
    if all(item["return_code"] == 0 for item in results) and plan.get("attack_command"):
        results.append(run_command(plan["attack_command"], cwd=plan["repo_root"], timeout_seconds=timeout_seconds))
    external_steps = plan["external_plan_steps"]
    for key in (
        "materialize_baseline_command",
        "baseline_execution_command",
        "materialize_metric_command",
        "metric_execution_command",
    ):
        if all(item["return_code"] == 0 for item in results) and external_steps.get(key):
            results.append(run_command(external_steps[key], cwd=plan["repo_root"], timeout_seconds=timeout_seconds))
    if all(item["return_code"] == 0 for item in results):
        results.append(run_command(plan["build_command"], cwd=plan["repo_root"], timeout_seconds=timeout_seconds))
    if all(item["return_code"] == 0 for item in results):
        results.append(run_command(plan["package_command"], cwd=plan["repo_root"], timeout_seconds=timeout_seconds))

    paper_result_evidence_report = None
    paper_result_index = None
    formal_result_gap_report = None
    if all(item["return_code"] == 0 for item in results):
        paper_result_index = write_colab_paper_result_index(workspace)
        from main.analysis.paper_result_evidence import write_paper_result_evidence_report

        # 先生成 package 级 evidence, 使首次 bundle 导出即可包含可解析的 provenance 文件。
        paper_result_evidence_report = write_paper_result_evidence_report(
            Path(str(plan["package_root"])),
            workspace / "paper_result_evidence_report.json",
            allow_dry_run=use_dry_run_inputs,
            require_experiment_coverage=require_experiment_coverage,
            require_external_command_results=False,
        )
        formal_result_gap_report = write_colab_formal_result_gap_report(workspace)

    summary = {
        "artifact_name": "colab_cold_start_summary.json",
        "overall_decision": "pass" if results and all(item["return_code"] == 0 for item in results) else "fail",
        "environment": build_colab_environment_summary(plan["repo_root"]),
        "drive_output_root": plan.get("drive_output_root"),
        "output_layout": plan.get("output_layout"),
        "colab_output_layout_manifest_path": str(workspace / "colab_output_layout_manifest.json"),
        "colab_output_layout_manifest": output_layout_manifest,
        "colab_formal_input_contract_path": str(workspace / "colab_formal_input_contract.json"),
        "colab_formal_input_contract": formal_input_contract,
        "formal_input_templates_manifest_path": str(workspace / "inputs" / "formal_input_templates_manifest.json"),
        "formal_input_templates_manifest": formal_input_templates_manifest,
        "colab_paper_result_index_path": str(workspace / "colab_paper_result_index.json") if paper_result_index else None,
        "colab_paper_result_index": paper_result_index,
        "colab_paper_result_semantic_check_summary": paper_result_index.get("semantic_check_summary") if paper_result_index else None,
        "colab_paper_result_semantic_check_failures": paper_result_index.get("semantic_check_failures") if paper_result_index else None,
        "colab_paper_result_required_group_failures": paper_result_index.get("required_result_group_failures") if paper_result_index else None,
        "colab_paper_result_production_trace_summary": paper_result_index.get("production_trace_summary") if paper_result_index else None,
        "colab_formal_result_gap_report_path": str(workspace / "colab_formal_result_gap_report.json") if formal_result_gap_report else None,
        "colab_formal_result_gap_report": formal_result_gap_report,
        "colab_formal_runbook_path": str(workspace / "colab_formal_runbook.md"),
        "command_plan": plan,
        "input_manifest": input_manifest,
        "provided_result_files_manifest": provided_result_files_manifest,
        "formal_run_checklist": formal_run_checklist,
        "colab_formal_run_checklist_path": str(workspace / "colab_formal_run_checklist.json"),
        "colab_formal_run_checklist_decision": formal_run_checklist.get("overall_decision"),
        "paper_result_evidence_report_path": str(workspace / "paper_result_evidence_report.json") if paper_result_evidence_report else None,
        "paper_result_evidence_decision": paper_result_evidence_report.get("overall_decision") if paper_result_evidence_report else None,
        "paper_result_evidence_target_kind": paper_result_evidence_report.get("target_kind") if paper_result_evidence_report else None,
        "command_results": results,
        "colab_run_bundle_root": str(workspace / "colab_run_bundle"),
        "colab_run_bundle_manifest_path": str(workspace / "colab_run_bundle" / "colab_run_bundle_manifest.json"),
    }
    (workspace / "colab_cold_start_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    bundle_manifest = export_colab_run_bundle(workspace)

    if paper_result_evidence_report is not None:
        from main.analysis.paper_result_evidence import write_paper_result_evidence_report

        # 最终交付给读者的是 Colab bundle, 因此最终 evidence 报告必须以 bundle 为目标。
        paper_result_evidence_report = write_paper_result_evidence_report(
            workspace / "colab_run_bundle",
            workspace / "paper_result_evidence_report.json",
            allow_dry_run=use_dry_run_inputs,
            require_experiment_coverage=require_experiment_coverage,
            require_external_command_results=run_external_plans,
        )
        summary["paper_result_evidence_report_path"] = str(workspace / "paper_result_evidence_report.json")
        summary["paper_result_evidence_decision"] = paper_result_evidence_report.get("overall_decision")
        summary["paper_result_evidence_target_kind"] = paper_result_evidence_report.get("target_kind")
        formal_result_gap_report = write_colab_formal_result_gap_report(workspace)
        summary["colab_formal_result_gap_report_path"] = str(workspace / "colab_formal_result_gap_report.json")
        summary["colab_formal_result_gap_report"] = formal_result_gap_report
        (workspace / "colab_cold_start_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        bundle_manifest = export_colab_run_bundle(workspace)

    summary["colab_run_bundle_file_count"] = bundle_manifest["file_count"]
    summary["colab_run_bundle_validation_decision"] = bundle_manifest.get("validation_decision")
    (workspace / "colab_cold_start_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    final_bundle_manifest = export_colab_run_bundle(workspace)
    summary["colab_run_bundle_file_count"] = final_bundle_manifest["file_count"]
    summary["colab_run_bundle_validation_decision"] = final_bundle_manifest.get("validation_decision")
    (workspace / "colab_cold_start_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    archive_preview_path = Path(build_colab_output_layout(workspace)["archives_root"]) / "ceg_colab_run_bundle.zip"
    archive_preview_path.parent.mkdir(parents=True, exist_ok=True)
    archive_preview_manifest = _build_colab_archive_manifest_base(
        workspace,
        workspace / "colab_run_bundle",
        archive_preview_path,
        allow_dry_run=use_dry_run_inputs,
        require_experiment_coverage=require_experiment_coverage,
        require_external_command_results=run_external_plans,
    )
    (archive_preview_path.parent / "colab_bundle_archive_manifest.json").write_text(
        json.dumps(archive_preview_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["colab_bundle_archive_path"] = str(archive_preview_path)
    summary["colab_bundle_archive_manifest_path"] = str(archive_preview_path.parent / "colab_bundle_archive_manifest.json")
    summary["colab_bundle_archive_name"] = archive_preview_path.name
    (workspace / "colab_cold_start_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    export_colab_run_bundle(workspace)
    acceptance_report = run_colab_acceptance_checks(
        repo_root,
        workspace,
        allow_dry_run=use_dry_run_inputs,
        require_experiment_coverage=require_experiment_coverage,
        require_external_command_results=run_external_plans,
        timeout_seconds=timeout_seconds,
    )
    summary["colab_acceptance_report_path"] = str(workspace / "colab_acceptance_report.json")
    summary["colab_acceptance_decision"] = acceptance_report.get("overall_decision")
    summary["colab_acceptance_report_decisions"] = acceptance_report.get("report_decisions")
    summary["colab_acceptance_blocking_report_decisions"] = acceptance_report.get("blocking_report_decisions")
    summary["colab_acceptance_formal_result_gap_decision"] = acceptance_report.get("formal_result_gap_decision")
    summary["colab_acceptance_formal_result_gap_decision_mode"] = acceptance_report.get("formal_result_gap_decision_mode")
    (workspace / "colab_cold_start_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    accepted_bundle_manifest = export_colab_run_bundle(workspace)
    summary["colab_run_bundle_file_count"] = accepted_bundle_manifest["file_count"]
    summary["colab_run_bundle_validation_decision"] = accepted_bundle_manifest.get("validation_decision")
    (workspace / "colab_cold_start_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    archive_preview_path = Path(build_colab_output_layout(workspace)["archives_root"]) / "ceg_colab_run_bundle.zip"
    archive_preview_path.parent.mkdir(parents=True, exist_ok=True)
    archive_preview_manifest = _build_colab_archive_manifest_base(
        workspace,
        workspace / "colab_run_bundle",
        archive_preview_path,
        allow_dry_run=use_dry_run_inputs,
        require_experiment_coverage=require_experiment_coverage,
        require_external_command_results=run_external_plans,
    )
    (archive_preview_path.parent / "colab_bundle_archive_manifest.json").write_text(
        json.dumps(archive_preview_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["colab_bundle_archive_path"] = str(archive_preview_path)
    summary["colab_bundle_archive_manifest_path"] = str(archive_preview_path.parent / "colab_bundle_archive_manifest.json")
    summary["colab_bundle_archive_name"] = archive_preview_path.name
    (workspace / "colab_cold_start_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    final_bundle_manifest = export_colab_run_bundle(workspace)
    summary["colab_run_bundle_file_count"] = final_bundle_manifest["file_count"]
    summary["colab_run_bundle_validation_decision"] = final_bundle_manifest.get("validation_decision")
    (workspace / "colab_cold_start_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    archive_manifest = create_colab_bundle_archive(
        workspace,
        allow_dry_run=use_dry_run_inputs,
        require_experiment_coverage=require_experiment_coverage,
        require_external_command_results=run_external_plans,
    )
    summary["colab_run_bundle_file_count"] = final_bundle_manifest["file_count"]
    summary["colab_run_bundle_validation_decision"] = final_bundle_manifest.get("validation_decision")
    output_layout_manifest = write_colab_output_layout_manifest(workspace)
    formal_input_contract = write_colab_formal_input_contract(workspace)
    formal_input_templates_manifest = write_colab_formal_input_templates(workspace)
    paper_result_index = write_colab_paper_result_index(workspace)
    formal_result_gap_report = write_colab_formal_result_gap_report(workspace)
    formal_runbook = write_colab_formal_runbook(workspace)
    summary["colab_output_layout_manifest"] = output_layout_manifest
    summary["colab_formal_input_contract_path"] = str(workspace / "colab_formal_input_contract.json")
    summary["colab_formal_input_contract"] = formal_input_contract
    summary["formal_input_templates_manifest_path"] = str(workspace / "inputs" / "formal_input_templates_manifest.json")
    summary["formal_input_templates_manifest"] = formal_input_templates_manifest
    summary["colab_paper_result_index_path"] = str(workspace / "colab_paper_result_index.json")
    summary["colab_paper_result_index"] = paper_result_index
    summary["colab_paper_result_semantic_check_summary"] = paper_result_index.get("semantic_check_summary")
    summary["colab_paper_result_semantic_check_failures"] = paper_result_index.get("semantic_check_failures")
    summary["colab_paper_result_required_group_failures"] = paper_result_index.get("required_result_group_failures")
    summary["colab_paper_result_production_trace_summary"] = paper_result_index.get("production_trace_summary")
    summary["colab_formal_result_gap_report_path"] = str(workspace / "colab_formal_result_gap_report.json")
    summary["colab_formal_result_gap_report"] = formal_result_gap_report
    summary["colab_formal_runbook_path"] = str(workspace / "colab_formal_runbook.md")
    summary["colab_formal_runbook"] = formal_runbook
    summary["colab_bundle_archive_manifest_path"] = archive_manifest["archive_manifest_path"]
    summary["colab_bundle_archive_manifest"] = archive_manifest
    summary["colab_bundle_archive_path"] = archive_manifest["archive_path"]
    summary["colab_bundle_archive_sha256"] = archive_manifest["archive_sha256"]
    summary["colab_bundle_offline_acceptance_command"] = archive_manifest["offline_acceptance_command"]
    (workspace / "colab_cold_start_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
