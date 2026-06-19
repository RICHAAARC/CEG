"""运行 WAM 的 CEG 补充表 baseline 适配器。

该脚本读取 CEG clean 图像, 调用 Watermark Anything 的 embed/detect 接口生成图像水印
和 bit accuracy observation。该实现属于外部 baseline 适配层, 不进入 CEG 主方法。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from external_baselines.supplementary_table.image_watermark_baseline_common import (  # noqa: E402
    as_text,
    build_observation,
    clean_image_path,
    derive_threshold,
    load_image_pairs,
    load_json,
    row_image_id,
    safe_file_stem,
    write_json,
)
from main.analysis.attack_images import run_attack_workflow  # noqa: E402
from main.core.digest import build_stable_digest  # noqa: E402

BASELINE_ID = "wam"
PRODUCER_ID = "watermark_anything_ceg_adapter"
SCORE_NAME = "wam_payload_bit_accuracy"


def _source_root() -> Path:
    return ROOT / "external_baselines" / "supplementary_table" / "watermark_anything" / "source"


def _prepare_backend(args: argparse.Namespace):
    source_root = _source_root()
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    try:
        import torch  # type: ignore
        import torch.nn.functional as F  # type: ignore
        from PIL import Image  # type: ignore
        from torchvision.utils import save_image  # type: ignore
        from watermark_anything.data.metrics import msg_predict_inference  # type: ignore
        from watermark_anything.data.transforms import default_transform, unnormalize_img  # type: ignore
        from notebooks.inference_utils import load_model_from_checkpoint  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("缺少 WAM 运行依赖, 请在 Colab baseline 环境安装 watermark-anything requirements。") from exc
    ckpt_path = Path(args.checkpoint) if args.checkpoint else source_root / "checkpoints" / "wam_mit.pth"
    json_path = Path(args.params_json) if args.params_json else source_root / "checkpoints" / "params.json"
    if not ckpt_path.is_file():
        raise FileNotFoundError(f"WAM checkpoint 不存在: {ckpt_path}")
    old_cwd = Path.cwd()
    os.chdir(source_root)
    try:
        device = torch.device("cuda" if torch.cuda.is_available() and not args.force_cpu else "cpu")
        wam = load_model_from_checkpoint(str(json_path), str(ckpt_path)).to(device).eval()
    finally:
        os.chdir(old_cwd)
    return torch, F, Image, save_image, msg_predict_inference, default_transform, unnormalize_img, wam, device


def _message(torch: Any, device: Any, nbits: int, seed: int):
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    return torch.randint(0, 2, (int(nbits),), generator=generator).float().to(device)


def _score_image(torch: Any, F: Any, Image: Any, msg_predict_inference: Any, default_transform: Any, wam: Any, device: Any, path: str | Path, message: Any) -> float:
    with torch.inference_mode():
        image = Image.open(path).convert("RGB")
        image_tensor = default_transform(image).unsqueeze(0).to(device)
        preds = wam.detect(image_tensor)["preds"]
        mask_preds = F.sigmoid(preds[:, 0, :, :])
        bit_preds = preds[:, 1:, :, :]
        pred_message = msg_predict_inference(bit_preds, mask_preds).to(device).float().squeeze(0)
        return float((pred_message == message).float().mean().item())


def run_adapter(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    torch, F, Image, save_image, msg_predict_inference, default_transform, unnormalize_img, wam, device = _prepare_backend(args)
    rows = load_image_pairs(args.image_pairs)
    if args.max_samples is not None:
        rows = rows[: int(args.max_samples)]
    artifact_root = Path(args.artifact_root) if args.artifact_root else Path(args.out).resolve().parent
    clean_dir = artifact_root / "images" / "clean"
    watermarked_dir = artifact_root / "images" / "watermarked"
    clean_dir.mkdir(parents=True, exist_ok=True)
    watermarked_dir.mkdir(parents=True, exist_ok=True)
    message = _message(torch, device, args.nbits, args.seed)

    image_pairs: list[dict[str, Any]] = []
    observations_without_threshold: list[dict[str, Any]] = []
    for index, source_row in enumerate(rows, start=1):
        image_id = row_image_id(source_row, index)
        file_stem = safe_file_stem(image_id, f"wam_image_{index:04d}")
        clean_target = clean_dir / f"{file_stem}_clean.png"
        watermarked_target = watermarked_dir / f"{file_stem}_wam.png"
        image = Image.open(clean_image_path(source_row)).convert("RGB")
        image.save(clean_target)
        with torch.inference_mode():
            image_tensor = default_transform(image).unsqueeze(0).to(device)
            outputs = wam.embed(image_tensor, message.unsqueeze(0))
            watermarked_tensor = outputs["imgs_w"]
            save_image(unnormalize_img(watermarked_tensor).clamp(0, 1), str(watermarked_target))
        clean_score = _score_image(torch, F, Image, msg_predict_inference, default_transform, wam, device, clean_target, message)
        watermarked_score = _score_image(torch, F, Image, msg_predict_inference, default_transform, wam, device, watermarked_target, message)
        pair = dict(source_row)
        pair.update({
            "event_id": image_id,
            "image_id": image_id,
            "clean_image_path": str(clean_target),
            "watermarked_image_path": str(watermarked_target),
            "baseline_id": BASELINE_ID,
        })
        image_pairs.append(pair)
        for sample_role, score in (("clean_negative", clean_score), ("positive_source", watermarked_score)):
            observations_without_threshold.append(build_observation(
                baseline_id=BASELINE_ID,
                score_name=SCORE_NAME,
                producer_id=PRODUCER_ID,
                event_id=f"{image_id}__{sample_role}",
                score=score,
                threshold=0.0,
                threshold_source="pending",
                source_row=source_row,
                source_index=index,
                sample_role=sample_role,
                attack_family="clean",
                attack_condition="clean_none",
                image_id=image_id,
                extra={"payload_bit_length": int(args.nbits)},
            ))
        if str(device) == "cuda":
            torch.cuda.empty_cache()

    threshold, threshold_source = derive_threshold(observations_without_threshold, args.threshold)
    observations = []
    for row in observations_without_threshold:
        updated = dict(row)
        updated["threshold"] = threshold
        updated["threshold_source"] = threshold_source
        updated["final_decision"] = bool(float(updated["score"]) >= threshold)
        observations.append(updated)

    attacked_manifest_path = None
    attacks = [item.strip() for item in str(args.attack_families or "").split(",") if item.strip()]
    if attacks:
        attack_root = artifact_root / "attacks"
        run_attack_workflow(image_pairs, attack_root, attack_families=attacks)
        attacked_manifest_path = str(attack_root / "image_manifests" / "attacked_image_manifest.json")
        for attack_index, record in enumerate(load_json(attacked_manifest_path).get("attacked_images", []), start=1):
            source_id = as_text(record.get("source_image_id"))
            source_pair = next((item for item in image_pairs if item["image_id"] == source_id), None)
            if source_pair is None:
                continue
            score = _score_image(torch, F, Image, msg_predict_inference, default_transform, wam, device, record["attacked_image_path"], message)
            observations.append(build_observation(
                baseline_id=BASELINE_ID,
                score_name=SCORE_NAME,
                producer_id=PRODUCER_ID,
                event_id=as_text(record.get("attacked_image_id"), f"attacked_{attack_index:04d}"),
                score=score,
                threshold=threshold,
                threshold_source=threshold_source,
                source_row=source_pair,
                source_index=attack_index,
                sample_role=as_text(record.get("sample_role"), "attacked_positive"),
                attack_family=as_text(record.get("attack_family"), "unknown_attack"),
                attack_condition=as_text(record.get("attack_condition"), "unknown_attack_condition"),
                image_id=source_id,
                extra={"payload_bit_length": int(args.nbits)},
            ))
            if str(device) == "cuda":
                torch.cuda.empty_cache()

    write_json(artifact_root / "image_pairs_wam.json", image_pairs)
    manifest = {
        "artifact_name": "watermark_anything_ceg_adapter_manifest.json",
        "producer_id": PRODUCER_ID,
        "baseline_id": BASELINE_ID,
        "image_pair_count": len(image_pairs),
        "observation_count": len(observations),
        "payload_bit_length": int(args.nbits),
        "threshold": threshold,
        "threshold_source": threshold_source,
        "attacked_image_manifest_path": attacked_manifest_path,
        "formal_result_claim": False,
        "adapter_digest": build_stable_digest({"baseline_id": BASELINE_ID, "image_pair_count": len(image_pairs), "observation_count": len(observations)}),
    }
    return observations, manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 WAM CEG 补充表 baseline adapter。")
    parser.add_argument("--image-pairs", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--artifact-root", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--params-json", default=None)
    parser.add_argument("--nbits", type=int, default=32)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--attack-families", default="")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--force-cpu", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    observations, manifest = run_adapter(args)
    write_json(args.out, observations)
    write_json(Path(args.out).resolve().parent / "watermark_anything_ceg_adapter_manifest.json", manifest)
    print({"baseline_id": BASELINE_ID, "observation_count": len(observations)})


if __name__ == "__main__":
    main()
