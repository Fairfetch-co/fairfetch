"""Tests for the wallet-based fast-path payment flow."""

from __future__ import annotations

import pytest

from payments.wallet_ledger import WalletLedger

# ---------------------------------------------------------------------------
# Unit tests: WalletLedger in isolation
# ---------------------------------------------------------------------------


class TestWalletLedger:
    def test_seed_wallets_exist(self) -> None:
        ledger = WalletLedger()
        alpha = ledger.get_account("wallet_test_agent_alpha")
        beta = ledger.get_account("wallet_test_agent_beta")
        assert alpha is not None
        assert alpha.balance == 100_000
        assert alpha.owner == "TestAgentAlpha"
        assert beta is not None
        assert beta.balance == 500_000

    def test_create_wallet(self) -> None:
        ledger = WalletLedger()
        account = ledger.create_wallet(owner="Acme AI", initial_balance=50_000)
        assert account.owner == "Acme AI"
        assert account.balance == 50_000
        assert account.wallet_token.startswith("wallet_")

    def test_charge_success(self) -> None:
        ledger = WalletLedger()
        tx = ledger.charge(
            "wallet_test_agent_alpha", 1000, content_url="https://example.com", usage_category="rag"
        )
        assert tx is not None
        assert tx.amount == 1000
        assert tx.balance_after == 99_000
        assert tx.tx_type == "charge"
        assert tx.usage_category == "rag"
        account = ledger.get_account("wallet_test_agent_alpha")
        assert account is not None
        assert account.balance == 99_000

    def test_charge_insufficient_balance(self) -> None:
        ledger = WalletLedger()
        tx = ledger.charge("wallet_test_agent_alpha", 999_999)
        assert tx is None
        account = ledger.get_account("wallet_test_agent_alpha")
        assert account is not None
        assert account.balance == 100_000  # unchanged

    def test_charge_unknown_wallet(self) -> None:
        ledger = WalletLedger()
        tx = ledger.charge("nonexistent_token", 100)
        assert tx is None

    def test_top_up(self) -> None:
        ledger = WalletLedger()
        tx = ledger.top_up("wallet_test_agent_alpha", 25_000)
        assert tx is not None
        assert tx.amount == 25_000
        assert tx.balance_after == 125_000
        assert tx.tx_type == "topup"

    def test_top_up_unknown_wallet(self) -> None:
        ledger = WalletLedger()
        tx = ledger.top_up("nonexistent_token", 100)
        assert tx is None

    def test_transaction_history(self) -> None:
        ledger = WalletLedger()
        ledger.charge("wallet_test_agent_alpha", 500, content_url="url1", usage_category="summary")
        ledger.charge("wallet_test_agent_alpha", 1000, content_url="url2", usage_category="rag")
        ledger.top_up("wallet_test_agent_alpha", 2000)

        txs = ledger.get_transactions("wallet_test_agent_alpha")
        assert len(txs) == 3
        assert txs[0].tx_type == "topup"  # most recent first
        assert txs[1].content_url == "url2"
        assert txs[2].content_url == "url1"

    def test_has_sufficient_balance(self) -> None:
        ledger = WalletLedger()
        assert ledger.has_sufficient_balance("wallet_test_agent_alpha", 100_000) is True
        assert ledger.has_sufficient_balance("wallet_test_agent_alpha", 100_001) is False
        assert ledger.has_sufficient_balance("nonexistent", 1) is False

    def test_multiple_charges_drain_balance(self) -> None:
        ledger = WalletLedger()
        for _ in range(100):
            tx = ledger.charge("wallet_test_agent_alpha", 1000, usage_category="summary")
            assert tx is not None
        account = ledger.get_account("wallet_test_agent_alpha")
        assert account is not None
        assert account.balance == 0
        tx = ledger.charge("wallet_test_agent_alpha", 1)
        assert tx is None


# ---------------------------------------------------------------------------
# Integration tests: wallet flow through the API
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_wallet_fast_path(client) -> None:
    """Wallet token skips the 402 and returns content directly."""
    resp = await client.get(
        "/content/fetch",
        params={"url": "https://example.com"},
        headers={"X-WALLET-TOKEN": "wallet_test_agent_alpha", "Accept": "text/markdown"},
    )
    assert resp.status_code == 200
    assert "Test Article" in resp.text
    assert resp.headers.get("X-FairFetch-Payment-Method") == "wallet"
    assert "X-FairFetch-Wallet-Balance" in resp.headers
    assert resp.headers.get("X-PAYMENT-RECEIPT", "").startswith("ff_")


@pytest.mark.anyio
async def test_wallet_insufficient_balance_returns_402(client) -> None:
    """Wallet with zero balance returns 402 with shortfall info."""
    resp = await client.get(
        "/content/fetch",
        params={"url": "https://example.com"},
        headers={"X-WALLET-TOKEN": "wallet_test_agent_alpha"},
    )
    # drain the wallet first by repeating until 402
    token = "wallet_test_agent_alpha"
    while resp.status_code == 200:
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={"X-WALLET-TOKEN": token},
        )
    assert resp.status_code == 402
    body = resp.json()
    assert body.get("wallet_error") == "insufficient_balance"
    assert "shortfall" in body
    assert "wallet_balance" in body


@pytest.mark.anyio
async def test_wallet_unknown_token_returns_402(client) -> None:
    """Unknown wallet token returns 402 with insufficient_balance."""
    resp = await client.get(
        "/content/fetch",
        params={"url": "https://example.com"},
        headers={"X-WALLET-TOKEN": "wallet_nonexistent_fake"},
    )
    assert resp.status_code == 402
    body = resp.json()
    assert body.get("wallet_error") == "insufficient_balance"


@pytest.mark.anyio
async def test_wallet_with_usage_category(client) -> None:
    """Wallet payment respects usage category pricing."""
    resp = await client.get(
        "/content/fetch",
        params={"url": "https://example.com", "usage": "rag"},
        headers={"X-WALLET-TOKEN": "wallet_test_agent_beta", "Accept": "text/markdown"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-FairFetch-Payment-Method") == "wallet"


@pytest.mark.anyio
async def test_x402_still_works(client) -> None:
    """Standard x402 flow continues to work alongside wallets."""
    resp = await client.get(
        "/content/fetch",
        params={"url": "https://example.com"},
        headers={"X-PAYMENT": "test_paid_fairfetch", "Accept": "text/markdown"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-FairFetch-Payment-Method") == "x402"


@pytest.mark.anyio
async def test_no_payment_402_includes_wallet_hint(client) -> None:
    """402 response hints about wallet option."""
    resp = await client.get(
        "/content/fetch",
        params={"url": "https://example.com"},
    )
    assert resp.status_code == 402
    body = resp.json()
    assert "hint" in body
    assert "X-WALLET-TOKEN" in body["hint"]


@pytest.mark.anyio
async def test_wallet_register_endpoint(client) -> None:
    """Register a new wallet via API."""
    resp = await client.post(
        "/wallet/register", params={"owner": "TestCorp", "initial_balance": 50000}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["owner"] == "TestCorp"
    assert body["balance"] == 50000
    assert body["wallet_token"].startswith("wallet_")
    assert "usage" in body


@pytest.mark.anyio
async def test_wallet_balance_endpoint(client) -> None:
    """Check balance of a test wallet."""
    resp = await client.get("/wallet/balance", params={"token": "wallet_test_agent_alpha"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["owner"] == "TestAgentAlpha"
    assert isinstance(body["balance"], int)


@pytest.mark.anyio
async def test_wallet_balance_not_found(client) -> None:
    resp = await client.get("/wallet/balance", params={"token": "nonexistent"})
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_wallet_topup_endpoint(client) -> None:
    """Top up a wallet and verify new balance."""
    resp = await client.post(
        "/wallet/topup",
        params={"token": "wallet_test_agent_beta", "amount": 10000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount_added"] == 10000
    assert body["new_balance"] == 510_000


@pytest.mark.anyio
async def test_wallet_transactions_endpoint(client) -> None:
    """Fetch transaction history after a charge."""
    await client.get(
        "/content/fetch",
        params={"url": "https://example.com"},
        headers={"X-WALLET-TOKEN": "wallet_test_agent_beta", "Accept": "text/markdown"},
    )
    resp = await client.get(
        "/wallet/transactions",
        params={"token": "wallet_test_agent_beta"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["transactions"]) >= 1
    assert body["transactions"][0]["tx_type"] == "charge"
