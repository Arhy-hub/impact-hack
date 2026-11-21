"""The agent's side of paying for energy.

Each step the house uses some electricity. The wallet pays for it from
blocks of credit bought from the supplier, buying a new block (one paid call)
whenever the unspent credit can't cover this step.

If the supplier says payment is required (402), the wallet does **not** stop
the heating dead. It covers safety-level heating from *emergency credit*,
recorded as debt (like a UK prepayment meter), and raises an approval request
with the checkout link so a human can top up. The controller drops all rooms
to the safety floor until credit returns. See docs/DECISIONS.md (W3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .supplier import PaymentRequired


@dataclass
class Receipt:
    step: int
    kwh: float
    pence: float
    carbon_g: float
    blocks_bought: int


@dataclass
class Wallet:
    supplier: object
    customer_ref: str
    credit_pence: float = 0.0  # bought but not yet spent
    spent_pence: float = 0.0
    emergency_pence: float = 0.0  # used while out of credit, owed
    blocks_bought: int = 0
    receipts: list[Receipt] = field(default_factory=list)
    checkout_url: str | None = None  # set while a top-up is needed

    @property
    def needs_topup(self) -> bool:
        return self.checkout_url is not None

    def pay(self, step: int, kwh: float, price_p: float, carbon_g_per_kwh: float) -> bool:
        """Pay for ``kwh`` at ``price_p``. Returns False if it had to use emergency credit."""
        cost = kwh * price_p
        bought = 0
        while self.credit_pence < cost:
            try:
                block = self.supplier.buy_block(self.customer_ref)
            except PaymentRequired as err:
                self.checkout_url = err.checkout_url
                # Use what credit is left, cover the rest from emergency credit.
                self.spent_pence += self.credit_pence
                self.emergency_pence += cost - self.credit_pence
                self.credit_pence = 0.0
                self.receipts.append(Receipt(step, kwh, cost, kwh * carbon_g_per_kwh, bought))
                self.blocks_bought += bought
                return False
            self.credit_pence += block["pence"]
            bought += 1
        self.checkout_url = None
        self.credit_pence -= cost
        self.spent_pence += cost
        self.blocks_bought += bought
        if kwh > 0:
            self.receipts.append(Receipt(step, kwh, cost, kwh * carbon_g_per_kwh, bought))
        return True
