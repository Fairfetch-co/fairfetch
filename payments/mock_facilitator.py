"""Mock Facilitator for local development and testing.

Accepts any X-PAYMENT header starting with 'test_' as valid.
No crypto wallet, testnet ETH, or network access required.
"""

from __future__ import annotations

import hashlib
import time

from interfaces.facilitator import BaseFacilitator, FacilitatorResult, PaymentRequirement

TEST_PAYMENT_PREFIX = "test_"
ALWAYS_VALID_TOKEN = "test_paid_fairfetch"


class MockFacilitator(BaseFacilitator):
    """Local mock that accepts any X-PAYMENT value starting with 'test_'.

    Usage in tests:
        facilitator = MockFacilitator()
        result = await facilitator.verify("test_abc123", requirement)
        assert result.valid
    """

    def __init__(self) -> None:
        self._settled: dict[str, FacilitatorResult] = {}

    async def verify(
        self, payment_header: str, requirement: PaymentRequirement
    ) -> FacilitatorResult:
        if not payment_header.startswith(TEST_PAYMENT_PREFIX):
            return FacilitatorResult(
                valid=False,
                error=f"Mock facilitator only accepts tokens starting with '{TEST_PAYMENT_PREFIX}'",
            )

        return FacilitatorResult(
            valid=True,
            payer="0xTestPayer0000000000000000000000000000",
            amount=requirement.price,
        )

    async def settle(
        self, payment_header: str, requirement: PaymentRequirement
    ) -> FacilitatorResult:
        verification = await self.verify(payment_header, requirement)
        if not verification.valid:
            return verification

        fake_tx = hashlib.sha256(f"{payment_header}:{time.time_ns()}".encode()).hexdigest()

        result = FacilitatorResult(
            valid=True,
            tx_hash=f"0x{fake_tx}",
            payer=verification.payer,
            amount=requirement.price,
        )
        self._settled[payment_header] = result
        return result

    def get_settlement(self, payment_header: str) -> FacilitatorResult | None:
        return self._settled.get(payment_header)
