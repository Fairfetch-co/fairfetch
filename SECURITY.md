# Security

## Reporting a vulnerability

We take security seriously. If you believe you have found a security vulnerability, please report it responsibly:

- **Do not** open a public GitHub issue for security-sensitive bugs.
- Open a private [GitHub Security Advisory](https://github.com/Fairfetch-co/fairfetch/security/advisories/new) with a description and steps to reproduce.
- We will acknowledge receipt and aim to respond within a reasonable time. We may ask for more detail and will coordinate disclosure if the report is accepted.

## Security measures

Fairfetch implements multiple layers of security; see the [Security section](README.md#-security) of the README for details, including:

- **URL validation** — SSRF protection (blocked private IPs, cloud metadata, non-HTTP(S))
- **Route-based pricing** — Path normalization and numeric-only prices to prevent bypass
- **Test mode** — CORS and wallet behavior in production vs development
- **Error handling** — No sensitive details in client-facing error responses

Thank you for helping keep Fairfetch and its users safe.
