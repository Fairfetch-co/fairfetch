//! Fairfetch Edge — Fastly Compute@Edge with bot-steering and x402 enforcement.

use fastly::http::{header, StatusCode};
use fastly::{Error, Request, Response};

const BACKEND: &str = "fairfetch_origin";
const LLMS_TXT: &str = "/.well-known/llms.txt";
const MCP_ENDPOINT: &str = "/mcp";

const AI_ACCEPT_TYPES: &[&str] = &[
    "application/ai-context+json",
    "application/ld+json",
    "text/markdown",
];

const KNOWN_CRAWLER_UAS: &[&str] = &[
    "chatgpt", "claude", "anthropic", "openai", "perplexity",
    "gptbot", "ccbot", "cohere-ai", "google-extended",
    "bytespider", "claudebot", "amazonbot", "diffbot",
    "semrushbot", "ahrefsbot", "mj12bot", "dotbot", "petalbot",
];

const PAYMENT_REQUIRED_BODY: &str = r#"{
    "accepts": {
        "price": "1000",
        "asset": "USDC",
        "network": "base",
        "payTo": "PUBLISHER_WALLET_ADDRESS",
        "facilitator": "https://x402.org/facilitator"
    },
    "error": "Payment Required",
    "message": "Include an X-PAYMENT header with a valid payment proof."
}"#;

fn is_known_crawler(ua: &str) -> bool {
    let ua_lower = ua.to_lowercase();
    KNOWN_CRAWLER_UAS.iter().any(|p| ua_lower.contains(p))
}

fn is_ai_agent(req: &Request) -> bool {
    if let Some(accept) = req.get_header_str(header::ACCEPT) {
        let accept_lower = accept.to_lowercase();
        if AI_ACCEPT_TYPES.iter().any(|t| accept_lower.contains(t)) {
            return true;
        }
    }
    if let Some(ua) = req.get_header_str(header::USER_AGENT) {
        return is_known_crawler(ua);
    }
    false
}

fn is_scraper_requesting_html(req: &Request) -> bool {
    let ua = req.get_header_str(header::USER_AGENT).unwrap_or("");
    if !is_known_crawler(ua) {
        return false;
    }
    let accept = req.get_header_str(header::ACCEPT).unwrap_or("");
    let wants_html = accept.is_empty() || accept.contains("text/html");
    let not_fairfetch = !AI_ACCEPT_TYPES.iter().any(|t| accept.contains(t));
    wants_html && not_fairfetch
}

fn add_steering_headers(resp: &mut Response) {
    resp.set_header("X-FairFetch-Preferred-Access", "mcp+json-ld");
    resp.set_header("X-FairFetch-LLMS-Txt", LLMS_TXT);
    resp.set_header("X-FairFetch-MCP-Endpoint", MCP_ENDPOINT);
    let link_val = format!(
        "<{}>; rel=\"ai-policy\", <{}>; rel=\"ai-content-api\"",
        LLMS_TXT, MCP_ENDPOINT
    );
    resp.set_header("Link", &link_val);
    resp.set_header("X-FairFetch-Scraper-Intercepted", "true");
}

#[fastly::main]
fn main(req: Request) -> Result<Response, Error> {
    if is_scraper_requesting_html(&req) {
        let mut resp = req.send(BACKEND)?;
        add_steering_headers(&mut resp);
        resp.set_header("X-Served-By", "fairfetch-fastly-edge");
        return Ok(resp);
    }

    if !is_ai_agent(&req) {
        return Ok(req.send(BACKEND)?);
    }

    let has_payment = req.get_header_str("X-PAYMENT").is_some();

    if !has_payment {
        return Ok(Response::from_status(StatusCode::PAYMENT_REQUIRED)
            .with_header(header::CONTENT_TYPE, "application/json")
            .with_header("X-Payment-Required", "true")
            .with_header(header::CACHE_CONTROL, "no-store")
            .with_body(PAYMENT_REQUIRED_BODY));
    }

    let original_url = req.get_url_str().to_string();
    let api_path = format!("/content/fetch?url={}", urlencoding(&original_url));

    let mut proxy_req = req;
    proxy_req.set_url(
        proxy_req
            .get_url()
            .join(&api_path)
            .unwrap_or_else(|_| proxy_req.get_url().clone()),
    );
    proxy_req.set_header("X-Edge-Provider", "fastly");

    let mut resp = proxy_req.send(BACKEND)?;
    resp.set_header("X-Served-By", "fairfetch-fastly-edge");

    Ok(resp)
}

fn urlencoding(s: &str) -> String {
    s.chars()
        .map(|c| match c {
            'A'..='Z' | 'a'..='z' | '0'..='9' | '-' | '_' | '.' | '~' => c.to_string(),
            _ => format!("%{:02X}", c as u32),
        })
        .collect()
}
