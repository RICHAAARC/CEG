"""CEG attestation 原语导出。"""

from main.watermarking.attestation.binding import (
    ATTESTATION_BACKEND_ID,
    ATTESTATION_BACKEND_ROLE,
    AttestationBindingRequest,
    AttestationBindingResult,
    build_attestation_binding,
)

__all__ = [
    "ATTESTATION_BACKEND_ID",
    "ATTESTATION_BACKEND_ROLE",
    "AttestationBindingRequest",
    "AttestationBindingResult",
    "build_attestation_binding",
]
