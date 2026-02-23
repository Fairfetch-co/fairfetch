# Publisher Onboarding Guide

**Get your website ready for AI agents — in plain language.**

This guide is for **content owners** (publishers, blogs, news sites) who want to offer their content to AI companies through a **paid, legal pipeline** instead of being scraped for free. No coding experience? No problem. We’ll walk you through each step with examples and simple checks.

---

## 📑 Navigate this guide

| Step | What you’ll do | Time |
|------|----------------|------|
| [**Step 1: Check your setup**](#step-1-check-your-setup) | Confirm you have what you need (computer, accounts) | 2 min |
| [**Step 2: Try Fairfetch on your computer**](#step-2-try-fairfetch-on-your-computer) | Run Fairfetch locally and see it work | 5 min |
| [**Step 3: Set your site’s options**](#step-3-set-your-sites-options) | Choose price, license, and get a “signing key” | 10 min |
| [**Step 4: Add an AI policy file (llms.txt)**](#step-4-add-an-ai-policy-file-llmstxt) | Tell AI crawlers how to use your content legally | 5 min |
| [**Step 5: Point your CDN or server at Fairfetch**](#step-5-point-your-cdn-or-server-at-fairfetch) | Use Cloudflare, Nginx, or another option | 15–30 min |
| [**Step 6: Run Fairfetch for real (production)**](#step-6-run-fairfetch-for-real-production) | Run the API 24/7 with Docker or a service | 10 min |
| [**Step 7: Check that everything works**](#step-7-check-that-everything-works) | Verify payments, signatures, and monitoring | 5 min |

---

## What you get as a publisher

| Benefit | In simple terms |
|--------|------------------|
| **Revenue** | AI companies pay a small amount per article view (micro-payments in USDC). |
| **Legal control** | You set the rules (e.g. “publisher terms”). Every access is recorded with a signed **Usage Grant** so there’s proof of legal use. |
| **Visibility** | You can see how many bot visits were “steered” from raw scraping to your official API. |
| **Efficiency** | Your server prepares content once; many AI agents use that same clean version instead of each one scraping and processing your site. |

---

## Step 1: Check your setup

**What you need before starting**

- A **computer** (Windows, Mac, or Linux) with internet.
- **Python 3.11 or newer** installed.  
  - **Check:** Open a terminal (or Command Prompt) and type: `python3 --version`  
  - **Example output:** `Python 3.11.6`  
  - **If you see “command not found”:** Install Python from [python.org](https://www.python.org/downloads/).
- **(Optional)** A **GitHub account** to download Fairfetch, or you can download the code as a ZIP from the repo.
- For **production**: A **domain** you control (e.g. `yoursite.com`) and access to your **CDN or web server** (e.g. Cloudflare, Nginx).

> **Tip:** If you’re not sure what a “CDN” or “domain” is, you can still do Steps 2–3 on your own computer. Steps 5–6 involve your live website and may need help from your hosting or tech team.

---

## Step 2: Try Fairfetch on your computer

**Goal:** Run Fairfetch on your machine and confirm it responds. No payment or real site required.

### 2.1 Download and install

**What to do:**

1. Open a terminal (Mac/Linux) or Command Prompt / PowerShell (Windows).
2. Go to a folder where you keep projects (e.g. `Desktop` or `Documents`).
3. Run the commands below. **Replace nothing** — copy and paste as-is.

```bash
git clone https://github.com/Fairfetch-co/fairfetch.git
cd fairfetch
python3 -m venv .venv
```

**On Mac/Linux:**

```bash
source .venv/bin/activate
make setup-dev
make dev
```

**On Windows (Command Prompt):**

```cmd
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn api.main:app --host 0.0.0.0 --port 8402
```

**What you should see:** Text saying the server is running and listening on `http://localhost:8402`. Leave this window open.

**If something goes wrong:**

| What you see | What to do |
|--------------|------------|
| `git: command not found` | Install [Git](https://git-scm.com/) or download the repo as ZIP from GitHub and unzip it, then `cd fairfetch`. |
| `make: command not found` (Windows) | Use the Windows commands above (with `pip` and `uvicorn`) instead of `make`. |
| `python3` not found | Try `python --version`; if that works, use `python` instead of `python3` in the commands. |
| Port 8402 already in use | Stop the other program using that port, or use a different port: `uvicorn api.main:app --port 8403` (then use 8403 in the next steps). |

### 2.2 Verify it’s working

Open a **new** terminal window. Run:

```bash
curl http://localhost:8402/health
```

**Example of a good response:**

```json
{"status":"ok","service":"fairfetch","version":"0.2.0","scraper_interceptions":0}
```

If you see `"status":"ok"`, Fairfetch is running correctly.

**If you see “Connection refused” or no response:** The server in the first window is not running or not on port 8402. Start it again with `make dev` (or the Windows command above).

### 2.3 Request content (test payment)

Still in the second terminal, run:

```bash
curl -H "X-PAYMENT: test_paid_fairfetch" -H "Accept: text/markdown" "http://localhost:8402/content/fetch?url=https://example.com"
```

**What you should see:** Some short text (the content of example.com in clean Markdown). That means “payment” (test mode) and content delivery both work.

**Example (shortened) output:**

```text
This domain is for use in documentation examples...
```

Once you see content like this, you’re ready to configure Fairfetch for **your** site.

---

## Step 3: Set your site’s options

**Goal:** Tell Fairfetch your domain, how much to charge, and get a **signing key** so that every response can be cryptographically tied to you.

### 3.1 Create a config file (`.env`)

In the `fairfetch` folder, create a file named **exactly** `.env` (with the dot at the start). Put the following lines in it, then **edit the values** to match your site.

> **Security:** Keep `.env` private. Do not commit it to Git or share it publicly — it can contain your signing key and wallet details.

**Example for a site “News Today” at `newstoday.com`:**

```bash
# .env — keep this file private; do not commit to Git or share publicly

FAIRFETCH_TEST_MODE=false
FAIRFETCH_PUBLISHER_WALLET=0xYourEVMWalletAddress
FAIRFETCH_PUBLISHER_DOMAIN=newstoday.com
FAIRFETCH_CONTENT_PRICE=1000
FAIRFETCH_LICENSE_TYPE=publisher-terms
FAIRFETCH_SIGNING_KEY=
LITELLM_MODEL=gpt-4o-mini
```

**What each line means:**

| Setting | Meaning | Example |
|--------|---------|--------|
| `FAIRFETCH_TEST_MODE` | `false` = real payments and production behavior; `true` = test mode (no real money) | Use `false` when you go live. |
| `FAIRFETCH_PUBLISHER_WALLET` | Your crypto wallet address where payments go (e.g. USDC) | Get this from your wallet app or Fairfetch setup. |
| `FAIRFETCH_PUBLISHER_DOMAIN` | Your website’s domain (no `https://`) | `newstoday.com` |
| `FAIRFETCH_CONTENT_PRICE` | Price per request in smallest USDC unit (1000 ≈ $0.001) | `1000` |
| `FAIRFETCH_LICENSE_TYPE` | Legal terms you offer: `publisher-terms`, `commercial`, or `research-only` | `publisher-terms` |
| `FAIRFETCH_SIGNING_KEY` | Leave empty at first; we’ll generate a key next. | (empty) |
| `LITELLM_MODEL` | Model used to generate summaries (needs an API key in production) | `gpt-4o-mini` |

> **Important:** With `FAIRFETCH_TEST_MODE=false`, only your domain is allowed for CORS, and no test wallets are pre-created — AI agents must register and pay through your API or the Fairfetch marketplace.

### 3.2 Generate a signing key (recommended for production)

This key lets AI agents (and you) verify that content really came from your server.

**What to do:** In the `fairfetch` folder, with the virtual environment activated, run:

```bash
python3 -c "
from core.signatures import Ed25519Signer
s = Ed25519Signer()
print('Private key (keep secret):', s.private_key_b64)
print('Public key (share):       ', s.public_key_b64)
"
```

**Example output:**

```text
Private key (keep secret): xY7k...long string...
Public key (share):        J2nlmFsgoUtF3Avdmkt...
```

- Copy the **private key** into your `.env` file as the value of `FAIRFETCH_SIGNING_KEY=` (one line, no quotes).
- Put the **public key** on your site (e.g. in your llms.txt or docs) so agents can verify signatures.

> **Important:** Never share the private key. Only the public key should be visible to others.

**If you see “No module named 'core'”:** Run the command from inside the `fairfetch` folder with the venv activated: `source .venv/bin/activate` (Mac/Linux) or `.venv\Scripts\activate` (Windows).

---

## Step 4: Add an AI policy file (llms.txt)

**Goal:** Publish a small text file that tells AI crawlers **how** and **where** to access your content legally (similar in spirit to `robots.txt`, but for AI).

### 4.1 What to put in the file

Create a file named **llms.txt** with content like this. Replace the placeholders with your real URLs and contact.

**Example for News Today:**

```text
# llms.txt — AI access policy for newstoday.com
# See https://fairfetch.dev/llms-txt

User-agent: *
Fairfetch-API: https://api.newstoday.com
Fairfetch-MCP: https://api.newstoday.com/mcp
License: publisher-terms
Price: 1000 USDC (per request)
Payment: x402
Contact: ai-licensing@newstoday.com
```

**Meaning of each line:**

| Line | Meaning |
|------|--------|
| `Fairfetch-API` | Base URL of your Fairfetch API (where agents request content). |
| `Fairfetch-MCP` | URL of your MCP endpoint (for MCP clients). |
| `License` | Same as `FAIRFETCH_LICENSE_TYPE` (e.g. publisher-terms). |
| `Price` | Human-readable price (e.g. 1000 USDC per request). |
| `Contact` | Email or page for AI/licensing questions. |

### 4.2 Where to put it on your site

The file **must** be reachable at:

```text
https://yourdomain.com/.well-known/llms.txt
```

So for `newstoday.com`, the full URL is:

```text
https://newstoday.com/.well-known/llms.txt
```

**How to do it:** Depends on your host.

- **Static site / shared hosting:** Create a folder `.well-known` in your web root and put `llms.txt` inside it. Make sure the server serves it as plain text.
- **Nginx:** We’ll add a rule for this in Step 5.
- **Cloudflare / CDN:** Usually you upload or configure the file at `/.well-known/llms.txt` in your CDN or origin.

**Check:** Open `https://yourdomain.com/.well-known/llms.txt` in a browser. You should see the file content (and not a 404).

---

## Step 5: Point your CDN or server at Fairfetch

**Goal:** When an AI agent or crawler visits your site, your **edge** (CDN or server) either sends them to your Fairfetch API or adds headers that point to your API and llms.txt. So traffic is “steered” to the legal, paid pipeline.

Choose the option that matches how your site is hosted.

---

### Option A: Cloudflare Workers (if your site uses Cloudflare)

**Best for:** Sites already on Cloudflare.

1. In the Fairfetch repo, go to the folder `deploy/cloudflare`.
2. Open `wrangler.toml` and set your API origin and paths. **Example:**

```toml
[vars]
FAIRFETCH_API_ORIGIN = "https://api.newstoday.com"
FAIRFETCH_LLMS_TXT = "/.well-known/llms.txt"
FAIRFETCH_MCP_ENDPOINT = "/mcp"
```

3. Log in and deploy:

```bash
npx wrangler login
npx wrangler deploy
```

**What happens:** Normal visitors see your site as usual. Known AI crawlers requesting HTML get headers pointing to `llms.txt` and your API. Requests that already target your API (e.g. with `Accept: application/ai-context+json`) can be proxied to your Fairfetch backend.

**If deploy fails:** Ensure Node.js is installed (`node --version`) and that you’re logged in to the correct Cloudflare account (`npx wrangler login`).

---

### Option B: Nginx (your own server)

**Best for:** Self-hosted sites using Nginx.

Add a new config file (e.g. `/etc/nginx/conf.d/fairfetch.conf`) with content like below. Replace `127.0.0.1:8402` if your Fairfetch API runs on another machine or port.

```nginx
# Proxy content requests to Fairfetch
location /content/ {
    proxy_pass http://127.0.0.1:8402;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
}

# Serve llms.txt
location /.well-known/llms.txt {
    alias /var/www/llms.txt;
    add_header Content-Type text/plain;
}

# Optional: mark crawler traffic and add steering headers
map $http_user_agent $is_crawler {
    default 0;
    "~*gptbot|ccbot|claudebot|chatgpt|anthropic|bytespider|perplexity" 1;
}
# In your server { } block, add:
# if ($is_crawler) {
#     add_header X-FairFetch-Preferred-Access "mcp+json-ld" always;
#     add_header X-FairFetch-LLMS-Txt "/.well-known/llms.txt" always;
#     add_header Link '</.well-known/llms.txt>; rel="ai-policy"' always;
# }
```

Put your `llms.txt` file at `/var/www/llms.txt` (or change the `alias` path to where you store it). Then reload Nginx: `sudo nginx -t && sudo systemctl reload nginx`.

**If the site breaks:** Comment out the new `location` blocks and the `if ($is_crawler)` block, reload Nginx, and check the error log: `sudo tail -f /var/log/nginx/error.log`.

---

### Option C: AWS CloudFront + Lambda@Edge

**Best for:** Sites already on AWS with CloudFront.

1. Package the viewer-request code: from `deploy/cloudfront`, run `zip viewer_request.zip viewer_request.py`.
2. In AWS, create a Lambda function (Python 3.12, region us-east-1), upload the ZIP, and set the handler to `viewer_request.handler`.
3. Publish a new version of the function, then in CloudFront attach it to your distribution as a **Viewer Request** association.

Detailed commands and console steps are in the repo under `deploy/cloudfront`. If Lambda fails, check CloudWatch Logs for the function and ensure the execution role has permission to run Lambda@Edge.

---

### Option D: Fastly or Akamai

- **Fastly:** Use the code in `deploy/fastly`; build and deploy with the Fastly CLI and point the Fairfetch origin to your API.
- **Akamai:** Use `deploy/akamai`; upload the EdgeWorker bundle and attach it to your property, with the origin set to your Fairfetch API.

---

## Step 6: Run Fairfetch for real (production)

**Goal:** Run the Fairfetch API so it’s always on and reachable at the URL you put in llms.txt (e.g. `https://api.newstoday.com`).

### 6.1 Using Docker (recommended if you use Docker)

**Example:** Build and run with your `.env` file:

```bash
cd fairfetch
docker build -t fairfetch .
docker run -p 8402:8402 --env-file .env fairfetch
```

Your API is then available on port 8402 on that host. Put a reverse proxy (e.g. Nginx or your cloud load balancer) in front of it and serve HTTPS for `api.newstoday.com`.

**If the container exits immediately:** Check `docker logs <container_id>`. Often the cause is a missing or invalid env var (e.g. `FAIRFETCH_SIGNING_KEY` or `OPENAI_API_KEY` if you use summarization).

### 6.2 Using a system service (Linux with systemd)

**Example:** Create `/etc/systemd/system/fairfetch.service`:

```ini
[Unit]
Description=Fairfetch AI Content API
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/fairfetch
EnvironmentFile=/opt/fairfetch/.env
ExecStart=/opt/fairfetch/.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8402
Restart=always

[Install]
WantedBy=multi-user.target
```

Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable fairfetch
sudo systemctl start fairfetch
sudo systemctl status fairfetch
```

**If status shows “failed”:** Run `journalctl -u fairfetch -n 50` and fix the error (often path or `.env`).

---

## Step 7: Check that everything works

**Goal:** Confirm that requests get content, payment, and the right headers (the “three pillars”: content, signature, usage grant).

### 7.1 Health check

```bash
curl https://api.newstoday.com/health
```

**Example response:**

```json
{"status":"ok","service":"fairfetch","version":"0.2.0","scraper_interceptions":0}
```

### 7.2 Request content with test payment (if still in test mode)

If you’re still using test mode on a staging URL:

```bash
curl -v -H "X-PAYMENT: test_paid_fairfetch" "https://api.newstoday.com/content/fetch?url=https://newstoday.com/some-article"
```

In the response headers you should see lines like:

```text
X-Data-Origin-Verified: true
X-AI-License-Type: publisher-terms
X-FairFetch-Origin-Signature: ...
X-FairFetch-License-ID: ...
X-Content-Hash: sha256:...
X-PAYMENT-RECEIPT: ...
X-Fairfetch-Version: 0.2
```

If all of these are present, your pipeline is working end-to-end.

### 7.3 Scraper steering (optional)

To see how many crawler requests were steered to your API, call `/health` and check `scraper_interceptions` in the JSON. This number can help you understand how much bot traffic is being converted to legal API use.

---

## Quick reference

| I want to… | Where to look |
|------------|----------------|
| Run Fairfetch locally only | Step 2 |
| Set my price and domain | Step 3 |
| Tell AI crawlers how to access my content | Step 4 (llms.txt) |
| Connect my CDN/server to Fairfetch | Step 5 (pick your platform) |
| Run the API 24/7 | Step 6 |
| Verify responses and monitoring | Step 7 |

---

## Need help?

- **Docs and concepts:** [Concepts Guide](CONCEPTS.md) explains headers and terms in plain language.
- **Issues and code:** [GitHub — Fairfetch-co/fairfetch](https://github.com/Fairfetch-co/fairfetch).
- **Production payments:** For real USDC and wallet integration, see the Fairfetch marketplace or managed offering.
