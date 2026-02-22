"""Tests for x402 payments + Usage Grant (Legal Indemnity pillar)."""

from __future__ import annotations

from interfaces.facilitator import PaymentRequirement
from interfaces.license_provider import UsageGrant
from payments.mock_facilitator import ALWAYS_VALID_TOKEN, MockFacilitator
from payments.mock_license_facilitator import MockLicenseFacilitator, MockLicenseProvider


class TestMockFacilitator:
    async def test_verify_valid_token(
        self, mock_facilitator: MockFacilitator, payment_requirement: PaymentRequirement
    ):
        result = await mock_facilitator.verify("test_abc123", payment_requirement)
        assert result.valid is True
        assert result.payer != ""

    async def test_verify_always_valid_token(
        self, mock_facilitator: MockFacilitator, payment_requirement: PaymentRequirement
    ):
        result = await mock_facilitator.verify(ALWAYS_VALID_TOKEN, payment_requirement)
        assert result.valid is True

    async def test_verify_invalid_token(
        self, mock_facilitator: MockFacilitator, payment_requirement: PaymentRequirement
    ):
        result = await mock_facilitator.verify("invalid_token", payment_requirement)
        assert result.valid is False
        assert result.error != ""

    async def test_settle_produces_tx_hash(
        self, mock_facilitator: MockFacilitator, payment_requirement: PaymentRequirement
    ):
        result = await mock_facilitator.settle("test_settle123", payment_requirement)
        assert result.valid is True
        assert result.tx_hash.startswith("0x")
        assert len(result.tx_hash) > 10

    async def test_settle_records_settlement(
        self, mock_facilitator: MockFacilitator, payment_requirement: PaymentRequirement
    ):
        token = "test_record_check"
        await mock_facilitator.settle(token, payment_requirement)
        settlement = mock_facilitator.get_settlement(token)
        assert settlement is not None
        assert settlement.valid is True

    async def test_settle_invalid_token_fails(
        self, mock_facilitator: MockFacilitator, payment_requirement: PaymentRequirement
    ):
        result = await mock_facilitator.settle("bad_token", payment_requirement)
        assert result.valid is False


class TestPaymentRequirement:
    def test_402_body_structure(self, payment_requirement: PaymentRequirement):
        body = payment_requirement.to_402_body()
        assert "accepts" in body
        assert body["accepts"]["asset"] == "USDC"
        assert body["accepts"]["network"] == "base"
        assert "payTo" in body["accepts"]
        assert body["error"] == "Payment Required"

    def test_custom_price(self):
        req = PaymentRequirement(price="5000", pay_to="0xABC")
        body = req.to_402_body()
        assert body["accepts"]["price"] == "5000"


class TestUsageGrant:
    """Legal Indemnity: cryptographic proof of legal access."""

    async def test_issue_grant(self, mock_license_provider: MockLicenseProvider):
        grant = await mock_license_provider.issue_grant(
            content_url="https://example.com/article",
            content_hash="abc123def456",
            license_type="publisher-terms",
            granted_to="0xTestPayer",
        )

        assert isinstance(grant, UsageGrant)
        assert grant.content_url == "https://example.com/article"
        assert grant.content_hash == "abc123def456"
        assert grant.license_type == "publisher-terms"
        assert grant.granted_to == "0xTestPayer"
        assert grant.signature is not None

    async def test_grant_is_verifiable(self, mock_license_provider: MockLicenseProvider):
        grant = await mock_license_provider.issue_grant(
            content_url="https://example.com",
            content_hash="deadbeef",
            license_type="commercial",
            granted_to="agent-1",
        )

        assert grant.verify() is True

    async def test_grant_header_value(self, mock_license_provider: MockLicenseProvider):
        grant = await mock_license_provider.issue_grant(
            content_url="https://example.com",
            content_hash="abc",
            license_type="publisher-terms",
            granted_to="agent",
        )

        header = grant.to_header_value()
        assert ":" in header
        assert grant.grant_id in header

    async def test_tampered_grant_fails_verification(
        self, mock_license_provider: MockLicenseProvider
    ):
        grant = await mock_license_provider.issue_grant(
            content_url="https://example.com",
            content_hash="original",
            license_type="publisher-terms",
            granted_to="agent",
        )

        grant.content_hash = "tampered"
        assert grant.verify() is False

    async def test_verify_grant_via_provider(self, mock_license_provider: MockLicenseProvider):
        grant = await mock_license_provider.issue_grant(
            content_url="https://example.com",
            content_hash="test",
            license_type="publisher-terms",
            granted_to="agent",
        )

        is_valid = await mock_license_provider.verify_grant(grant)
        assert is_valid is True


class TestMockLicenseFacilitator:
    """Integration: payment + grant in a single flow."""

    async def test_settle_and_grant(
        self,
        mock_license_facilitator: MockLicenseFacilitator,
        payment_requirement: PaymentRequirement,
    ):
        result, grant = await mock_license_facilitator.settle_and_grant(
            payment_header="test_paid_fairfetch",
            requirement=payment_requirement,
            content_url="https://example.com/article",
            content_hash="abc123",
        )

        assert result.valid is True
        assert result.tx_hash.startswith("0x")
        assert grant is not None
        assert grant.verify() is True
        assert grant.content_url == "https://example.com/article"

    async def test_failed_payment_no_grant(
        self,
        mock_license_facilitator: MockLicenseFacilitator,
        payment_requirement: PaymentRequirement,
    ):
        result, grant = await mock_license_facilitator.settle_and_grant(
            payment_header="invalid_token",
            requirement=payment_requirement,
            content_url="https://example.com/article",
            content_hash="abc123",
        )

        assert result.valid is False
        assert grant is None
