"""The energy supplier the agent buys from, behind a paywall.

The agent buys energy in fixed **blocks** (``BLOCK_PENCE``, default 10p).
One paid call buys one block. This matches how SolvaPay meters usage: each
paid call records exactly one unit (see ``solvapay.paywall.decide.track_usage``),
so a variable amount per call is not possible. See docs/DECISIONS.md (W1).

Two interchangeable suppliers:

* ``LocalSupplier``: an in-memory ledger that behaves like the SolvaPay
  paywall (402 and a checkout link when the customer has no blocks left). Used
  for tests and whenever no SolvaPay key is configured.
* ``SolvaPaySupplier``: the real thing. Wraps the purchase with
  ``solvapay.payable`` against the sandbox, using ``SOLVAPAY_SECRET_KEY`` and
  ``SOLVAPAY_PRODUCT_REF`` from the environment. The product's plan must be set
  up in the SolvaPay dashboard so one unit costs one block (10p).

``make_supplier()`` picks SolvaPay when a key is present, local otherwise.
``create_app()`` exposes either one over HTTP as ``POST /buy_energy``.
"""

from __future__ import annotations

import asyncio
import itertools
import os
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

BLOCK_PENCE = 10
_CUSTOMER_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class PaymentRequired(Exception):
    """No credit left. ``checkout_url`` is where a human can approve a top-up."""

    def __init__(self, checkout_url: str, message: str = "Payment required"):
        super().__init__(message)
        self.checkout_url = checkout_url


def validate_customer_ref(customer_ref: str) -> str:
    if not isinstance(customer_ref, str) or not _CUSTOMER_RE.match(customer_ref):
        raise ValueError("customer_ref must be 1-64 letters, digits, '_' or '-'")
    return customer_ref


@dataclass
class LocalSupplier:
    """Paywall stand-in: customers buy blocks via ``checkout``, spend them via ``buy_block``."""

    block_pence: int = BLOCK_PENCE
    blocks: dict[str, int] = field(default_factory=dict)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    name = "local"

    def checkout(self, customer_ref: str, pounds: float) -> int:
        """Simulate a human paying ``pounds`` at checkout. Returns blocks added."""
        validate_customer_ref(customer_ref)
        if pounds <= 0:
            raise ValueError("top-up must be positive")
        added = int(round(pounds * 100)) // self.block_pence
        self.blocks[customer_ref] = self.blocks.get(customer_ref, 0) + added
        return added

    def buy_block(self, customer_ref: str) -> dict:
        validate_customer_ref(customer_ref)
        if self.blocks.get(customer_ref, 0) <= 0:
            raise PaymentRequired(f"local://checkout?customer={customer_ref}")
        self.blocks[customer_ref] -= 1
        return {"block_id": f"blk_{next(self._ids)}", "pence": self.block_pence}

    def balance_blocks(self, customer_ref: str) -> int:
        return self.blocks.get(customer_ref, 0)


class SolvaPaySupplier:
    """Real SolvaPay sandbox paywall. Needs ``SOLVAPAY_SECRET_KEY`` and ``SOLVAPAY_PRODUCT_REF``.

    Not exercised by the test suite (it needs a live sandbox account). Verify by
    hand: see README, "Running against the SolvaPay sandbox".
    """

    name = "solvapay"

    def __init__(self, block_pence: int = BLOCK_PENCE):
        from solvapay import PaywallError, create_solvapay  # imported lazily: optional dependency

        self.block_pence = block_pence
        self._paywall_error = PaywallError
        self._loop = asyncio.new_event_loop()
        self._sp = create_solvapay()
        self._ids = itertools.count(1)

        @self._sp.payable()
        async def buy_energy_block(*, customer_ref: str) -> dict:
            return {"block_id": f"blk_{next(self._ids)}", "pence": self.block_pence}

        self._buy = buy_energy_block

    def buy_block(self, customer_ref: str) -> dict:
        validate_customer_ref(customer_ref)
        try:
            return self._loop.run_until_complete(self._buy(customer_ref=customer_ref))
        except self._paywall_error as err:
            raise PaymentRequired(str(err.gate.get("checkoutUrl", "")), str(err)) from err

    def checkout(self, customer_ref: str, pounds: float) -> int:
        raise RuntimeError("With SolvaPay, top-ups happen in the browser at the checkout URL.")

    def close(self) -> None:
        self._loop.run_until_complete(self._sp.aclose())
        self._loop.close()


def make_supplier():
    """SolvaPay when ``SOLVAPAY_SECRET_KEY`` is set, otherwise the local stand-in."""
    if os.environ.get("SOLVAPAY_SECRET_KEY"):
        return SolvaPaySupplier()
    return LocalSupplier()


class Buy(BaseModel):
    customer_ref: str = Field(pattern=_CUSTOMER_RE.pattern)


class TopUp(Buy):
    pounds: float = Field(gt=0, le=500)  # cap so a typo can't create silly balances


def create_app(supplier=None):
    """HTTP front for a supplier: ``POST /buy_energy`` returns 200 with a receipt or 402."""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse

    supplier = supplier or make_supplier()
    app = FastAPI(title="Heatwise mock energy supplier", docs_url=None, redoc_url=None)

    @app.post("/buy_energy")
    def buy_energy(body: Buy):
        try:
            return supplier.buy_block(body.customer_ref)
        except PaymentRequired as err:
            return JSONResponse(status_code=402, content={"error": "payment_required", "checkoutUrl": err.checkout_url})

    @app.post("/checkout")
    def checkout(body: TopUp):
        if not isinstance(supplier, LocalSupplier):
            raise HTTPException(404, "checkout happens on SolvaPay")
        return {"blocks_added": supplier.checkout(body.customer_ref, body.pounds)}

    return app
