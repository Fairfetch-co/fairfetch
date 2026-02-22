"""FastAPI route handlers — Direct Pipeline protocol with Green + Legal + Indemnity triple."""

from __future__ import annotations

import hashlib
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
from interfaces.license_provider import BaseLicenseProvider, UsageCategory
from interfaces.summarizer import BaseSummarizer

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
        Query(description="Usage category: summary, rag, research, training, commercial"),
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

    tracker = DataLineageTracker(source_url=url)

    result = await converter.from_url(url)
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
        return md_response

    summary_result = await summarizer.summarize(result.markdown)
    tracker.record(
        "summarize",
        tool=f"litellm/{summary_result.model}",
        output_hash=DataLineageTracker.hash_content(summary_result.summary),
    )

    packet = packet_builder.build(
        markdown=result.markdown,
        summary=summary_result.summary,
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

    result = await converter.from_url(url)
    summary_result = await summarizer.summarize(result.markdown)

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
        Query(description="Usage category: summary, rag, research, training, commercial"),
    ] = "",
) -> PlainTextResponse:
    """Return clean Markdown extraction of a URL (Green AI)."""
    converter: ContentConverter = request.app.state.converter
    signer: Ed25519Signer = request.app.state.signer
    license_type: str = request.app.state.config.license_type
    usage_cat = _resolve_usage_category(usage, request)

    result = await converter.from_url(url)
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
