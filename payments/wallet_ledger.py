"""In-memory wallet ledger for pre-funded AI agent accounts.

Provides a fast path that skips the 402 round-trip: if an AI agent sends a
wallet token (X-WALLET-TOKEN header) and the wallet has sufficient balance,
the content is served immediately and the balance is deducted.

In production (Fairfetch Premium), this would be backed by a blockchain-based
ledger with monthly settlement. Here it's a simple in-memory dict for
demonstration and local testing.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime

MAX_BALANCE = 1_000_000_000  # $1,000 — safety cap for in-memory ledger
MAX_OWNER_LENGTH = 200


@dataclass(frozen=True)
class WalletTransaction:
    """A single charge or top-up event."""

    tx_id: str
    wallet_token: str
    amount: int
    balance_after: int
    content_url: str
    usage_category: str
    timestamp: str
    tx_type: str  # "charge" or "topup"

    def to_dict(self) -> dict[str, object]:
        return {
            "tx_id": self.tx_id,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "content_url": self.content_url,
            "usage_category": self.usage_category,
            "timestamp": self.timestamp,
            "tx_type": self.tx_type,
        }


@dataclass
class WalletAccount:
    """An AI agent's pre-funded account."""

    wallet_token: str
    owner: str
    balance: int  # in smallest USDC unit (1000 = $0.001)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    transactions: list[WalletTransaction] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "owner": self.owner,
            "balance": self.balance,
            "created_at": self.created_at,
            "transaction_count": len(self.transactions),
        }


def _generate_tx_id() -> str:
    return f"ff_{secrets.token_hex(16)}"


def _generate_wallet_token() -> str:
    return f"wallet_{secrets.token_hex(24)}"


class WalletLedger:
    """In-memory ledger mapping wallet tokens to prepaid balances.

    All balance-mutating operations are protected by a lock to prevent
    race conditions (double-spend, negative balances).

    In production, this would be backed by a blockchain-based ledger or a
    managed database with monthly settlement cycles.

    Pre-seeded test wallets (only in test mode):
        - ``wallet_test_agent_alpha`` — balance 100,000 ($0.10)
        - ``wallet_test_agent_beta``  — balance 500,000 ($0.50)
    """

    def __init__(self, *, test_mode: bool = True) -> None:
        self._wallets: dict[str, WalletAccount] = {}
        self._lock = threading.Lock()
        if test_mode:
            self._seed_test_wallets()

    def _seed_test_wallets(self) -> None:
        self.create_wallet(
            token="wallet_test_agent_alpha",
            owner="TestAgentAlpha",
            initial_balance=100_000,
        )
        self.create_wallet(
            token="wallet_test_agent_beta",
            owner="TestAgentBeta",
            initial_balance=500_000,
        )

    def create_wallet(
        self,
        *,
        owner: str,
        initial_balance: int = 0,
        token: str | None = None,
    ) -> WalletAccount:
        if not owner or not owner.strip():
            raise ValueError("Owner name is required")
        if len(owner) > MAX_OWNER_LENGTH:
            raise ValueError(f"Owner name exceeds {MAX_OWNER_LENGTH} characters")
        if initial_balance < 0:
            raise ValueError("Initial balance cannot be negative")
        if initial_balance > MAX_BALANCE:
            raise ValueError(f"Initial balance exceeds maximum ({MAX_BALANCE})")

        wallet_token = token or _generate_wallet_token()

        with self._lock:
            if wallet_token in self._wallets:
                raise ValueError("Wallet token already exists")
            account = WalletAccount(
                wallet_token=wallet_token,
                owner=owner.strip(),
                balance=initial_balance,
            )
            self._wallets[wallet_token] = account
        return account

    def get_account(self, wallet_token: str) -> WalletAccount | None:
        return self._wallets.get(wallet_token)

    def has_sufficient_balance(self, wallet_token: str, amount: int) -> bool:
        with self._lock:
            account = self._wallets.get(wallet_token)
            if account is None:
                return False
            return account.balance >= amount

    def charge(
        self,
        wallet_token: str,
        amount: int,
        *,
        content_url: str = "",
        usage_category: str = "summary",
    ) -> WalletTransaction | None:
        """Deduct amount from wallet. Returns the transaction, or None if insufficient funds.

        Thread-safe: the balance check and deduction are atomic.
        """
        if amount <= 0:
            return None

        with self._lock:
            account = self._wallets.get(wallet_token)
            if account is None or account.balance < amount:
                return None

            account.balance -= amount

            tx = WalletTransaction(
                tx_id=_generate_tx_id(),
                wallet_token=wallet_token,
                amount=amount,
                balance_after=account.balance,
                content_url=content_url,
                usage_category=usage_category,
                timestamp=datetime.now(UTC).isoformat(),
                tx_type="charge",
            )
            account.transactions.append(tx)
        return tx

    def top_up(self, wallet_token: str, amount: int) -> WalletTransaction | None:
        """Add funds to a wallet. Returns the transaction, or None if wallet not found."""
        if amount <= 0:
            return None

        with self._lock:
            account = self._wallets.get(wallet_token)
            if account is None:
                return None

            if account.balance + amount > MAX_BALANCE:
                return None

            account.balance += amount

            tx = WalletTransaction(
                tx_id=_generate_tx_id(),
                wallet_token=wallet_token,
                amount=amount,
                balance_after=account.balance,
                content_url="",
                usage_category="",
                timestamp=datetime.now(UTC).isoformat(),
                tx_type="topup",
            )
            account.transactions.append(tx)
        return tx

    def get_transactions(self, wallet_token: str, *, limit: int = 50) -> list[WalletTransaction]:
        account = self._wallets.get(wallet_token)
        if account is None:
            return []
        return list(reversed(account.transactions[-limit:]))
