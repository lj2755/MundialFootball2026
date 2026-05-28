"""
Bet execution layer.
Handles the full flow: validate → approve USDC → buy shares on Polymarket.

Polymarket CLOB bets use LIMIT orders, not market orders. This module
builds a market-equivalent order by setting a price slightly above the ask.

Reference: https://docs.polymarket.com/#clob-api (Order endpoints)
"""
import time
import secrets
import json
import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

from execution_layer.wallet_connector import WalletConnector
from config.settings import POLYMARKET_API_BASE, POLYGON_RPC_URL, EXECUTION_MODE


class BetExecutor:
    def __init__(self, wallet: WalletConnector):
        self.wallet = wallet

    def _build_order(
        self,
        token_id: str,
        side: str,  # "BUY" or "SELL"
        price: float,
        size_usdc: float,
        maker_address: str,
    ) -> dict:
        """
        Builds a signed limit order for the Polymarket CLOB API.
        price = max you're willing to pay per share (0–1)
        size_usdc = total USDC to spend
        """
        salt = int(secrets.token_hex(16), 16)
        maker_amount = int(size_usdc * 1e6)   # USDC in micro-units
        taker_amount = int(maker_amount / price) if price > 0 else 0

        order_data = {
            "salt": salt,
            "maker": maker_address,
            "signer": maker_address,
            "taker": "0x0000000000000000000000000000000000000000",
            "tokenId": int(token_id),
            "makerAmount": maker_amount,
            "takerAmount": taker_amount,
            "expiration": 0,  # GTC (good till cancelled)
            "nonce": 0,
            "feeRateBps": 0,
            "side": 0 if side == "BUY" else 1,
            "signatureType": 0,  # EOA signature
        }

        # Sign the order hash (EIP-712 — Polymarket specific)
        order_hash = self._compute_order_hash(order_data)
        if not self.wallet._private_key:
            raise ValueError("Private key required for signing orders.")

        signed = Account.sign_message(
            encode_defunct(hexstr=order_hash),
            private_key=self.wallet._private_key,
        )
        order_data["signature"] = signed.signature.hex()
        return order_data

    def _compute_order_hash(self, order: dict) -> str:
        """
        Simplified order hash — in production this must implement Polymarket's
        EIP-712 domain separator exactly. Check Polymarket's Python SDK or JS SDK
        for the canonical implementation.
        """
        encoded = Web3.solidity_keccak(
            ["uint256", "address", "address", "uint256", "uint256", "uint256", "uint8"],
            [
                order["salt"],
                order["maker"],
                order["taker"],
                order["tokenId"],
                order["makerAmount"],
                order["takerAmount"],
                order["side"],
            ],
        )
        return encoded.hex()

    async def execute_bet(
        self,
        condition_id: str,
        token_id: str,         # YES token_id from market data
        price: float,          # current ask price
        size_usdc: float,      # how much USDC to bet
        slippage: float = 0.02, # 2% max slippage
    ) -> dict:
        """
        Full bet execution flow.
        In manual mode: returns tx calldata for wallet signature.
        In auto mode: signs and broadcasts.
        """
        if not self.wallet.address:
            return {"status": "error", "message": "No wallet connected"}

        # Balance check
        balance = self.wallet.get_usdc_balance(self.wallet.address)
        if balance < size_usdc:
            return {
                "status": "error",
                "message": f"Insufficient USDC balance: {balance:.2f} < {size_usdc:.2f}",
            }

        # Add slippage buffer to price
        max_price = min(price * (1 + slippage), 0.99)

        if EXECUTION_MODE == "manual":
            # Return unsigned transaction data for the frontend to present to MetaMask
            approve_tx = self.wallet.build_approve_tx(self.wallet.address, size_usdc)
            return {
                "status": "pending_signature",
                "mode": "manual",
                "condition_id": condition_id,
                "amount_usdc": size_usdc,
                "price": price,
                "expected_shares": self.wallet.estimate_shares(size_usdc, price),
                "approve_calldata": self.wallet.get_calldata_for_ui(approve_tx),
                "message": "Sign the approval transaction in your wallet, then confirm the bet.",
            }

        # Auto mode — sign and broadcast
        try:
            approve_tx = self.wallet.build_approve_tx(self.wallet.address, size_usdc)
            approve_hash = self.wallet.sign_and_send(approve_tx)

            order = self._build_order(
                token_id=token_id,
                side="BUY",
                price=max_price,
                size_usdc=size_usdc,
                maker_address=self.wallet.address,
            )

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{POLYMARKET_API_BASE}/order",
                    json=order,
                    headers={"Content-Type": "application/json"},
                )

            if resp.status_code in (200, 201):
                order_data = resp.json()
                return {
                    "status": "success",
                    "approve_tx": approve_hash,
                    "order_id": order_data.get("orderID"),
                    "amount_usdc": size_usdc,
                    "expected_shares": self.wallet.estimate_shares(size_usdc, price),
                }
            else:
                return {
                    "status": "error",
                    "message": f"Order rejected by Polymarket: {resp.text[:200]}",
                }

        except Exception as e:
            return {"status": "error", "message": str(e)}
