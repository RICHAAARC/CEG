"""CEG 内容链真实检测 backend。

该模块读取 `image_pairs.json` 和可选 attack manifest, 对 clean / watermarked / attacked 图像
执行真实图像像素驱动的 semantic mask 与 LF/HF 内容链 scoring, 并写出下游协议可消费的
`detection_events.json`、`detection_thresholds.json` 和 `ceg_detection_producer_manifest.json`。

该实现属于项目方法推进中的真实检测入口。当前已经接入内容链 scoring、affine / perspective / feature / local deformation 几何恢复和 attestation 绑定。
模块会根据实际运行证据动态写出 `paper_main_method_ready`。当提供 keyed HMAC attestation 且调用方显式声明 `formal_result_claim` 时,
manifest 才会把 detection backend 标记为正式方法结果。fixed-FPR 校准集规模和外部 baseline 属于下游统计与论文交付流程, 不再作为 detection backend 自身的未实现阻塞原因。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from main.core.digest import build_stable_digest
from main.methods.ceg.ablations import CEG_ABLATIONS
from main.watermarking.attestation import AttestationBindingRequest, build_attestation_binding
from main.watermarking.content_chain import ContentChainRequest, extract_content_chain_evidence
from main.watermarking.geometry import GeometryRegistrationRequest, estimate_geometry_registration
from main.watermarking.interfaces import WatermarkPromptContext
from main.watermarking.semantic_mask import GRADIENT_SALIENCY_BACKEND_ID, SemanticMaskRequest, extract_semantic_mask

from experiments.ceg_detection_producer import (
    DETECTION_EVENTS_NAME,
    DETECTION_PRODUCER_MANIFEST_NAME,
    DETECTION_THRESHOLDS_NAME,
    _bool_from_any,
    _image_id,
    _optional_string,
    _source_lookup,
    default_detection_thresholds,
)

CONTENT_CHAIN_DETECTION_BACKEND_ID = "ceg_content_chain_detection_backend"
CONTENT_CHAIN_DETECTION_BACKEND_ROLE = "real_content_chain_detection_with_translation_geometry_and_attestation"


DEFAULT_EVENT_THRESHOLDS = {
    "content_threshold": 0.5,
    "attestation_threshold": 0.5,
    "registration_confidence_min": 0.3,
    "anchor_inlier_ratio_min": 0.5,
    "recovered_sync_consistency_min": 0.55,
    "rescue_delta_low": 0.05,
}


DEFAULT_DETECTOR_CONFIG = {
    "semantic_mask_backend_id": GRADIENT_SALIENCY_BACKEND_ID,
    "mask_threshold_quantile": 0.80,
    "mask_open_iters": 1,
    "mask_close_iters": 1,
    "lf_grid_size": 8,
    "hf_grid_size": 8,
    "lf_weight": 0.5,
    "hf_weight": 0.5,
    "geometry_search_radius": 8,
    "geometry_downsample_size": 96,
    "geometry_anchor_grid_size": 4,
    "affine_rotation_degrees": [-6.0, -3.0, 0.0, 3.0, 6.0],
    "affine_scales": [0.95, 1.0, 1.05],
    "perspective_offsets": [0.0],
    "feature_homography_enabled": True,
    "feature_max_features": 48,
    "homography_ransac_max_trials": 160,
    "local_deformation_enabled": True,
    "local_deformation_grid_size": 4,
    "local_deformation_search_radius": 2,
    "attestation_key_env": None,
    "attestation_key_id": None,
    "attestation_secret_key": None,
    "formal_result_claim": False,
}


def load_image_pair_rows(path: str | Path) -> list[dict[str, Any]]:
    """读取 image pair 行文件, 支持 JSON / JSONL / CSV。

    该函数在真实 backend 中复用脚本层常见输入格式, 但只返回普通字典列表, 不把 CLI 或
    notebook 约束写入方法逻辑。
    """

    import csv

    input_path = Path(path)
    if input_path.suffix == ".json":
        payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            raise TypeError("image pair JSON must contain a list")
        return [dict(row) for row in payload]
    if input_path.suffix == ".jsonl":
        return [json.loads(line) for line in input_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if input_path.suffix == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"unsupported image pair extension: {input_path.suffix}")


def load_optional_manifest(path: str | Path | None) -> dict[str, Any] | None:
    """读取可选 JSON manifest, 缺失时返回 None。"""

    if path is None:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("manifest JSON must contain an object")
    return dict(payload)


def write_content_chain_detection_inputs(
    image_pairs_path: str | Path,
    output_root: str | Path,
    *,
    attacked_image_manifest_path: str | Path | None = None,
    detector_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """运行真实内容链检测并写出统一 detection 输入。"""

    image_pair_path = Path(image_pairs_path)
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    rows = load_image_pair_rows(image_pair_path)
    attacked_manifest = load_optional_manifest(attacked_image_manifest_path)
    config = _merge_config(detector_config)
    mask_root = output_path / "semantic_masks"
    aligned_root = output_path / "aligned_images"

    events: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        pair_events, pair_records = _events_from_image_pair(row, index, image_pair_path.parent, mask_root, aligned_root, config)
        events.extend(pair_events)
        records.extend(pair_records)

    if attacked_manifest is not None:
        attack_events, attack_records = _events_from_attack_manifest(
            attacked_manifest,
            rows,
            image_pair_path.parent,
            mask_root,
            aligned_root,
            config,
        )
        events.extend(attack_events)
        records.extend(attack_records)

    thresholds = default_detection_thresholds()
    (output_path / DETECTION_EVENTS_NAME).write_text(
        json.dumps(events, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_path / DETECTION_THRESHOLDS_NAME).write_text(
        json.dumps(thresholds, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    records_name = "content_chain_detection_records.json"
    (output_path / records_name).write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    readiness = _assess_method_readiness(events, records, config)
    manifest = {
        "artifact_name": DETECTION_PRODUCER_MANIFEST_NAME,
        "producer_id": CONTENT_CHAIN_DETECTION_BACKEND_ID,
        "producer_role": CONTENT_CHAIN_DETECTION_BACKEND_ROLE,
        "formal_result_claim": bool(config.get("formal_result_claim") and readiness["paper_main_method_ready"]),
        "paper_main_method_ready": readiness["paper_main_method_ready"],
        "paper_main_method_blocking_reasons": readiness["blocking_reasons"],
        "method_readiness_checks": readiness["checks"],
        "events_path": DETECTION_EVENTS_NAME,
        "thresholds_path": DETECTION_THRESHOLDS_NAME,
        "content_chain_detection_records_path": records_name,
        "event_count": len(events),
        "content_chain_detection_record_count": len(records),
        "attacked_manifest_consumed": attacked_manifest is not None,
        "sample_roles": sorted({str(event["sample_role"]) for event in events}),
        "attack_families": sorted({str(event["attack_family"]) for event in events}),
        "detector_config": config,
        "producer_digest": build_stable_digest({"events": events, "thresholds": thresholds, "records": records}),
    }
    (output_path / DETECTION_PRODUCER_MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest



def _assess_method_readiness(
    events: list[dict[str, Any]], records: list[dict[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    """根据真实运行证据判断 detection backend 是否已满足论文主方法运行条件。

    该函数只检查 detection backend 自身的方法原语是否齐备, 不把 fixed-FPR 校准集规模、外部 baseline
    或论文结果包验收混入检测方法 readiness。后者属于下游统计和论文交付流程。
    """

    event_count = len(events)
    geometry_ready_count = sum(1 for record in records if bool(record.get("geometry", {}).get("paper_main_method_ready")))
    attestation_ready_count = sum(1 for record in records if bool(record.get("attestation", {}).get("paper_main_method_ready")))
    content_record_count = sum(
        1
        for record in records
        if bool(record.get("content_chain", {}).get("content_chain_digest"))
        and bool(record.get("aligned_content_chain", {}).get("content_chain_digest"))
    )
    checks = {
        "content_chain_records_present": {
            "passed": event_count > 0 and content_record_count == event_count,
            "passed_count": content_record_count,
            "required_count": event_count,
        },
        "geometry_recovery_ready": {
            "passed": event_count > 0 and geometry_ready_count == event_count,
            "passed_count": geometry_ready_count,
            "required_count": event_count,
        },
        "keyed_attestation_ready": {
            "passed": event_count > 0 and attestation_ready_count == event_count,
            "passed_count": attestation_ready_count,
            "required_count": event_count,
            "attestation_key_env": config.get("attestation_key_env"),
            "attestation_key_id": config.get("attestation_key_id"),
        },
    }
    blocking_reasons = [name for name, check in checks.items() if not bool(check["passed"])]
    return {
        "paper_main_method_ready": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "checks": checks,
    }


def _event_blocking_reasons(geometry_record: Mapping[str, Any], attestation_record: Mapping[str, Any]) -> list[str]:
    """给单个 detection event 写出方法原语级阻塞原因。"""

    reasons: list[str] = []
    if not bool(geometry_record.get("paper_main_method_ready")):
        reasons.append("geometry_recovery_ready")
    if not bool(attestation_record.get("paper_main_method_ready")):
        reasons.append("keyed_attestation_ready")
    return reasons

def _merge_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    """合并 detector 配置并进行轻量类型规整。"""

    merged = {**DEFAULT_DETECTOR_CONFIG, **dict(config or {})}
    merged["mask_threshold_quantile"] = float(merged["mask_threshold_quantile"])
    merged["mask_open_iters"] = int(merged["mask_open_iters"])
    merged["mask_close_iters"] = int(merged["mask_close_iters"])
    merged["lf_grid_size"] = int(merged["lf_grid_size"])
    merged["hf_grid_size"] = int(merged["hf_grid_size"])
    merged["lf_weight"] = float(merged["lf_weight"])
    merged["hf_weight"] = float(merged["hf_weight"])
    merged["geometry_search_radius"] = int(merged["geometry_search_radius"])
    merged["geometry_downsample_size"] = int(merged["geometry_downsample_size"])
    merged["geometry_anchor_grid_size"] = int(merged["geometry_anchor_grid_size"])
    return merged


def _events_from_image_pair(
    row: dict[str, Any],
    index: int,
    base_dir: Path,
    mask_root: Path,
    aligned_root: Path,
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """从单个 image pair 生成 clean 负样本和 watermarked 正样本事件。"""

    image_id = _image_id(row, index)
    events: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    clean_path = _resolve_existing_path(
        _optional_string(row, "clean_image_path") or _optional_string(row, "reference_path"),
        base_dir,
        field_name="clean_image_path",
    )
    watermarked_path = _resolve_existing_path(
        _optional_string(row, "watermarked_image_path") or _optional_string(row, "watermarked_path"),
        base_dir,
        field_name="watermarked_image_path",
    )

    clean_event, clean_record = _build_detection_event(
        image_path=clean_path,
        row=row,
        event_id=f"{image_id}__clean_negative",
        sample_role="clean_negative",
        attack_family="clean",
        attack_condition="clean_none",
        is_watermarked=False,
        source_image_id=image_id,
        reference_image_path=clean_path,
        mask_root=mask_root,
        aligned_root=aligned_root,
        config=config,
        suffix="clean",
    )
    events.append(clean_event)
    records.append(clean_record)

    watermarked_event, watermarked_record = _build_detection_event(
        image_path=watermarked_path,
        row=row,
        event_id=f"{image_id}__positive_source",
        sample_role="positive_source",
        attack_family="clean",
        attack_condition="clean_none",
        is_watermarked=True,
        source_image_id=image_id,
        reference_image_path=clean_path,
        mask_root=mask_root,
        aligned_root=aligned_root,
        config=config,
        suffix="watermarked",
    )
    events.append(watermarked_event)
    records.append(watermarked_record)
    return events, records


def _events_from_attack_manifest(
    attacked_manifest: Mapping[str, Any],
    rows: Iterable[dict[str, Any]],
    base_dir: Path,
    mask_root: Path,
    aligned_root: Path,
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """从 attack manifest 生成 attacked detection 事件。"""

    attack_records = attacked_manifest.get("attacked_images", [])
    if not isinstance(attack_records, list):
        raise TypeError("attacked_image_manifest.attacked_images must be list")
    lookup = _source_lookup(rows)
    events: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for index, record in enumerate(attack_records, start=1):
        if not isinstance(record, dict):
            raise TypeError(f"attacked_images[{index}] must be object")
        source_key = _optional_string(record, "source_image_id") or _optional_string(record, "event_id")
        source_row = lookup.get(source_key or "", {})
        attacked_image_id = _optional_string(record, "attacked_image_id", f"attacked_{index:04d}") or f"attacked_{index:04d}"
        attacked_path = _resolve_existing_path(
            _optional_string(record, "attacked_image_path"),
            base_dir,
            field_name="attacked_image_path",
        )
        is_watermarked = _infer_attack_watermark_label(record, source_row)
        reference_path = _resolve_existing_path(
            _optional_string(record, "watermarked_image_path")
            or _optional_string(source_row, "watermarked_image_path")
            or _optional_string(source_row, "watermarked_path"),
            base_dir,
            field_name="reference_watermarked_image_path",
        )
        event, detection_record = _build_detection_event(
            image_path=attacked_path,
            row={**source_row, **record},
            event_id=attacked_image_id,
            sample_role="attacked_positive" if is_watermarked else "attacked_negative",
            attack_family=_optional_string(record, "attack_family", "unknown_attack") or "unknown_attack",
            attack_condition=(
                _optional_string(record, "attack_condition", "unknown_attack_condition")
                or "unknown_attack_condition"
            ),
            is_watermarked=is_watermarked,
            source_image_id=_optional_string(record, "source_image_id"),
            reference_image_path=reference_path,
            mask_root=mask_root,
            aligned_root=aligned_root,
            config=config,
            suffix="attacked",
        )
        events.append(event)
        records.append(detection_record)
    return events, records


def _infer_attack_watermark_label(record: Mapping[str, Any], source_row: Mapping[str, Any]) -> bool:
    """从 attack record 或 source row 推断 attacked 样本标签。"""

    if "is_watermarked" in record:
        return _bool_from_any(record.get("is_watermarked"), default=True)
    if "is_watermarked" in source_row:
        return _bool_from_any(source_row.get("is_watermarked"), default=True)
    role = str(source_row.get("sample_role") or record.get("sample_role") or "").lower()
    if "negative" in role:
        return False
    return True


def _build_detection_event(
    *,
    image_path: Path,
    row: Mapping[str, Any],
    event_id: str,
    sample_role: str,
    attack_family: str,
    attack_condition: str,
    is_watermarked: bool,
    source_image_id: str | None,
    reference_image_path: Path,
    mask_root: Path,
    aligned_root: Path,
    config: Mapping[str, Any],
    suffix: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """对单张图像运行 semantic mask 与内容链 scoring 并构造协议事件。"""

    prompt_context = _prompt_context(row, event_id=event_id, source_image_id=source_image_id)
    safe_event_id = _safe_path_token(event_id)
    mask_path = mask_root / f"{safe_event_id}__{suffix}_semantic_mask.png"
    semantic_mask = extract_semantic_mask(
        SemanticMaskRequest(
            image_path=image_path,
            output_mask_path=mask_path,
            backend_id=str(config["semantic_mask_backend_id"]),
            threshold_quantile=float(config["mask_threshold_quantile"]),
            open_iters=int(config["mask_open_iters"]),
            close_iters=int(config["mask_close_iters"]),
            config={
                "detector_backend": CONTENT_CHAIN_DETECTION_BACKEND_ID,
                "attestation_key_env": config.get("attestation_key_env"),
                "attestation_key_id": config.get("attestation_key_id"),
            },
        )
    )
    content_result = extract_content_chain_evidence(
        ContentChainRequest(
            image_path=image_path,
            semantic_mask=semantic_mask,
            prompt_context=prompt_context,
            lf_grid_size=int(config["lf_grid_size"]),
            hf_grid_size=int(config["hf_grid_size"]),
            lf_weight=float(config["lf_weight"]),
            hf_weight=float(config["hf_weight"]),
            config={"detector_backend": CONTENT_CHAIN_DETECTION_BACKEND_ID},
        )
    )
    content_record = content_result.to_record()
    semantic_record = semantic_mask.to_record()
    aligned_path = aligned_root / f"{safe_event_id}__{suffix}_aligned.png"
    geometry_result = estimate_geometry_registration(
        GeometryRegistrationRequest(
            target_image_path=image_path,
            reference_image_path=reference_image_path,
            output_aligned_image_path=aligned_path,
            search_radius=int(config["geometry_search_radius"]),
            downsample_size=int(config["geometry_downsample_size"]),
            anchor_grid_size=int(config["geometry_anchor_grid_size"]),
            config={
                    "detector_backend": CONTENT_CHAIN_DETECTION_BACKEND_ID,
                    "affine_rotation_degrees": config.get("affine_rotation_degrees"),
                    "affine_scales": config.get("affine_scales"),
                    "perspective_offsets": config.get("perspective_offsets"),
                    "feature_homography_enabled": config.get("feature_homography_enabled"),
                    "feature_max_features": config.get("feature_max_features"),
                    "homography_ransac_max_trials": config.get("homography_ransac_max_trials"),
                    "local_deformation_enabled": config.get("local_deformation_enabled"),
                    "local_deformation_grid_size": config.get("local_deformation_grid_size"),
                    "local_deformation_search_radius": config.get("local_deformation_search_radius"),
                },
        )
    )
    geometry_record = geometry_result.to_record()
    aligned_image_path = Path(geometry_result.aligned_image_path) if geometry_result.aligned_image_path else image_path
    aligned_mask = extract_semantic_mask(
        SemanticMaskRequest(
            image_path=aligned_image_path,
            output_mask_path=mask_root / f"{safe_event_id}__{suffix}_aligned_semantic_mask.png",
            backend_id=str(config["semantic_mask_backend_id"]),
            threshold_quantile=float(config["mask_threshold_quantile"]),
            open_iters=int(config["mask_open_iters"]),
            close_iters=int(config["mask_close_iters"]),
            config={"detector_backend": CONTENT_CHAIN_DETECTION_BACKEND_ID, "geometry_aligned": True},
        )
    )
    aligned_content_result = extract_content_chain_evidence(
        ContentChainRequest(
            image_path=aligned_image_path,
            semantic_mask=aligned_mask,
            prompt_context=prompt_context,
            lf_grid_size=int(config["lf_grid_size"]),
            hf_grid_size=int(config["hf_grid_size"]),
            lf_weight=float(config["lf_weight"]),
            hf_weight=float(config["hf_weight"]),
            config={"detector_backend": CONTENT_CHAIN_DETECTION_BACKEND_ID, "geometry_aligned": True},
        )
    )
    aligned_content_record = aligned_content_result.to_record()
    content_score = round(float(content_result.content_score), 6)
    aligned_content_score = round(float(aligned_content_result.content_score), 6)
    if content_score >= DEFAULT_EVENT_THRESHOLDS["content_threshold"]:
        content_fail_reason = "content_chain_scored"
    elif aligned_content_score >= content_score:
        content_fail_reason = "geometry_suspected"
    else:
        content_fail_reason = "content_chain_below_threshold"
    image_provenance = {
        "image_id": event_id,
        "source_image_id": source_image_id,
        "image_path": image_path.as_posix(),
        "reference_image_path": reference_image_path.as_posix(),
        "aligned_image_path": geometry_result.aligned_image_path,
        "prompt_id": prompt_context.prompt_id,
        "model_id": prompt_context.model_id,
    }
    attestation_result = build_attestation_binding(
        AttestationBindingRequest(
            event_id=event_id,
            method_name="ceg",
            sample_role=sample_role,
            image_path=image_path,
            prompt_context=prompt_context,
            semantic_mask_record=semantic_record,
            content_chain_record=content_record,
            aligned_content_chain_record=aligned_content_record,
            geometry_record=geometry_record,
            image_provenance=image_provenance,
            config={
                "detector_backend": CONTENT_CHAIN_DETECTION_BACKEND_ID,
                "attestation_key_env": config.get("attestation_key_env"),
                "attestation_key_id": config.get("attestation_key_id"),
                "attestation_secret_key": config.get("attestation_secret_key"),
            },
        )
    )
    attestation_record = attestation_result.to_record()
    payload = {
        "thresholds": dict(DEFAULT_EVENT_THRESHOLDS),
        "content": {
            "content_score_raw": content_score,
            "content_score_aligned": aligned_content_score,
            "content_fail_reason": content_fail_reason,
            "payload_probe_score": content_score,
        },
        "geometry": {
            "registration_confidence": geometry_result.registration_confidence,
            "anchor_inlier_ratio": geometry_result.anchor_inlier_ratio,
            "recovered_sync_consistency": geometry_result.recovered_sync_consistency,
            "alignment_residual": geometry_result.alignment_residual,
            "geometry_fail_reason": "translation_registration_only",
            "geometry_record": geometry_record,
        },
        "attestation": attestation_record,
        "ceg_ablation_variants": list(CEG_ABLATIONS),
        "semantic_mask": semantic_record,
        "content_chain": content_record,
        "aligned_content_chain": aligned_content_record,
        "image_provenance": image_provenance,
        "detection_source": {
            "producer": CONTENT_CHAIN_DETECTION_BACKEND_ID,
            "producer_role": CONTENT_CHAIN_DETECTION_BACKEND_ROLE,
            "formal_result_claim": bool(config.get("formal_result_claim") and attestation_record.get("paper_main_method_ready")),
            "paper_main_method_ready": bool(
                geometry_record.get("paper_main_method_ready") and attestation_record.get("paper_main_method_ready")
            ),
            "paper_main_method_blocking_reasons": _event_blocking_reasons(geometry_record, attestation_record),
        },
    }
    event = {
        "event_id": event_id,
        "method_name": "ceg",
        "split": _optional_string(dict(row), "split", "test") or "test",
        "sample_role": sample_role,
        "attack_family": attack_family,
        "attack_condition": attack_condition,
        "is_watermarked": is_watermarked,
        "payload": payload,
    }
    detection_record = {
        "event_id": event_id,
        "sample_role": sample_role,
        "attack_family": attack_family,
        "attack_condition": attack_condition,
        "is_watermarked": is_watermarked,
        "image_path": image_path.as_posix(),
        "semantic_mask": semantic_record,
        "content_chain": content_record,
        "aligned_content_chain": aligned_content_record,
        "geometry": geometry_record,
        "attestation": attestation_record,
        "record_digest": build_stable_digest(
            {
                "event": event_id,
                "semantic_mask": semantic_record,
                "content_chain": content_record,
                "aligned_content_chain": aligned_content_record,
                "geometry": geometry_record,
                "attestation": attestation_record,
            }
        ),
    }
    return event, detection_record


def _prompt_context(row: Mapping[str, Any], *, event_id: str, source_image_id: str | None) -> WatermarkPromptContext:
    """从 image pair 或 attack record 中构造 prompt 上下文。"""

    row_dict = dict(row)
    image_id = source_image_id or _optional_string(row_dict, "image_id") or event_id
    prompt_id = _optional_string(row_dict, "prompt_id") or f"prompt_for_{image_id}"
    prompt_text = _optional_string(row_dict, "prompt_text") or _optional_string(row_dict, "prompt") or ""
    model_id = _optional_string(row_dict, "model_id") or _optional_string(row_dict, "generator_model_id")
    seed = _optional_int(row_dict.get("seed"))
    generation_params = {
        key: row_dict[key]
        for key in ("height", "width", "guidance_scale", "num_inference_steps", "negative_prompt")
        if key in row_dict
    }
    return WatermarkPromptContext(
        image_id=str(image_id),
        prompt_id=str(prompt_id),
        prompt_text=str(prompt_text),
        seed=seed,
        model_id=model_id,
        generation_params=generation_params,
    )


def _optional_int(value: Any) -> int | None:
    """把可选 seed 字段规整为整数。"""

    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_existing_path(value: str | None, base_dir: Path, *, field_name: str) -> Path:
    """解析图像路径并确认文件存在。"""

    if value is None:
        raise ValueError(f"missing required image path field: {field_name}")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{field_name} not found: {resolved}")
    return resolved


def _safe_path_token(value: str) -> str:
    """把 event id 转换为安全文件名片段。"""

    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)[:120]
