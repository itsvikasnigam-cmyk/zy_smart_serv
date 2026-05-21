from __future__ import annotations

from backend.shared.catalog_lookup import CatalogItemRow, lookup_catalog


def _items() -> list[CatalogItemRow]:
    return [
        CatalogItemRow(
            sku="WIDGET-A",
            name="Widget A",
            description=None,
            price_inr=499.0,
            stock_qty=12,
        ),
        CatalogItemRow(
            sku="GADGET-B",
            name="Gadget B",
            description=None,
            price_inr=999.0,
            stock_qty=0,
        ),
    ]


def test_price_by_sku_deterministic() -> None:
    r = lookup_catalog("What is the price of WIDGET-A?", _items())
    assert r is not None
    assert r.action == "REPLY"
    assert r.intent == "catalog_fact"
    assert "499" in (r.reply_text or "")
    assert "WIDGET-A" in (r.reply_text or "")


def test_stock_out_of_stock() -> None:
    r = lookup_catalog("Is GADGET-B in stock?", _items())
    assert r is not None
    assert r.action == "REPLY"
    assert "out of stock" in (r.reply_text or "").lower()


def test_unknown_product_needs_owner_data() -> None:
    r = lookup_catalog("How much is the mystery product?", _items())
    assert r is not None
    assert r.action == "NEEDS_OWNER_DATA"
    assert r.intent == "catalog_unknown_product"
    assert "product_match" in r.missing_fields


def test_name_with_price_keyword() -> None:
    r = lookup_catalog("What is the price of Widget A?", _items())
    assert r is not None
    assert r.action == "REPLY"
    assert "499" in (r.reply_text or "")


def test_no_catalog_intent_returns_none() -> None:
    r = lookup_catalog("What are your store hours tomorrow?", _items())
    assert r is None
