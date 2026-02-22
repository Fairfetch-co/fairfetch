# AI Agent Integration Guide

This guide shows AI agent developers how to consume content through the
Fairfetch protocol instead of scraping HTML. You get clean Markdown, verified
provenance, and a cryptographic Usage Grant that protects you from copyright
claims.

---

## Why Use Fairfetch

| Scraping | Fairfetch |
|----------|-----------|
| Parse raw HTML, strip ads, handle JS | Get clean Markdown in one call |
| No proof of legal access | Ed25519-signed Usage Grant |
| 402/403 blocks, CAPTCHAs | x402 payment = guaranteed access |
| Duplicate compute across agents | Pre-processed at source (Green AI) |
| Legal risk | Legal indemnity |

---

## Option A: MCP Integration (Recommended)

The fastest way to connect. Works with Claude Desktop, Cursor, and any
MCP-compatible client.

### Install and Test Locally (5 minutes)

```bash
# 1. Clone and install
git clone https://github.com/Fairfetch-co/fairfetch.git
cd fairfetch
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Test with MCP Inspector (opens in browser)
npx @modelcontextprotocol/inspector python -m mcp_server.server
```

In the Inspector UI:
1. Click "Connect"
2. Go to "Tools" tab
3. Call `fetch_article_markdown` with `url: "https://example.com"`
4. See the clean Markdown result

### Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "fairfetch": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/fairfetch",
      "env": {
        "FAIRFETCH_TEST_MODE": "true"
      }
    }
  }
}
```

Restart Claude Desktop. You can now ask Claude:
- "Summarize the article at https://example.com/news/article"
- "Get verified facts from https://publisher.com/report"

### Add to Cursor IDE

Create or edit `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "fairfetch": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/fairfetch",
      "env": {
        "FAIRFETCH_TEST_MODE": "true"
      }
    }
  }
}
```

Or copy the included `mcp.json` from the repo root and update the `cwd` path.

### Available MCP Tools

| Tool | Input | Returns |
|------|-------|---------|
| `get_site_summary` | `url: string`, `usage?: string` | JSON: title, author, summary, signature, usage_grant |
| `fetch_article_markdown` | `url: string` | Clean Markdown with source header |
| `get_verified_facts` | `url: string`, `usage?: string` | Full JSON-LD knowledge packet + lineage + grant |

The `usage` parameter selects the usage category (`summary`, `rag`, `research`,
`training`, `commercial`) which determines the pricing tier and compliance level
recorded in the Usage Grant.

### Available MCP Resources

| Resource URI | Returns |
|-------------|---------|
| `fairfetch://config` | Server config (version, model, public key, formats) |
| `fairfetch://public-key` | Ed25519 public key for signature verification |

---

## Option B: REST API Integration

For custom agents, pipelines, or any HTTP client.

### Quick Test (curl)

```bash
# Start the local server
cd fairfetch && make dev

# Step 1: Try without payment — get 402 with pricing info
curl -s http://localhost:8402/content/fetch?url=https://example.com | python -m json.tool
```

Response:
```json
{
  "accepts": {
    "price": "1000",
    "asset": "USDC",
    "network": "base",
    "payTo": "0x...",
    "usage_category": "summary",
    "compliance_level": "standard"
  },
  "available_tiers": {
    "summary":    { "price": "1000",  "compliance_level": "standard" },
    "rag":        { "price": "2000",  "compliance_level": "standard" },
    "research":   { "price": "3000",  "compliance_level": "elevated" },
    "training":   { "price": "5000",  "compliance_level": "strict" },
    "commercial": { "price": "10000", "compliance_level": "strict" }
  },
  "error": "Payment Required",
  "message": "This content requires micro-payment..."
}
```

```bash
# Step 2: Pay and get content (test mode — no real wallet needed)
# Specify usage=rag for RAG grounding (2x base price)
curl -s \
  -H "X-PAYMENT: test_paid_fairfetch" \
  -H "Accept: application/ai-context+json" \
  "http://localhost:8402/content/fetch?url=https://example.com&usage=rag" | python -m json.tool
```

### Python Client Example

```python
"""Minimal Fairfetch client for AI agents."""
import httpx

FAIRFETCH_URL = "http://localhost:8402"
PAYMENT_TOKEN = "test_paid_fairfetch"  # test mode token

async def fetch_article(url: str, usage: str = "summary") -> dict:
    """Fetch an article through FairFetch and get a Usage Grant.

    Args:
        url: The article URL to fetch.
        usage: Usage category — summary, rag, research, training, commercial.
               Controls pricing tier and compliance level.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FAIRFETCH_URL}/content/fetch",
            params={"url": url, "usage": usage},
            headers={
                "X-PAYMENT": PAYMENT_TOKEN,
                "Accept": "application/ai-context+json",
            },
        )

        if resp.status_code == 402:
            data = resp.json()
            pricing = data["accepts"]
            tiers = data.get("available_tiers", {})
            raise Exception(
                f"Payment required: {pricing['price']} {pricing['asset']} "
                f"(usage={pricing.get('usage_category')}). "
                f"Available tiers: {list(tiers.keys())}"
            )

        resp.raise_for_status()

        return {
            "content": resp.json(),
            "origin_sig": resp.headers.get("X-FairFetch-Origin-Signature"),
            "license_id": resp.headers.get("X-FairFetch-License-ID"),
            "usage_category": resp.headers.get("X-FairFetch-Usage-Category"),
            "compliance_level": resp.headers.get("X-FairFetch-Compliance-Level"),
            "content_hash": resp.headers.get("X-Content-Hash"),
            "payment_receipt": resp.headers.get("X-PAYMENT-RECEIPT"),
        }

async def fetch_markdown(url: str) -> str:
    """Get just the clean Markdown — lightest option."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FAIRFETCH_URL}/content/markdown",
            params={"url": url},
            headers={"X-PAYMENT": PAYMENT_TOKEN},
        )
        resp.raise_for_status()
        return resp.text

async def get_summary(url: str) -> dict:
    """Get just the AI-generated summary."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FAIRFETCH_URL}/content/summary",
            params={"url": url},
            headers={"X-PAYMENT": PAYMENT_TOKEN},
        )
        resp.raise_for_status()
        return resp.json()


# Usage:
# import asyncio
# result = asyncio.run(fetch_article("https://example.com"))
# print(result["content"]["headline"])
# print(result["license_id"])  # store this as proof of legal access
```

### TypeScript / Node.js Client Example

```typescript
const FAIRFETCH_URL = "http://localhost:8402";
const PAYMENT_TOKEN = "test_paid_fairfetch";

async function fetchArticle(url: string) {
  const resp = await fetch(
    `${FAIRFETCH_URL}/content/fetch?url=${encodeURIComponent(url)}`,
    {
      headers: {
        "X-PAYMENT": PAYMENT_TOKEN,
        "Accept": "application/ai-context+json",
      },
    }
  );

  if (resp.status === 402) {
    const pricing = await resp.json();
    throw new Error(`Payment required: ${JSON.stringify(pricing.accepts)}`);
  }

  const content = await resp.json();
  return {
    content,
    originSignature: resp.headers.get("X-FairFetch-Origin-Signature"),
    licenseId: resp.headers.get("X-FairFetch-License-ID"),
    paymentReceipt: resp.headers.get("X-PAYMENT-RECEIPT"),
  };
}
```

---

## Verifying Usage Grants

Every response includes a Usage Grant — your proof of legal access.
Store these grants. They protect you in case of copyright disputes.

### Quick Verification (Python)

```python
from interfaces.license_provider import UsageGrant

# The grant data comes from the JSON-LD response body
# under "fairfetch:usageGrant", or you can reconstruct
# it from the X-FairFetch-License-ID header + the content hash

grant = UsageGrant(
    grant_id="a1b2c3d4...",
    content_url="https://publisher.com/article",
    content_hash="sha256:...",
    license_type="publisher-terms",
    granted_to="0xYourWallet",
    granted_at="2026-02-22T12:00:00Z",
    signature={
        "algorithm": "Ed25519",
        "signature": "...",
        "public_key": "...",
    },
)

# Verify the grant's cryptographic signature
print(f"Grant valid: {grant.verify()}")
```

### Manual Verification (Any Language)

The signing payload is deterministic:
```
{grant_id}|{content_url}|{content_hash}|{license_type}|{granted_to}|{granted_at}
```

Verify using any Ed25519 library:
```python
import base64
from nacl.signing import VerifyKey

public_key = base64.b64decode(grant_public_key_b64)
signature = base64.b64decode(grant_signature_b64)
payload = f"{grant_id}|{content_url}|{content_hash}|{license_type}|{granted_to}|{granted_at}".encode()

verify_key = VerifyKey(public_key)
verify_key.verify(payload, signature)  # raises if invalid
print("Valid!")
```

---

## Content Negotiation

Control what format you get back by setting the `Accept` header:

| Accept Header | Response |
|--------------|----------|
| `application/ai-context+json` | Full JSON-LD knowledge packet with lineage + grant |
| `application/ld+json` | JSON-LD article with signature |
| `text/markdown` | Clean Markdown only (fastest) |
| `application/json` | Standard JSON (default) |

---

## Detecting Fairfetch-Enabled Sites

When crawling the web, look for these signals that a site supports Fairfetch:

1. **`/.well-known/llms.txt`** — AI access policy file (like robots.txt)
2. **`Link` header** with `rel="ai-content-api"` — points to the MCP/API endpoint
3. **`X-FairFetch-Preferred-Access: mcp+json-ld`** — the site prefers you use the API

```python
async def check_fairfetch_support(url: str) -> dict | None:
    """Check if a site supports Fairfetch before scraping."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.head(url, headers={"User-Agent": "MyAIAgent/1.0"})

        preferred = resp.headers.get("X-FairFetch-Preferred-Access")
        link = resp.headers.get("Link", "")
        llms_txt = resp.headers.get("X-FairFetch-LLMS-Txt")

        if preferred or "ai-content-api" in link:
            return {
                "supported": True,
                "preferred_access": preferred,
                "llms_txt": llms_txt,
                "api_endpoint": _extract_api_from_link(link),
            }
        return None

def _extract_api_from_link(link_header: str) -> str:
    for part in link_header.split(","):
        if "ai-content-api" in part:
            url = part.split(";")[0].strip().strip("<>")
            return url
    return ""
```

---

## End-to-End Example: RAG Pipeline

```python
"""Example: Use Fairfetch as a source in a RAG pipeline."""
import asyncio
import httpx

FAIRFETCH_URL = "http://localhost:8402"

async def rag_with_fairfetch(query: str, source_urls: list[str]) -> str:
    """Fetch verified content from multiple sources, then answer."""
    context_chunks = []
    grants = []

    async with httpx.AsyncClient() as client:
        for url in source_urls:
            resp = await client.get(
                f"{FAIRFETCH_URL}/content/fetch",
                params={"url": url},
                headers={
                    "X-PAYMENT": "test_paid_fairfetch",
                    "Accept": "application/ai-context+json",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                context_chunks.append(data.get("articleBody", ""))
                grants.append(resp.headers.get("X-FairFetch-License-ID"))

    # Now use the verified content in your LLM prompt
    context = "\n\n---\n\n".join(context_chunks)
    prompt = f"Based on the following verified sources:\n\n{context}\n\nAnswer: {query}"

    # ... send to your LLM ...
    # Store `grants` as proof that all sources were legally accessed
    return prompt

# asyncio.run(rag_with_fairfetch("What is the latest on climate?", [...]))
```
