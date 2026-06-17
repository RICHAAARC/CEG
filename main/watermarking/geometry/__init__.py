"""CEG 几何恢复原语导出。"""

from main.watermarking.geometry.registration import (
    GEOMETRY_REGISTRATION_BACKEND_ID,
    GEOMETRY_REGISTRATION_BACKEND_ROLE,
    GeometryRegistrationRequest,
    GeometryRegistrationResult,
    estimate_geometry_registration,
)

__all__ = [
    "GEOMETRY_REGISTRATION_BACKEND_ID",
    "GEOMETRY_REGISTRATION_BACKEND_ROLE",
    "GeometryRegistrationRequest",
    "GeometryRegistrationResult",
    "estimate_geometry_registration",
]
