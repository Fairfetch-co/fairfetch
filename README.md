<div align="center">

# Fairfetch

**The web protocol for the agentic economy.**

[![CI](https://github.com/Fairfetch-co/fairfetch/actions/workflows/ci.yml/badge.svg)](https://github.com/Fairfetch-co/fairfetch/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-30173d.svg)](https://docs.astral.sh/ruff/)
[![MCP](https://img.shields.io/badge/protocol-MCP-7c3aed.svg)](https://modelcontextprotocol.io)
[![x402](https://img.shields.io/badge/payments-x402-22c55e.svg)](https://www.x402.org/)
[![EU AI Act](https://img.shields.io/badge/compliance-EU%20AI%20Act%202026-0055a4.svg)](#-compliance-headers)

<br />

An open-source infrastructure layer that lets publishers serve machine-ready
content directly to AI agents — replacing illegal scraping with a paid, signed,
legally verifiable pipeline.

[Quick Start](#-quick-start) · [Publisher Guide](docs/PUBLISHER_GUIDE.md) · [AI Agent Guide](docs/AI_AGENT_GUIDE.md) · [Development](DEVELOPMENT.md)

</div>

<br />

## The Problem

Every day, AI companies scrape the same web pages **thousands of times**, burning compute, violating copyright, and creating legal liability for everyone involved.

Fairfetch solves all three problems at once:

<table>
<tr>
<td width="33%" valign="top">

### 🌱 Green AI

**Pre-process once at the source.**

Publishers convert HTML to clean Markdown and generate summaries once. AI agents fetch the result — eliminating the redundant 1,000x compute cost of web crawling.

</td>
<td width="33%" valign="top">

### 🛡️ Legal Safe Harbor

**Cryptographic proof of legal access.**

Every request produces an Ed25519-signed **Usage Grant** — courtroom-grade evidence of authorized usage. Publishers set the terms. AI companies sleep at night.

</td>
<td width="33%" valign="top">

### 🔗 Direct Pipeline

**Cut out the middleman crawlers.**

Edge workers steer known bots (GPTBot, CCBot) from raw HTML toward the official API, converting "illegal" crawls into paid, legal API hits in real time.

</td>
</tr>
</table>

<br />

## Two Parties, One Protocol

<table>
<tr>
<th></th>
<th>📰 Publisher (Content Provider)</th>
<th>🤖 AI Agent (Consumer)</th>
</tr>
<tr>
<td><strong>Goal</strong></td>
<td>Monetize content, stop illegal scraping</td>
<td>Get clean content with legal cover</td>
</tr>
<tr>
<td><strong>Deploys</strong></td>
<td>Edge worker + Fairfetch API</td>
<td>MCP client or REST calls</td>
</tr>
<tr>
<td><strong>Gets</strong></td>
<td>Revenue, analytics, legal control</td>
<td>Markdown, signatures, Usage Grants</td>
</tr>
<tr>
<td><strong>Guide</strong></td>
<td><a href="docs/PUBLISHER_GUIDE.md"><strong>Publisher Onboarding →</strong></a></td>
<td><a href="docs/AI_AGENT_GUIDE.md"><strong>AI Agent Integration →</strong></a></td>
</tr>
</table>

<br />

## 🚀 Quick Start

```bash
git clone https://github.com/Fairfetch-co/fairfetch.git
cd fairfetch
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
make setup-dev

# Start the development server
make dev
```

<details>
<summary><strong>For Publishers — Verify your setup</strong></summary>

```bash
# Health check
curl http://localhost:8402/health

# Simulate an AI agent paying for content
curl -v -H "X-PAYMENT: test_paid_fairfetch" \
     -H "Accept: application/ai-context+json" \
     "http://localhost:8402/content/fetch?url=https://example.com"

# Response headers include the three pillars:
#   X-FairFetch-Origin-Signature  → Legal (content is signed)
#   X-FairFetch-License-ID        → Indemnity (Usage Grant issued)
#   X-PAYMENT-RECEIPT              → Payment (settlement confirmed)

# Simulate a scraper — see the steering headers
curl -v -H "X-PAYMENT: test_paid_fairfetch" \
     -H "User-Agent: GPTBot/1.0" \
     -H "Accept: text/html" \
     "http://localhost:8402/content/fetch?url=https://example.com" 2>&1 \
     | grep "X-FairFetch"
```

</details>

<details>
<summary><strong>For AI Agents — Get content in 30 seconds</strong></summary>

**Option 1 — MCP (zero code):**

```bash
npx @modelcontextprotocol/inspector python -m mcp_server.server
# → Connect → Tools → call fetch_article_markdown with url: "https://example.com"
```

**Option 2 — REST API:**

```bash
curl -H "X-PAYMENT: test_paid_fairfetch" \
     -H "Accept: text/markdown" \
     "http://localhost:8402/content/fetch?url=https://example.com"
```

**Option 3 — Python client:**

```python
import httpx, asyncio

async def main():
    async with httpx.AsyncClient() as c:
        r = await c.get(
            "http://localhost:8402/content/fetch",
            params={"url": "https://example.com"},
            headers={
                "X-PAYMENT": "test_paid_fairfetch",
                "Accept": "application/ai-context+json",
            },
        )
        print(r.json())
        print(r.headers["X-FairFetch-License-ID"])

asyncio.run(main())
```

</details>

> [!TIP]
> Every response includes the **Green + Legal + Indemnity** triple:
> clean Markdown content, an `X-FairFetch-Origin-Signature` header, and an `X-FairFetch-License-ID` header.

<br />

## 🏗️ Architecture

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

<br />

## 💳 The x402 Payment Flow

```
Agent                         Fairfetch                   Facilitator
  |                               |                            |
  |  GET /content/fetch?url=...   |                            |
  |  &usage=rag                   |                            |
  |------------------------------>|                            |
  |                               |                            |
  |  402 Payment Required         |                            |
  |  { accepts: { price (2x),    |                            |
  |    usage_category: "rag" },   |                            |
  |    available_tiers: {...} }   |                            |
  |<------------------------------|                            |
  |                               |                            |
  |  GET + X-PAYMENT: <proof>     |                            |
  |------------------------------>|                            |
  |                               |  POST /settle              |
  |                               |------------------------->  |
  |                               |       { valid, tx_hash }   |
  |                               |<-------------------------  |
  |                               |                            |
  |  200 OK + Content             |                            |
  |  X-PAYMENT-RECEIPT: 0x...     |                            |
  |  X-FairFetch-License-ID: ...  |                            |
  |  X-FairFetch-Usage-Category:  |                            |
  |    rag                        |                            |
  |  X-FairFetch-Compliance-Level:|                            |
  |    standard                   |                            |
  |<------------------------------|                            |
```

> [!NOTE]
> For local testing, any `X-PAYMENT` value starting with `test_` is accepted.
> The magic token `test_paid_fairfetch` always works.

<br />

## 📊 Usage Categories & Tiered Pricing

Not all content usage is equal. Fairfetch defines **usage categories** that control what an AI agent is permitted to do with the content, with escalating compliance requirements and pricing:

| Category | Compliance | Price Multiplier | Use Case |
|----------|-----------|-----------------|----------|
| `summary` | Standard | 1x | Display a short summary or snippet |
| `rag` | Standard | 2x | Retrieval-Augmented Generation / search grounding |
| `research` | Elevated | 3x | Academic or internal research use |
| `training` | Strict | 5x | Model fine-tuning or pre-training |
| `commercial` | Strict | 10x | Redistribution or commercial derivative works |

> [!IMPORTANT]
> The `usage` parameter is specified via query param (`?usage=rag`), HTTP header (`X-USAGE-CATEGORY: training`), or MCP tool argument. It determines the effective price and the compliance level recorded in the Usage Grant.

```bash
# Fetch for RAG (2x base price)
curl -H "X-PAYMENT: test_paid_fairfetch" \
     "http://localhost:8402/content/fetch?url=https://example.com&usage=rag"

# Fetch for training (5x base price, strict compliance)
curl -H "X-PAYMENT: test_paid_fairfetch" \
     "http://localhost:8402/content/fetch?url=https://example.com&usage=training"

# The 402 response includes all available tiers and their prices
curl "http://localhost:8402/content/fetch?url=https://example.com"
```

Every 402 response includes an `available_tiers` object showing the price for each category, so agents can choose the appropriate tier for their needs.

<br />

## 🔐 Usage Grants (Legal Indemnity)

A Usage Grant is an Ed25519-signed token proving legal content access under a specific usage category:

```json
{
  "grant_id": "a1b2c3d4...",
  "content_url": "https://publisher.com/article",
  "content_hash": "sha256:...",
  "license_type": "publisher-terms",
  "usage_category": "rag",
  "granted_to": "0xPayerWallet...",
  "granted_at": "2026-02-22T12:00:00Z",
  "signature": {
    "algorithm": "Ed25519",
    "signature": "...",
    "publicKey": "..."
  }
}
```

The `usage_category` field is part of the cryptographic signature, so it cannot be altered after issuance. An agent granted `summary` access cannot claim `training` rights — a new grant with appropriate pricing is required.

<details>
<summary><strong>How to verify a grant locally</strong></summary>

```bash
# Get the public key via MCP resource
# In MCP Inspector: Resources → fairfetch://public-key

# Or extract it from any response's grant signature (the publicKey field)

# The grant's signature covers:
#   grant_id | content_url | content_hash | license_type | usage_category | granted_to | granted_at
# Verify using any Ed25519 library against the public key
```

</details>

<br />

## 🤖 MCP Server (Direct Pipeline)

Three tools for AI agents (all accept an optional `usage` parameter for tier selection):

| Tool | Description |
|------|-------------|
| `get_site_summary` | Summary + origin signature + usage grant |
| `fetch_article_markdown` | Clean Markdown (Green AI) |
| `get_verified_facts` | Full knowledge packet + lineage + grant |

<details>
<summary><strong>Test with MCP Inspector</strong></summary>

```bash
make dev-mcp
# Opens the Inspector UI in your browser. Click Connect → Tools → call any tool.
```

</details>

<details>
<summary><strong>Add to Claude Desktop</strong></summary>

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

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

</details>

<details>
<summary><strong>Add to Cursor IDE</strong></summary>

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

</details>

<br />

## 🚧 Anti-Scraper Bot Steering

When a known crawler (GPTBot, CCBot, etc.) requests raw HTML, edge workers inject headers steering it to the legal path:

```http
X-FairFetch-Preferred-Access: mcp+json-ld
X-FairFetch-LLMS-Txt: /.well-known/llms.txt
X-FairFetch-MCP-Endpoint: /mcp
Link: </.well-known/llms.txt>; rel="ai-policy", </mcp>; rel="ai-content-api"
```

The `/health` endpoint reports `scraper_interceptions` — the count of crawler requests steered, showing publishers the conversion rate.

Edge boilerplates are provided for **Cloudflare Workers**, **AWS CloudFront Lambda@Edge**, **Fastly Compute@Edge**, and **Akamai EdgeWorkers**.

<br />

## 📋 Compliance Headers

| Header | Description |
|--------|-------------|
| `X-Data-Origin-Verified` | EU AI Act origin attestation |
| `X-AI-License-Type` | `publisher-terms` · `commercial` · `research-only` · `opt-out` |
| `X-FairFetch-Usage-Category` | `summary` · `rag` · `research` · `training` · `commercial` |
| `X-FairFetch-Compliance-Level` | `standard` · `elevated` · `strict` |
| `X-FairFetch-Origin-Signature` | Ed25519 signature of content body |
| `X-FairFetch-License-ID` | Usage Grant compact identifier |
| `X-Content-Hash` | `sha256:<hex>` hash of content |
| `X-Fairfetch-Version` | Protocol version (`0.2`) |

<br />

## 🧩 Open Core Model

| Layer | Open Source (this repo) | Cloud (Commercial) |
|-------|------------------------|-------------------|
| `interfaces/` | Abstract standard | Same |
| `core/` | HTML-to-MD, signing | Same |
| `api/` · `mcp_server/` | REST + MCP protocol | Same |
| `payments/` | Mock facilitator | Real EIP-3009 settlement |
| `compliance/` | Headers, lineage | Same |
| `plugins/` | Placeholder stubs | Managed Clearinghouse |

> The open-source repo is **fully functional** for local development and testing.
> The commercial cloud layer adds real on-chain payments, publisher-verified
> key management, and persistent Usage Grant audit trails.

<br />

## 📁 Project Structure

```
fairfetch/
├── docs/                    # Guides for publishers & AI agents
│   ├── PUBLISHER_GUIDE.md   # CDN deployment & onboarding
│   └── AI_AGENT_GUIDE.md    # MCP/REST integration for agents
├── interfaces/              # Open Standard (abstract bases)
│   ├── facilitator.py       # BaseFacilitator
│   ├── summarizer.py        # BaseSummarizer
│   └── license_provider.py  # BaseLicenseProvider + UsageGrant + UsageCategory
├── core/                    # Green AI layer
│   ├── converter.py         # HTML → Markdown (trafilatura)
│   ├── summarizer.py        # LiteLLM implementation
│   ├── knowledge_packet.py  # JSON-LD builder
│   └── signatures.py        # Ed25519 signing
├── mcp_server/              # Direct Pipeline (MCP)
│   └── server.py            # FastMCP tools + resources
├── api/                     # Direct Pipeline (REST)
│   ├── main.py              # FastAPI app
│   ├── routes.py            # Endpoints + triple validation
│   ├── negotiation.py       # Content negotiation + bot steering
│   └── dependencies.py      # FairFetchConfig + DI
├── payments/                # x402 micro-payments
│   ├── x402.py              # Middleware with grant issuance
│   ├── mock_facilitator.py  # Local test facilitator
│   └── mock_license_facilitator.py
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
├── tests/                   # 106 tests · 98% coverage
├── .github/workflows/       # CI pipeline
├── openapi.yaml             # REST API spec
├── mcp.json                 # MCP Inspector config
├── pyproject.toml            # Package config
├── Makefile                 # Dev commands
└── LICENSE                  # Apache 2.0
```

<br />

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FAIRFETCH_TEST_MODE` | `true` | Enable mock facilitator + grants |
| `FAIRFETCH_PUBLISHER_WALLET` | `0x000...` | EVM wallet for payments |
| `FAIRFETCH_PUBLISHER_DOMAIN` | `localhost` | Publisher domain |
| `FAIRFETCH_CONTENT_PRICE` | `1000` | Price in smallest USDC unit |
| `FAIRFETCH_SIGNING_KEY` | *(generated)* | Ed25519 private key (b64) |
| `FAIRFETCH_LICENSE_TYPE` | `publisher-terms` | Default license |
| `FAIRFETCH_DEFAULT_USAGE_CATEGORY` | `summary` | Default usage tier for pricing |
| `FAIRFETCH_ENABLE_GRANTS` | `true` | Issue Usage Grants |
| `FAIRFETCH_PREFERRED_ACCESS` | `true` | Inject bot-steering headers |
| `LITELLM_MODEL` | `gpt-4o-mini` | LLM for summarization |

<br />

## 📖 Detailed Guides

| Guide | What's Inside |
|-------|---------------|
| [**Publisher Onboarding**](docs/PUBLISHER_GUIDE.md) | CDN deployment for Cloudflare, CloudFront, Fastly, Akamai, Nginx |
| [**AI Agent Integration**](docs/AI_AGENT_GUIDE.md) | MCP for Claude/Cursor, REST clients (Python & TS), Usage Grant verification |
| [**Development**](DEVELOPMENT.md) | Local dev setup, testing the three pillars, architecture decisions |
| [**Contributing**](CONTRIBUTING.md) | How to contribute, CLA, code standards |

<br />

## 📄 License

[Apache 2.0](LICENSE) — use it freely, commercially or otherwise.

<br />

---

<div align="center">

**[Website](https://fairfetch.co)** · **[Docs](docs/)** · **[Issues](https://github.com/Fairfetch-co/fairfetch/issues)** · **[Discussions](https://github.com/Fairfetch-co/fairfetch/discussions)**

<sub>Built with conviction that AI and publishers can thrive together.</sub>

</div>
