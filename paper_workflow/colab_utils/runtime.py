"""Colab 冷启动运行与 Drive 交接工具。

该模块只服务 `paper_workflow` 中的 Notebook 编排, 不实现 CEG 主方法、
水印算法、检测算法或论文指标。它的通用价值在于把独立 Colab 会话中的
仓库拉取、依赖安装、模型缓存、InSPyReNet 权重准备、阶段归档和阶段恢复
统一为可审计函数, 避免每个 Notebook 手写一套不一致的运行逻辑。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import urllib.request
from typing import Any, Iterable, Mapping
from zipfile import ZIP_DEFLATED, ZipFile


DEFAULT_REPO_URL = "https://github.com/RICHAAARC/CEG.git"
DEFAULT_REPO_ROOT = Path("/content/CEG")
DEFAULT_DRIVE_ROOT = Path("/content/drive/MyDrive/CEG")
DEFAULT_LOCAL_RUNTIME_ROOT = Path("/content/ceg_runtime")
DEFAULT_INSPYRENET_WEIGHT_URL = "https://huggingface.co/plemeri/InSPyReNet/resolve/main/ckpt_base.pth"
DEFAULT_INSPYRENET_WEIGHT_DRIVE_PATH = Path("/content/drive/MyDrive/Models/inspyrenet/ckpt_base.pth")
DEFAULT_HF_CACHE_ROOT = DEFAULT_LOCAL_RUNTIME_ROOT / "huggingface_cache"


def write_json(path: Path, payload: Any) -> None:
    """写出 UTF-8 JSON 文件, 作为 Notebook 与脚本之间的稳定交接格式。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    """读取 UTF-8 或带 BOM 的 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_sha256(path: Path) -> str:
    """计算文件 SHA-256, 用于 Drive 归档 manifest 的完整性记录。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checked(command: list[str], *, cwd: Path | None = None) -> None:
    """执行命令并在失败时抛出异常, 供 Notebook 明确中止当前阶段。"""

    print("运行:", " ".join(command))
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def mount_google_drive() -> None:
    """在 Colab 中挂载 Google Drive, 非 Colab 环境下只打印诊断信息。"""

    try:
        from google.colab import drive  # type: ignore

        drive.mount("/content/drive")
    except Exception as exc:  # pragma: no cover - 由 Colab 环境决定
        print(f"非 Colab 环境或 Drive 已挂载: {exc}")


def clone_or_update_repo(
    *,
    repo_url: str = DEFAULT_REPO_URL,
    repo_root: Path = DEFAULT_REPO_ROOT,
    repo_branch: str = "",
) -> Path:
    """从 GitHub 拉取或更新 CEG 仓库。

    该函数对齐 CEG-WM 的冷启动约定: 每个 Notebook 都可以在空白 Colab 会话中
    独立执行, 不依赖上一个 Notebook 会话中的 `/content/CEG`。
    """

    if not repo_root.exists():
        command = ["git", "clone"]
        if repo_branch:
            command.extend(["--branch", repo_branch])
        command.extend([repo_url, str(repo_root)])
        run_checked(command)
    elif (repo_root / ".git").exists():
        run_checked(["git", "-C", str(repo_root), "fetch", "--all", "--prune"])
        if repo_branch:
            run_checked(["git", "-C", str(repo_root), "checkout", repo_branch])
        run_checked(["git", "-C", str(repo_root), "pull", "--ff-only"])
    else:
        raise FileNotFoundError(f"repo_root 已存在但不是 Git 仓库: {repo_root}")
    return repo_root


def install_repo_for_colab(
    *,
    repo_root: Path = DEFAULT_REPO_ROOT,
    install_image_dependencies: bool = False,
    install_requirements: bool = False,
) -> None:
    """安装仓库与可选依赖。

    `install_requirements=True` 对齐 CEG-WM 的成熟做法, 优先安装仓库声明的
    requirements。`install_image_dependencies=True` 用于图像生成阶段补齐 GPU
    运行常见依赖。
    """

    run_checked([sys.executable, "-m", "pip", "install", "-e", str(repo_root)])
    requirements = repo_root / "requirements.txt"
    if install_requirements and requirements.is_file():
        run_checked([sys.executable, "-m", "pip", "install", "-r", str(requirements)])
    if install_image_dependencies:
        run_checked(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "diffusers",
                "transformers",
                "accelerate",
                "safetensors",
                "Pillow",
                "PyYAML",
                "huggingface_hub",
                "transparent-background",
            ]
        )


def ensure_attestation_key(env_name: str = "CEG_ATTESTATION_KEY") -> None:
    """确保 attestation key 位于环境变量中, 且不写入磁盘。"""

    if os.environ.get(env_name):
        print(f"{env_name} 已存在, 不打印密钥内容。")
        return
    secret_value = None
    try:
        from google.colab import userdata  # type: ignore

        secret_value = userdata.get(env_name)
    except Exception:
        secret_value = None
    if not secret_value:
        secret_value = secrets.token_urlsafe(48)
        print(f"{env_name} 未在 Colab secrets 中定义, 已为本次运行生成临时密钥。")
    os.environ[env_name] = secret_value
    print(f"{env_name} configured =", bool(os.environ.get(env_name)))


def prepare_inspyrenet_weight(
    *,
    drive_weight_path: Path = DEFAULT_INSPYRENET_WEIGHT_DRIVE_PATH,
    weight_url: str = DEFAULT_INSPYRENET_WEIGHT_URL,
    cache_paths: Iterable[Path] | None = None,
    env_name: str = "INSPYRENET_CKPT_PATH",
) -> Path:
    """准备 InSPyReNet 权重并设置环境变量。

    该逻辑只属于 Colab 环境准备。CEG 主方法只接收显式权重路径或环境变量,
    不把 Drive 路径硬编码到方法实现中。
    """

    if not drive_weight_path.is_file():
        drive_weight_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = drive_weight_path.with_suffix(drive_weight_path.suffix + ".downloading")
        urllib.request.urlretrieve(weight_url, str(temp_path))
        temp_path.replace(drive_weight_path)
    effective_cache_paths = list(
        cache_paths
        if cache_paths is not None
        else [
            Path.home() / ".transparent-background" / "ckpt_base.pth",
            Path.home() / ".cache" / "transparent-background" / "ckpt_base.pth",
        ]
    )
    for cache_path in effective_cache_paths:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if not cache_path.exists():
            shutil.copyfile(drive_weight_path, cache_path)
    os.environ[env_name] = str(drive_weight_path)
    print("InSPyReNet 权重已准备:", drive_weight_path)
    return drive_weight_path


def prepare_huggingface_snapshot(
    *,
    model_id: str,
    revision: str | None = None,
    hf_token_env: str = "HF_TOKEN",
    cache_root: Path = DEFAULT_HF_CACHE_ROOT,
) -> dict[str, Any]:
    """预下载或复用 Hugging Face 模型 snapshot。

    该函数学习 CEG-WM 的成熟逻辑: 先把模型放到 session-local cache, 再让
    diffusers 使用同一 cache。这样后续真实 backend 失败时可以明确区分
    “模型访问/下载失败”和“方法执行失败”。
    """

    from huggingface_hub import snapshot_download  # type: ignore

    hub_cache = cache_root / "hub"
    hub_cache.mkdir(parents=True, exist_ok=True)
    token = os.environ.get(hf_token_env) if hf_token_env else None
    local_files_only = False
    try:
        snapshot_path = Path(
            snapshot_download(
                repo_id=model_id,
                revision=revision,
                cache_dir=str(hub_cache),
                token=token,
                local_files_only=True,
            )
        )
        cache_mode = "local_session_cache"
    except Exception:
        snapshot_path = Path(
            snapshot_download(
                repo_id=model_id,
                revision=revision,
                cache_dir=str(hub_cache),
                token=token,
                local_files_only=local_files_only,
            )
        )
        cache_mode = "downloaded_this_session"
    summary = {
        "model_id": model_id,
        "revision": revision or "main",
        "hf_token_env": hf_token_env,
        "hf_token_configured": bool(token),
        "cache_root": str(cache_root),
        "hub_cache": str(hub_cache),
        "snapshot_path": str(snapshot_path),
        "snapshot_exists": snapshot_path.is_dir(),
        "cache_mode": cache_mode,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def create_local_workspace(
    *,
    local_runtime_root: Path,
    run_id: str,
    reset: bool = True,
) -> Path:
    """创建本次 Colab 会话的本地运行工作区。"""

    workspace = local_runtime_root / run_id
    if workspace.exists() and reset:
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def archive_directory_to_drive(
    *,
    source_root: Path,
    drive_root: Path,
    archive_group: str,
    run_id: str,
    archive_name: str | None = None,
) -> dict[str, Any]:
    """把阶段输出目录打包到 Google Drive, 供独立 Colab 会话读取。"""

    if not source_root.is_dir():
        raise FileNotFoundError(f"待归档目录不存在: {source_root}")
    archive_root = drive_root / "archives" / archive_group
    archive_root.mkdir(parents=True, exist_ok=True)
    stem = archive_name or f"{archive_group}_{run_id}"
    zip_path = archive_root / f"{stem}.zip"
    manifest_path = archive_root / f"{stem}_manifest.json"
    archived_files: list[dict[str, Any]] = []
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zip_file:
        for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
            relative_path = path.relative_to(source_root).as_posix()
            zip_file.write(path, arcname=relative_path)
            archived_files.append({"relative_path": relative_path, "byte_count": path.stat().st_size})
    manifest = {
        "artifact_name": "colab_stage_archive_manifest.json",
        "overall_decision": "pass" if archived_files else "fail",
        "archive_group": archive_group,
        "run_id": run_id,
        "source_root": str(source_root),
        "archive_zip_path": str(zip_path),
        "archive_manifest_path": str(manifest_path),
        "archive_sha256": file_sha256(zip_path),
        "archived_file_count": len(archived_files),
        "archived_files": archived_files,
    }
    write_json(manifest_path, manifest)
    return manifest


def _strip_archive_prefix(name: str, prefix: str | None) -> str | None:
    """移除阶段归档中的可选目录前缀, 返回应该写入目标目录的相对路径。

    该函数用于兼容两类已经存在的阶段归档:
    - 新归档: `image_pairs.json`, `clean/...`, `watermarked/...`
    - 旧归档: `inputs/images/image_pairs.json`, `inputs/images/clean/...`

    返回 `None` 表示该 zip 条目不属于当前恢复目标, 应跳过。
    """

    normalized = name.replace("\\", "/").lstrip("/")
    if not normalized or normalized.endswith("/"):
        return None
    if prefix is None:
        return normalized
    normalized_prefix = prefix.replace("\\", "/").strip("/")
    if normalized == normalized_prefix:
        return None
    marker = normalized_prefix + "/"
    if normalized.startswith(marker):
        stripped = normalized[len(marker) :]
        return stripped or None
    return None


def extract_stage_archive(
    *,
    archive_zip_path: Path,
    destination_root: Path,
    reset: bool = True,
    strip_prefix: str | None = None,
    auto_strip_known_prefixes: bool = True,
) -> Path:
    """从 Drive 阶段 zip 恢复输出到当前 Colab 本地工作区。

    `strip_prefix` 用于把旧归档中的 `inputs/images/...` 解压为目标目录下的
    `...`。当 `auto_strip_known_prefixes=True` 且目标目录名为 `images` 时,
    函数会自动识别 `inputs/images/` 前缀, 以兼容已经落盘的图像生成 zip。
    """

    if not archive_zip_path.is_file():
        raise FileNotFoundError(f"阶段归档 zip 不存在: {archive_zip_path}")
    if destination_root.exists() and reset:
        shutil.rmtree(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_zip_path, "r") as zip_file:
        names = [item.filename for item in zip_file.infolist() if not item.is_dir()]
        effective_prefix = strip_prefix
        if effective_prefix is None and auto_strip_known_prefixes and destination_root.name == "images":
            if any(name.replace("\\", "/").startswith("inputs/images/") for name in names):
                effective_prefix = "inputs/images"
        for info in zip_file.infolist():
            relative_name = _strip_archive_prefix(info.filename, effective_prefix)
            if relative_name is None:
                continue
            target_path = destination_root / relative_name
            resolved_target = target_path.resolve()
            resolved_root = destination_root.resolve()
            if resolved_root != resolved_target and resolved_root not in resolved_target.parents:
                raise RuntimeError(f"阶段归档包含非法路径: {info.filename}")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if info.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                with zip_file.open(info, "r") as source, target_path.open("wb") as target:
                    shutil.copyfileobj(source, target)
    return destination_root


def write_model_config_with_cache(
    *,
    path: Path,
    model_id: str,
    snapshot_summary: Mapping[str, Any] | None = None,
    height: int = 512,
    width: int = 512,
    num_inference_steps: int = 28,
    guidance_scale: float = 7.0,
) -> None:
    """写出图像生成模型配置, 显式记录 cache_dir 和模型身份。"""

    payload: dict[str, Any] = {
        "artifact_name": "model_config.draft.json",
        "model_id": model_id,
        "sd_model_id": model_id,
        "torch_dtype": "float16",
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "height": height,
        "width": width,
    }
    if snapshot_summary:
        payload["cache_dir"] = str(Path(str(snapshot_summary["hub_cache"])))
        payload["hf_snapshot_path"] = str(snapshot_summary["snapshot_path"])
        payload["hf_cache_mode"] = snapshot_summary.get("cache_mode")
    write_json(path, payload)

