"""x402 (HTTP 402) middleware — gates content behind micro-payments.

Supports two payment paths:
1. **Wallet (fast path):** AI agent sends ``X-WALLET-TOKEN`` header. If the
   wallet has sufficient balance, the amount is deducted immediately and content
   is served — no 402 round-trip required.
2. **x402 (standard path):** AI agent sends ``X-PAYMENT`` header with a
   one-time payment proof. The payment is verified and settled through the
   facilitator.

If neither header is present, a 402 response is returned with pricing info
and the option to register a wallet for faster future access.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from interfaces.facilitator import BaseFacilitator, PaymentRequirement
from interfaces.license_provider import BaseLicenseProvider, UsageCategory
from payments.wallet_ledger import WalletLedger

logger = logging.getLogger("fairfetch.x402")

PAYMENT_HEADER = "X-PAYMENT"
WALLET_TOKEN_HEADER = "X-WALLET-TOKEN"
USAGE_CATEGORY_HEADER = "X-USAGE-CATEGORY"
RECEIPT_HEADER = "X-PAYMENT-RECEIPT"
LICENSE_ID_HEADER = "X-FairFetch-License-ID"


class X402Middleware(BaseHTTPMiddleware):
    """Intercepts requests to paid routes and enforces payment.

    Checks for wallet-based payment first (fast path), then falls back
    to the standard x402 payment flow. The usage category (from query
    param or header) determines the effective price tier and compliance level.
    """

    def __init__(
        self,
        app: Any,
        *,
        facilitator: BaseFacilitator,
        requirement: PaymentRequirement,
        license_provider: BaseLicenseProvider | None = None,
        wallet_ledger: WalletLedger | None = None,
        paid_path_prefixes: list[str] | None = None,
        exempt_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._facilitator = facilitator
        self._requirement = requirement
        self._license_provider = license_provider
        self._wallet_ledger = wallet_ledger
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

        usage_cat = self._resolve_usage_category(request)
        req_for_category = self._requirement.model_copy(update={"usage_category": usage_cat})
        effective_price = int(req_for_category.effective_price())

        wallet_token = request.headers.get(WALLET_TOKEN_HEADER)
        payment_header = request.headers.get(PAYMENT_HEADER)

        # --- Fast path: wallet-based payment (no 402 round-trip) ---
        if wallet_token and self._wallet_ledger:
            content_url = request.query_params.get("url", request.url.path)
            tx = self._wallet_ledger.charge(
                wallet_token,
                effective_price,
                content_url=content_url,
                usage_category=usage_cat,
            )
            if tx:
                logger.info(
                    "Wallet charged for %s — tx: %s, amount: %s, balance: %s, usage: %s",
                    request.url.path,
                    tx.tx_id,
                    tx.amount,
                    tx.balance_after,
                    usage_cat,
                )
                account = self._wallet_ledger.get_account(wallet_token)
                payer = account.owner if account else wallet_token
                request.state.payment_result = None
                request.state.payment_payer = payer
                request.state.usage_category = usage_cat
                request.state.wallet_tx = tx

                response = await call_next(request)
                response.headers[RECEIPT_HEADER] = tx.tx_id
                response.headers["X-FairFetch-Payment-Method"] = "wallet"
                response.headers["X-FairFetch-Wallet-Balance"] = str(tx.balance_after)
                await self._issue_grant(
                    request,
                    response,
                    usage_cat,
                    payer,
                )
                return response

            account = self._wallet_ledger.get_account(wallet_token)
            balance = account.balance if account else 0
            logger.info(
                "Wallet insufficient for %s — need %s, have %s",
                request.url.path,
                effective_price,
                balance,
            )
            return JSONResponse(
                status_code=402,
                content={
                    **req_for_category.to_402_body(),
                    "wallet_error": "insufficient_balance",
                    "wallet_balance": balance,
                    "amount_required": effective_price,
                    "shortfall": effective_price - balance,
                },
            )

        # --- Standard path: x402 one-time payment ---
        if not payment_header:
            body = req_for_category.to_402_body()
            body["hint"] = (
                "For faster access without 402 round-trips, use a pre-funded wallet. "
                "Send X-WALLET-TOKEN header instead of X-PAYMENT. "
                "See /wallet/register to create one."
            )
            logger.info("402 issued for %s (usage=%s)", request.url.path, usage_cat)
            return JSONResponse(
                status_code=402,
                content=body,
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
        response.headers["X-FairFetch-Payment-Method"] = "x402"
        await self._issue_grant(request, response, usage_cat, result.payer)
        return response

    async def _issue_grant(
        self,
        request: Request,
        response: Response,
        usage_cat: str,
        payer: str,
    ) -> None:
        if not self._license_provider:
            return
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
                granted_to=payer,
            )
            response.headers[LICENSE_ID_HEADER] = grant.to_header_value()
            logger.info("Usage grant issued: %s (usage=%s)", grant.grant_id, usage_cat)
        except Exception:
            logger.exception("Failed to issue usage grant")

    def _is_paid_route(self, path: str) -> bool:
        if path in self._exempt:
            return False
        return any(path.startswith(prefix) for prefix in self._paid_prefixes)
