"""x402 (HTTP 402) middleware — gates content behind micro-payments."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from interfaces.facilitator import BaseFacilitator, PaymentRequirement
from interfaces.license_provider import BaseLicenseProvider, UsageCategory

logger = logging.getLogger("fairfetch.x402")

PAYMENT_HEADER = "X-PAYMENT"
USAGE_CATEGORY_HEADER = "X-USAGE-CATEGORY"
RECEIPT_HEADER = "X-PAYMENT-RECEIPT"
LICENSE_ID_HEADER = "X-FairFetch-License-ID"


class X402Middleware(BaseHTTPMiddleware):
    """Intercepts requests to paid routes and enforces x402 payment flow.

    When a valid payment is provided, settles the transaction and (optionally)
    issues a cryptographic Usage Grant that the AI agent can store as proof
    of legal access. The usage category (from query param or header) determines
    the effective price tier and compliance level.
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

    def _resolve_usage_category(self, request: Request) -> str:
        usage = request.query_params.get("usage", "")
        if usage:
            try:
                return UsageCategory(usage.lower()).value
            except ValueError:
                pass
        header_val = request.headers.get(USAGE_CATEGORY_HEADER, "")
        if header_val:
            try:
                return UsageCategory(header_val.lower()).value
            except ValueError:
                pass
        return self._requirement.usage_category

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self._is_paid_route(request.url.path):
            return await call_next(request)

        payment_header = request.headers.get(PAYMENT_HEADER)
        usage_cat = self._resolve_usage_category(request)

        req_for_category = self._requirement.model_copy(update={"usage_category": usage_cat})

        if not payment_header:
            logger.info("402 issued for %s (usage=%s)", request.url.path, usage_cat)
            return JSONResponse(
                status_code=402,
                content=req_for_category.to_402_body(),
                headers={"X-Payment-Required": "true"},
            )

        result = await self._facilitator.settle(payment_header, req_for_category)

        if not result.valid:
            logger.warning("Payment rejected for %s: %s", request.url.path, result.error)
            return JSONResponse(
                status_code=402,
                content={
                    **req_for_category.to_402_body(),
                    "verification_error": result.error,
                },
            )

        logger.info(
            "Payment settled for %s — tx: %s, usage: %s",
            request.url.path,
            result.tx_hash,
            usage_cat,
        )

        request.state.payment_result = result
        request.state.payment_payer = result.payer
        request.state.usage_category = usage_cat

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
                    usage_category=usage_cat,
                    granted_to=result.payer,
                )
                response.headers[LICENSE_ID_HEADER] = grant.to_header_value()
                logger.info("Usage grant issued: %s (usage=%s)", grant.grant_id, usage_cat)
            except Exception:
                logger.exception("Failed to issue usage grant")

        return response

    def _is_paid_route(self, path: str) -> bool:
        if path in self._exempt:
            return False
        return any(path.startswith(prefix) for prefix in self._paid_prefixes)
