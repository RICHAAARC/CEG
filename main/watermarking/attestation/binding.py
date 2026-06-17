"""CEG 事件级 attestation 绑定原语。

该模块把 prompt 上下文、semantic mask、内容链、几何恢复和图像 provenance 绑定成可审计的
attestation record。它不依赖 CEG-WM, 不包含 notebook、Google Drive 打包或 harness 门禁逻辑。

当前实现是公开 digest 级 attestation: 它真实检查输入 evidence 的完整性、一致性和可复现绑定摘要,
并输出 `attestation_score`。它不是密码学签名, 也不是外部可信执行环境证明, 因此仍保持
`paper_main_method_ready = False`。后续可以在同一接口下替换为 keyed signature 或外部 verifier。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from main.core.digest import build_stable_digest
from main.watermarking.interfaces import WatermarkPromptContext


ATTESTATION_BACKEND_ID = "ceg_public_digest_attestation"
ATTESTATION_BACKEND_ROLE = "event_level_evidence_binding_primitive"
ATTESTATION_VERSION = "ceg_attestation_v1"


@dataclass(frozen=True)
class AttestationBindingRequest:
    """描述一次事件级 attestation 绑定请求。

    该结构属于通用工程写法: 它把 detector 已经得到的 evidence 作为显式输入, 避免 attestation
    模块反向读取脚本临时状态。这样后续可以把公开 digest backend 替换为带密钥或外部 verifier 的实现。
    """

    event_id: str
    method_name: str
    sample_role: str
    image_path: Path
    prompt_context: WatermarkPromptContext
    semantic_mask_record: Mapping[str, Any]
    content_chain_record: Mapping[str, Any]
    aligned_content_chain_record: Mapping[str, Any]
    geometry_record: Mapping[str, Any]
    image_provenance: Mapping[str, Any]
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AttestationBindingResult:
    """描述 attestation 输出。

    `attestation_score` 是 `[0, 1]` 连续分数, 当前由 evidence 完整性、一致性和文件可验证性综合得到。
    """

    status: str
    attestation_score: float
    attestation_digest: str
    evidence_bundle_digest: str
    verifier_digest: str
    check_results: Mapping[str, Any]
    diagnostics: Mapping[str, Any]
    backend_id: str = ATTESTATION_BACKEND_ID
    backend_role: str = ATTESTATION_BACKEND_ROLE
    paper_main_method_ready: bool = False

    def to_record(self) -> dict[str, Any]:
        """转换为 detection event 可消费的普通字典。"""

        return {
            "attestation_score": self.attestation_score,
            "attestation_status": self.status,
            "attestation_digest": self.attestation_digest,
            "evidence_bundle_digest": self.evidence_bundle_digest,
            "verifier_digest": self.verifier_digest,
            "check_results": dict(self.check_results),
            "diagnostics": dict(self.diagnostics),
            "backend_id": self.backend_id,
            "backend_role": self.backend_role,
            "paper_main_method_ready": self.paper_main_method_ready,
            "paper_main_method_blocking_reason": "public_digest_attestation_lacks_keyed_or_external_verifier",
        }


def build_attestation_binding(request: AttestationBindingRequest) -> AttestationBindingResult:
    """构造事件级 attestation record。"""

    checks = _run_checks(request)
    passed = sum(1 for item in checks.values() if bool(item.get("passed")))
    total = max(1, len(checks))
    score = round(float(passed / total), 8)
    evidence_bundle = {
        "attestation_version": ATTESTATION_VERSION,
        "event_id": request.event_id,
        "method_name": request.method_name,
        "sample_role": request.sample_role,
        "prompt_context": request.prompt_context.to_record(),
        "semantic_mask_digest": request.semantic_mask_record.get("mask_digest"),
        "semantic_routing_digest": request.semantic_mask_record.get("routing_digest"),
        "content_chain_digest": request.content_chain_record.get("content_chain_digest"),
        "aligned_content_chain_digest": request.aligned_content_chain_record.get("content_chain_digest"),
        "geometry_alignment_digest": request.geometry_record.get("alignment_digest"),
        "image_provenance": dict(request.image_provenance),
        "config": dict(request.config),
    }
    evidence_bundle_digest = build_stable_digest(evidence_bundle)
    verifier_digest = build_stable_digest(
        {
            "backend_id": ATTESTATION_BACKEND_ID,
            "backend_role": ATTESTATION_BACKEND_ROLE,
            "attestation_version": ATTESTATION_VERSION,
            "check_names": sorted(checks),
        }
    )
    attestation_digest = build_stable_digest(
        {
            "evidence_bundle_digest": evidence_bundle_digest,
            "verifier_digest": verifier_digest,
            "attestation_score": score,
            "check_results": checks,
        }
    )
    status = "ok" if score >= 1.0 else "failed_checks"
    return AttestationBindingResult(
        status=status,
        attestation_score=score,
        attestation_digest=attestation_digest,
        evidence_bundle_digest=evidence_bundle_digest,
        verifier_digest=verifier_digest,
        check_results=checks,
        diagnostics={
            "attestation_version": ATTESTATION_VERSION,
            "passed_check_count": passed,
            "total_check_count": total,
            "score_rule": "passed_check_count / total_check_count",
        },
        paper_main_method_ready=False,
    )


def _run_checks(request: AttestationBindingRequest) -> dict[str, dict[str, Any]]:
    """执行 attestation 完整性和一致性检查。"""

    prompt_record = request.prompt_context.to_record()
    return {
        "image_file_exists": _check(request.image_path.is_file(), {"image_path": request.image_path.as_posix()}),
        "prompt_identity_present": _check(
            bool(prompt_record.get("image_id")) and bool(prompt_record.get("prompt_id")),
            {"image_id": prompt_record.get("image_id"), "prompt_id": prompt_record.get("prompt_id")},
        ),
        "semantic_mask_digest_present": _check_digest_pair(
            request.semantic_mask_record.get("mask_digest"),
            request.semantic_mask_record.get("routing_digest"),
        ),
        "content_chain_digest_present": _check_digest_pair(
            request.content_chain_record.get("content_chain_digest"),
            request.aligned_content_chain_record.get("content_chain_digest"),
        ),
        "geometry_alignment_digest_present": _check_hex_digest(request.geometry_record.get("alignment_digest")),
        "geometry_metrics_numeric": _check_geometry_metrics(request.geometry_record),
        "provenance_paths_present": _check(
            bool(request.image_provenance.get("image_path")) and bool(request.image_provenance.get("reference_image_path")),
            {
                "image_path": request.image_provenance.get("image_path"),
                "reference_image_path": request.image_provenance.get("reference_image_path"),
            },
        ),
        "method_identity_bound": _check(
            request.method_name == "ceg" and bool(request.event_id) and bool(request.sample_role),
            {"event_id": request.event_id, "method_name": request.method_name, "sample_role": request.sample_role},
        ),
    }


def _check(passed: bool, evidence: Mapping[str, Any]) -> dict[str, Any]:
    """构造单个检查项。"""

    return {"passed": bool(passed), "evidence": dict(evidence)}


def _check_hex_digest(value: Any) -> dict[str, Any]:
    """检查字段是否为 64 位十六进制 digest。"""

    text = str(value or "")
    passed = len(text) == 64 and all(char in "0123456789abcdef" for char in text.lower())
    return _check(passed, {"digest_length": len(text)})


def _check_digest_pair(first: Any, second: Any) -> dict[str, Any]:
    """检查两个 digest 字段是否同时有效。"""

    first_check = _check_hex_digest(first)
    second_check = _check_hex_digest(second)
    return _check(
        bool(first_check["passed"] and second_check["passed"]),
        {
            "first_digest_length": first_check["evidence"]["digest_length"],
            "second_digest_length": second_check["evidence"]["digest_length"],
        },
    )


def _check_geometry_metrics(record: Mapping[str, Any]) -> dict[str, Any]:
    """检查几何指标是否是可用于 formal decision 的数值。"""

    fields = (
        "registration_confidence",
        "anchor_inlier_ratio",
        "recovered_sync_consistency",
        "alignment_residual",
    )
    numeric = []
    for field_name in fields:
        value = record.get(field_name)
        numeric.append(isinstance(value, (int, float)) and not isinstance(value, bool))
    return _check(all(numeric), {"numeric_fields": dict(zip(fields, numeric))})
