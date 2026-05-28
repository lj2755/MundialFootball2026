"""
Polygon / Polymarket wallet integration.

Two modes:
  manual  → generates the transaction calldata and returns it for the user to sign
            in MetaMask or any web3 wallet (safest approach)
  auto    → signs and broadcasts using a local private key from .env
            USE ONLY FOR SMALL TEST AMOUNTS — store the private key in .env, never in code

Polymarket bets on Polygon:
  1. Approve USDC spend on the CTF Exchange contract
  2. Call buyShares() on the CTFExchange with the condition_id + outcome_index + amount
"""
import os
from decimal import Decimal

from web3 import Web3
from eth_account import Account

from config.settings import (
    POLYGON_RPC_URL,
    USDC_CONTRACT,
    CTF_EXCHANGE,
    EXECUTION_MODE,
)

# Minimal ABIs — only the functions we need
USDC_ABI = [
    {
        "name": "approve",
        "type": "function",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
    },
    {
        "name": "allowance",
        "type": "function",
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "balanceOf",
        "type": "function",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
]

# Simplified CTF Exchange ABI (buy side only)
CTF_EXCHANGE_ABI = [
    {
        "name": "fillOrder",
        "type": "function",
        "inputs": [
            {
                "name": "order",
                "type": "tuple",
                "components": [
                    {"name": "salt", "type": "uint256"},
                    {"name": "maker", "type": "address"},
                    {"name": "signer", "type": "address"},
                    {"name": "taker", "type": "address"},
                    {"name": "tokenId", "type": "uint256"},
                    {"name": "makerAmount", "type": "uint256"},
                    {"name": "takerAmount", "type": "uint256"},
                    {"name": "expiration", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "feeRateBps", "type": "uint256"},
                    {"name": "side", "type": "uint8"},
                    {"name": "signatureType", "type": "uint8"},
                    {"name": "signature", "type": "bytes"},
                ],
            },
            {"name": "fillAmount", "type": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    }
]

USDC_DECIMALS = 6  # USDC on Polygon uses 6 decimals


class WalletConnector:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL))
        self.usdc = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_CONTRACT), abi=USDC_ABI
        )
        self.exchange = self.w3.eth.contract(
            address=Web3.to_checksum_address(CTF_EXCHANGE), abi=CTF_EXCHANGE_ABI
        )
        self._private_key: str | None = os.getenv("WALLET_PRIVATE_KEY")
        self._account = (
            Account.from_key(self._private_key) if self._private_key else None
        )

    @property
    def address(self) -> str | None:
        return self._account.address if self._account else None

    def is_connected(self) -> bool:
        return self.w3.is_connected()

    def get_usdc_balance(self, address: str) -> float:
        """Returns USDC balance in human-readable form (e.g. 100.50)."""
        raw = self.usdc.functions.balanceOf(Web3.to_checksum_address(address)).call()
        return raw / (10 ** USDC_DECIMALS)

    def estimate_shares(self, amount_usdc: float, price: float) -> float:
        """
        How many outcome shares you get for `amount_usdc` at `price` (0–1).
        shares = usdc / price
        """
        if price <= 0:
            return 0.0
        return amount_usdc / price

    def build_approve_tx(self, owner_address: str, amount_usdc: float) -> dict:
        """
        Build USDC approval transaction — user must sign this in their wallet
        before the buy transaction can go through.
        Returns the raw tx dict (not yet signed or broadcast).
        """
        amount_raw = int(Decimal(str(amount_usdc)) * Decimal(10 ** USDC_DECIMALS))
        nonce = self.w3.eth.get_transaction_count(Web3.to_checksum_address(owner_address))

        tx = self.usdc.functions.approve(
            Web3.to_checksum_address(CTF_EXCHANGE),
            amount_raw,
        ).build_transaction({
            "from": Web3.to_checksum_address(owner_address),
            "nonce": nonce,
            "gas": 80_000,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": 137,  # Polygon mainnet
        })
        return tx

    def sign_and_send(self, tx: dict) -> str:
        """
        Signs a transaction with the locally stored private key and broadcasts it.
        Only works if EXECUTION_MODE=auto and WALLET_PRIVATE_KEY is set.
        Returns the tx hash.
        """
        if EXECUTION_MODE != "auto":
            raise RuntimeError(
                "sign_and_send requires EXECUTION_MODE=auto. "
                "In manual mode, return tx data to user for signing."
            )
        if not self._private_key:
            raise ValueError("WALLET_PRIVATE_KEY not set in .env")

        signed = self.w3.eth.account.sign_transaction(tx, self._private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        return tx_hash.hex()

    def get_calldata_for_ui(self, tx: dict) -> dict:
        """
        Returns tx calldata in a format suitable for display in the dashboard
        or injection into MetaMask via window.ethereum.request.
        """
        return {
            "to": tx.get("to"),
            "data": tx.get("data"),
            "value": "0x0",
            "gas": hex(tx.get("gas", 80000)),
            "chainId": "0x89",  # 137 in hex = Polygon
        }
