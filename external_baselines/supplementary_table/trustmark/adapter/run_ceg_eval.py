"""运行 TrustMark 的 CEG 补充表 baseline 适配器。

该脚本读取 CEG clean 图像, 调用 Adobe TrustMark Python 接口生成图像水印, 再把解码结果
转成 CEG 统一 baseline observations。该实现属于外部 baseline 适配层, 不进入 CEG 主方法。
"""

from __future__ import annotations

import argparse
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

BASELINE_ID = "trustmark"
PRODUCER_ID = "trustmark_ceg_adapter"
SCORE_NAME = "trustmark_present_binary_score"


def _source_root() -> Path:
    return ROOT / "external_baselines" / "supplementary_table" / "trustmark" / "source" / "python"


def _load_backend(args: argparse.Namespace):
    source_root = _source_root()
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    try:
        from PIL import Image  # type: ignore
        from trustmark import TrustMark  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("缺少 TrustMark 运行依赖, 请在 Colab baseline 环境安装 trustmark/python 依赖。") from exc
    tm = TrustMark(
        verbose=bool(args.verbose_backend),
        model_type=str(args.model_type),
        device=str(args.device or ""),
        loadRemover=False,
        loadBBoxDetector=False,
    )
    return Image, tm


def _score_image(tm: Any, Image: Any, path: str | Path, *, payload: str) -> tuple[float, dict[str, Any]]:
    image = Image.open(path).convert("RGB")
    decoded_secret, present, schema = tm.decode(image)
    decoded_text = "" if decoded_secret is None else str(decoded_secret)
    score = 1.0 if bool(present) and decoded_text == payload else 0.0
    return score, {"trustmark_present": bool(present), "trustmark_schema": schema, "decoded_secret": decoded_text}


def run_adapter(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    Image, tm = _load_backend(args)
    rows = load_image_pairs(args.image_pairs)
    if args.max_samples is not None:
        rows = rows[: int(args.max_samples)]
    artifact_root = Path(args.artifact_root) if args.artifact_root else Path(args.out).resolve().parent
    clean_dir = artifact_root / "images" / "clean"
    watermarked_dir = artifact_root / "images" / "watermarked"
    clean_dir.mkdir(parents=True, exist_ok=True)
    watermarked_dir.mkdir(parents=True, exist_ok=True)

    image_pairs: list[dict[str, Any]] = []
    observations_without_threshold: list[dict[str, Any]] = []
    for index, source_row in enumerate(rows, start=1):
        image_id = row_image_id(source_row, index)
        file_stem = safe_file_stem(image_id, f"trustmark_image_{index:04d}")
        clean_target = clean_dir / f"{file_stem}_clean.png"
        watermarked_target = watermarked_dir / f"{file_stem}_trustmark.png"
        image = Image.open(clean_image_path(source_row)).convert("RGB")
        image.save(clean_target)
        tm.encode(image, args.payload).save(watermarked_target)
        clean_score, clean_extra = _score_image(tm, Image, clean_target, payload=args.payload)
        watermarked_score, watermarked_extra = _score_image(tm, Image, watermarked_target, payload=args.payload)
        pair = dict(source_row)
        pair.update({
            "event_id": image_id,
            "image_id": image_id,
            "clean_image_path": str(clean_target),
            "watermarked_image_path": str(watermarked_target),
            "baseline_id": BASELINE_ID,
        })
        image_pairs.append(pair)
        for sample_role, score, extra in (
            ("clean_negative", clean_score, clean_extra),
            ("positive_source", watermarked_score, watermarked_extra),
        ):
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
                extra={"payload_text": args.payload, "model_type": args.model_type, **extra},
            ))

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
            score, extra = _score_image(tm, Image, record["attacked_image_path"], payload=args.payload)
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
                extra={"payload_text": args.payload, "model_type": args.model_type, **extra},
            ))

    write_json(artifact_root / "image_pairs_trustmark.json", image_pairs)
    manifest = {
        "artifact_name": "trustmark_ceg_adapter_manifest.json",
        "producer_id": PRODUCER_ID,
        "baseline_id": BASELINE_ID,
        "image_pair_count": len(image_pairs),
        "observation_count": len(observations),
        "payload_text": args.payload,
        "model_type": args.model_type,
        "threshold": threshold,
        "threshold_source": threshold_source,
        "attacked_image_manifest_path": attacked_manifest_path,
        "formal_result_claim": False,
        "adapter_digest": build_stable_digest({"baseline_id": BASELINE_ID, "image_pair_count": len(image_pairs), "observation_count": len(observations)}),
    }
    return observations, manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 TrustMark CEG 补充表 baseline adapter。")
    parser.add_argument("--image-pairs", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--artifact-root", default=None)
    parser.add_argument("--payload", default="cegmark")
    parser.add_argument("--model-type", default="Q", choices=["C", "Q", "B", "P"])
    parser.add_argument("--device", default="")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--attack-families", default="")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--verbose-backend", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    observations, manifest = run_adapter(args)
    write_json(args.out, observations)
    write_json(Path(args.out).resolve().parent / "trustmark_ceg_adapter_manifest.json", manifest)
    print({"baseline_id": BASELINE_ID, "observation_count": len(observations)})


if __name__ == "__main__":
    main()
