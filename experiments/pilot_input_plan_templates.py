"""为真实 pilot 工作区生成最小输入计划模板.

这些模板只用于人工或外部 runner 填充真实输入, 不包含正式实验结果.
所有需要替换的字段均使用 `_placeholder` 后缀, 以符合项目占位字段治理规则.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PLAN_TEMPLATE_MANIFEST_NAME = "pilot_input_plan_template_manifest.json"


def build_prompt_plan_template(run_id: str) -> dict[str, Any]:
    """构造 prompt 计划模板."""
    return {
        "artifact_name": "prompt_plan.json",
        "manifest_status": "draft_requires_real_prompts",
        "run_id": run_id,
        "prompts": [
            {
                "prompt_id": "prompt_0001",
                "prompt_text_placeholder": "replace_with_real_prompt_text",
                "prompt_family_placeholder": "replace_with_prompt_family",
                "license_note_placeholder": "replace_with_prompt_source_or_license_note",
            }
        ],
    }


def build_split_plan_template(run_id: str) -> dict[str, Any]:
    """构造 calibration / test split 计划模板."""
    return {
        "artifact_name": "split_plan.json",
        "manifest_status": "draft_requires_real_split_assignment",
        "run_id": run_id,
        "split_policy": "calibration_clean_negative_for_threshold_test_split_for_evaluation",
        "assignments": [
            {
                "prompt_id": "prompt_0001",
                "split_placeholder": "calibration_or_test",
                "sample_role_placeholder": "positive_source_or_clean_negative",
            }
        ],
    }


def build_seed_plan_template(run_id: str) -> dict[str, Any]:
    """构造 seed 计划模板."""
    return {
        "artifact_name": "seed_plan.json",
        "manifest_status": "draft_requires_real_seed_values",
        "run_id": run_id,
        "seeds": [
            {
                "prompt_id": "prompt_0001",
                "seed_placeholder": "replace_with_integer_seed",
                "seed_role_placeholder": "primary_or_replicate",
            }
        ],
    }


def build_model_config_template(run_id: str) -> dict[str, Any]:
    """构造真实图像生成模型配置模板."""
    return {
        "artifact_name": "model_config.json",
        "manifest_status": "draft_requires_real_generation_backend",
        "run_id": run_id,
        "backend_type_placeholder": "diffusers_or_external_command",
        "model_id_placeholder": "replace_with_sd_model_id_or_local_path",
        "scheduler_placeholder": "replace_with_scheduler_name",
        "num_inference_steps_placeholder": "replace_with_step_count",
        "guidance_scale_placeholder": "replace_with_guidance_scale",
        "image_size_placeholder": "replace_with_width_height",
        "requires_huggingface_token_placeholder": "true_or_false",
    }


def build_watermark_config_template(run_id: str) -> dict[str, Any]:
    """构造水印方法配置模板."""
    return {
        "artifact_name": "watermark_config.json",
        "manifest_status": "draft_requires_real_watermark_backend",
        "run_id": run_id,
        "watermark_method_placeholder": "replace_with_ceg_watermark_method_or_external_method",
        "payload_bits_placeholder": "replace_with_payload_bits_or_payload_spec",
        "watermark_strength_placeholder": "replace_with_strength_or_embedding_params",
        "backend_command_placeholder": "replace_with_command_if_external_backend_is_used",
        "evidence_path_placeholder": "replace_with_backend_log_or_run_manifest_path",
    }


def scaffold_pilot_input_plan_templates(*, workspace_root: str | Path, run_id: str) -> dict[str, Any]:
    """在真实 pilot 工作区写出输入计划模板."""
    root = Path(workspace_root)
    prompt_dir = root / "inputs" / "prompts"
    config_dir = root / "configs"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    templates = {
        "prompt_plan": (prompt_dir / "prompt_plan.draft.json", build_prompt_plan_template(run_id)),
        "split_plan": (prompt_dir / "split_plan.draft.json", build_split_plan_template(run_id)),
        "seed_plan": (prompt_dir / "seed_plan.draft.json", build_seed_plan_template(run_id)),
        "model_config": (config_dir / "model_config.draft.json", build_model_config_template(run_id)),
        "watermark_config": (
            config_dir / "watermark_config.draft.json",
            build_watermark_config_template(run_id),
        ),
    }

    written_files: dict[str, str] = {}
    for key, (path, payload) in templates.items():
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written_files[key] = str(path)

    manifest = {
        "artifact_name": PLAN_TEMPLATE_MANIFEST_NAME,
        "run_id": run_id,
        "workspace_root": str(root),
        "template_status": "draft_requires_real_inputs",
        "written_files": written_files,
        "next_action": (
            "用真实 prompt、split、seed、model 和 watermark 参数替换 *_placeholder 字段, "
            "然后生成真实 image_pairs.json."
        ),
    }
    manifest_path = root / PLAN_TEMPLATE_MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
