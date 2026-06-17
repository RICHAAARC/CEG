"""运行 Colab 端到端论文结果包流水线。

该脚本属于实验编排层, 不实现 Stable Diffusion 采样、水印嵌入、攻击、检测或论文指标算法本身。
它只把项目内已经存在的正式入口串联起来, 形成 Colab 中可直接执行的单一入口:

1. 可选调用真实图像生成 backend, 生成 clean / watermarked 图像和 manifests。
2. 验收图像生成产物是否满足后续论文流程契约。
3. 将图像生成产物打包为 zip, 保存到 Google Drive 风格目录。
4. 调用论文结果包流水线, 完成 attack、真实 CEG detection、fixed-FPR 校准、论文结果包导出和归档。
5. 写出统一 manifest, 便于 notebook、审计脚本和人工复现实验读取。

通用工程写法是把 GPU 任务、CPU 统计任务和归档任务拆成可审计子命令, 再由本脚本只做顺序编排。
项目特定写法是默认使用 CEG 内容链水印和 CEG 内容链检测, 不调用 CEG-WM 或其他项目代码。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.core.digest import build_stable_digest


END_TO_END_MANIFEST_NAME = "colab_end_to_end_paper_pipeline_manifest.json"
IMAGE_GENERATION_ARCHIVE_MANIFEST_NAME = "image_generation_outputs_archive_manifest.json"


def _write_json(path: Path, payload: Any) -> None:
    """写出 UTF-8 JSON 文件, 作为后续 Colab 单元和验收脚本的稳定接口。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    """读取 UTF-8 或带 BOM 的 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8-sig"))


def _run_command(command: list[str]) -> dict[str, Any]:
    """执行子命令并返回可写入 manifest 的审计摘要。"""

    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _append_optional(command: list[str], flag: str, value: str | None) -> None:
    """当可选参数存在且非空时追加到命令。"""

    if value is not None and str(value).strip() != "":
        command.extend([flag, str(value)])


def _append_repeated_paths(command: list[str], flag: str, values: list[str]) -> None:
    """把重复路径参数追加到命令, 用于 baseline evidence 等场景。"""

    for value in values:
        if str(value).strip():
            command.extend([flag, str(Path(value).resolve())])


def _fail(output_root: Path, *, failed_step: str, results: dict[str, Any]) -> None:
    """写出失败 manifest, 使 notebook 能够定位失败阶段。"""

    manifest = {
        "artifact_name": END_TO_END_MANIFEST_NAME,
        "overall_decision": "fail",
        "failed_step": failed_step,
        **results,
    }
    _write_json(output_root / END_TO_END_MANIFEST_NAME, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def _archive_image_generation_outputs(image_output_root: Path, drive_root: Path, run_id: str) -> dict[str, Any]:
    """把图像生成产物打包到 Google Drive 风格归档目录。

    该归档只复制已经生成并通过验收的文件, 不修改任何图像内容。zip 中保留相对路径,
    因此后续可以在其他机器上解压并复现 image_pairs 与 manifests。
    """

    archive_root = drive_root / "archives" / "image_generation_outputs"
    archive_root.mkdir(parents=True, exist_ok=True)
    zip_path = archive_root / f"image_generation_outputs_{run_id}.zip"
    manifest_path = archive_root / f"image_generation_outputs_{run_id}_manifest.json"

    archived_files: list[dict[str, Any]] = []
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zip_file:
        for path in sorted(item for item in image_output_root.rglob("*") if item.is_file()):
            relative_path = path.relative_to(image_output_root).as_posix()
            zip_file.write(path, arcname=relative_path)
            archived_files.append(
                {
                    "relative_path": relative_path,
                    "byte_count": path.stat().st_size,
                }
            )

    manifest = {
        "artifact_name": IMAGE_GENERATION_ARCHIVE_MANIFEST_NAME,
        "overall_decision": "pass" if archived_files else "fail",
        "run_id": run_id,
        "image_output_root": str(image_output_root),
        "drive_root": str(drive_root),
        "archive_zip_path": str(zip_path),
        "archive_manifest_path": str(manifest_path),
        "archived_file_count": len(archived_files),
        "archived_files": archived_files,
        "records_digest": build_stable_digest({"run_id": run_id, "archived_files": archived_files}),
    }
    _write_json(manifest_path, manifest)
    return manifest


def _ensure_image_generation_inputs(args: argparse.Namespace, image_output_root: Path) -> tuple[Path, Path]:
    """解析 prompt plan 和 model config, 并在需要运行图像生成时要求它们存在。"""

    prompt_plan = Path(args.prompt_plan).resolve() if args.prompt_plan else args.workspace / "inputs" / "prompts" / "prompt_plan.draft.json"
    model_config = Path(args.model_config).resolve() if args.model_config else args.workspace / "configs" / "model_config.draft.json"
    if args.run_image_generation:
        missing = [str(path) for path in (prompt_plan, model_config) if not path.is_file()]
        if missing:
            raise FileNotFoundError("运行真实图像生成需要存在前序输入文件: " + ", ".join(missing))
    if not args.run_image_generation and not (image_output_root / "image_pairs.json").is_file():
        raise FileNotFoundError(f"未运行图像生成时必须已存在 image_pairs.json: {image_output_root / 'image_pairs.json'}")
    return prompt_plan, model_config


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="运行 CEG Colab 端到端论文结果包流水线。")
    parser.add_argument("--workspace", required=True, type=Path, help="Google Drive 中的 CEG pilot workspace。")
    parser.add_argument("--drive-root", default="/content/drive/MyDrive/CEG", help="Google Drive CEG 根目录。")
    parser.add_argument("--run-id", default=None, help="归档运行 ID, 默认使用 workspace 名称。")
    parser.add_argument("--out", default=None, help="端到端流水线输出目录, 默认写入 workspace/paper_end_to_end_pipeline。")

    parser.add_argument("--run-image-generation", action="store_true", help="运行真实 SD 与 CEG watermark 图像生成 backend。")
    parser.add_argument("--prompt-plan", default=None, help="prompt_plan.draft.json 路径。")
    parser.add_argument("--model-config", default=None, help="model_config.draft.json 路径。")
    parser.add_argument("--image-output-root", default=None, help="图像生成输出根目录, 默认 workspace/inputs/images。")
    parser.add_argument("--sd-model-id", default=None, help="覆盖 model_config 中的 Hugging Face 模型 ID。")
    parser.add_argument("--hf-token-env", default="HF_TOKEN", help="Hugging Face token 环境变量名。")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"], help="真实图像生成设备。")
    parser.add_argument("--allow-cpu-image-generation", action="store_true", help="仅调试使用, 允许图像生成在 CPU 上运行。")
    parser.add_argument(
        "--watermark-backend",
        default="ceg_content_chain_embedding",
        choices=["ceg_content_chain_embedding", "ceg_native_lsb", "external_command"],
        help="图像生成阶段使用的水印 backend。",
    )
    parser.add_argument("--content-lf-strength", type=float, default=3.0)
    parser.add_argument("--content-hf-strength", type=float, default=2.0)
    parser.add_argument("--content-mask-threshold-quantile", type=float, default=0.80)
    parser.add_argument("--watermark-command-json-file", default=None, help="external_command watermark 模板 JSON 文件。")

    parser.add_argument("--attack-families", default="brightness_contrast,gaussian_noise,rotate,resize,jpeg")
    parser.add_argument("--target-fpr", type=float, default=0.01)
    parser.add_argument("--profile", default="paper_main_probe")
    parser.add_argument("--allow-incomplete-package", action="store_true")
    parser.add_argument("--allow-invalid-archive", action="store_true")
    parser.add_argument("--attestation-key-env", default=None)
    parser.add_argument("--attestation-key-id", default=None)
    parser.add_argument("--affine-rotation-degrees", default="-6,-3,0,3,6")
    parser.add_argument("--affine-scales", default="0.95,1.0,1.05")
    parser.add_argument("--perspective-offsets", default="0.0")
    parser.add_argument("--feature-homography-enabled", default="true")
    parser.add_argument("--local-deformation-enabled", default="true")
    parser.add_argument("--baseline-plan", default=None)
    parser.add_argument("--baseline-observations", default=None)
    parser.add_argument("--baseline-execution-manifest", default=None)
    parser.add_argument("--baseline-formal-result-claim", action="store_true")
    parser.add_argument("--baseline-evidence-path", action="append", default=[])
    parser.add_argument("--refresh-stage-summary", action="store_true")
    return parser


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    args.workspace = args.workspace.resolve()
    workspace = args.workspace
    drive_root = Path(args.drive_root).resolve()
    run_id = args.run_id or workspace.name
    output_root = Path(args.out).resolve() if args.out else workspace / "paper_end_to_end_pipeline"
    image_output_root = Path(args.image_output_root).resolve() if args.image_output_root else workspace / "inputs" / "images"
    output_root.mkdir(parents=True, exist_ok=True)

    prompt_plan, model_config = _ensure_image_generation_inputs(args, image_output_root)

    image_generation_result = None
    if args.run_image_generation:
        image_generation_command = [
            sys.executable,
            str(ROOT / "scripts" / "run_pilot_real_image_generation_backend.py"),
            "--prompt-plan",
            str(prompt_plan),
            "--out",
            str(image_output_root),
            "--model-config",
            str(model_config),
            "--hf-token-env",
            str(args.hf_token_env),
            "--device",
            str(args.device),
            "--watermark-backend",
            str(args.watermark_backend),
            "--content-lf-strength",
            str(args.content_lf_strength),
            "--content-hf-strength",
            str(args.content_hf_strength),
            "--content-mask-threshold-quantile",
            str(args.content_mask_threshold_quantile),
            "--require-pass",
        ]
        _append_optional(image_generation_command, "--sd-model-id", args.sd_model_id)
        _append_optional(image_generation_command, "--watermark-command-json-file", args.watermark_command_json_file)
        if args.allow_cpu_image_generation:
            image_generation_command.append("--allow-cpu")
        image_generation_result = _run_command(image_generation_command)
        if image_generation_result["return_code"] != 0:
            _fail(output_root, failed_step="run_pilot_real_image_generation_backend", results={"image_generation_result": image_generation_result})
            raise SystemExit(int(image_generation_result["return_code"]))

    image_acceptance_report = image_output_root / "pilot_image_generation_output_acceptance_report.json"
    image_acceptance_command = [
        sys.executable,
        str(ROOT / "scripts" / "validate_pilot_image_generation_outputs.py"),
        "--output-root",
        str(image_output_root),
        "--out",
        str(image_acceptance_report),
        "--require-pass",
    ]
    image_acceptance_result = _run_command(image_acceptance_command)
    if image_acceptance_result["return_code"] != 0:
        _fail(
            output_root,
            failed_step="validate_pilot_image_generation_outputs",
            results={
                "image_generation_result": image_generation_result,
                "image_acceptance_result": image_acceptance_result,
            },
        )
        raise SystemExit(int(image_acceptance_result["return_code"]))

    image_archive_manifest = _archive_image_generation_outputs(image_output_root, drive_root, run_id)
    if image_archive_manifest["overall_decision"] != "pass":
        _fail(
            output_root,
            failed_step="archive_image_generation_outputs",
            results={
                "image_generation_result": image_generation_result,
                "image_acceptance_result": image_acceptance_result,
                "image_archive_manifest": image_archive_manifest,
            },
        )
        raise SystemExit(1)

    paper_pipeline_root = output_root / "paper_results_pipeline"
    paper_pipeline_command = [
        sys.executable,
        str(ROOT / "scripts" / "run_colab_paper_results_pipeline.py"),
        "--workspace",
        str(workspace),
        "--drive-root",
        str(drive_root),
        "--run-id",
        str(run_id),
        "--image-pairs",
        str(image_output_root / "image_pairs.json"),
        "--out",
        str(paper_pipeline_root),
        "--attack-families",
        str(args.attack_families),
        "--target-fpr",
        str(args.target_fpr),
        "--profile",
        str(args.profile),
        "--affine-rotation-degrees",
        str(args.affine_rotation_degrees),
        "--affine-scales",
        str(args.affine_scales),
        "--perspective-offsets",
        str(args.perspective_offsets),
        "--feature-homography-enabled",
        str(args.feature_homography_enabled),
        "--local-deformation-enabled",
        str(args.local_deformation_enabled),
    ]
    _append_optional(paper_pipeline_command, "--attestation-key-env", args.attestation_key_env)
    _append_optional(paper_pipeline_command, "--attestation-key-id", args.attestation_key_id)
    _append_optional(paper_pipeline_command, "--baseline-plan", args.baseline_plan)
    _append_optional(paper_pipeline_command, "--baseline-observations", args.baseline_observations)
    _append_optional(paper_pipeline_command, "--baseline-execution-manifest", args.baseline_execution_manifest)
    _append_repeated_paths(paper_pipeline_command, "--baseline-evidence-path", args.baseline_evidence_path)
    if args.baseline_formal_result_claim:
        paper_pipeline_command.append("--baseline-formal-result-claim")
    if args.allow_incomplete_package:
        paper_pipeline_command.append("--allow-incomplete-package")
    if args.allow_invalid_archive:
        paper_pipeline_command.append("--allow-invalid-archive")
    if args.refresh_stage_summary:
        paper_pipeline_command.append("--refresh-stage-summary")

    paper_pipeline_result = _run_command(paper_pipeline_command)
    if paper_pipeline_result["return_code"] != 0:
        _fail(
            output_root,
            failed_step="run_colab_paper_results_pipeline",
            results={
                "image_generation_result": image_generation_result,
                "image_acceptance_result": image_acceptance_result,
                "image_archive_manifest": image_archive_manifest,
                "paper_pipeline_result": paper_pipeline_result,
            },
        )
        raise SystemExit(int(paper_pipeline_result["return_code"]))

    paper_pipeline_manifest_path = paper_pipeline_root / "colab_paper_results_pipeline_manifest.json"
    paper_pipeline_manifest = _read_json(paper_pipeline_manifest_path)
    manifest = {
        "artifact_name": END_TO_END_MANIFEST_NAME,
        "overall_decision": "pass",
        "workspace": str(workspace),
        "drive_root": str(drive_root),
        "run_id": run_id,
        "output_root": str(output_root),
        "run_image_generation": bool(args.run_image_generation),
        "prompt_plan": str(prompt_plan),
        "model_config": str(model_config),
        "image_output_root": str(image_output_root),
        "image_pairs": str(image_output_root / "image_pairs.json"),
        "image_acceptance_report": str(image_acceptance_report),
        "image_generation_archive_zip": image_archive_manifest["archive_zip_path"],
        "image_generation_archive_manifest": image_archive_manifest["archive_manifest_path"],
        "paper_pipeline_root": str(paper_pipeline_root),
        "paper_pipeline_manifest": str(paper_pipeline_manifest_path),
        "paper_results_package_root": paper_pipeline_manifest.get("paper_results_package_root"),
        "image_generation_result": image_generation_result,
        "image_acceptance_result": image_acceptance_result,
        "image_archive_manifest": image_archive_manifest,
        "paper_pipeline_result": paper_pipeline_result,
        "paper_pipeline_summary": {
            "attack_root": paper_pipeline_manifest.get("attack_root"),
            "detection_root": paper_pipeline_manifest.get("detection_root"),
            "baseline_root": paper_pipeline_manifest.get("baseline_root"),
            "package_run_root": paper_pipeline_manifest.get("package_run_root"),
        },
        "execution_digest": build_stable_digest(
            {
                "run_id": run_id,
                "image_generation_result": image_generation_result,
                "image_acceptance_command": image_acceptance_command,
                "image_archive_digest": image_archive_manifest["records_digest"],
                "paper_pipeline_command": paper_pipeline_command,
            }
        ),
    }
    _write_json(output_root / END_TO_END_MANIFEST_NAME, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
