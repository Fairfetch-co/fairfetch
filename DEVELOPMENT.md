# Development Guide

## Prerequisites

- Python 3.11+
- Node.js 18+ (for MCP Inspector)
- Git

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

make setup-dev
```

## Running

### Full Dev Server (recommended)

```bash
make dev
# Launches FastAPI on http://localhost:8402 with helpful startup banner
```

### REST API Only

```bash
make dev-rest
# Starts FastAPI with hot-reload, test mode enabled
```

### MCP Server (via Inspector)

```bash
make dev-mcp
# Opens the MCP Inspector UI in your browser
# Test tools: get_site_summary, fetch_article_markdown, get_verified_facts
```

## Testing

### Run All Tests

```bash
make test
```

### Unit Tests Only

```bash
make test-unit
```

## Testing the Three Pillars Locally

### 1. Green AI (Content Extraction)

```bash
# Fetch clean Markdown — no LLM needed for this endpoint
curl -H "X-PAYMENT: test_paid_fairfetch" \
     -H "Accept: text/markdown" \
     "http://localhost:8402/content/markdown?url=https://example.com"
```

### 2. Legal (Signed Origin)

Every response includes compliance headers:

```bash
curl -v -H "X-PAYMENT: test_paid_fairfetch" \
     "http://localhost:8402/content/fetch?url=https://example.com" 2>&1 | grep -i "x-fairfetch\|x-data-origin\|x-ai-license\|x-content-hash"
```

Expected headers:
- `X-Data-Origin-Verified: true`
- `X-FairFetch-Origin-Signature: <base64>`
- `X-AI-License-Type: publisher-terms`
- `X-Content-Hash: sha256:<hex>`

### 3. Indemnity (Usage Grants)

The `X-FairFetch-License-ID` header contains the grant reference:

```bash
curl -v -H "X-PAYMENT: test_paid_fairfetch" \
     -H "Accept: application/ai-context+json" \
     "http://localhost:8402/content/fetch?url=https://example.com" 2>&1 | grep "X-FairFetch-License-ID"
```

The full knowledge packet (JSON-LD) includes `fairfetch:usageGrant` with
the complete grant object.

### Verifying a Usage Grant Locally

A Usage Grant is verified by checking the Ed25519 signature against the
content owner's public key.

```python
from core.signatures import Ed25519Verifier

# 1. Get the content owner's public key (from fairfetch://public-key resource or API)
public_key_b64 = "..."  # base64-encoded Ed25519 public key

# 2. Reconstruct the signing payload from the grant fields
payload = f"{grant_id}|{content_url}|{content_hash}|{license_type}|{usage_category}|{granted_to}|{granted_at}"

# 3. Verify
verifier = Ed25519Verifier(public_key_b64)
is_valid = verifier.verify(payload.encode(), signature_b64)
print(f"Grant valid: {is_valid}")
```

Or use the built-in verification:

```python
from interfaces.license_provider import UsageGrant

grant = UsageGrant.model_validate(grant_data)
print(f"Grant valid: {grant.verify()}")
```

## Testing x402 Payment Flow

```bash
# Step 1: Request without payment -> 402 (includes available_tiers with all pricing)
curl -i "http://localhost:8402/content/fetch?url=https://example.com"
# Response: 402 with {"accepts": {...}, "available_tiers": {"search_engine_indexing": ..., "summary": ..., "rag": ..., "training": ...}}

# Step 2: Request with test payment -> 200 + receipt + grant (default usage: summary)
curl -i -H "X-PAYMENT: test_paid_fairfetch" \
     "http://localhost:8402/content/fetch?url=https://example.com"

# Step 3: Request with specific usage category -> higher compliance tier
curl -i -H "X-PAYMENT: test_paid_fairfetch" \
     "http://localhost:8402/content/fetch?url=https://example.com&usage=training"
# Response: 200 with X-FairFetch-Usage-Category: training, X-FairFetch-Compliance-Level: strict
```

Any `X-PAYMENT` value starting with `test_` works. The token
`test_paid_fairfetch` is guaranteed valid.

## Testing Bot Steering

Simulate a known crawler requesting raw HTML. The `X-PAYMENT` header is
needed to pass the x402 middleware before the steering logic runs:

```bash
curl -v -H "X-PAYMENT: test_paid_fairfetch" \
     -H "User-Agent: GPTBot/1.0" \
     -H "Accept: text/html" \
     "http://localhost:8402/content/fetch?url=https://example.com" 2>&1 | grep "X-FairFetch"
```

Expected steering headers:
- `X-FairFetch-Preferred-Access: mcp+json-ld`
- `X-FairFetch-LLMS-Txt: /.well-known/llms.txt`
- `X-FairFetch-MCP-Endpoint: /mcp`
- `Link: <...>; rel="ai-policy", <...>; rel="ai-content-api"`

## Code Quality

```bash
make lint       # ruff check + format
make typecheck  # mypy strict mode
```

## Security

### URL validation (SSRF protection)

The `url` query parameter is validated before any outbound fetch. Blocked targets include:

- Non-HTTP(S) schemes (`file://`, `ftp://`, etc.)
- Loopback and private IPs (`127.x`, `10.x`, `172.16–31.x`, `192.168.x`)
- Link-local and cloud metadata (e.g. `169.254.169.254`, `metadata.google.internal`)

Requests with a disallowed URL receive `400` with `{"error": "url_blocked", "detail": "The requested URL is not allowed."}`.

To test:

```bash
curl -s "http://localhost:8402/content/fetch?url=http://127.0.0.1/admin" \
  -H "X-PAYMENT: test_paid_fairfetch"
# → 400, url_blocked
```

### Test mode vs production

- **`FAIRFETCH_TEST_MODE=true`** (default): CORS allows all origins (`*`); wallet ledger pre-seeds `wallet_test_agent_alpha` and `wallet_test_agent_beta`; mock payment tokens accepted.
- **`FAIRFETCH_TEST_MODE=false`**: CORS is restricted to `https://{FAIRFETCH_PUBLISHER_DOMAIN}`; no pre-seeded wallets; use real payment integration.

Optional **`FAIRFETCH_PRICE_BY_ROUTE`** (JSON map of path prefix → price) enables variable pricing by content URL path. Prices must be numeric; path is normalized for matching; up to 256 entries. See [Site owner guide](docs/PUBLISHER_GUIDE.md) and [README Configuration](README.md#-configuration).

## Architecture Decisions

### Open Core: interfaces/ vs implementations

The `interfaces/` directory defines the FairFetch standard as abstract base
classes. Anyone can implement `BaseFacilitator`, `BaseSummarizer`, or
`BaseLicenseProvider` without depending on the rest of the codebase. The
concrete implementations in `core/`, `payments/`, and `plugins/` are one
possible realization of the standard.

### Why Usage Grants?

Copyright law is ambiguous for AI training. Usage Grants provide a
deterministic, cryptographically verifiable proof that content was accessed
through an authorized channel under explicit terms. This removes legal
uncertainty for both content creators and AI companies.

### Why Ed25519?

Fast (62,000 signatures/sec on commodity hardware), small (64-byte
signatures), deterministic, and widely supported. The same key pair signs
both origin attestations and usage grants.

### Why bot steering instead of blocking?

Blocking crawlers breaks the web. Steering them with `Link` headers and
`X-FairFetch-Preferred-Access` is a cooperative signal: "Here's a better
way to get this content legally." Site owners can see the conversion rate
in the `/health` endpoint's `scraper_interceptions` counter.
