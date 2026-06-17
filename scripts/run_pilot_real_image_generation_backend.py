"""运行真实图像生成 backend, 产出 clean / watermarked 图像与 manifests。

该脚本是 Colab 图像生成流程的正式仓库入口。它直接调用 Hugging Face diffusers
加载 Stable Diffusion 或兼容的 text-to-image pipeline 生成 clean 图像, 然后使用 CEG 项目内的
原生图像水印原语生成 watermarked 图像。

通用工程写法是: 把 GPU 模型采样、水印命令调用、文件契约写出和验收前置检查拆成
清晰的函数, 使 Notebook 只负责调度。项目特定写法是: 输出固定遵守 CEG 论文流程要求
的 prompt_plan.json、clean / watermarked 目录、image_pairs.json 和 image manifests。

重要边界: 本脚本不会用复制、mock 或可见叠字伪造水印图像。默认水印后端完全位于 CEG
仓库内, 不调用其他项目。若切换到 external_command, 外部命令也必须写出与 clean 不同的图像文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_image_generation_output_acceptance import (  # noqa: E402
    REPORT_NAME as ACCEPTANCE_REPORT_NAME,
    write_pilot_image_generation_output_acceptance_report,
)
from main.analysis.image_examples import build_image_generation_manifest, build_image_pair_manifest  # noqa: E402
from main.core.digest import build_stable_digest  # noqa: E402
from main.watermarking.native_lsb import embed_native_lsb_watermark  # noqa: E402

BACKEND_MANIFEST_NAME = "real_image_generation_backend_manifest.json"
PROMPT_PLAN_NAME = "prompt_plan.json"
IMAGE_PAIRS_NAME = "image_pairs.json"


def _write_json(path: Path, payload: Any) -> None:
    """写出 UTF-8 JSON 文件, 供 Colab、验收脚本和论文结果包复用。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    """读取 UTF-8 或带 BOM 的 JSON 文件。"""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_mapping_config(path: Path) -> dict[str, Any]:
    """读取 JSON/YAML 配置文件, 缺失时返回空映射。

    Colab 工作区中的 model_config.draft.json 通常是 JSON。这里把 YAML 作为可选能力,
    便于用户把等价模型配置迁移到 CEG 内部, 没有安装 PyYAML 时会给出明确错误。
    """
    if not path.is_file():
        return {}
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - 由 Colab 环境依赖决定
            raise RuntimeError("读取 YAML model config 需要安装 PyYAML。") from exc
        loaded = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    else:
        loaded = _read_json(path)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"配置文件必须是 object: {path}")
    return dict(loaded)


def _as_text(value: Any, default: str = "") -> str:
    """把可选字段转换为去空白字符串。"""
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _safe_file_stem(value: str, fallback: str) -> str:
    """把 image_id 转换为安全文件名主干, 避免路径穿越和平台差异。"""
    candidate = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value).strip("._")
    return candidate or fallback


def _file_sha256(path: Path) -> str:
    """计算文件 SHA256, 用于确认 watermarked 不是 clean 的直接复制。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_prompt_rows(path: Path) -> list[dict[str, Any]]:
    """读取 prompt plan, 支持 list 或带 prompts/items/records 字段的对象。"""
    payload = _read_json(path)
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = None
        for field_name in ("prompts", "items", "records", "prompt_rows"):
            candidate = payload.get(field_name)
            if isinstance(candidate, list):
                rows = candidate
                break
        if rows is None:
            raise ValueError("prompt plan object 必须包含 prompts、items、records 或 prompt_rows 列表字段。")
    else:
        raise ValueError("prompt plan 必须是 list 或 object。")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"prompt plan 第 {index} 行不是 object。")
        prompt_text = _as_text(row.get("prompt_text") or row.get("prompt") or row.get("text"))
        if not prompt_text:
            raise ValueError(f"prompt plan 第 {index} 行缺少 prompt_text/prompt/text。")
        normalized.append(dict(row))
    if not normalized:
        raise ValueError("prompt plan 不能为空。")
    return normalized


def _resolve_int(row: Mapping[str, Any], config: Mapping[str, Any], field_names: Sequence[str], default: int) -> int:
    """按 row 优先、config 次之的顺序解析整数参数。"""
    for source in (row, config):
        for field_name in field_names:
            value = source.get(field_name)
            if value is not None and value != "":
                return int(value)
    return default


def _resolve_float(row: Mapping[str, Any], config: Mapping[str, Any], field_names: Sequence[str], default: float) -> float:
    """按 row 优先、config 次之的顺序解析浮点参数。"""
    for source in (row, config):
        for field_name in field_names:
            value = source.get(field_name)
            if value is not None and value != "":
                return float(value)
    return default


def _resolve_model_id(args: argparse.Namespace, config: Mapping[str, Any]) -> str:
    """解析 Hugging Face 模型 ID。"""
    candidates = [args.sd_model_id, config.get("model_id"), config.get("sd_model_id")]
    model_node = config.get("model")
    if isinstance(model_node, dict):
        candidates.extend([model_node.get("model_id"), model_node.get("id")])
    for value in candidates:
        text = _as_text(value)
        if text and text not in {"<absent>", "none", "null"}:
            return text
    return "stabilityai/stable-diffusion-3.5-medium"


def _resolve_dtype_name(args: argparse.Namespace, config: Mapping[str, Any]) -> str:
    """解析 torch dtype 名称。"""
    if args.torch_dtype:
        return args.torch_dtype
    model_node = config.get("model")
    if isinstance(model_node, dict):
        dtype = _as_text(model_node.get("dtype"))
        if dtype:
            return dtype
    return _as_text(config.get("torch_dtype"), "float16")


def _torch_dtype(dtype_name: str, torch_module: Any) -> Any:
    """把配置中的 dtype 字符串转换为 torch dtype。"""
    normalized = dtype_name.lower().replace("torch.", "")
    mapping = {
        "float16": torch_module.float16,
        "fp16": torch_module.float16,
        "bfloat16": torch_module.bfloat16,
        "bf16": torch_module.bfloat16,
        "float32": torch_module.float32,
        "fp32": torch_module.float32,
    }
    if normalized not in mapping:
        raise ValueError(f"不支持的 torch dtype: {dtype_name}")
    return mapping[normalized]


def _build_pipeline(args: argparse.Namespace, config: Mapping[str, Any]) -> Any:
    """加载 diffusers text-to-image pipeline。

    依赖采用运行时导入, 使本地 CPU 单元测试不需要安装 diffusers 或 torch。
    """
    try:
        import torch  # type: ignore
        from diffusers import AutoPipelineForText2Image  # type: ignore
    except ImportError as exc:  # pragma: no cover - 默认测试不安装 GPU 依赖
        raise RuntimeError(
            "真实图像生成需要安装 torch、diffusers、transformers、accelerate 和 Pillow。"
        ) from exc

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu" and not args.allow_cpu:
        raise RuntimeError("当前未检测到 CUDA。正式图像生成必须使用 GPU, 如仅调试请显式传入 --allow-cpu。")

    model_id = _resolve_model_id(args, config)
    dtype = _torch_dtype(_resolve_dtype_name(args, config), torch)
    token = os.environ.get(args.hf_token_env) if args.hf_token_env else None
    revision = _as_text(args.revision or config.get("revision") or config.get("hf_revision")) or None
    cache_dir = _as_text(args.cache_dir or config.get("cache_dir")) or None

    pipeline = AutoPipelineForText2Image.from_pretrained(
        model_id,
        torch_dtype=dtype,
        token=token,
        revision=revision,
        cache_dir=cache_dir,
    )
    pipeline = pipeline.to(device)
    if hasattr(pipeline, "set_progress_bar_config"):
        pipeline.set_progress_bar_config(disable=bool(args.disable_progress_bar))
    return pipeline


def _generate_clean_image(
    pipeline: Any,
    row: Mapping[str, Any],
    config: Mapping[str, Any],
    clean_path: Path,
    *,
    index: int,
    device: str,
) -> dict[str, Any]:
    """调用真实 SD pipeline 生成单张 clean 图像。"""
    try:
        import torch  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("真实图像生成需要 torch。") from exc

    prompt = _as_text(row.get("prompt_text") or row.get("prompt") or row.get("text"))
    negative_prompt = _as_text(row.get("negative_prompt") or config.get("negative_prompt")) or None
    seed = _resolve_int(row, config, ("seed", "random_seed"), index)
    steps = _resolve_int(row, config, ("num_inference_steps", "inference_num_steps"), 28)
    guidance = _resolve_float(row, config, ("guidance_scale", "inference_guidance_scale"), 7.0)
    height = _resolve_int(row, config, ("height", "inference_height"), 512)
    width = _resolve_int(row, config, ("width", "inference_width"), 512)
    generator_device = "cuda" if device == "cuda" else "cpu"
    generator = torch.Generator(device=generator_device).manual_seed(seed)
    result = pipeline(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=steps,
        guidance_scale=guidance,
        height=height,
        width=width,
        generator=generator,
    )
    images = getattr(result, "images", None)
    if not images:
        raise RuntimeError("diffusers pipeline 未返回 images。")
    clean_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(clean_path)
    return {
        "prompt_text": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "height": height,
        "width": width,
    }


def _load_command_template(path: Path | None, inline_json: str | None) -> list[str] | None:
    """读取外部 watermark 命令模板。"""
    payload: Any | None = None
    if inline_json:
        payload = json.loads(inline_json)
    elif path is not None:
        if not path.is_file():
            raise FileNotFoundError(f"watermark command JSON 文件不存在: {path}")
        payload = _read_json(path)
    if payload is None:
        return None
    if isinstance(payload, dict):
        payload = payload.get("watermark_command") or payload.get("external_command")
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError("watermark command 必须是 list[str], 或包含 watermark_command/external_command 字段的 object。")
    if not payload:
        raise ValueError("watermark command 不能为空。")
    return list(payload)


def _render_command_template(template: Iterable[str], values: Mapping[str, str]) -> list[str]:
    """渲染 argv 模板占位符, 不经过 shell 拼接。"""
    rendered: list[str] = []
    for item in template:
        lowered = item.lower()
        if "replace_with" in lowered or "placeholder" in lowered:
            raise ValueError(f"watermark command 仍包含 placeholder: {item}")
        rendered.append(item.format(**values))
    return rendered


def _run_external_watermark_command(
    template: Sequence[str],
    *,
    clean_path: Path,
    watermarked_path: Path,
    metadata_path: Path,
    row: Mapping[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    """调用用户配置的真实外部 watermark 命令。"""
    values = {
        "clean_image": str(clean_path),
        "watermarked_image": str(watermarked_path),
        "metadata_json": str(metadata_path),
        "prompt": _as_text(row.get("prompt_text") or row.get("prompt") or row.get("text")),
        "image_id": _as_text(row.get("image_id") or row.get("event_id")),
        "prompt_id": _as_text(row.get("prompt_id")),
        "seed": _as_text(row.get("seed")),
    }
    command = _render_command_template(template, values)
    completed = subprocess.run(command, check=False, text=True, capture_output=True, timeout=timeout_seconds)
    return {
        "watermark_backend": "external_command",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "command": command,
    }


def _run_native_ceg_watermark(
    *,
    clean_path: Path,
    watermarked_path: Path,
    row: Mapping[str, Any],
    generation_meta: Mapping[str, Any],
    bit_count: int,
) -> dict[str, Any]:
    """调用 CEG 内部 pilot 水印模块生成 watermarked 图像。"""
    return embed_native_lsb_watermark(
        clean_path=clean_path,
        watermarked_path=watermarked_path,
        row=row,
        generation_meta=generation_meta,
        bit_count=bit_count,
    ).to_report()


def _write_watermark_metadata(path: Path, row: Mapping[str, Any], generation_meta: Mapping[str, Any]) -> None:
    """为外部 watermark backend 写出单图元数据, 便于真实命令复用。"""
    payload = {
        "image_id": _as_text(row.get("image_id") or row.get("event_id")),
        "prompt_id": _as_text(row.get("prompt_id")),
        "prompt_text": generation_meta.get("prompt_text"),
        "seed": generation_meta.get("seed"),
        "generation_meta": dict(generation_meta),
    }
    _write_json(path, payload)


def _assert_valid_watermarked(clean_path: Path, watermarked_path: Path) -> tuple[str, str]:
    """确认 watermarked 图像存在, 且不是 clean 文件的字节级复制。"""
    if not watermarked_path.is_file():
        raise FileNotFoundError(f"watermarked 图像未写出: {watermarked_path}")
    clean_digest = _file_sha256(clean_path)
    watermarked_digest = _file_sha256(watermarked_path)
    if clean_digest == watermarked_digest:
        raise RuntimeError("watermarked 图像与 clean 图像字节完全一致, 拒绝把复制文件当作真实水印输出。")
    return clean_digest, watermarked_digest


def _build_image_pair_row(
    row: Mapping[str, Any],
    generation_meta: Mapping[str, Any],
    *,
    image_id: str,
    prompt_id: str,
    clean_path: Path,
    watermarked_path: Path,
    clean_sha256: str,
    watermarked_sha256: str,
    model_id: str,
) -> dict[str, Any]:
    """把 prompt row 和图像路径合并为 image_pairs.json 的一行。"""
    return {
        "image_id": image_id,
        "event_id": _as_text(row.get("event_id"), image_id),
        "prompt_id": prompt_id,
        "prompt_text": generation_meta["prompt_text"],
        "negative_prompt": generation_meta.get("negative_prompt"),
        "seed": generation_meta["seed"],
        "model_id": _as_text(row.get("model_id"), model_id),
        "scheduler": _as_text(row.get("scheduler"), "diffusers_default"),
        "num_inference_steps": generation_meta["num_inference_steps"],
        "guidance_scale": generation_meta["guidance_scale"],
        "height": generation_meta["height"],
        "width": generation_meta["width"],
        "method_name": _as_text(row.get("method_name"), "ceg"),
        "split": _as_text(row.get("split"), "test"),
        "sample_role": _as_text(row.get("sample_role"), "unknown_role"),
        "attack_family": _as_text(row.get("attack_family"), "clean"),
        "attack_condition": _as_text(row.get("attack_condition"), "clean_none"),
        "clean_image_path": str(clean_path),
        "watermarked_image_path": str(watermarked_path),
        "reference_path": str(clean_path),
        "watermarked_path": str(watermarked_path),
        "clean_image_sha256": clean_sha256,
        "watermarked_image_sha256": watermarked_sha256,
    }


def run_backend(args: argparse.Namespace) -> dict[str, Any]:
    """执行完整真实图像生成流程并返回 backend manifest。"""
    prompt_plan_path = Path(args.prompt_plan)
    output_root = Path(args.out)
    model_config_path = Path(args.model_config)
    config = _read_mapping_config(model_config_path)
    prompt_rows = _load_prompt_rows(prompt_plan_path)
    output_root.mkdir(parents=True, exist_ok=True)
    clean_root = output_root / "clean"
    watermarked_root = output_root / "watermarked"
    metadata_root = output_root / "watermark_metadata"
    manifest_root = output_root / "image_manifests"
    for directory in (clean_root, watermarked_root, metadata_root, manifest_root):
        directory.mkdir(parents=True, exist_ok=True)

    command_template = _load_command_template(
        Path(args.watermark_command_json_file) if args.watermark_command_json_file else None,
        args.watermark_command_json,
    )
    if args.watermark_backend == "external_command" and command_template is None:
        raise ValueError("watermark_backend=external_command 时必须提供 --watermark-command-json 或 --watermark-command-json-file。")

    pipeline = _build_pipeline(args, config)
    device = args.device
    if device == "auto":
        try:
            import torch  # type: ignore

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    model_id = _resolve_model_id(args, config)
    image_pairs: list[dict[str, Any]] = []
    watermark_runs: list[dict[str, Any]] = []

    for index, row in enumerate(prompt_rows, start=1):
        image_id = _as_text(row.get("image_id") or row.get("event_id"), f"image_{index:04d}")
        prompt_id = _as_text(row.get("prompt_id"), f"prompt_{index:04d}")
        file_stem = _safe_file_stem(image_id, f"image_{index:04d}")
        clean_path = clean_root / f"{file_stem}.png"
        watermarked_path = watermarked_root / f"{file_stem}.png"
        generation_meta = _generate_clean_image(pipeline, row, config, clean_path, index=index, device=device)
        metadata_path = metadata_root / f"{file_stem}.json"
        _write_watermark_metadata(metadata_path, row, generation_meta)

        if args.watermark_backend == "ceg_native_lsb":
            watermark_report = _run_native_ceg_watermark(
                clean_path=clean_path,
                watermarked_path=watermarked_path,
                row=row,
                generation_meta=generation_meta,
                bit_count=args.native_watermark_bits,
            )
        elif args.watermark_backend == "external_command":
            assert command_template is not None
            watermark_report = _run_external_watermark_command(
                command_template,
                clean_path=clean_path,
                watermarked_path=watermarked_path,
                metadata_path=metadata_path,
                row=row,
                timeout_seconds=args.watermark_timeout_seconds,
            )
        else:  # pragma: no cover - argparse choices 已阻断
            raise ValueError(f"不支持的 watermark backend: {args.watermark_backend}")

        watermark_runs.append(watermark_report)
        if int(watermark_report.get("returncode", 1)) != 0:
            raise RuntimeError(f"watermark backend 执行失败: image_id={image_id}")
        clean_sha256, watermarked_sha256 = _assert_valid_watermarked(clean_path, watermarked_path)
        image_pairs.append(
            _build_image_pair_row(
                row,
                generation_meta,
                image_id=image_id,
                prompt_id=prompt_id,
                clean_path=clean_path,
                watermarked_path=watermarked_path,
                clean_sha256=clean_sha256,
                watermarked_sha256=watermarked_sha256,
                model_id=model_id,
            )
        )

    _write_json(output_root / PROMPT_PLAN_NAME, prompt_rows)
    _write_json(output_root / IMAGE_PAIRS_NAME, image_pairs)
    _write_json(manifest_root / "image_generation_manifest.json", build_image_generation_manifest(image_pairs))
    _write_json(manifest_root / "image_pair_manifest.json", build_image_pair_manifest(image_pairs))
    backend_manifest = {
        "artifact_name": BACKEND_MANIFEST_NAME,
        "backend_role": "real_sd_and_real_watermark_generation",
        "formal_result_claim": True,
        "prompt_plan_source_path": str(prompt_plan_path),
        "model_config_path": str(model_config_path),
        "output_root": str(output_root),
        "model_id": model_id,
        "hf_token_env": args.hf_token_env,
        "hf_token_written_to_disk": False,
        "watermark_backend": args.watermark_backend,
        "prompt_count": len(prompt_rows),
        "image_pair_count": len(image_pairs),
        "image_pairs_path": str(output_root / IMAGE_PAIRS_NAME),
        "image_generation_manifest_path": str(manifest_root / "image_generation_manifest.json"),
        "image_pair_manifest_path": str(manifest_root / "image_pair_manifest.json"),
        "watermark_run_count": len(watermark_runs),
        "watermark_runs": watermark_runs,
        "records_digest": build_stable_digest({"prompt_rows": prompt_rows, "image_pairs": image_pairs}),
    }
    _write_json(output_root / BACKEND_MANIFEST_NAME, backend_manifest)
    acceptance = write_pilot_image_generation_output_acceptance_report(output_root, output_root / ACCEPTANCE_REPORT_NAME)
    backend_manifest["acceptance_overall_decision"] = acceptance["overall_decision"]
    _write_json(output_root / BACKEND_MANIFEST_NAME, backend_manifest)
    return backend_manifest


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(description="调用真实 SD 与真实 watermark backend 生成 CEG 图像产物。")
    parser.add_argument("--prompt-plan", required=True, help="prompt_plan.draft.json 或等价 prompt plan 路径。")
    parser.add_argument("--out", required=True, help="图像输出根目录, 通常是工作区 inputs/images。")
    parser.add_argument("--model-config", required=True, help="模型配置 JSON/YAML 路径。")
    parser.add_argument("--sd-model-id", default=None, help="覆盖 model_config 中的 Hugging Face 模型 ID。")
    parser.add_argument("--revision", default=None, help="可选 Hugging Face revision。")
    parser.add_argument("--cache-dir", default=None, help="可选 Hugging Face cache 目录。")
    parser.add_argument("--hf-token-env", default="HF_TOKEN", help="读取 Hugging Face token 的环境变量名。")
    parser.add_argument("--torch-dtype", default=None, help="float16、bfloat16 或 float32。")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"], help="运行设备。正式运行建议 auto/cuda。")
    parser.add_argument("--allow-cpu", action="store_true", help="仅调试使用: 允许无 CUDA 时在 CPU 运行。")
    parser.add_argument("--disable-progress-bar", action="store_true", help="关闭 diffusers 进度条, 减少 notebook 日志噪声。")
    parser.add_argument(
        "--watermark-backend",
        default="ceg_native_lsb",
        choices=["ceg_native_lsb", "external_command"],
        help="真实水印 backend。默认使用 CEG 仓库内原生 LSB 图像水印原语。",
    )
    parser.add_argument("--native-watermark-bits", type=int, default=1024, help="CEG 原生水印嵌入 bit 数。")
    parser.add_argument("--watermark-command-json", default=None, help="外部 watermark argv 模板 JSON list[str]。")
    parser.add_argument("--watermark-command-json-file", default=None, help="外部 watermark argv 模板 JSON 文件。")
    parser.add_argument("--watermark-timeout-seconds", type=int, default=3600, help="单张图像 watermark 命令超时时间。")
    parser.add_argument("--require-pass", action="store_true", help="验收未通过时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    try:
        manifest = run_backend(args)
        print(
            json.dumps(
                {
                    "artifact_name": manifest["artifact_name"],
                    "output_root": manifest["output_root"],
                    "image_pair_count": manifest["image_pair_count"],
                    "acceptance_overall_decision": manifest["acceptance_overall_decision"],
                    "backend_manifest_path": str(Path(args.out) / BACKEND_MANIFEST_NAME),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if args.require_pass and manifest["acceptance_overall_decision"] != "pass":
            raise SystemExit(1)
    except Exception as exc:
        failure_report = {
            "artifact_name": BACKEND_MANIFEST_NAME,
            "overall_decision": "fail",
            "failure_type": type(exc).__name__,
            "failure_message": str(exc),
            "output_root": str(Path(args.out)),
        }
        _write_json(Path(args.out) / BACKEND_MANIFEST_NAME, failure_report)
        print(json.dumps(failure_report, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1 if args.require_pass else 2)


if __name__ == "__main__":
    main()
