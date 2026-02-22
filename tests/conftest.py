"""Shared fixtures for the Fairfetch test suite."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app
from core.converter import ConversionResult
from core.signatures import Ed25519Signer
from interfaces.facilitator import PaymentRequirement
from interfaces.license_provider import UsageGrant
from payments.mock_facilitator import MockFacilitator
from payments.mock_license_facilitator import MockLicenseFacilitator, MockLicenseProvider

MOCK_CONVERSION = ConversionResult(
    markdown="# Test Article\n\nGlobal temperatures have risen by 1.5°C.",
    title="Test Article",
    author="Dr. Jane Smith",
    date="2026-01-15",
    url="https://example.com",
)


@pytest.fixture
def signer() -> Ed25519Signer:
    return Ed25519Signer()


@pytest.fixture
def mock_facilitator() -> MockFacilitator:
    return MockFacilitator()


@pytest.fixture
def mock_license_provider(signer: Ed25519Signer) -> MockLicenseProvider:
    return MockLicenseProvider(signer)


@pytest.fixture
def mock_license_facilitator(signer: Ed25519Signer) -> MockLicenseFacilitator:
    return MockLicenseFacilitator(signer)


@pytest.fixture
def payment_requirement() -> PaymentRequirement:
    return PaymentRequirement(
        price="1000",
        pay_to="0xTestPublisher0000000000000000000000",
    )


@pytest.fixture
def sample_html() -> str:
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Article</title></head>
    <body>
        <nav><a href="/">Home</a></nav>
        <article>
            <h1>Climate Change Report 2026</h1>
            <p class="author">By Dr. Jane Smith</p>
            <p>Global temperatures have risen by 1.5°C since pre-industrial levels,
            according to new data released by the IPCC. The report highlights
            urgent need for carbon reduction strategies across all sectors.</p>
            <p>Key findings include accelerated ice sheet melting in Greenland
            and Antarctica, rising sea levels affecting coastal communities,
            and increased frequency of extreme weather events worldwide.</p>
        </article>
        <footer><p>&copy; 2026 News Corp</p></footer>
        <script>console.log('tracking');</script>
    </body>
    </html>
    """


@pytest.fixture
async def client():
    """Async test client for the FastAPI app with mocked network calls.

    Mocks both LiteLLM (no real LLM calls) and ContentConverter.from_url
    (no real HTTP fetches) so tests run without network access.
    """
    mock_llm_response = AsyncMock()
    mock_llm_response.choices = [
        AsyncMock(message=AsyncMock(content="Test summary of the article content."))
    ]
    mock_llm_response.model = "test-model"
    mock_llm_response.usage = AsyncMock(total_tokens=50)

    with (
        patch("core.summarizer.litellm.acompletion", return_value=mock_llm_response),
        patch(
            "core.converter.ContentConverter.from_url",
            new_callable=AsyncMock,
            return_value=MOCK_CONVERSION,
        ),
    ):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
