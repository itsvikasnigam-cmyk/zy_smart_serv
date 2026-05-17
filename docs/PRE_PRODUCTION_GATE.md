# Pre-production gate — real WhatsApp + billing + clients

Use this **before** final testing with real Meta numbers, Razorpay/Paddle, and live customers.

Always start tool commands with:

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window; . .\dev-env.ps1
```

## What is already built (dev slice)

- Gateway, AI, workers, inbox, billing APIs, Flutter owner + super-admin UIs
- Alert → SOP auto-run, owner broadcast screen, billing read + Razorpay checkout API

## P0 — You must do these (not all automatic in code)

| Step | Action |
|------|--------|
| 1 | **Public HTTPS** for Meta (`/webhooks/meta` on **8081**) and billing webhooks (**8086**) — use ngrok/Cloudflare tunnel or staging host |
| 2 | Root **`.env`**: `META_APP_SECRET`, `META_VERIFY_TOKEN`, `META_ACCESS_TOKEN`, `BILLING_*` keys |
| 3 | `python backend/tools/dev_seed.py --meta-phone-number-id <YOUR_META_ID> --trial-days 14` |
| 4 | `python backend/tools/seed_bill_plans.py` with your Razorpay plan IDs |
| 5 | Create tenant: `POST /signup` **or** `setup_dev_logins.py` on seeded client |
| 6 | Run workers: `batch_processor`, `outbox_sender`, optional `metrics_rollup_worker` |
| 7 | Keep `WA_GATEWAY_ALLOW_CLIENT_ID_HEADER=false` in production |

## P1 — Product paths now in repo

| Feature | How |
|---------|-----|
| New business signup | `POST http://127.0.0.1:8085/signup` (trial + `trial_end`) |
| Shared trial line routing | `python backend/tools/map_trial_customer.py` |
| Change plan for testing | `python backend/tools/set_client_plan.py --plan growth` |
| Razorpay checkout (API) | `POST /billing/razorpay/create-checkout` on **8086**; Flutter **Billing → Upgrade (Razorpay test)** |
| Readiness report | `python backend/tools/pre_production_checklist.py` |

## P2 — Still future / manual

- OTP auth, team users, catalog CRUD (M3 remainder)
- Full Razorpay Checkout SDK in Flutter (today: shows order + key for sandbox test)
- Paddle UI, KYC verify workflow, MRR dash tiles
- `/ops/releases*`, CI Postgres job
- Meta app review, production WABA policies

## Service map

| Port | Service |
|------|---------|
| 8081 | `wa_gateway` — Meta |
| 8083 | `ai_engine` |
| 8085 | `client_api` — login, inbox, signup |
| 8086 | `billing_api` |
| 8087 | `ops_api` |

## Suggested first real-life test

1. Seed WA line + signup owner  
2. Send WhatsApp message to your business number from your personal phone  
3. Confirm inbox in Flutter (owner)  
4. Razorpay sandbox checkout → webhook → `entitlement_plan` becomes `starter`/`growth`  
5. Super admin: Runs + Alerts if billing webhook fails  
