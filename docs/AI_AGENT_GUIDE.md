# AI Agent Integration Guide

**Consume publisher content through Fairfetch instead of scraping — with clean Markdown, verified provenance, and a cryptographic Usage Grant for legal indemnity.**

This guide is for **developers** building AI agents, RAG pipelines, or MCP clients that need to fetch web content in a compliant, paid, and legally verifiable way.

---

## 📑 Navigate this guide

| Section | What you’ll get |
|--------|-----------------|
| [**System requirements & checks**](#system-requirements--checks) | Python/Node versions, network, and limitations |
| [**Why Fairfetch vs scraping**](#why-fairfetch-vs-scraping) | Quick comparison and benefits |
| [**Option A: MCP integration**](#option-a-mcp-integration-recommended) | Connect via MCP (Claude, Cursor, custom clients) |
| [**Option B: REST API**](#option-b-rest-api-integration) | curl, Python, TypeScript examples and flows |
| [**Payment: x402 vs wallet**](#payment-x402-vs-wallet) | When to use which; example requests and responses |
| [**Failure points & mitigations**](#failure-points--mitigations) | Status codes, errors, and what to do |
| [**Verifying Usage Grants**](#verifying-usage-grants) | How to verify and store grants |
| [**Content negotiation & detection**](#content-negotiation--detection) | Accept header and Fairfetch-enabled site detection |
| [**End-to-end example**](#end-to-end-example-rag-pipeline) | RAG pipeline with multiple sources and grants |

---

## System requirements & checks

**Recommended environment**

| Requirement | Minimum | How to check |
|-------------|---------|--------------|
| **Python** | 3.11+ | `python3 --version` or `python --version` |
| **Node.js** (for MCP Inspector only) | 18+ | `node --version` |
| **Network** | Outbound HTTPS | Can reach publisher API and (if used) LiteLLM/OpenAI |

**Run these before starting:**

```bash
python3 --version   # e.g. Python 3.11.6
node --version      # optional; e.g. v20.x for MCP Inspector
curl -sI https://example.com | head -1   # e.g. HTTP/2 200
```

**Infrastructure limitations (open-source Fairfetch)**

| Limitation | Meaning |
|------------|--------|
| **URL allowlist** | Only **public HTTP/HTTPS** URLs. Private IPs, `localhost`, and cloud metadata URLs (e.g. `169.254.169.254`) are rejected with `400 url_blocked`. |
| **No built-in rate limiting** | The open-source server does not throttle by IP or key; deploy behind a reverse proxy or use Fairfetch Premium for production rate limits. |
| **Test wallets** | Pre-seeded test wallets (`wallet_test_agent_alpha`, `wallet_test_agent_beta`) exist **only when** the server runs with `FAIRFETCH_TEST_MODE=true`. In production, register via `/wallet/register` or the marketplace. |
| **Summarization** | Requires a configured LLM (e.g. `OPENAI_API_KEY` for LiteLLM). If missing, summary endpoints may return 503; content-only endpoints (e.g. Markdown) still work. |

---

## Why Fairfetch vs scraping

| Scraping | Fairfetch |
|----------|-----------|
| Parse raw HTML, strip ads, handle JS | One call returns clean Markdown |
| No proof of legal access | Ed25519-signed Usage Grant |
| 402/403, CAPTCHAs, blocks | x402 or wallet = predictable access |
| Each agent re-processes the same page | Pre-processed at source (Green AI) |
| Legal risk | Legal indemnity (store grants) |

---

## Option A: MCP integration (recommended)

**Best for:** Claude Desktop, Cursor, or any MCP-compatible client. One config, then use tools from your AI assistant.

### Step 1: Install and run the server

**Input (commands):**

```bash
git clone https://github.com/Fairfetch-co/fairfetch.git
cd fairfetch
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**Expected:** No errors; packages install. Then start the MCP server (e.g. under the Inspector):

```bash
npx @modelcontextprotocol/inspector python -m mcp_server.server
```

**Expected:** Browser opens the MCP Inspector; status shows “Connected” or a transport ready.

**If it fails:**

| Symptom | Cause | Mitigation |
|--------|--------|------------|
| `python3` not found | Python not installed or not on PATH | Install Python 3.11+; use `python` if that’s the command on your system. |
| `npx` not found | Node.js not installed | Install Node 18+ for MCP Inspector; or call the MCP server from your own client without the Inspector. |
| Inspector doesn’t connect | Wrong cwd or transport | Run from repo root; ensure `python -m mcp_server.server` starts without errors. |

### Step 2: Call a tool (example)

In the Inspector: **Tools** → pick **fetch_article_markdown** → set `url` to `https://example.com` → **Run**.

**Example input (JSON):**

```json
{ "url": "https://example.com" }
```

**Example output (shortened):**

```text
# Example Domain
This domain is for use in documentation examples...
```

If you see Markdown content, the MCP server and content path work.

### Step 3: Add to Claude Desktop or Cursor

**Claude Desktop (macOS):** Edit `~/Library/Application Support/Claude/claude_desktop_config.json`.

**Cursor:** Create or edit `.cursor/mcp.json` in your project root.

**Example config (replace the path with your actual fairfetch repo path):**

```json
{
  "mcpServers": {
    "fairfetch": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/fairfetch",
      "env": { "FAIRFETCH_TEST_MODE": "true" }
    }
  }
}
```

Restart Claude or Cursor. You can then ask: “Summarize the article at https://example.com” or “Get verified facts from https://publisher.com/article”.

### MCP tools and resources

| Tool | Input | Returns |
|------|-------|--------|
| `get_site_summary` | `url`, optional `usage` | Title, author, summary, signature, usage_grant |
| `fetch_article_markdown` | `url` | Clean Markdown |
| `get_verified_facts` | `url`, optional `usage` | Full JSON-LD knowledge packet + lineage + grant |

| Resource URI | Returns |
|---------------|--------|
| `fairfetch://config` | Server config (version, model, public key, formats) |
| `fairfetch://public-key` | Ed25519 public key for signature verification |

The optional `usage` parameter sets the usage category (`summary`, `rag`, `research`, `training`, `commercial`) and thus pricing tier and compliance level on the grant.

---

## Option B: REST API integration

**Best for:** Custom agents, scripts, or non-MCP clients. All operations are HTTP.

### Step 1: Get pricing (no payment) — expect 402

**Request:**

```bash
curl -s "http://localhost:8402/content/fetch?url=https://example.com"
```

**Example response (402):**

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

Only **public HTTP/HTTPS** URLs are allowed. Private IPs and cloud metadata URLs return **400** with `{"error": "url_blocked", "detail": "The requested URL is not allowed."}`.

### Step 2a: Pay with one-time token (x402)

**Request:**

```bash
curl -s -H "X-PAYMENT: test_paid_fairfetch" \
     -H "Accept: application/ai-context+json" \
     "http://localhost:8402/content/fetch?url=https://example.com&usage=rag"
```

**Example response (200):** JSON-LD body with `articleBody`, `fairfetch:usageGrant`, etc., and headers such as `X-FairFetch-License-ID`, `X-PAYMENT-RECEIPT`, `X-FairFetch-Payment-Method: x402`.

### Step 2b: Pay with wallet (no 402 round-trip)

**Request:**

```bash
curl -s -H "X-WALLET-TOKEN: wallet_test_agent_alpha" \
     -H "Accept: text/markdown" \
     "http://localhost:8402/content/fetch?url=https://example.com"
```

**Example response (200):** Markdown body; headers include `X-FairFetch-Payment-Method: wallet`, `X-FairFetch-Wallet-Balance: 99000`, `X-PAYMENT-RECEIPT: ff_...`.

Test wallets are available only when the server runs with `FAIRFETCH_TEST_MODE=true`. In production, register a wallet first (see below).

---

## Payment: x402 vs wallet

| | x402 (one-time) | Wallet (pre-funded) |
|---|------------------|----------------------|
| **First request** | 402 → pay → retry → content | Content immediately |
| **Round-trips** | 2 | 1 |
| **Header** | `X-PAYMENT: <proof>` | `X-WALLET-TOKEN: <token>` |
| **Best for** | Discovery, occasional use | High-volume production |

### Wallet registration and management (production)

**Register (example):**

```bash
curl -X POST "http://localhost:8402/wallet/register?owner=MyAgent&initial_balance=100000"
```

**Example response:**

```json
{
  "wallet_token": "wallet_abc123...",
  "owner": "MyAgent",
  "balance": 100000,
  "created_at": "...",
  "usage": "Include this token in the X-WALLET-TOKEN header..."
}
```

**Check balance:**

```bash
curl "http://localhost:8402/wallet/balance?token=wallet_abc123..."
```

**Top up:**

```bash
curl -X POST "http://localhost:8402/wallet/topup?token=wallet_abc123...&amount=50000"
```

---

## Failure points & mitigations

| Status / symptom | Likely cause | What to do |
|------------------|--------------|------------|
| **400** `url_blocked` | URL is private IP, metadata, or non-HTTP | Use only public `http://` or `https://` URLs. |
| **402** (no payment) | No `X-PAYMENT` or `X-WALLET-TOKEN` | Add payment header; in test use `X-PAYMENT: test_paid_fairfetch` or a valid wallet token. |
| **402** `wallet_error: insufficient_balance` | Wallet balance &lt; request price | Top up the wallet or use a different wallet/token. |
| **402** `verification_error` | Invalid or expired payment proof | Retry with a fresh payment proof or wallet token. |
| **502** `upstream_fetch_failed` | Publisher’s server or target URL unreachable | Retry later; check target URL is public and reachable. |
| **503** `summarization_unavailable` | LLM not configured (e.g. no API key) | Use `Accept: text/markdown` for content without summary, or configure LiteLLM. |
| **Connection refused** | Fairfetch server not running or wrong port | Start the API (e.g. `make dev`) and use the correct base URL and port. |
| **CORS errors** (browser) | Origin not allowed (production) | Server allows only `https://{publisher_domain}` when not in test mode; call from that origin or from a non-browser client. |

**Example: handling 402 in code**

```python
if resp.status_code == 402:
    data = resp.json()
    if data.get("wallet_error") == "insufficient_balance":
        raise Exception(f"Wallet balance too low: {data['wallet_balance']}, need {data['amount_required']}")
    raise Exception(f"Payment required: {data['accepts']}")
```

---

## Verifying Usage Grants

Every successful response includes a **Usage Grant** (in the body as `fairfetch:usageGrant` and/or in the header `X-FairFetch-License-ID`). Store it as proof of legal access.

### Quick verification (Python)

```python
from interfaces.license_provider import UsageGrant

grant = UsageGrant.model_validate(grant_data)  # from JSON body or reconstruct from header + hash
print(grant.verify())  # True if signature valid
```

### Manual verification (any language)

The signed payload is:

```text
{grant_id}|{content_url}|{content_hash}|{license_type}|{usage_category}|{granted_to}|{granted_at}
```

Use the publisher’s public key (e.g. from `fairfetch://public-key` or response headers) and verify the signature with an Ed25519 library.

---

## Content negotiation & detection

**Accept header → response format:**

| Accept | Response |
|--------|----------|
| `application/ai-context+json` | Full JSON-LD knowledge packet + lineage + grant |
| `application/ld+json` | JSON-LD article with signature |
| `text/markdown` | Markdown only (fastest) |
| `application/json` | Default JSON |

**Detecting Fairfetch-enabled sites:** Prefer the official API over scraping when you see:

1. `/.well-known/llms.txt` — AI policy file
2. `Link` header with `rel="ai-content-api"` — API endpoint
3. `X-FairFetch-Preferred-Access: mcp+json-ld` — preference for API use

Example (Python): HEAD the URL and check for `X-FairFetch-Preferred-Access` or `Link` containing `ai-content-api`; if present, use the Fairfetch API URL from `Link` or llms.txt instead of scraping.

---

## End-to-end example: RAG pipeline

**Scenario:** Answer a question using multiple Fairfetch sources and keep grants for compliance.

**Example flow:**

1. Request content from each source URL with `X-PAYMENT` or `X-WALLET-TOKEN` and `Accept: application/ai-context+json`.
2. On 200, collect `articleBody` (or equivalent) and append to context; collect `X-FairFetch-License-ID` (or full grant) per URL.
3. Build a prompt: “Based on the following verified sources: … Answer: {query}”.
4. Send the prompt to your LLM.
5. Store the list of grants for the sources used.

**Minimal Python sketch:**

```python
async def rag_with_fairfetch(query: str, source_urls: list[str]) -> tuple[str, list[str]]:
    context_chunks = []
    grants = []
    async with httpx.AsyncClient() as client:
        for url in source_urls:
            resp = await client.get(
                f"{FAIRFETCH_URL}/content/fetch",
                params={"url": url},
                headers={"X-PAYMENT": "test_paid_fairfetch", "Accept": "application/ai-context+json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                context_chunks.append(data.get("articleBody", ""))
                grants.append(resp.headers.get("X-FairFetch-License-ID"))
    context = "\n\n---\n\n".join(context_chunks)
    prompt = f"Based on the following verified sources:\n\n{context}\n\nAnswer: {query}"
    return prompt, grants
```

Use the returned `grants` for audit/compliance.

---

## Python client reference

```python
"""Minimal Fairfetch client for AI agents."""
import httpx

FAIRFETCH_URL = "http://localhost:8402"
WALLET_TOKEN = "wallet_test_agent_alpha"   # or None to use X-PAYMENT
PAYMENT_TOKEN = "test_paid_fairfetch"

async def fetch_article(url: str, usage: str = "summary", wallet_token: str | None = None) -> dict:
    headers = {"Accept": "application/ai-context+json"}
    if wallet_token:
        headers["X-WALLET-TOKEN"] = wallet_token
    else:
        headers["X-PAYMENT"] = PAYMENT_TOKEN

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FAIRFETCH_URL}/content/fetch",
            params={"url": url, "usage": usage},
            headers=headers,
        )
        if resp.status_code == 402:
            data = resp.json()
            if data.get("wallet_error") == "insufficient_balance":
                raise Exception(f"Wallet low: have {data['wallet_balance']}, need {data['amount_required']}")
            raise Exception(f"Payment required: {data['accepts']}")
        resp.raise_for_status()
        return {
            "content": resp.json(),
            "payment_method": resp.headers.get("X-FairFetch-Payment-Method"),
            "wallet_balance": resp.headers.get("X-FairFetch-Wallet-Balance"),
            "license_id": resp.headers.get("X-FairFetch-License-ID"),
            "usage_category": resp.headers.get("X-FairFetch-Usage-Category"),
            "payment_receipt": resp.headers.get("X-PAYMENT-RECEIPT"),
        }
```

---

## TypeScript / Node.js snippet

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
    licenseId: resp.headers.get("X-FairFetch-License-ID"),
    paymentReceipt: resp.headers.get("X-PAYMENT-RECEIPT"),
  };
}
```

---

For plain-language concepts and header definitions, see the [Concepts Guide](CONCEPTS.md). For repository and API details, see [GitHub — Fairfetch-co/fairfetch](https://github.com/Fairfetch-co/fairfetch).
