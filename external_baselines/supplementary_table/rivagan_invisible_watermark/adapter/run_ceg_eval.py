"""运行 RivaGAN invisible-watermark 的 CEG 补充表 baseline 适配器。

该脚本读取 CEG 已生成的 clean 图像, 使用 invisible-watermark 中的 RivaGAN 图像水印
接口生成 watermarked 图像, 再把解码 bit accuracy 写成 CEG 统一 baseline observations。
该实现属于外部 baseline 适配层, 不进入 CEG 主方法。
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
    bit_accuracy,
    build_observation,
    bytes_to_bits,
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

BASELINE_ID = "rivagan_invisible_watermark"
PRODUCER_ID = "rivagan_invisible_watermark_ceg_adapter"
SCORE_NAME = "rivagan_payload_bit_accuracy"


def _source_root() -> Path:
    return ROOT / "external_baselines" / "supplementary_table" / "rivagan_invisible_watermark" / "source"


def _payload_bytes(value: str) -> bytes:
    payload = value.encode("utf-8")
    if len(payload) != 4:
        raise ValueError("RivaGAN invisible-watermark payload 必须是 4 个 UTF-8 单字节字符, 即 32 bit。")
    return payload


def _decode_bits(decoded: Any) -> list[int]:
    if isinstance(decoded, bytes):
        return bytes_to_bits(decoded)
    if isinstance(decoded, str):
        return bytes_to_bits(decoded.encode("utf-8", errors="ignore"))
    if isinstance(decoded, (list, tuple)):
        return [int(value) & 1 for value in decoded]
    return []


def _load_backend():
    source_root = _source_root()
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    try:
        import cv2  # type: ignore
        from imwatermark import WatermarkDecoder, WatermarkEncoder  # type: ignore
    except Exception as exc:  # pragma: no cover - 依赖由 Colab baseline 环境提供
        raise RuntimeError("缺少 invisible-watermark 运行依赖, 请在 Colab baseline 环境安装 opencv-python 和仓库依赖。") from exc
    WatermarkEncoder.loadModel()
    WatermarkDecoder.loadModel()
    return cv2, WatermarkEncoder, WatermarkDecoder


def _score_image(cv2: Any, decoder_cls: Any, path: str | Path, *, payload_bits: list[int], method: str) -> float:
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"无法读取图像: {path}")
    decoder = decoder_cls("bytes", len(payload_bits))
    decoded = decoder.decode(image, method)
    return bit_accuracy(_decode_bits(decoded), payload_bits)


def run_adapter(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cv2, encoder_cls, decoder_cls = _load_backend()
    rows = load_image_pairs(args.image_pairs)
    if args.max_samples is not None:
        rows = rows[: int(args.max_samples)]
    artifact_root = Path(args.artifact_root) if args.artifact_root else Path(args.out).resolve().parent
    clean_dir = artifact_root / "images" / "clean"
    watermarked_dir = artifact_root / "images" / "watermarked"
    clean_dir.mkdir(parents=True, exist_ok=True)
    watermarked_dir.mkdir(parents=True, exist_ok=True)
    payload = _payload_bytes(args.payload)
    payload_bits = bytes_to_bits(payload)

    image_pairs: list[dict[str, Any]] = []
    observations_without_threshold: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        image_id = row_image_id(row, index)
        file_stem = safe_file_stem(image_id, f"rivagan_image_{index:04d}")
        source_clean = Path(clean_image_path(row))
        clean_target = clean_dir / f"{file_stem}_clean.png"
        watermarked_target = watermarked_dir / f"{file_stem}_rivagan.png"
        clean_bgr = cv2.imread(str(source_clean))
        if clean_bgr is None:
            raise FileNotFoundError(f"无法读取 clean 图像: {source_clean}")
        cv2.imwrite(str(clean_target), clean_bgr)
        encoder = encoder_cls()
        encoder.set_watermark("bytes", payload)
        encoded = encoder.encode(clean_bgr, args.method)
        cv2.imwrite(str(watermarked_target), encoded)
        clean_score = _score_image(cv2, decoder_cls, clean_target, payload_bits=payload_bits, method=args.method)
        watermarked_score = _score_image(cv2, decoder_cls, watermarked_target, payload_bits=payload_bits, method=args.method)
        pair = dict(row)
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
                baseline_id=BASELINE_ID, score_name=SCORE_NAME, producer_id=PRODUCER_ID,
                event_id=f"{image_id}__{sample_role}", score=score, threshold=0.0,
                threshold_source="pending", source_row=row, source_index=index,
                sample_role=sample_role, attack_family="clean", attack_condition="clean_none",
                image_id=image_id, extra={"watermark_method": args.method, "payload_bit_length": len(payload_bits)},
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
            score = _score_image(cv2, decoder_cls, record["attacked_image_path"], payload_bits=payload_bits, method=args.method)
            observations.append(build_observation(
                baseline_id=BASELINE_ID, score_name=SCORE_NAME, producer_id=PRODUCER_ID,
                event_id=as_text(record.get("attacked_image_id"), f"attacked_{attack_index:04d}"),
                score=score, threshold=threshold, threshold_source=threshold_source,
                source_row=source_pair, source_index=attack_index,
                sample_role=as_text(record.get("sample_role"), "attacked_positive"),
                attack_family=as_text(record.get("attack_family"), "unknown_attack"),
                attack_condition=as_text(record.get("attack_condition"), "unknown_attack_condition"),
                image_id=source_id, extra={"watermark_method": args.method, "payload_bit_length": len(payload_bits)},
            ))

    write_json(artifact_root / "image_pairs_rivagan_invisible_watermark.json", image_pairs)
    manifest = {
        "artifact_name": "rivagan_invisible_watermark_ceg_adapter_manifest.json",
        "producer_id": PRODUCER_ID,
        "baseline_id": BASELINE_ID,
        "image_pair_count": len(image_pairs),
        "observation_count": len(observations),
        "payload_bit_length": len(payload_bits),
        "threshold": threshold,
        "threshold_source": threshold_source,
        "attacked_image_manifest_path": attacked_manifest_path,
        "formal_result_claim": False,
        "adapter_digest": build_stable_digest({"baseline_id": BASELINE_ID, "image_pair_count": len(image_pairs), "observation_count": len(observations)}),
    }
    return observations, manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 RivaGAN invisible-watermark CEG 补充表 baseline adapter。")
    parser.add_argument("--image-pairs", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--artifact-root", default=None)
    parser.add_argument("--payload", default="CEG0")
    parser.add_argument("--method", default="rivaGan")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--attack-families", default="")
    parser.add_argument("--max-samples", type=int, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    observations, manifest = run_adapter(args)
    write_json(args.out, observations)
    write_json(Path(args.out).resolve().parent / "rivagan_invisible_watermark_ceg_adapter_manifest.json", manifest)
    print({"baseline_id": BASELINE_ID, "observation_count": len(observations)})


if __name__ == "__main__":
    main()
