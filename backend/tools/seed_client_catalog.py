"""Seed or update tenant catalog rows (Chat U).

Usage:

    python backend/tools/seed_client_catalog.py --client-id <uuid> --sku WIDGET-A --name "Widget A" --price 499 --stock 12
    python backend/tools/seed_client_catalog.py --client-id <uuid> --list
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    p = argparse.ArgumentParser(description="Seed client_catalog_items for Chat U.")
    p.add_argument("--client-id", required=True)
    p.add_argument("--list", action="store_true", help="Print active catalog rows and exit")
    p.add_argument("--sku", default=None)
    p.add_argument("--name", default=None)
    p.add_argument("--description", default=None)
    p.add_argument("--price", type=float, default=None, help="price_inr")
    p.add_argument("--stock", type=int, default=None, help="stock_qty")
    p.add_argument("--inactive", action="store_true", help="Deactivate SKU instead of upserting")
    args = p.parse_args()
    cid = args.client_id.strip()

    with engine.begin() as conn:
        if args.list:
            rows = conn.execute(
                text(
                    """
                    SELECT sku, name, price_inr, stock_qty, active
                    FROM client_catalog_items
                    WHERE client_id = CAST(:cid AS uuid)
                    ORDER BY lower(name)
                    """
                ),
                {"cid": cid},
            ).all()
            if not rows:
                print("(no catalog rows)")
                return 0
            for r in rows:
                print(f"{r[0]}\t{r[1]}\t₹{r[2]}\tstock={r[3]}\tactive={r[4]}")
            return 0

        if not args.sku or not args.name:
            print("ERROR: --sku and --name required unless --list", file=sys.stderr)
            return 2

        if args.inactive:
            conn.execute(
                text(
                    """
                    UPDATE client_catalog_items
                    SET active = false, updated_at = now()
                    WHERE client_id = CAST(:cid AS uuid) AND sku = :sku
                    """
                ),
                {"cid": cid, "sku": args.sku.strip()},
            )
            print(f"OK: deactivated {args.sku}")
            return 0

        price = args.price if args.price is not None else 0.0
        stock = args.stock if args.stock is not None else 0
        conn.execute(
            text(
                """
                INSERT INTO client_catalog_items (
                  client_id, sku, name, description, price_inr, stock_qty, active
                )
                VALUES (
                  CAST(:cid AS uuid), :sku, :name, :desc, :price, :stock, true
                )
                ON CONFLICT (client_id, sku) DO UPDATE SET
                  name = EXCLUDED.name,
                  description = EXCLUDED.description,
                  price_inr = EXCLUDED.price_inr,
                  stock_qty = EXCLUDED.stock_qty,
                  active = true,
                  updated_at = now()
                """
            ),
            {
                "cid": cid,
                "sku": args.sku.strip(),
                "name": args.name.strip(),
                "desc": args.description,
                "price": price,
                "stock": stock,
            },
        )
    print(f"OK: catalog {args.sku} for client {cid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
