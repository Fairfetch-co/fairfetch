# Publisher Onboarding Guide

This guide walks you through deploying Fairfetch on your site so AI agents
can access your content through a paid, signed, legally verifiable pipeline
instead of scraping your HTML.

---

## What You Get

1. **Revenue** — Every AI agent pays per-request via x402 (USDC micro-payments)
2. **Legal control** — You set the license terms; every access produces a signed Usage Grant
3. **Scraper visibility** — See how many bots are being steered from illegal scraping to your API
4. **Green compute** — Your server pre-processes content once instead of letting 1,000 crawlers each do it

---

## Step 1: Run Fairfetch Locally

```bash
git clone https://github.com/Fairfetch-co/fairfetch.git
cd fairfetch

# Create a virtual environment and install
python -m venv .venv
source .venv/bin/activate
make setup-dev

# Start the server in test mode (no wallet needed)
make dev
```

Verify it works:

```bash
# Health check
curl http://localhost:8402/health
# {"status":"ok","service":"fairfetch","version":"0.2.0","scraper_interceptions":0}

# Fetch content with a test payment
curl -H "X-PAYMENT: test_paid_fairfetch" \
     -H "Accept: application/ai-context+json" \
     "http://localhost:8402/content/fetch?url=https://example.com"
```

---

## Step 2: Configure for Your Site

Create a `.env` file (never commit this):

```bash
# .env — publisher configuration
FAIRFETCH_TEST_MODE=false
FAIRFETCH_PUBLISHER_WALLET=0xYourEVMWalletAddress
FAIRFETCH_PUBLISHER_DOMAIN=yoursite.com
FAIRFETCH_CONTENT_PRICE=1000          # $0.001 USDC per request
FAIRFETCH_LICENSE_TYPE=publisher-terms # or: commercial, research-only
FAIRFETCH_SIGNING_KEY=                # leave empty to auto-generate, or set a persistent base64 Ed25519 key
LITELLM_MODEL=gpt-4o-mini             # for summarization (requires OPENAI_API_KEY)
```

Generate a persistent signing key (recommended for production):

```python
from core.signatures import Ed25519Signer

signer = Ed25519Signer()
print(f"Private key (keep secret): {signer.private_key_b64}")
print(f"Public key (share):        {signer.public_key_b64}")
```

Set `FAIRFETCH_SIGNING_KEY` to the private key. Publish the public key on your
site so AI agents can verify your signatures.

---

## Step 3: Create Your llms.txt

Create `/.well-known/llms.txt` on your site (like robots.txt, but for AI):

```text
# llms.txt — AI access policy for yoursite.com
# See https://fairfetch.dev/llms-txt

User-agent: *
Fairfetch-API: https://api.yoursite.com
Fairfetch-MCP: https://api.yoursite.com/mcp
License: publisher-terms
Price: 1000 USDC (per request)
Payment: x402
Contact: ai-licensing@yoursite.com
```

---

## Step 4: Deploy the Edge Worker

Choose your CDN and deploy the Fairfetch edge worker. This intercepts crawler
requests at the CDN level and steers them to your Fairfetch API.

### Cloudflare Workers

```bash
cd deploy/cloudflare

# Edit wrangler.toml with your settings
```

Update `wrangler.toml`:

```toml
name = "fairfetch-edge"
main = "worker.ts"
compatibility_date = "2025-12-01"

[vars]
FAIRFETCH_API_ORIGIN = "https://api.yoursite.com"
FAIRFETCH_LLMS_TXT = "/.well-known/llms.txt"
FAIRFETCH_MCP_ENDPOINT = "/mcp"
```

Deploy:

```bash
npx wrangler login
npx wrangler deploy
```

What happens after deployment:
- Regular browsers see your site as normal
- Known crawlers (GPTBot, CCBot, etc.) requesting HTML get steering headers:
  `Link: </.well-known/llms.txt>; rel="ai-policy"`
- AI agents using `Accept: application/ai-context+json` get proxied to your Fairfetch API

### AWS CloudFront + Lambda@Edge

1. Package the viewer request function:

```bash
cd deploy/cloudfront
zip viewer_request.zip viewer_request.py
```

2. Create a Lambda function (Python 3.12, us-east-1 region):

```bash
aws lambda create-function \
  --function-name fairfetch-viewer-request \
  --runtime python3.12 \
  --handler viewer_request.handler \
  --zip-file fileb://viewer_request.zip \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-edge-role \
  --region us-east-1
```

3. Publish a version and associate with your CloudFront distribution:

```bash
aws lambda publish-version \
  --function-name fairfetch-viewer-request \
  --region us-east-1

# Then in CloudFront console:
# Distribution > Behaviors > Edit > Lambda Function Associations
# Event Type: Viewer Request
# Function ARN: arn:aws:lambda:us-east-1:...:function:fairfetch-viewer-request:1
```

### Fastly Compute@Edge

```bash
cd deploy/fastly

# Install Fastly CLI
brew install fastly/tap/fastly

# Build and deploy
fastly compute build
fastly compute deploy
```

Configure the backend in your Fastly service to point `fairfetch_origin` at
your Fairfetch API server.

### Akamai EdgeWorkers

```bash
cd deploy/akamai

# Create a tarball
tar -czf fairfetch-edgeworker.tgz edgeworker.js bundle.json

# Upload via Akamai CLI
akamai edgeworkers upload \
  --edgeworker-id YOUR_EW_ID \
  --bundle fairfetch-edgeworker.tgz
```

Add a property rule to route requests through the EdgeWorker and define
`fairfetch_api` as an origin pointing to your API host.

### Nginx (Self-Hosted)

If you don't use a CDN, add this to your nginx config:

```nginx
# /etc/nginx/conf.d/fairfetch.conf

# Proxy AI agent requests to Fairfetch API
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

# Add steering headers for known crawlers
map $http_user_agent $is_crawler {
    default 0;
    "~*gptbot|ccbot|claudebot|chatgpt|anthropic|bytespider|perplexity" 1;
}

server {
    # ... your existing config ...

    # Inject FairFetch headers for crawlers
    if ($is_crawler) {
        add_header X-FairFetch-Preferred-Access "mcp+json-ld" always;
        add_header X-FairFetch-LLMS-Txt "/.well-known/llms.txt" always;
        add_header Link '</.well-known/llms.txt>; rel="ai-policy"' always;
    }
}
```

---

## Step 5: Production Deployment

Run the Fairfetch API as a systemd service or in Docker:

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8402
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8402"]
```

```bash
docker build -t fairfetch .
docker run -p 8402:8402 --env-file .env fairfetch
```

### Systemd

```ini
# /etc/systemd/system/fairfetch.service
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

---

## Step 6: Monitor

### Scraper Interception Dashboard

```bash
# Check how many crawlers have been steered
curl http://localhost:8402/health | jq .scraper_interceptions
```

### Verify Your Signatures

```bash
# Check that responses include all three pillars
curl -v -H "X-PAYMENT: test_paid_fairfetch" \
     "http://localhost:8402/content/fetch?url=https://yoursite.com/article" 2>&1 \
     | grep -E "X-FairFetch|X-Data-Origin|X-AI-License|X-Content-Hash|X-PAYMENT-RECEIPT"
```

You should see:
```
X-Data-Origin-Verified: true
X-AI-License-Type: publisher-terms
X-FairFetch-Origin-Signature: <base64>
X-FairFetch-License-ID: <grant_id>:<sig_prefix>
X-Content-Hash: sha256:<hex>
X-PAYMENT-RECEIPT: 0x<tx_hash>
X-Fairfetch-Version: 0.2
```
