# RFC: [Title]

Copy this template into a GitHub issue when proposing a major architectural change (see [CONTRIBUTING.md](../CONTRIBUTING.md#proposing-major-changes-rfc-process)).

**Status:** Draft  
**Author:** [Your name or GitHub handle]

---

## Summary

[One paragraph: what is being proposed? Example: "This RFC proposes a production implementation of `BaseFacilitator` that verifies and settles EIP-3009 (gasless USDC) transfers on Base. It adds a new `plugins/` implementation that calls an on-chain permit2-style flow while leaving the open-source `interfaces/facilitator.py` contract unchanged."]

---

## Motivation

- **Why are we doing this?** [Describe the problem or gap.]
- **What use case does it solve?** [Who benefits? e.g. site owners who want real USDC settlement without running mock facilitators.]

---

## Guide-level explanation

Explain the change as if it were already implemented. How does a developer or operator use it?

- **Configuration:** [e.g. env vars, config file changes.]
- **Usage:** [e.g. "Set `FAIRFETCH_FACILITATOR=cloud` and provide `FAIRFETCH_CLOUD_API_KEY`. The middleware will use the new facilitator for all `/content/` routes."]
- **Observable behavior:** [What do users see or get? e.g. real on-chain receipts, different 402 body fields.]

---

## Reference-level explanation

Technical deep dive for maintainers and implementers.

- **Interfaces:** [Changes to `interfaces/` — new methods, new types, or extended contracts. Mention backward compatibility.]
- **Core / pipeline:** [Changes to `core/`, `api/`, or `payments/` — new modules, call sites, or flow.]
- **Data models:** [Pydantic models, request/response shapes, or 402 body extensions.]
- **Async and types:** [All I/O must be async; all public APIs must be type-hinted. Call out any new `async def` or `Awaitable` usage.]

---

## Drawbacks

- **Risks:** [e.g. new dependency, trust boundary, or failure mode.]
- **Latency or complexity:** [Does this add round-trips, new config surface, or cognitive load?]
- **Open Core impact:** [Does this blur the line between the open standard and commercial offerings?]

---

## Rationale and alternatives

- **Why this design?** [Explain why this approach is the best fit for Fairfetch's goals and constraints.]
- **Alternatives considered:** [List other designs (e.g. "Alternative A: embed facilitator in middleware. Rejected because …").]

---

## Unresolved questions

- [ ] [What still needs to be decided? e.g. "Exact on-chain event format for receipt verification."]
- [ ] [Another open point.]
- [ ] [Optional: link to design doc or spike branch.]
