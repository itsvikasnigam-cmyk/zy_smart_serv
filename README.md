# ZY Smart Serv (v6.1)

Backend services (FastAPI) for WhatsApp Gateway, AI engine, Client API, Billing, Dashboards, SOPs.

## Local dev (Phase A/B)

1. Copy environment file.
   - `backend/.env.example` → `backend/.env`
2. Create a venv and install deps.
   - `pip install -r backend/requirements.txt`
3. Run migrations (requires `DATABASE_URL` env var set).
   - PowerShell example:
     - `$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"`
     - `alembic -c backend/alembic.ini upgrade head`
3. Run WA Gateway.
   - `uvicorn backend.apps.wa_gateway.main:app --reload --port 8081`

Health:
- `GET /health`
- `GET /ready`

## Non-dev local smoke test (no SQL)

Prereq: Postgres running locally with db `zysmart` and user/pass `postgres/postgres`.

1) Set DB env var (PowerShell):
- `$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"`

2) Run migrations:
- `alembic -c backend/alembic.ini upgrade head`

3) Seed a test client + WA number mapping (replace the ID with your Meta `phone_number_id`):
- `python backend/tools/dev_seed.py --meta-phone-number-id <META_PHONE_NUMBER_ID>`

4) Start services (3 terminals):
- WA gateway: `uvicorn backend.apps.wa_gateway.main:app --reload --port 8081`
- AI engine: `uvicorn backend.apps.ai_engine.main:app --reload --port 8083`
- Batch worker: `$env:AI_ENGINE_URL="http://127.0.0.1:8083"; python backend/workers/batch_processor.py`

5) Send a test inbound message:
- `python backend/tools/dev_send_inbound.py --meta-phone-number-id <META_PHONE_NUMBER_ID> --from +919999999999 --text "Hi"`

6) Wait ~5 seconds and check DB outputs:
- `python backend/tools/dev_check.py`

