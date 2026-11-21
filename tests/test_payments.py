import pytest
from fastapi.testclient import TestClient

from heatwise.supplier import LocalSupplier, PaymentRequired, create_app, make_supplier
from heatwise.wallet import Wallet


def test_local_supplier_requires_payment_then_sells_blocks():
    sup = LocalSupplier(block_pence=10)
    with pytest.raises(PaymentRequired) as err:
        sup.buy_block("house1")
    assert "checkout" in err.value.checkout_url
    assert sup.checkout("house1", 1.00) == 10
    assert sup.buy_block("house1")["pence"] == 10
    assert sup.balance_blocks("house1") == 9


def test_customer_ref_is_validated():
    sup = LocalSupplier()
    for bad in ["", "a b", "x" * 65, "../etc", "<script>"]:
        with pytest.raises(ValueError):
            sup.buy_block(bad)


def test_wallet_buys_blocks_as_needed():
    sup = LocalSupplier(block_pence=10)
    sup.checkout("house1", 1.00)
    w = Wallet(sup, "house1")
    assert w.pay(step=0, kwh=0.5, price_p=25.0, carbon_g_per_kwh=200)  # 12.5p -> 2 blocks
    assert w.blocks_bought == 2
    assert w.spent_pence == pytest.approx(12.5)
    assert w.credit_pence == pytest.approx(7.5)
    assert w.receipts[0].carbon_g == pytest.approx(100)


def test_wallet_uses_emergency_credit_and_flags_topup():
    sup = LocalSupplier(block_pence=10)
    sup.checkout("house1", 0.10)
    w = Wallet(sup, "house1")
    assert not w.pay(0, kwh=1.0, price_p=25.0, carbon_g_per_kwh=200)  # 25p, only 10p available
    assert w.needs_topup
    assert w.spent_pence == pytest.approx(10)
    assert w.emergency_pence == pytest.approx(15)
    sup.checkout("house1", 1.00)
    assert w.pay(1, kwh=0.1, price_p=25.0, carbon_g_per_kwh=200)
    assert not w.needs_topup


def test_zero_use_costs_nothing():
    w = Wallet(LocalSupplier(), "house1")
    assert w.pay(0, 0.0, 30.0, 200)
    assert w.receipts == [] and w.blocks_bought == 0


def test_http_supplier_402_then_200():
    client = TestClient(create_app(LocalSupplier()))
    r = client.post("/buy_energy", json={"customer_ref": "house1"})
    assert r.status_code == 402 and r.json()["checkoutUrl"]
    assert client.post("/checkout", json={"customer_ref": "house1", "pounds": 1}).status_code == 200
    assert client.post("/buy_energy", json={"customer_ref": "house1"}).status_code == 200


def test_http_rejects_bad_input():
    client = TestClient(create_app(LocalSupplier()))
    assert client.post("/buy_energy", json={"customer_ref": "a b"}).status_code == 422
    assert client.post("/checkout", json={"customer_ref": "h", "pounds": -5}).status_code == 422
    assert client.post("/checkout", json={"customer_ref": "h", "pounds": 10_000}).status_code == 422


def test_make_supplier_defaults_to_local(monkeypatch):
    monkeypatch.delenv("SOLVAPAY_SECRET_KEY", raising=False)
    assert isinstance(make_supplier(), LocalSupplier)
