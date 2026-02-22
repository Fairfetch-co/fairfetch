"""Re-exports from interfaces for backward compatibility.

All abstract types now live in interfaces.facilitator — this module
re-exports them so existing imports continue to work.
"""

from interfaces.facilitator import (
    BaseFacilitator,
    FacilitatorResult,
    PaymentNetwork,
    PaymentRequirement,
)

Facilitator = BaseFacilitator

__all__ = [
    "BaseFacilitator",
    "Facilitator",
    "FacilitatorResult",
    "PaymentNetwork",
    "PaymentRequirement",
]
