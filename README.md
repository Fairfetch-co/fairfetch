# Fairfetch

**The open standard for AI-to-Publisher content access.**

Fairfetch is an open-source infrastructure layer that lets publishers serve
machine-ready content directly to AI agents — replacing illegal scraping with
a paid, signed, legally verifiable pipeline.

---

## Why Fairfetch Exists

Every day, AI companies scrape the same web pages thousands of times, burning
compute, violating copyright, and creating legal liability for everyone
involved. Fairfetch solves all three problems at once.

### 1. Green AI Infrastructure

> Pre-process once at the source. Eliminate the redundant 1,000x compute cost of web crawling.

Publishers convert HTML to clean Markdown and generate summaries **once**.
AI agents fetch the result instead of each independently parsing raw HTML,
stripping ads, and running extraction pipelines. This is a direct reduction
in global AI inference cost and energy consumption.

### 2. Legal Indemnity (Safe Harbor)

> Cryptographic "Usage Grants" give AI companies proof of legal access.

Every successful content request produces a **Usage Grant** — an Ed25519-signed
token that records what was accessed, when, by whom, and under what license.
AI companies store these grants as courtroom-grade evidence of authorized usage,
removing the fear of copyright litigation. Publishers control the terms.

### 3. Direct-to-Source Economy (Anti-Scraper)

> A machine-readable layer that bypasses middleman crawlers, connecting AI agents directly to publishers.

Fairfetch actively steers known crawlers (GPTBot, CCBot, etc.) away from raw
HTML scraping and toward the official API. Edge workers inject `Link` headers
pointing to `/llms.txt` and the MCP endpoint, converting "illegal" crawls
into "legal" API hits — and publishers see the conversion rate in real time.

---

## Two Parties, One Protocol

Fairfetch connects two parties through a shared open standard:

| | **Publisher** (Content Provider) | **AI Agent** (Consumer) |
|---|---|---|
| **Goal** | Monetize content, stop illegal scraping | Get clean content with legal cover |
| **Deploys** | Edge worker + Fairfetch API | MCP client or REST calls |
| **Gets** | Revenue, analytics, legal control | Markdown, signatures, Usage Grants |
| **Guide** | [Publisher Onboarding →](docs/PUBLISHER_GUIDE.md) | [AI Agent Integration →](docs/AI_AGENT_GUIDE.md) |

---

## Quick Start

```bash
git clone https://github.com/Fairfetch-co/fairfetch.git
cd fairfetch
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
make setup-dev

# Start the development server
make dev
```

### For Publishers: Verify Your Setup

```bash
# Health check — confirm the server is running
curl http://localhost:8402/health

# Simulate an AI agent paying for your content
curl -v -H "X-PAYMENT: test_paid_fairfetch" \
     -H "Accept: application/ai-context+json" \
     "http://localhost:8402/content/fetch?url=https://example.com"

# Check the response headers for the three pillars:
#   X-FairFetch-Origin-Signature  (Legal — your content is signed)
#   X-FairFetch-License-ID        (Indemnity — Usage Grant issued)
#   X-PAYMENT-RECEIPT              (Payment — settlement confirmed)

# Simulate a scraper and see the steering headers
# (X-PAYMENT is required to pass the x402 middleware before steering kicks in)
curl -v -H "X-PAYMENT: test_paid_fairfetch" \
     -H "User-Agent: GPTBot/1.0" \
     -H "Accept: text/html" \
     "http://localhost:8402/content/fetch?url=https://example.com" 2>&1 \
     | grep "X-FairFetch"
```

### For AI Agents: Get Content in 30 Seconds

**Option 1 — MCP (zero code):**

```bash
# Test with MCP Inspector (opens in browser)
npx @modelcontextprotocol/inspector python -m mcp_server.server
# → Connect → Tools → call fetch_article_markdown with url: "https://example.com"
```

**Option 2 — REST API (curl):**

```bash
# Get clean Markdown
curl -H "X-PAYMENT: test_paid_fairfetch" \
     -H "Accept: text/markdown" \
     "http://localhost:8402/content/fetch?url=https://example.com"

# Get full knowledge packet with Usage Grant
curl -H "X-PAYMENT: test_paid_fairfetch" \
     -H "Accept: application/ai-context+json" \
     "http://localhost:8402/content/fetch?url=https://example.com"
```

**Option 3 — Python client (3 lines):**

```python
import httpx, asyncio

async def main():
    async with httpx.AsyncClient() as c:
        r = await c.get(
            "http://localhost:8402/content/fetch",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "test_paid_fairfetch", "Accept": "application/ai-context+json"},
        )
        print(r.json())           # content + summary + lineage
        print(r.headers["X-FairFetch-License-ID"])  # your Usage Grant

asyncio.run(main())
```

Every response includes the **Green + Legal + Indemnity** triple:
1. Clean Markdown content (Green)
2. `X-FairFetch-Origin-Signature` header (Legal)
3. `X-FairFetch-License-ID` header (Indemnity)

---

## Architecture

```
                          AI Agent / LLM
                    (ChatGPT, Claude, Perplexity)
                     /                        \
              MCP (stdio)                REST API
                   |                          |
          +--------v--------+    +------------v-----------+
          |   MCP Server    |    |    FastAPI (:8402)      |
          |   (FastMCP)     |    |                         |
          |                 |    |  Content     x402       |
          |  get_summary    |    |  Negotiation Middleware  |
          |  fetch_md       |    |  Bot Steering           |
          |  verified_facts |    |  Usage Grants            |
          +--------+--------+    +------------+------------+
                   |                          |
                   +----------+  +------------+
                              |  |
                   +----------v--v-----------+
                   |      Core Engine        |
                   |    (Green AI Layer)      |
                   |                         |
                   | Converter  Summarizer   |
                   | (trafilat) (LiteLLM)    |
                   | KnowledgePacket (LD)    |
                   | Ed25519 Signatures      |
                   +----------+--------------+
                              |
                   +----------v--------------+
                   |    Interfaces Layer      |
                   |   (Open Standard)        |
                   |                         |
                   | BaseFacilitator          |
                   | BaseSummarizer           |
                   | BaseLicenseProvider      |
                   +-------------------------+
```

## Open Core Model

| Layer | Open Source | Cloud (Commercial) |
|-------|-----------|-------------------|
| `interfaces/` | Abstract standard | Same |
| `core/` | HTML-to-MD, signing | Same |
| `api/`, `mcp_server/` | REST + MCP protocol | Same |
| `payments/` | Mock facilitator | Real EIP-3009 settlement |
| `compliance/` | Headers, lineage | Same |
| `plugins/` | Placeholder stubs | Managed Clearinghouse |

The open-source repo is fully functional for local development and testing.
The commercial cloud layer adds real on-chain payments, publisher-verified
key management, and persistent Usage Grant audit trails.

---

## The x402 Payment Flow

```
Agent                        Fairfetch                   Facilitator
  |                              |                            |
  |  GET /content/fetch?url=...  |                            |
  |----------------------------->|                            |
  |                              |                            |
  |  402 Payment Required        |                            |
  |  { accepts: { price, asset,  |                            |
  |    network, payTo } }        |                            |
  |<-----------------------------|                            |
  |                              |                            |
  |  GET + X-PAYMENT: <proof>    |                            |
  |----------------------------->|                            |
  |                              |  POST /settle              |
  |                              |------------------------->  |
  |                              |       { valid, tx_hash }   |
  |                              |<-------------------------  |
  |                              |                            |
  |  200 OK + Content            |                            |
  |  X-PAYMENT-RECEIPT: 0x...    |                            |
  |  X-FairFetch-License-ID: ... |                            |
  |  X-FairFetch-Origin-Sig: ... |                            |
  |<-----------------------------|                            |
```

For local testing, any `X-PAYMENT` value starting with `test_` is accepted.
The magic token `test_paid_fairfetch` always works.

---

## Usage Grants (Legal Indemnity)

A Usage Grant is an Ed25519-signed token proving legal content access:

```json
{
  "grant_id": "a1b2c3d4...",
  "content_url": "https://publisher.com/article",
  "content_hash": "sha256:...",
  "license_type": "publisher-terms",
  "granted_to": "0xPayerWallet...",
  "granted_at": "2026-02-22T12:00:00Z",
  "signature": { "algorithm": "Ed25519", "signature": "...", "publicKey": "..." }
}
```

Verify locally with the publisher's public key:

```bash
# Get the public key via MCP resource
# In MCP Inspector: Resources → fairfetch://public-key

# Or extract it from any response's grant signature (the publicKey field)

# The grant's signature covers: grant_id|content_url|content_hash|license_type|granted_to|granted_at
# Verify using any Ed25519 library against the public key
```

---

## MCP Server (Direct Pipeline)

Three tools for AI agents:

| Tool | Description |
|------|-------------|
| `get_site_summary` | Summary + origin signature + usage grant |
| `fetch_article_markdown` | Clean Markdown (Green AI) |
| `get_verified_facts` | Full knowledge packet + lineage + grant |

### Test with MCP Inspector

```bash
make dev-mcp
# Opens the Inspector UI in your browser. Click Connect → Tools → call any tool.
```

### Add to Claude Desktop

Edit your Claude Desktop config
(`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

### Add to Cursor IDE

Create `.cursor/mcp.json` in your project root:

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

---

## Anti-Scraper Bot Steering

When a known crawler (GPTBot, CCBot, etc.) requests raw HTML, edge workers
inject headers steering it to the legal path:

```
X-FairFetch-Preferred-Access: mcp+json-ld
X-FairFetch-LLMS-Txt: /.well-known/llms.txt
X-FairFetch-MCP-Endpoint: /mcp
Link: </.well-known/llms.txt>; rel="ai-policy", </mcp>; rel="ai-content-api"
```

The `/health` endpoint reports `scraper_interceptions` — the count of crawler
requests that were steered, showing publishers the conversion rate.

Edge boilerplates are provided for Cloudflare Workers, AWS CloudFront
Lambda@Edge, Fastly Compute@Edge, and Akamai EdgeWorkers.

---

## Compliance Headers

| Header | Description |
|--------|-------------|
| `X-Data-Origin-Verified` | EU AI Act origin attestation |
| `X-AI-License-Type` | `publisher-terms`, `commercial`, `research-only`, `opt-out` |
| `X-FairFetch-Origin-Signature` | Ed25519 signature of content body |
| `X-FairFetch-License-ID` | Usage Grant compact identifier |
| `X-Content-Hash` | `sha256:<hex>` hash of content |
| `X-Fairfetch-Version` | Protocol version (`0.2`) |

---

## Project Structure

```
fairfetch/
├── docs/                    # Guides for publishers & AI agents
│   ├── PUBLISHER_GUIDE.md   # CDN deployment & onboarding
│   └── AI_AGENT_GUIDE.md    # MCP/REST integration for agents
├── interfaces/              # Open Standard (abstract bases)
│   ├── facilitator.py       # BaseFacilitator
│   ├── summarizer.py        # BaseSummarizer
│   └── license_provider.py  # BaseLicenseProvider + UsageGrant
├── core/                    # Green AI layer
│   ├── converter.py         # HTML -> Markdown (trafilatura)
│   ├── summarizer.py        # LiteLLM implementation
│   ├── knowledge_packet.py  # JSON-LD builder
│   └── signatures.py        # Ed25519 signing
├── mcp_server/              # Direct Pipeline (MCP)
│   └── server.py            # FastMCP tools + resources
├── api/                     # Direct Pipeline (REST)
│   ├── main.py              # FastAPI app
│   ├── routes.py            # Endpoints with triple validation
│   ├── negotiation.py       # Content negotiation + bot steering
│   └── dependencies.py      # FairFetchConfig + DI
├── payments/                # x402 micro-payments
│   ├── x402.py              # Middleware with grant issuance
│   ├── mock_facilitator.py  # Local test facilitator
│   └── mock_license_facilitator.py  # Mock grants
├── compliance/              # EU AI Act 2026
│   ├── headers.py           # Standardized headers
│   ├── lineage.py           # Data lineage tracking
│   └── copyright.py         # Copyright opt-out log
├── plugins/                 # Cloud extension point
│   └── cloud_adapter.py     # Managed Clearinghouse stub
├── deploy/                  # Edge boilerplates
│   ├── cloudflare/          # Workers (TS)
│   ├── cloudfront/          # Lambda@Edge (Python)
│   ├── fastly/              # Compute@Edge (Rust)
│   └── akamai/              # EdgeWorkers (JS)
├── scripts/                 # Dev scripts
│   └── dev_server.py        # Local launcher (make dev)
├── tests/                   # Pytest suite (106 tests, 98% coverage)
├── .github/workflows/       # CI pipeline
├── openapi.yaml             # REST API spec
├── mcp.json                 # MCP Inspector config
├── pyproject.toml           # Package config
├── Makefile                 # Dev commands
└── LICENSE                  # Apache 2.0
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FAIRFETCH_TEST_MODE` | `true` | Enable mock facilitator + grants |
| `FAIRFETCH_PUBLISHER_WALLET` | `0x000...` | EVM wallet for payments |
| `FAIRFETCH_PUBLISHER_DOMAIN` | `localhost` | Publisher domain |
| `FAIRFETCH_CONTENT_PRICE` | `1000` | Price in smallest USDC unit |
| `FAIRFETCH_SIGNING_KEY` | (generated) | Ed25519 private key (b64) |
| `FAIRFETCH_LICENSE_TYPE` | `publisher-terms` | Default license |
| `FAIRFETCH_ENABLE_GRANTS` | `true` | Issue Usage Grants |
| `FAIRFETCH_PREFERRED_ACCESS` | `true` | Inject bot-steering headers |
| `LITELLM_MODEL` | `gpt-4o-mini` | LLM for summarization |

## Detailed Guides

- **[Publisher Onboarding Guide](docs/PUBLISHER_GUIDE.md)** — Step-by-step CDN deployment for Cloudflare, AWS CloudFront, Fastly, Akamai, and Nginx
- **[AI Agent Integration Guide](docs/AI_AGENT_GUIDE.md)** — MCP setup for Claude/Cursor, REST client examples in Python and TypeScript, Usage Grant verification, RAG pipeline example
- **[Development Guide](DEVELOPMENT.md)** — Local dev setup, testing the three pillars, architecture decisions

## License

Apache 2.0 - see [LICENSE](LICENSE).
