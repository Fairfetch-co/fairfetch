/**
 * Cloudflare Worker — Fairfetch Edge Proxy
 *
 * Implements the Direct Pipeline at the edge:
 *  1. Detects AI agents / known crawlers
 *  2. Steers scrapers toward the official FairFetch API (Legal Path)
 *  3. Proxies legitimate requests with x402 payment enforcement
 *  4. Logs "Scraper Interceptions" for publisher analytics
 */

interface Env {
  FAIRFETCH_API_ORIGIN: string;
  FAIRFETCH_LLMS_TXT: string;
  FAIRFETCH_MCP_ENDPOINT: string;
}

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

function isAiAgentRequest(request: Request): boolean {
  const accept = request.headers.get("accept") || "";
  if (AI_ACCEPT_TYPES.some((t) => accept.includes(t))) return true;
  const ua = (request.headers.get("user-agent") || "").toLowerCase();
  return KNOWN_CRAWLER_UAS.some((p) => ua.includes(p));
}

function isScraperRequestingHtml(request: Request): boolean {
  const ua = (request.headers.get("user-agent") || "").toLowerCase();
  const accept = (request.headers.get("accept") || "").toLowerCase();
  const isCrawler = KNOWN_CRAWLER_UAS.some((p) => ua.includes(p));
  const wantsHtml = !accept || accept.includes("text/html");
  const notUsingFairfetch = !AI_ACCEPT_TYPES.some((t) => accept.includes(t));
  return isCrawler && wantsHtml && notUsingFairfetch;
}

function steeringHeaders(env: Env): Record<string, string> {
  const llmsTxt = env.FAIRFETCH_LLMS_TXT || "/.well-known/llms.txt";
  const mcpEndpoint = env.FAIRFETCH_MCP_ENDPOINT || "/mcp";
  return {
    "X-FairFetch-Preferred-Access": "mcp+json-ld",
    "X-FairFetch-LLMS-Txt": llmsTxt,
    "X-FairFetch-MCP-Endpoint": mcpEndpoint,
    "Link": `<${llmsTxt}>; rel="ai-policy", <${mcpEndpoint}>; rel="ai-content-api"`,
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Scraper requesting raw HTML — serve the page but inject steering headers
    if (isScraperRequestingHtml(request)) {
      const origin = await fetch(request);
      const response = new Response(origin.body, origin);
      const headers = steeringHeaders(env);
      for (const [k, v] of Object.entries(headers)) {
        response.headers.set(k, v);
      }
      response.headers.set("X-FairFetch-Scraper-Intercepted", "true");
      response.headers.set("X-Served-By", "fairfetch-cf-edge");
      return response;
    }

    // AI agent using the correct Accept header — proxy to FairFetch API
    if (isAiAgentRequest(request)) {
      const url = new URL(request.url);
      const apiUrl = `${env.FAIRFETCH_API_ORIGIN}/content/fetch?url=${encodeURIComponent(url.toString())}`;

      const headers = new Headers(request.headers);
      headers.set("X-Forwarded-For", request.headers.get("cf-connecting-ip") || "");
      headers.set("X-Edge-Provider", "cloudflare");

      const paymentHeader = request.headers.get("X-PAYMENT");
      if (paymentHeader) {
        headers.set("X-PAYMENT", paymentHeader);
      }

      const response = await fetch(apiUrl, { method: "GET", headers });
      const newResponse = new Response(response.body, response);
      newResponse.headers.set("X-Served-By", "fairfetch-cf-edge");
      newResponse.headers.set("Cache-Control", "public, max-age=60, stale-while-revalidate=300");
      return newResponse;
    }

    // Regular browser — pass through
    return fetch(request);
  },
};
