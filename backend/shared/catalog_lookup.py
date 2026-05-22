"""Chat U: deterministic catalog lookup for price/stock questions (no vector DB)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

_PRICE_MARKERS = (
    "price",
    "cost",
    "rate",
    "how much",
    "kitna",
    "kya price",
    "kya rate",
    "mrp",
    "rupees",
    "rs ",
    " rs",
    "₹",
    "inr",
)

_STOCK_MARKERS = (
    "in stock",
    "out of stock",
    "available",
    "availability",
    "stock",
    "inventory",
    "available hai",
    "available hain",
)

_SKU_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9\-]{2,}\b")


def normalize_sku(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) >= 2]


def _asks_price(text: str) -> bool:
    lower = (text or "").lower()
    if re.search(r"\brs\.?\b", lower):
        return True
    return any(m in lower for m in _PRICE_MARKERS if m not in ("rs ", " rs"))


def _asks_stock(text: str) -> bool:
    lower = (text or "").lower()
    if re.search(r"\bstock\b", lower) or re.search(r"\binventory\b", lower):
        return True
    for m in _STOCK_MARKERS:
        if m in ("stock", "inventory"):
            continue
        if m in lower:
            return True
    return False


@dataclass(frozen=True)
class CatalogItemRow:
    sku: str
    name: str
    description: str | None
    price_inr: float
    stock_qty: int


@dataclass(frozen=True)
class CatalogLookupResult:
    action: str  # REPLY | NEEDS_OWNER_DATA
    reply_text: str | None
    intent: str
    routing_intent: str
    missing_fields: list[str]


def fetch_catalog_items(conn: Connection, client_id: str) -> list[CatalogItemRow]:
    rows = conn.execute(
        text(
            """
            SELECT sku, name, description, price_inr::float, stock_qty
            FROM client_catalog_items
            WHERE client_id = CAST(:cid AS uuid) AND active = true
            ORDER BY lower(name)
            """
        ),
        {"cid": client_id},
    ).all()
    out: list[CatalogItemRow] = []
    for r in rows:
        out.append(
            CatalogItemRow(
                sku=str(r[0]),
                name=str(r[1]),
                description=str(r[2]) if r[2] else None,
                price_inr=float(r[3] or 0),
                stock_qty=int(r[4] or 0),
            )
        )
    return out


def fetch_catalog_items_engine(engine: Engine, client_id: str) -> list[CatalogItemRow]:
    with engine.connect() as conn:
        return fetch_catalog_items(conn, client_id)


def _score_item(item: CatalogItemRow, text: str, tokens: list[str]) -> float:
    sku_norm = normalize_sku(item.sku)
    text_norm = (text or "").lower()
    score = 0.0
    if sku_norm and sku_norm in normalize_sku(text_norm):
        score += 100.0
    name_lower = item.name.lower()
    if name_lower and name_lower in text_norm:
        score += 80.0
    name_tokens = _tokenize(item.name)
    if name_tokens:
        overlap = sum(1 for t in name_tokens if t in tokens)
        score += overlap * 15.0
    if item.sku.lower() in text_norm:
        score += 40.0
    return score


def lookup_catalog(batch_text: str, items: list[CatalogItemRow]) -> CatalogLookupResult | None:
    """
    Return a catalog-based routing decision, or None if this message should use generic AI logic.
    """
    if not items:
        return None

    text = (batch_text or "").strip()
    if not text:
        return None

    tokens = _tokenize(text)
    asks_price = _asks_price(text)
    asks_stock = _asks_stock(text)

    scored: list[tuple[float, CatalogItemRow]] = []
    for item in items:
        s = _score_item(item, text, tokens)
        if s > 0:
            scored.append((s, item))
    if not scored:
        if asks_price or asks_stock:
            return CatalogLookupResult(
                action="NEEDS_OWNER_DATA",
                reply_text=None,
                intent="catalog_unknown_product",
                routing_intent="catalog",
                missing_fields=["product_match"],
            )
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    top_score, top_item = scored[0]

    # Avoid hijacking refund/invoice/human flows: only answer without price/stock
    # keywords when the customer message is an exact SKU hit.
    if not asks_price and not asks_stock and top_score < 100:
        return None

    # Ambiguous: multiple strong matches
    strong = [pair for pair in scored if pair[0] >= max(top_score * 0.6, 25)]
    if len(strong) > 1 and (asks_price or asks_stock):
        lines = [f"{it.name} ({it.sku})" for _, it in strong[:5]]
        return CatalogLookupResult(
            action="REPLY",
            reply_text=(
                "I found multiple products that might match. "
                f"Please specify which one you mean: {', '.join(lines)}."
            ),
            intent="catalog_ambiguous",
            routing_intent="catalog",
            missing_fields=[],
        )

    item = top_item
    price_line = f"₹{item.price_inr:.2f}"
    if item.stock_qty > 0:
        stock_line = f"In stock ({item.stock_qty} units available)."
    elif item.stock_qty == 0:
        stock_line = "Currently out of stock."
    else:
        stock_line = "Stock status: please confirm with the store."

    if asks_price and asks_stock:
        reply = (
            f"{item.name} (SKU {item.sku}): price {price_line}. {stock_line}"
        )
    elif asks_price:
        reply = f"{item.name} (SKU {item.sku}) is priced at {price_line}."
    elif asks_stock:
        reply = f"{item.name} (SKU {item.sku}): {stock_line}"
    else:
        reply = f"{item.name} (SKU {item.sku}): {price_line}. {stock_line}"

    return CatalogLookupResult(
        action="REPLY",
        reply_text=reply.strip(),
        intent="catalog_fact",
        routing_intent="catalog",
        missing_fields=[],
    )


def try_catalog_decision_for_ai(
    batch_text: str,
    items: list[CatalogItemRow],
    *,
    needs_owner_customer_reply: str,
) -> dict[str, Any] | None:
    """Map catalog lookup into batch_processor / AIResponse-shaped dict."""
    from backend.apps.ai_engine.helpers.respond_logic import detect_language

    result = lookup_catalog(batch_text, items)
    if result is None:
        return None

    lang = detect_language(batch_text)
    if result.action == "NEEDS_OWNER_DATA":
        return {
            "action": "NEEDS_OWNER_DATA",
            "reply_text": needs_owner_customer_reply,
            "intent": result.intent,
            "routing_intent": result.routing_intent,
            "confidence": 0.88,
            "language": lang,
            "handoff_reason": None,
            "missing_fields": result.missing_fields,
            "risk_reason": None,
        }
    return {
        "action": "REPLY",
        "reply_text": result.reply_text,
        "intent": result.intent,
        "routing_intent": result.routing_intent,
        "confidence": 0.9,
        "language": lang,
        "handoff_reason": None,
        "missing_fields": [],
        "risk_reason": None,
    }
