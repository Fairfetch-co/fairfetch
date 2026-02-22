"""AWS Lambda@Edge — Viewer Request interceptor with bot-steering logic.

Deployed as a CloudFront Lambda@Edge function on the "Viewer Request" event.
  1. Scrapers requesting HTML get steering headers pointing to the legal API path.
  2. AI agents with correct Accept headers get proxied to FairFetch API.
  3. Unpaid AI requests get a 402 with payment requirements.
"""

from __future__ import annotations

import json
from typing import Any

AI_ACCEPT_TYPES = [
    "application/ai-context+json",
    "application/ld+json",
    "text/markdown",
]

KNOWN_CRAWLER_UAS = [
    "chatgpt", "claude", "anthropic", "openai", "perplexity",
    "gptbot", "ccbot", "cohere-ai", "google-extended",
    "bytespider", "claudebot", "amazonbot", "diffbot",
    "semrushbot", "ahrefsbot", "mj12bot", "dotbot", "petalbot",
]

PAYMENT_REQUIREMENT = {
    "accepts": {
        "price": "1000",
        "asset": "USDC",
        "network": "base",
        "payTo": "PUBLISHER_WALLET_ADDRESS",
        "facilitator": "https://x402.org/facilitator",
        "description": "Content access fee",
    },
    "error": "Payment Required",
    "message": "This content requires micro-payment. Include an X-PAYMENT header.",
}

LLMS_TXT_URL = "/.well-known/llms.txt"
MCP_ENDPOINT = "/mcp"


def _get_header(headers: dict, name: str) -> str:
    entries = headers.get(name.lower(), [])
    return entries[0]["value"] if entries else ""


def is_ai_agent(request: dict[str, Any]) -> bool:
    headers = request.get("headers", {})
    accept_val = _get_header(headers, "accept").lower()
    if any(t in accept_val for t in AI_ACCEPT_TYPES):
        return True
    ua_val = _get_header(headers, "user-agent").lower()
    return any(p in ua_val for p in KNOWN_CRAWLER_UAS)


def is_scraper_html(request: dict[str, Any]) -> bool:
    headers = request.get("headers", {})
    ua_val = _get_header(headers, "user-agent").lower()
    accept_val = _get_header(headers, "accept").lower()
    is_crawler = any(p in ua_val for p in KNOWN_CRAWLER_UAS)
    wants_html = not accept_val or "text/html" in accept_val
    not_fairfetch = not any(t in accept_val for t in AI_ACCEPT_TYPES)
    return is_crawler and wants_html and not_fairfetch


def steering_headers() -> dict[str, list[dict[str, str]]]:
    return {
        "x-fairfetch-preferred-access": [{"key": "X-FairFetch-Preferred-Access", "value": "mcp+json-ld"}],
        "x-fairfetch-llms-txt": [{"key": "X-FairFetch-LLMS-Txt", "value": LLMS_TXT_URL}],
        "x-fairfetch-mcp-endpoint": [{"key": "X-FairFetch-MCP-Endpoint", "value": MCP_ENDPOINT}],
        "link": [{"key": "Link", "value": f'<{LLMS_TXT_URL}>; rel="ai-policy", <{MCP_ENDPOINT}>; rel="ai-content-api"'}],
        "x-fairfetch-scraper-intercepted": [{"key": "X-FairFetch-Scraper-Intercepted", "value": "true"}],
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    record = event["Records"][0]["cf"]
    request = record["request"]

    if is_scraper_html(request):
        for key, val in steering_headers().items():
            request.setdefault("headers", {})[key] = val
        return request

    if not is_ai_agent(request):
        return request

    headers = request.get("headers", {})
    payment_header = _get_header(headers, "x-payment")

    if not payment_header:
        return {
            "status": "402",
            "statusDescription": "Payment Required",
            "headers": {
                "content-type": [{"key": "Content-Type", "value": "application/json"}],
                "x-payment-required": [{"key": "X-Payment-Required", "value": "true"}],
                "cache-control": [{"key": "Cache-Control", "value": "no-store"}],
            },
            "body": json.dumps(PAYMENT_REQUIREMENT),
        }

    request["headers"]["x-payment-verified"] = [
        {"key": "X-Payment-Verified", "value": "edge-pending"}
    ]

    origin_path = request.get("uri", "/")
    query = request.get("querystring", "")
    request["uri"] = "/content/fetch"
    request["querystring"] = f"url={origin_path}&{query}".rstrip("&")

    return request
