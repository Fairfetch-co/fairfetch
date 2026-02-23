# Fairfetch Concepts Guide

A plain-language explanation of how Fairfetch works, what the headers and values
mean, and why they exist. No cryptography degree required.

---

## The Big Picture

Today, AI companies scrape websites to get content. This is:

- **Wasteful** — hundreds of bots process the same page independently
- **Legally risky** — scraping without permission can violate copyright
- **Adversarial** — site owners block bots, bots evade blocks, everyone loses

Fairfetch replaces this with a simple deal: **content creators and site owners
prepare content in a clean format, AI agents pay a small fee to access it, and
both sides get a signed record of the transaction.**

---

## How a Request Works (Plain English)

Fairfetch supports two ways for AI agents to pay — choose whichever fits your use case:

### Path A: One-Time Payment (x402)

Best for occasional access or trying out a site's content.

1. **AI agent asks for content.** It sends a normal HTTP request.
2. **Server says "that'll cost X."** The server responds with HTTP 402
   (Payment Required) and a price quote showing all usage tiers.
3. **AI agent pays.** It re-sends the request with a payment proof in the
   `X-PAYMENT` header.
4. **Server delivers.** Content + receipt + legal access grant.

This takes two round-trips (ask → price quote → pay → content).

### Path B: Pre-Funded Wallet (Fast Path)

Best for production use where an AI company makes thousands of requests.

1. **AI company registers a wallet** (through the API or, in production,
   through the Fairfetch marketplace). They get a wallet token and load it
   with funds.
2. **AI agent sends a request with the wallet token.** It includes the
   `X-WALLET-TOKEN` header.
3. **Server checks the balance, deducts the fee, and delivers content** —
   all in a single request. No 402, no negotiation.

This takes one round-trip (request with token → content). The charges
accumulate in a ledger and are settled periodically (e.g. monthly in the
production/premium version).

Think of it like the difference between paying cash at a toll booth every time
(x402) versus having an E-ZPass transponder that charges your account
automatically (wallet).

---

## Key Concepts

### Usage Categories

Not all content use is the same. Quoting a one-sentence summary in a chatbot is
very different from feeding an entire article into model training. Fairfetch
defines six usage categories, listed in order of increasing price:

| Category | What It Means | Analogy |
|----------|---------------|---------|
| **Search engine indexing** | Let search engines (Google, Bing, etc.) crawl and index your content (free when site owner allows) | Letting a library catalog list your book |
| **Summary** | Show a short snippet or headline | Reading the back cover of a book |
| **RAG** | Use the content to answer a specific question (Retrieval-Augmented Generation) | Looking up a fact in a reference book |
| **Research** | Internal analysis, academic research, trend analysis | Borrowing a book from a library |
| **Training** | Feed the content into an AI model's training data | Photocopying a book to teach from |
| **Commercial** | Redistribute, resell, or build a commercial product on top of the content | Reprinting a book under your own brand |

Each level (after search engine indexing) costs more and has stricter compliance requirements, because the impact on the content owner increases.

### Usage Grant

A Usage Grant is a digitally signed receipt that proves:

- **What** content was accessed (URL + fingerprint of the exact text)
- **Who** accessed it (the payer's identity)
- **When** it was accessed (timestamp)
- **Why** — what usage category was declared (search_engine_indexing, summary, training, etc.)
- **Under what terms** (the content owner's license type)

The signature is created by the content owner's server using a private key. Anyone
with the matching public key can verify that the grant is authentic and hasn't
been tampered with — but no one can forge a new one.

**Why this matters:** If a copyright dispute ever arises, the AI company can
produce the Usage Grant as evidence: *"We didn't scrape this. We paid for it
through an authorized channel, under these terms, on this date. Here's the
cryptographic proof."*

### Digital Signatures (Ed25519)

Ed25519 is a type of digital signature, like a tamper-proof wax seal on a
letter. Here's how it works in plain terms:

- The content owner has a **private key** (kept secret) and a **public key**
  (shared openly).
- When content is served, the content owner's server uses the private key to create
  a **signature** — a unique string that's mathematically tied to the exact
  content.
- Anyone can use the public key to **verify** that the signature is real and
  that the content hasn't been changed since it was signed.
- You can't create a valid signature without the private key, so a valid
  signature proves the content came from the content owner.

In Fairfetch, two things are signed:

1. **The content itself** → `X-FairFetch-Origin-Signature` header
2. **The Usage Grant** → the `signature` field inside the grant

### x402 (HTTP 402 Payment Required)

HTTP status code 402 was reserved decades ago for "Payment Required" but was
never widely used. The x402 protocol gives it a real purpose:

- Instead of blocking unpaid requests with a generic error, the server returns a
  **402 response with a machine-readable price quote** — what asset (USDC), how
  much, and where to pay.
- AI agents can read this programmatically, decide whether the price is
  acceptable, and pay automatically.
- After payment, they retry the request with a payment proof and get the content.

Think of it like a paywall that machines can understand and negotiate with —
no login forms, no CAPTCHAs, no human intervention.

### Pre-Funded Wallets

In production, it's impractical for an AI company to negotiate payment on every
single request — they might make thousands per minute. Pre-funded wallets solve
this:

- The AI company creates an account with a balance (like a prepaid phone card).
- Each request automatically deducts the fee from the balance.
- The content owner gets paid, the agent gets content, and neither side has to wait
  for a blockchain transaction on every call.
- At the end of the month, the actual settlement happens on-chain.

In the open-source version, wallets are stored in memory (reset on restart) for
demonstration. The production/premium version would use a persistent
blockchain-based ledger with monthly settlement cycles.

### URL validation (what URLs are allowed)

To prevent abuse (e.g. the server being tricked into fetching internal or
cloud-metadata URLs), Fairfetch only allows outbound fetches to **public
HTTP or HTTPS** URLs. The following are rejected with a 400 response
(`url_blocked`):

- **Non-HTTP(S) schemes** — e.g. `file://`, `ftp://`, `data:`
- **Private/internal IPs** — loopback (127.x), private ranges (10.x,
  172.16–31.x, 192.168.x), link-local
- **Cloud metadata endpoints** — e.g. 169.254.169.254,
  metadata.google.internal

So you can only request content from normal, publicly reachable web URLs.
If your use case requires fetching from an internal URL, you would need to
run Fairfetch in a trusted environment and adjust or disable this
validation accordingly.

### Content Hashing

A content hash (like `sha256:2c449548...`) is a unique fingerprint of the
content. The same text always produces the same hash, and even a single changed
character produces a completely different hash.

This lets you verify:
- The content you received is exactly what the content owner signed
- Nothing was altered in transit (by a proxy, CDN, or attacker)

### Bot Steering

When Fairfetch detects a known web crawler (like GPTBot or CCBot) trying to
scrape raw HTML, it doesn't block it. Instead, it adds headers saying:

*"Hey, we have a better way for you to get this content — here's our API
endpoint and our AI policy file. Use that instead of scraping."*

This is cooperative, not adversarial. The crawler can choose to follow the
suggestion and get clean, legal content through the API instead.

---

## Headers Reference (What You'll See in Responses)

### On Every Successful Response

| Header | Plain Meaning | Example |
|--------|---------------|---------|
| `X-Data-Origin-Verified` | "This content came directly from the original source." | `true` |
| `X-AI-License-Type` | "These are the content owner's terms for AI usage." | `publisher-terms` |
| `X-FairFetch-Origin-Signature` | "The content owner digitally signed this content. You can verify it hasn't been tampered with." | `GllQLb/V4Vd+Su...` |
| `X-Content-Hash` | "Here's a fingerprint of the content. Use it to verify integrity." | `sha256:2c449548...` |
| `X-FairFetch-Version` | "This server speaks Fairfetch protocol version 0.2." | `0.2` |

### When Payment Is Involved

| Header | Plain Meaning | Example |
|--------|---------------|---------|
| `X-PAYMENT` | (Request, x402 flow) "Here's my one-time payment proof." In test mode, use `test_paid_fairfetch`. | `test_paid_fairfetch` |
| `X-WALLET-TOKEN` | (Request, wallet flow) "Charge my pre-funded account." Use instead of `X-PAYMENT` for instant access. | `wallet_test_agent_alpha` |
| `X-PAYMENT-RECEIPT` | (Response) "Payment confirmed. Here's your transaction ID." For x402: blockchain tx hash (`0x...`). For wallets: ledger tx ID (`ff_...`). | `ff_3a7c9e2b...` |
| `X-FairFetch-Payment-Method` | (Response) "This is how you paid." Either `wallet` or `x402`. | `wallet` |
| `X-FairFetch-Wallet-Balance` | (Response, wallet only) "This is how much is left in your wallet after this charge." | `99000` |

### When a Usage Grant Is Issued

| Header | Plain Meaning | Example |
|--------|---------------|---------|
| `X-FairFetch-License-ID` | "Here's your legal access grant reference. Save this." Format: `grant_id:signature_prefix`. | `47db4290...:k2+wXE3x` |
| `X-FairFetch-Usage-Category` | "We recorded that you're using this content for this purpose." | `rag` |
| `X-FairFetch-Compliance-Level` | "This is the compliance tier that applies to your declared usage." | `standard` |

### When a Crawler Is Detected (Bot Steering)

| Header | Plain Meaning | Example |
|--------|---------------|---------|
| `X-FairFetch-Preferred-Access` | "We'd prefer you use our API instead of scraping HTML." | `mcp+json-ld` |
| `X-FairFetch-LLMS-Txt` | "Our AI access policy file is here (like robots.txt but for AI)." | `/.well-known/llms.txt` |
| `X-FairFetch-MCP-Endpoint` | "Our MCP endpoint is here — connect your AI agent to it." | `/mcp` |
| `Link` | Standard HTTP link header pointing to our AI policy and API. | `</.well-known/llms.txt>; rel="ai-policy"` |

---

## The 402 Response Body (Price Quote)

When you request content without paying, the 402 response tells you exactly
what it costs. Here's what each field means:

```json
{
  "accepts": {
    "price": "2000",
    "asset": "USDC",
    "network": "base",
    "payTo": "0x742d35Cc6634...",
    "usage_category": "rag",
    "compliance_level": "standard"
  },
  "available_tiers": {
    "search_engine_indexing": { "price": "0", "compliance_level": "standard" },
    "summary":    { "price": "1000",  "compliance_level": "standard" },
    "rag":        { "price": "2000",  "compliance_level": "standard" },
    "research":   { "price": "3000",  "compliance_level": "elevated" },
    "training":   { "price": "5000",  "compliance_level": "strict" },
    "commercial": { "price": "10000", "compliance_level": "strict" }
  }
}
```

| Field | Plain Meaning |
|-------|---------------|
| `price` | How much it costs, in the smallest unit of the currency. `1000` USDC = $0.001 USD. Site owners can set **variable prices by route** (e.g. higher for `/business`, lower for `/sports`); the 402 quote reflects the base price for the requested content URL, then multiplied by usage tier. |
| `asset` | What currency. Currently USDC (a stablecoin pegged to the US dollar). |
| `network` | Which blockchain network for payment. "base" = Base (an Ethereum layer-2 network with low fees). |
| `payTo` | The content owner's wallet address — where the money goes. |
| `usage_category` | The usage tier you requested (or the default). |
| `compliance_level` | How strict the rules are for that tier. "standard" for light use, "strict" for training/commercial. |
| `available_tiers` | A menu of all options with prices, so your agent can pick the cheapest tier that fits its needs. |

**Variable pricing by route:** A site owner can configure different base prices for different URL paths (e.g. `FAIRFETCH_PRICE_BY_ROUTE` in the [Site owner guide](PUBLISHER_GUIDE.md)). The 402 response for `?url=https://site.com/business` may show a different base price than `?url=https://site.com/sports`. Longest path prefix wins; the default price applies when no path matches. The path is normalized (encoding decoded, traversal collapsed) so route matching cannot be bypassed; only numeric prices are used.

---

## Content Negotiation (Choosing Your Format)

The `Accept` header in your request tells Fairfetch what format you want:

| What You Send | What You Get | When to Use It |
|---------------|-------------|----------------|
| `text/markdown` | Clean Markdown text only | Fastest option. Good for simple content extraction. |
| `application/ai-context+json` | Full JSON-LD "knowledge packet" with summary, metadata, lineage, and Usage Grant | Best for AI pipelines that need structured data and legal proof. |
| `application/ld+json` | Same as above (standard JSON-LD content type) | If your tools expect standard JSON-LD. |
| `application/json` | Standard JSON response | General-purpose fallback. |
| Anything else / none | Default format (JSON) | If you don't specify. |

---

## Glossary

| Term | Meaning |
|------|---------|
| **Ed25519** | A fast, widely-used digital signature algorithm. Used by Fairfetch to sign content and Usage Grants. |
| **JSON-LD** | A way of structuring JSON data so machines can understand its meaning. Fairfetch uses it for "knowledge packets." |
| **Knowledge Packet** | A structured JSON-LD document containing the article content, metadata, summary, origin signature, and data lineage. |
| **MCP** | Model Context Protocol — a standard for AI assistants (like Claude, Cursor) to connect to external tools and data sources. |
| **USDC** | A stablecoin (cryptocurrency) pegged 1:1 to the US Dollar. Used for micro-payments because it has low transaction fees. |
| **Wallet (Pre-Funded)** | An account with a prepaid balance. AI agents include a wallet token in their requests, and the fee is deducted automatically — no 402 round-trip needed. Like an E-ZPass for content. |
| **Wallet Token** | A string (like `wallet_test_agent_alpha`) that identifies a pre-funded wallet. Include it in the `X-WALLET-TOKEN` header. |
| **Route-based pricing** | Optional site config (`FAIRFETCH_PRICE_BY_ROUTE`) that sets different base prices for different URL path prefixes (e.g. `/business` vs `/sports`). Longest matching path wins; the 402 quote reflects the base price for the requested content URL. Path is normalized and only numeric prices are accepted. |
| **x402** | A protocol that uses HTTP status code 402 to enable machine-to-machine payments. The server tells the client the price; the client pays and retries. |
| **Usage Grant** | A signed receipt proving an AI agent was authorized to use specific content for a specific purpose. |
| **Bot Steering** | The practice of redirecting web crawlers from scraping HTML to using the site's official API instead. |
| **Data Lineage** | A record of how content was processed — what tools extracted it, when, and what the fingerprints were at each stage. Required by the EU AI Act. |
| **EU AI Act** | European Union regulation (effective 2026) requiring AI systems to track and disclose the provenance of their training data. |
| **Base (network)** | An Ethereum Layer-2 blockchain with low transaction fees, used for USDC micro-payments. |
| **EIP-3009** | A standard for "gasless" USDC transfers — the payer doesn't need to own ETH to pay transaction fees. |
| **Facilitator** | The service that verifies and settles payments. In test mode, this is mocked locally. In production, it connects to real blockchain infrastructure. |
| **Open Core** | A business model where the core protocol is open source, but advanced features (managed payment settlement, key management, audit trails) are offered as a commercial service. |
