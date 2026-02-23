"""Fairfetch FastAPI application — Direct Pipeline entry point."""

from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import (
    build_converter,
    build_facilitator,
    build_license_provider,
    build_packet_builder,
    build_payment_requirement,
    build_signer,
    build_summarizer,
    get_config,
)
from api.routes import router
from interfaces.facilitator import PaymentRequirement
from payments.wallet_ledger import WalletLedger
from payments.x402 import X402Middleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("fairfetch")


def create_app() -> FastAPI:
    config = get_config()
    signer = build_signer(config)

    application = FastAPI(
        title="Fairfetch — AI-Aware Content Layer",
        description=(
            "Green AI infrastructure for content creators and site owners. "
            "Serve machine-ready content to AI agents with x402 payments, "
            "cryptographic Usage Grants for legal indemnity, and EU AI Act 2026 compliance."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    cors_origins = ["*"] if config.test_mode else [f"https://{config.publisher_domain}"]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=[
            "*",
            "X-PAYMENT",
            "X-PAYMENT-RECEIPT",
            "X-WALLET-TOKEN",
            "X-USAGE-CATEGORY",
            "X-FairFetch-License-ID",
            "X-FairFetch-Origin-Signature",
        ],
        expose_headers=[
            "X-PAYMENT-RECEIPT",
            "X-Data-Origin-Verified",
            "X-AI-License-Type",
            "X-FairFetch-Usage-Category",
            "X-FairFetch-Compliance-Level",
            "X-FairFetch-License-ID",
            "X-FairFetch-Origin-Signature",
            "X-FairFetch-Payment-Method",
            "X-FairFetch-Wallet-Balance",
            "X-FairFetch-Preferred-Access",
            "X-FairFetch-LLMS-Txt",
            "X-FairFetch-MCP-Endpoint",
            "Link",
        ],
    )

    facilitator = build_facilitator(config)

    def get_requirement(url: str) -> PaymentRequirement:
        return build_payment_requirement(config, url)

    license_provider = (
        build_license_provider(config, signer) if config.enable_usage_grants else None
    )
    wallet_ledger = WalletLedger(test_mode=config.test_mode)

    application.add_middleware(
        X402Middleware,
        facilitator=facilitator,
        get_requirement=get_requirement,
        license_provider=license_provider,
        wallet_ledger=wallet_ledger,
        search_engines_allowed=config.search_engines_allowed,
        search_engines_blocked=config.search_engines_blocked,
        paid_path_prefixes=["/content/"],
        exempt_paths=[
            "/health",
            "/openapi.json",
            "/docs",
            "/redoc",
            "/compliance/",
            "/wallet/",
        ],
    )

    application.state.config = config
    application.state.signer = signer
    application.state.converter = build_converter()
    application.state.summarizer = build_summarizer(config)
    application.state.packet_builder = build_packet_builder(signer)
    application.state.license_provider = license_provider
    application.state.wallet_ledger = wallet_ledger
    application.state.scraper_intercept_count = 0

    application.include_router(router)

    logger.info(
        "Fairfetch v0.2.0 — test_mode=%s, grants=%s, preferred_access=%s, price=%s USDC",
        config.test_mode,
        config.enable_usage_grants,
        config.enable_preferred_access,
        config.content_price,
    )

    return application


app = create_app()


def run() -> None:
    config = get_config()
    uvicorn.run("api.main:app", host=config.host, port=config.port, reload=True)


if __name__ == "__main__":
    run()
