/**
 * Akamai EdgeWorkers — Fairfetch Direct Pipeline with bot steering.
 *
 * 1. Known crawlers requesting text/html → inject Link + steering headers
 * 2. AI agents with correct Accept → proxy to FairFetch API
 * 3. Unpaid AI requests → 402 Payment Required
 * 4. Logs scraper interceptions for publisher dashboards
 */

const AI_ACCEPT_TYPES = [
  "application/ai-context+json",
  "application/ld+json",
  "text/markdown",
];

const KNOWN_CRAWLER_UAS = [
  "chatgpt", "claude", "anthropic", "openai", "perplexity",
  "gptbot", "ccbot", "cohere-ai", "google-extended",
  "bytespider", "claudebot", "amazonbot", "diffbot",
  "semrushbot", "ahrefsbot", "mj12bot", "dotbot", "petalbot",
];

const LLMS_TXT = "/.well-known/llms.txt";
const MCP_ENDPOINT = "/mcp";

const PAYMENT_REQUIREMENT = JSON.stringify({
  accepts: {
    price: "1000",
    asset: "USDC",
    network: "base",
    payTo: "PUBLISHER_WALLET_ADDRESS",
    facilitator: "https://x402.org/facilitator",
  },
  error: "Payment Required",
  message: "Include an X-PAYMENT header with a valid payment proof.",
});

function isKnownCrawler(ua) {
  const lower = ua.toLowerCase();
  return KNOWN_CRAWLER_UAS.some((p) => lower.includes(p));
}

function isAiAgent(request) {
  const accept = (request.getHeader("Accept") || [""])[0].toLowerCase();
  if (AI_ACCEPT_TYPES.some((t) => accept.includes(t))) return true;
  const ua = (request.getHeader("User-Agent") || [""])[0];
  return isKnownCrawler(ua);
}

function isScraperHtml(request) {
  const ua = (request.getHeader("User-Agent") || [""])[0];
  if (!isKnownCrawler(ua)) return false;
  const accept = (request.getHeader("Accept") || [""])[0].toLowerCase();
  const wantsHtml = !accept || accept.includes("text/html");
  const notFairfetch = !AI_ACCEPT_TYPES.some((t) => accept.includes(t));
  return wantsHtml && notFairfetch;
}

export function onClientRequest(request) {
  if (isScraperHtml(request)) {
    request.setVariable("PMUSER_SCRAPER_INTERCEPTED", "true");
    return;
  }

  if (!isAiAgent(request)) return;

  const paymentHeader = request.getHeader("X-PAYMENT");
  if (!paymentHeader || paymentHeader.length === 0) {
    request.respondWith(402, {
      "Content-Type": "application/json",
      "X-Payment-Required": "true",
      "Cache-Control": "no-store",
    }, PAYMENT_REQUIREMENT);
    return;
  }

  const originalUrl = request.url;
  request.route({
    path: `/content/fetch?url=${encodeURIComponent(originalUrl)}`,
    origin: "fairfetch_api",
  });
  request.setHeader("X-Edge-Provider", "akamai");
}

export function onClientResponse(request, response) {
  const wasIntercepted = request.getVariable("PMUSER_SCRAPER_INTERCEPTED");
  if (wasIntercepted === "true") {
    response.setHeader("X-FairFetch-Preferred-Access", "mcp+json-ld");
    response.setHeader("X-FairFetch-LLMS-Txt", LLMS_TXT);
    response.setHeader("X-FairFetch-MCP-Endpoint", MCP_ENDPOINT);
    response.setHeader("Link",
      `<${LLMS_TXT}>; rel="ai-policy", <${MCP_ENDPOINT}>; rel="ai-content-api"`
    );
    response.setHeader("X-FairFetch-Scraper-Intercepted", "true");
  }

  if (isAiAgent(request)) {
    response.setHeader("X-Served-By", "fairfetch-akamai-edge");
  }
}
