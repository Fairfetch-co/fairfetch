"""Fairfetch Interfaces — the Open Core "Standard" layer.

These abstract base classes define the FairFetch protocol.  Any third-party
or cloud implementation can plug in by implementing these interfaces without
depending on the rest of the repository.
"""

from interfaces.facilitator import BaseFacilitator, FacilitatorResult, PaymentRequirement
from interfaces.license_provider import (
    BaseLicenseProvider,
    ComplianceLevel,
    UsageCategory,
    UsageGrant,
)
from interfaces.summarizer import BaseSummarizer, SummaryResult

__all__ = [
    "BaseFacilitator",
    "BaseLicenseProvider",
    "BaseSummarizer",
    "ComplianceLevel",
    "FacilitatorResult",
    "PaymentRequirement",
    "SummaryResult",
    "UsageCategory",
    "UsageGrant",
]
