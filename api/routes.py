"""FastAPI route handlers — Direct Pipeline protocol with Green + Legal + Indemnity triple."""

from __future__ import annotations

import hashlib
import logging
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from api.negotiation import (
    ContentFormat,
    PreferredAccessHeaders,
    is_scraper_request,
    negotiate,
)
from compliance.headers import ComplianceHeaders
from compliance.lineage import DataLineageTracker
from core.converter import ContentConverter
from core.knowledge_packet import KnowledgePacketBuilder
from core.signatures import Ed25519Signer
from core.url_validation import UnsafeURLError, validate_url
from interfaces.license_provider import BaseLicenseProvider, UsageCategory
from interfaces.summarizer import BaseSummarizer

logger = logging.getLogger("fairfetch.routes")

router = APIRouter()


def _attach_compliance_headers(
    response: Response,
    *,
    signer: Ed25519Signer,
    content: str,
    license_type: str,
    usage_category: str = UsageCategory.SUMMARY,
    license_id: str = "",
) -> None:
    sig_bundle = signer.sign(content.encode())
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    headers = ComplianceHeaders(
        origin_verified=True,
        license_type=license_type,
        usage_category=usage_category,
        signature=sig_bundle,
        content_hash=content_hash,
        license_id=license_id,
    )
    for k, v in headers.to_dict().items():
        response.headers[k] = v


def _attach_preferred_access(
    response: Response,
    request: Request,
) -> None:
    """If the request looks like a scraper requesting HTML, inject steering headers."""
    config = request.app.state.config
    if not config.enable_preferred_access:
        return

    user_agent = request.headers.get("user-agent", "")
    accept = request.headers.get("accept", "")

    if is_scraper_request(user_agent, accept):
        preferred = PreferredAccessHeaders(
            llms_txt_url=config.llms_txt_url,
            mcp_endpoint=config.mcp_endpoint,
        )
        for k, v in preferred.to_dict().items():
            response.headers[k] = v

        request.app.state.scraper_intercept_count = (
            getattr(request.app.state, "scraper_intercept_count", 0) + 1
        )


async def _issue_grant_for_response(
    request: Request,
    content: str,
    url: str,
    license_type: str,
    usage_category: str = UsageCategory.SUMMARY,
) -> str:
    """Issue a Usage Grant if a license provider is available. Returns the grant header value."""
    license_provider: BaseLicenseProvider | None = getattr(
        request.app.state, "license_provider", None
    )
    if not license_provider:
        return ""

    payer = getattr(getattr(request, "state", None), "payment_payer", "anonymous")
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    try:
        grant = await license_provider.issue_grant(
            content_url=url,
            content_hash=content_hash,
            license_type=license_type,
            usage_category=usage_category,
            granted_to=payer,
        )
        return grant.to_header_value()
    except Exception:
        return ""


@router.get("/content/fetch")
async def fetch_content(
    request: Request,
    url: Annotated[str, Query(description="URL of the page to fetch and convert")],
    usage: Annotated[
        str,
        Query(
            description=(
                "Usage category: search_engine_indexing, summary, rag, "
                "research, training, commercial"
            )
        ),
    ] = "",
    accept: Annotated[str, Header(alias="accept")] = "application/json",
) -> Response:
    """Fetch a URL, extract content, and return in the negotiated format.

    The response always includes the Green+Legal+Indemnity triple:
      1. Clean Markdown (Green AI — pre-processed at source)
      2. Signed Origin Packet (Legal — cryptographic provenance)
      3. Usage Grant Token (Indemnity — proof of legal access)

    The `usage` parameter controls the usage category for the grant and
    determines the compliance level and effective price tier.
    """
    converter: ContentConverter = request.app.state.converter
    summarizer: BaseSummarizer = request.app.state.summarizer
    packet_builder: KnowledgePacketBuilder = request.app.state.packet_builder
    signer: Ed25519Signer = request.app.state.signer
    config = request.app.state.config
    license_type: str = config.license_type

    usage_cat = _resolve_usage_category(usage, request)

    try:
        validate_url(url)
    except UnsafeURLError:
        return JSONResponse(
            {"error": "url_blocked", "detail": "The requested URL is not allowed."},
            status_code=400,
        )

    tracker = DataLineageTracker(source_url=url)

    try:
        result = await converter.from_url(url)
    except UnsafeURLError:
        return JSONResponse(
            {"error": "url_blocked", "detail": "The requested URL is not allowed."},
            status_code=400,
        )
    except Exception:
        logger.exception("Upstream fetch failed for %s", url)
        return JSONResponse(
            {"error": "upstream_fetch_failed", "detail": "Could not fetch the requested URL."},
            status_code=502,
        )
    tracker.record(
        "extract",
        tool="trafilatura",
        output_hash=DataLineageTracker.hash_content(result.markdown),
    )

    content_format = negotiate(accept)

    grant_header = await _issue_grant_for_response(
        request,
        result.markdown,
        url,
        license_type,
        usage_category=usage_cat,
    )

    if content_format == ContentFormat.MARKDOWN:
        md_response = PlainTextResponse(result.markdown, media_type="text/markdown")
        _attach_compliance_headers(
            md_response,
            signer=signer,
            content=result.markdown,
            license_type=license_type,
            usage_category=usage_cat,
            license_id=grant_header,
        )
        _attach_preferred_access(md_response, request)
        md_response.headers["Vary"] = "Accept"
        return md_response

    try:
        summary_result = await summarizer.summarize(result.markdown)
    except Exception:
        summary_result = None

    if summary_result:
        tracker.record(
            "summarize",
            tool=f"litellm/{summary_result.model}",
            output_hash=DataLineageTracker.hash_content(summary_result.summary),
        )
        summary_text = summary_result.summary
    else:
        summary_text = ""

    packet = packet_builder.build(
        markdown=result.markdown,
        summary=summary_text,
        title=result.title or "",
        author=result.author or "",
        url=url,
        date=result.date or "",
        license_type=license_type,
        usage_category=usage_cat,
    )

    if content_format in (ContentFormat.AI_CONTEXT, ContentFormat.JSON_LD):
        body = packet.to_jsonld()
        body["fairfetch:lineage"] = tracker.to_dict()
        if grant_header:
            body["fairfetch:usageGrant"] = grant_header
        media = content_format.value
        json_response = JSONResponse(content=body, media_type=media)
    else:
        json_response = JSONResponse(content=packet.to_jsonld())

    _attach_compliance_headers(
        json_response,
        signer=signer,
        content=result.markdown,
        license_type=license_type,
        usage_category=usage_cat,
        license_id=grant_header,
    )
    _attach_preferred_access(json_response, request)
    json_response.headers["Vary"] = "Accept"
    return json_response


def _resolve_usage_category(usage_param: str, request: Request) -> str:
    """Resolve usage category from query param, header, or config default."""
    if usage_param:
        try:
            return UsageCategory(usage_param.lower()).value
        except ValueError:
            pass

    header_val = request.headers.get("x-usage-category", "")
    if header_val:
        try:
            return UsageCategory(header_val.lower()).value
        except ValueError:
            pass

    default: str = request.app.state.config.default_usage_category
    return default


@router.get("/content/summary")
async def get_summary(
    request: Request,
    url: Annotated[str, Query(description="URL to summarize")],
) -> JSONResponse:
    """Return just the summary and metadata for a URL."""
    converter: ContentConverter = request.app.state.converter
    summarizer: BaseSummarizer = request.app.state.summarizer

    try:
        validate_url(url)
    except UnsafeURLError:
        return JSONResponse(
            {"error": "url_blocked", "detail": "The requested URL is not allowed."},
            status_code=400,
        )

    try:
        result = await converter.from_url(url)
    except UnsafeURLError:
        return JSONResponse(
            {"error": "url_blocked", "detail": "The requested URL is not allowed."},
            status_code=400,
        )
    except Exception:
        logger.exception("Upstream fetch failed for %s", url)
        return JSONResponse(
            {"error": "upstream_fetch_failed", "detail": "Could not fetch the requested URL."},
            status_code=502,
        )
    try:
        summary_result = await summarizer.summarize(result.markdown)
    except Exception:
        return JSONResponse(
            {
                "error": "summarization_unavailable",
                "detail": "Summarization service is unavailable.",
            },
            status_code=503,
        )

    return JSONResponse(
        content={
            "url": url,
            "title": result.title,
            "author": result.author,
            "summary": summary_result.summary,
            "model": summary_result.model,
        }
    )


@router.get("/content/markdown")
async def get_markdown(
    request: Request,
    url: Annotated[str, Query(description="URL to convert to Markdown")],
    usage: Annotated[
        str,
        Query(
            description=(
                "Usage category: search_engine_indexing, summary, rag, "
                "research, training, commercial"
            )
        ),
    ] = "",
) -> PlainTextResponse:
    """Return clean Markdown extraction of a URL (Green AI)."""
    converter: ContentConverter = request.app.state.converter
    signer: Ed25519Signer = request.app.state.signer
    license_type: str = request.app.state.config.license_type
    usage_cat = _resolve_usage_category(usage, request)

    try:
        validate_url(url)
    except UnsafeURLError:
        return PlainTextResponse("The requested URL is not allowed.", status_code=400)

    try:
        result = await converter.from_url(url)
    except UnsafeURLError:
        return PlainTextResponse("The requested URL is not allowed.", status_code=400)
    except Exception:
        logger.exception("Upstream fetch failed for %s", url)
        return PlainTextResponse("Could not fetch the requested URL.", status_code=502)
    grant_header = await _issue_grant_for_response(
        request,
        result.markdown,
        url,
        license_type,
        usage_category=usage_cat,
    )
    response = PlainTextResponse(result.markdown, media_type="text/markdown")
    _attach_compliance_headers(
        response,
        signer=signer,
        content=result.markdown,
        license_type=license_type,
        usage_category=usage_cat,
        license_id=grant_header,
    )
    _attach_preferred_access(response, request)
    return response


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    scraper_count = getattr(request.app.state, "scraper_intercept_count", 0)
    return {
        "status": "ok",
        "service": "fairfetch",
        "version": "0.2.0",
        "scraper_interceptions": scraper_count,
    }


@router.get("/compliance/optout")
async def get_optout_status(
    request: Request,
    domain: Annotated[str, Query(description="Domain to check opt-out status")],
) -> JSONResponse:
    """Check if a domain has opted out of AI training."""
    from compliance.copyright import CopyrightOptOutLog

    log = CopyrightOptOutLog()
    opted_out = log.is_opted_out(domain)
    entries = log.get_entries(domain)

    return JSONResponse(
        content={
            "domain": domain,
            "opted_out": opted_out,
            "entries": [e.model_dump() for e in entries],
        }
    )


# ---------------------------------------------------------------------------
# Wallet management endpoints
# ---------------------------------------------------------------------------


@router.post("/wallet/register")
async def register_wallet(
    request: Request,
    owner: Annotated[str, Query(description="Name or identifier for the wallet owner")],
    initial_balance: Annotated[
        int, Query(description="Starting balance in smallest USDC unit (1000 = $0.001)")
    ] = 0,
) -> JSONResponse:
    """Register a new pre-funded wallet for fast-path payment (no 402 round-trip)."""
    from payments.wallet_ledger import WalletLedger

    ledger: WalletLedger = request.app.state.wallet_ledger
    try:
        account = ledger.create_wallet(owner=owner, initial_balance=initial_balance)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_input", "detail": str(exc)},
        )
    return JSONResponse(
        content={
            "wallet_token": account.wallet_token,
            "owner": account.owner,
            "balance": account.balance,
            "created_at": account.created_at,
            "usage": (
                "Include this token in the X-WALLET-TOKEN header on every request. "
                "Content will be served immediately without a 402 payment step, "
                "as long as your wallet has sufficient balance."
            ),
        }
    )


@router.get("/wallet/balance")
async def wallet_balance(
    request: Request,
    token: Annotated[str, Query(description="Wallet token (from /wallet/register)")],
) -> JSONResponse:
    """Check a wallet's current balance and account info."""
    from payments.wallet_ledger import WalletLedger

    ledger: WalletLedger = request.app.state.wallet_ledger
    account = ledger.get_account(token)
    if account is None:
        return JSONResponse(
            status_code=404,
            content={"error": "wallet_not_found", "detail": "No wallet with that token."},
        )
    return JSONResponse(content=account.to_dict())


@router.post("/wallet/topup")
async def wallet_topup(
    request: Request,
    token: Annotated[str, Query(description="Wallet token")],
    amount: Annotated[int, Query(description="Amount to add (smallest USDC unit)")],
) -> JSONResponse:
    """Add funds to a wallet."""
    from payments.wallet_ledger import WalletLedger

    if amount <= 0:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_input", "detail": "Amount must be positive."},
        )

    ledger: WalletLedger = request.app.state.wallet_ledger
    tx = ledger.top_up(token, amount)
    if tx is None:
        account = ledger.get_account(token)
        if account is None:
            return JSONResponse(
                status_code=404,
                content={"error": "wallet_not_found", "detail": "No wallet with that token."},
            )
        return JSONResponse(
            status_code=400,
            content={"error": "balance_limit", "detail": "Top-up would exceed balance limit."},
        )
    account = ledger.get_account(token)
    return JSONResponse(
        content={
            "tx_id": tx.tx_id,
            "amount_added": tx.amount,
            "new_balance": tx.balance_after,
            "owner": account.owner if account else "",
        }
    )


@router.get("/wallet/transactions")
async def wallet_transactions(
    request: Request,
    token: Annotated[str, Query(description="Wallet token")],
    limit: Annotated[int, Query(description="Max transactions to return", ge=1, le=100)] = 20,
) -> JSONResponse:
    """Get recent transactions for a wallet."""
    from payments.wallet_ledger import WalletLedger

    ledger: WalletLedger = request.app.state.wallet_ledger
    account = ledger.get_account(token)
    if account is None:
        return JSONResponse(
            status_code=404,
            content={"error": "wallet_not_found", "detail": "No wallet with that token."},
        )
    txs = ledger.get_transactions(token, limit=limit)
    return JSONResponse(
        content={
            "owner": account.owner,
            "balance": account.balance,
            "transactions": [t.to_dict() for t in txs],
        }
    )
