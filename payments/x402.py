"""x402 (HTTP 402) middleware — gates content behind micro-payments."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from interfaces.facilitator import BaseFacilitator, PaymentRequirement
from interfaces.license_provider import BaseLicenseProvider

logger = logging.getLogger("fairfetch.x402")

PAYMENT_HEADER = "X-PAYMENT"
RECEIPT_HEADER = "X-PAYMENT-RECEIPT"
LICENSE_ID_HEADER = "X-FairFetch-License-ID"


class X402Middleware(BaseHTTPMiddleware):
    """Intercepts requests to paid routes and enforces x402 payment flow.

    When a valid payment is provided, settles the transaction and (optionally)
    issues a cryptographic Usage Grant that the AI agent can store as proof
    of legal access.
    """

    def __init__(
        self,
        app: Any,
        *,
        facilitator: BaseFacilitator,
        requirement: PaymentRequirement,
        license_provider: BaseLicenseProvider | None = None,
        paid_path_prefixes: list[str] | None = None,
        exempt_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._facilitator = facilitator
        self._requirement = requirement
        self._license_provider = license_provider
        self._paid_prefixes = paid_path_prefixes or ["/content/"]
        self._exempt = set(exempt_paths or ["/health", "/openapi.json", "/docs", "/redoc"])

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self._is_paid_route(request.url.path):
            return await call_next(request)

        payment_header = request.headers.get(PAYMENT_HEADER)

        if not payment_header:
            logger.info("402 issued for %s", request.url.path)
            return JSONResponse(
                status_code=402,
                content=self._requirement.to_402_body(),
                headers={"X-Payment-Required": "true"},
            )

        result = await self._facilitator.settle(payment_header, self._requirement)

        if not result.valid:
            logger.warning("Payment rejected for %s: %s", request.url.path, result.error)
            return JSONResponse(
                status_code=402,
                content={
                    **self._requirement.to_402_body(),
                    "verification_error": result.error,
                },
            )

        logger.info("Payment settled for %s — tx: %s", request.url.path, result.tx_hash)

        request.state.payment_result = result
        request.state.payment_payer = result.payer

        response = await call_next(request)

        response.headers[RECEIPT_HEADER] = result.tx_hash

        if self._license_provider:
            body_bytes = b""
            if hasattr(response, "body"):
                body_bytes = bytes(response.body)
            content_hash = hashlib.sha256(body_bytes).hexdigest() if body_bytes else ""

            url_param = request.query_params.get("url", request.url.path)
            try:
                grant = await self._license_provider.issue_grant(
                    content_url=url_param,
                    content_hash=content_hash,
                    license_type=self._requirement.description,
                    granted_to=result.payer,
                )
                response.headers[LICENSE_ID_HEADER] = grant.to_header_value()
                logger.info("Usage grant issued: %s", grant.grant_id)
            except Exception:
                logger.exception("Failed to issue usage grant")

        return response

    def _is_paid_route(self, path: str) -> bool:
        if path in self._exempt:
            return False
        return any(path.startswith(prefix) for prefix in self._paid_prefixes)
