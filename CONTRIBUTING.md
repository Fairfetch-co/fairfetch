# Contributing to Fairfetch

Thank you for your interest in contributing to Fairfetch. This document provides
guidelines, instructions, and legal information for contributors.

## Fork and Pull Request Model

**We use a fork-and-PR model.** To contribute:

1. **Fork** the repository on GitHub.
2. **Create a branch** in your fork (e.g. `feature/your-feature-name`).
3. **Submit a pull request** from your branch to the upstream `main` branch.

Only **core maintainers** can merge code into the upstream repository. This keeps
Fairfetch open and collaborative while maintaining clear control over what gets
merged. All contributions go through review via pull requests.

## Contributor License Agreement (CLA)

**By submitting a pull request or otherwise contributing code to this repository,
you agree to the following terms:**

1. You grant FairFetch and its affiliates a perpetual, worldwide, non-exclusive,
   royalty-free, irrevocable license to use, reproduce, modify, distribute,
   sublicense, and create derivative works from your contribution.

2. You grant FairFetch the right to use your contribution in both:
   - The **open-source** FairFetch project (Apache 2.0 License), and
   - The **commercial FairFetch Cloud** offering (Managed Clearinghouse service).

3. You represent that you have the legal right to grant these licenses and that
   your contribution does not violate any third-party rights.

4. You understand that your contribution is provided "as-is" without warranty.

This CLA is necessary to maintain the Open Core model: the open-source standard
remains freely available while enabling a sustainable commercial offering that
funds continued development.

If you have questions about the CLA, please open an issue or email legal@fairfetch.co.

## Proposing Major Changes (RFC Process)

Significant architectural changes require design review before implementation. This
protects contributor time and ensures architectural integrity and alignment with
Fairfetch's Open Core boundaries.

**When is an RFC required?** Examples include (but are not limited to):

- New payment facilitators or license providers
- Changes to `interfaces/` contracts or core protocol behavior
- New compliance or signing semantics
- Shifts in how the x402 middleware, wallet ledger, or content pipeline behave

**Process:**

1. **Open an issue** with the `[RFC]` tag and a clear title (e.g. `[RFC] Add EIP-3009 production facilitator`).
2. **Use the RFC template** — copy the structure from [docs/RFC_TEMPLATE.md](docs/RFC_TEMPLATE.md) into the issue body.
3. **Engage in technical debate** — maintainers and contributors will review the proposal. Ensure the design fits within the Open Core boundaries (see [Architecture Boundaries](#architecture-boundaries)) and does not blur the line between the open standard and commercial offerings.

We encourage thorough discussion before coding. Merging an RFC does not obligate you to implement it; it means the design is accepted and implementation can proceed in follow-up PRs.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment:

```bash
python -m venv .venv
source .venv/bin/activate
make setup-dev
```

4. Create a feature branch:

```bash
git checkout -b feature/your-feature-name
```

## Development Workflow

1. Make your changes
2. Write or update tests
3. Run the test suite: `make test`
4. Run linting: `make lint`
5. Run type checking: `make typecheck`

## Code Standards

- **Python 3.12+** with strict type annotations
- **Pydantic v2** for all data models
- **Async/await** for all network operations
- **ruff** for linting and formatting
- **mypy** in strict mode for type checking

### Architecture Boundaries

FairFetch follows the **Open Core** model with clear boundaries:

| Layer | Directory | Purpose |
|-------|-----------|---------|
| **Standard (Open)** | `interfaces/` | Abstract base classes anyone can implement |
| **Green AI (Open)** | `core/` | Content extraction, summarization, signing |
| **Protocol (Open)** | `api/`, `mcp_server/` | REST + MCP endpoints, content negotiation |
| **Payments (Open)** | `payments/` | x402 middleware, mock facilitator |
| **Compliance (Open)** | `compliance/` | EU AI Act headers, lineage, copyright |
| **Cloud (Placeholder)** | `plugins/` | Stubs for managed clearinghouse |

When contributing, ensure your changes respect these boundaries. Interface
changes should go in `interfaces/`, not be hardcoded into implementations.

### Style Guidelines

- Use `from __future__ import annotations` in all modules
- Prefer `dataclass(frozen=True, slots=True)` for immutable value types
- Use Pydantic `BaseModel` for serializable/API models
- All public classes and functions must have docstrings
- No comments that merely restate the code

## Testing

- All new features must include tests
- Use `pytest` with `pytest-asyncio` for async tests
- Mock external services (LLM APIs, network calls) in unit tests
- Use `MockFacilitator` and `MockLicenseProvider` for payment/grant tests
- Test fixtures go in `tests/conftest.py`
- Validate that responses include the **Green+Legal+Indemnity** triple

### Running Tests

```bash
make test            # Full suite with coverage
make test-unit       # Unit tests only
make dev-mcp         # MCP server manual testing via Inspector
```

## Pull Request Process

1. Ensure all tests pass
2. Update documentation if adding new features
3. Create a pull request from your fork to upstream with a clear description of the changes
4. Reference any related issues

Only core maintainers merge pull requests. Your PR will be reviewed; you may be asked for changes before it is merged.

### PR Title Convention

- `feat:` New functionality
- `fix:` Bug fixes
- `docs:` Documentation only
- `refactor:` No behavior change
- `test:` Test additions
- `chore:` Maintenance

## Areas for Contribution

### High Priority

- Production `BaseFacilitator` implementation (EIP-3009 on-chain verification)
- Production `BaseLicenseProvider` with persistent grant storage
- Additional edge deployment templates
- Performance benchmarking suite

### Good First Issues

- Improve error messages in the x402 middleware
- Add more crawler User-Agent patterns to the detection list
- Add support for additional content formats (EPUB, PDF)
- Improve test coverage for edge cases

## License

By contributing, you agree that your contributions will be licensed under the
Apache 2.0 License, subject to the CLA terms above.
