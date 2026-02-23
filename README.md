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

The payment flow works like a toll booth: you ask for content, get told the price, pay, and then receive the content along with a receipt and a legal access grant.

**Step 1 — Ask for content (no payment yet):**

```bash
curl "http://localhost:8402/content/fetch?url=https://example.com&usage=rag"
```

You get back a `402 Payment Required` response — this is not an error, it's a price quote:

```json
{
  "accepts": {
    "price": "2000",
    "asset": "USDC",
    "network": "base",
    "payTo": "0x742d35Cc...",
    "usage_category": "rag",
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
  "message": "This content requires micro-payment via x402..."
}
```

- **`price`** — cost in the smallest unit of USDC (1000 = $0.001). Adjusted by usage tier.
- **`payTo`** — the publisher's wallet address where payment goes.
- **`available_tiers`** — all usage options with their prices, so you can pick the right one.

**Step 2 — Pay and get content:**

```bash
curl -H "X-PAYMENT: test_paid_fairfetch" \
     -H "Accept: text/markdown" \
     "http://localhost:8402/content/fetch?url=https://example.com&usage=rag"
```

The `X-PAYMENT` header carries your payment proof. In production this is a cryptographic token from a real payment. For local testing, any value starting with `test_` works.

You get back `200 OK` with the content and these headers:

```http
X-PAYMENT-RECEIPT: 0x6d8ce1bf2daf...     # Transaction proof (like a bank receipt)
X-FairFetch-License-ID: 47db4290...:k2+w  # Your legal access grant (store this!)
X-FairFetch-Usage-Category: rag           # Confirmed: you paid for RAG usage
X-FairFetch-Compliance-Level: standard    # Compliance tier for this usage
X-FairFetch-Origin-Signature: GllQLb/...  # Publisher's digital signature on the content
X-Content-Hash: sha256:2c449548...        # Fingerprint of the content
```

> [!NOTE]
> For local testing, any `X-PAYMENT` value starting with `test_` is accepted.
> The magic token `test_paid_fairfetch` always works. No real wallet or money needed.

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

A **Usage Grant** is your proof of legal access — think of it as a digitally signed receipt that says *"this AI agent paid for and was authorized to use this content, for this specific purpose, on this date."*

Every field is included in the digital signature, so nothing can be changed after the fact:

```json
{
  "grant_id": "a1b2c3d4...",
  "content_url": "https://publisher.com/article",
  "content_hash": "sha256:2c449548...",
  "license_type": "publisher-terms",
  "usage_category": "rag",
  "granted_to": "0xPayerWallet...",
  "granted_at": "2026-02-22T12:00:00Z",
  "signature": {
    "algorithm": "Ed25519",
    "signature": "GllQLb/V4Vd+SuTY9Gk...",
    "publicKey": "J2nlmFsgoUtF3Avdmkt..."
  }
}
```

| Field | What It Means |
|-------|---------------|
| `grant_id` | A unique ID for this specific access event — like an order number. |
| `content_url` | The article or page that was accessed. |
| `content_hash` | A fingerprint of the exact content delivered, proving what was received. |
| `license_type` | The terms set by the publisher (e.g. "publisher-terms", "research-only"). |
| `usage_category` | What the AI agent said it would use the content for (e.g. "rag", "training"). This is locked in — you can't pay for "summary" and later claim you used it for "training." |
| `granted_to` | The wallet or identity of who paid. |
| `granted_at` | When the access happened. |
| `signature` | The publisher's digital signature covering all the fields above. Like a notarized stamp — unforgeable and tamper-proof. The `publicKey` lets anyone independently verify it. |

> [!IMPORTANT]
> **Store your grants.** If a publisher ever questions whether you had permission to use their content, the grant is your courtroom-ready evidence. No he-said-she-said — just math.

<details>
<summary><strong>How to verify a grant</strong></summary>

The signature covers all grant fields joined with `|`. You can verify it with any Ed25519 library:

```python
from nacl.signing import VerifyKey
import base64

public_key = base64.b64decode("J2nlmFsgoUtF3Avdmkt...")
signature  = base64.b64decode("GllQLb/V4Vd+SuTY9Gk...")

payload = "a1b2c3d4...|https://publisher.com/article|sha256:2c449548...|publisher-terms|rag|0xPayerWallet...|2026-02-22T12:00:00Z"

VerifyKey(public_key).verify(payload.encode(), signature)  # raises if tampered
```

Or use the built-in helper:

```python
from interfaces.license_provider import UsageGrant

grant = UsageGrant.model_validate(grant_data)
print(f"Valid: {grant.verify()}")
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

## 📋 Response Headers Explained

Every successful response includes these headers. Think of them as a receipt and proof-of-origin attached to the content:

| Header | What It Means | Example Value |
|--------|---------------|---------------|
| `X-Data-Origin-Verified` | "This content came directly from the publisher, not a third party." Required by the EU AI Act for provenance tracking. | `true` |
| `X-AI-License-Type` | The terms under which the publisher is licensing this content to you. | `publisher-terms` |
| `X-FairFetch-Usage-Category` | What you told us you're using the content for. This is locked into your Usage Grant. | `rag` |
| `X-FairFetch-Compliance-Level` | How strict the rules are for your chosen usage. Higher-impact uses (like training) require stricter compliance. | `standard` |
| `X-FairFetch-Origin-Signature` | A digital fingerprint proving the publisher's server produced this exact content. Like a notary stamp — tamper-proof. | `GllQLb/V4Vd+Su...` (base64) |
| `X-FairFetch-License-ID` | Your Usage Grant reference. Store this — it's your proof of legal access if questions arise later. Format: `grant_id:signature_prefix`. | `47db4290...:k2+wXE3x...` |
| `X-Content-Hash` | A fingerprint of the content body itself, so you can verify nothing was altered in transit. | `sha256:2c449548...` |
| `X-PAYMENT-RECEIPT` | Proof that payment was settled. In test mode this is a simulated transaction hash. In production, a real on-chain transaction ID. | `0x6d8ce1bf...` |
| `X-Fairfetch-Version` | Protocol version, so clients know which Fairfetch spec they're talking to. | `0.2` |

> [!TIP]
> For a plain-language explanation of all Fairfetch concepts, headers, and terminology, see the [Concepts Guide](docs/CONCEPTS.md).

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
| [**Concepts (Plain Language)**](docs/CONCEPTS.md) | What every header, value, and term means — no jargon |
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
