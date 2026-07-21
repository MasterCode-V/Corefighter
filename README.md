# CORE FIGHTER — Backend

**Language:** English (this file) · [日本語 README](./README.ja.md)

AI-powered article draft generation, review, approval and WordPress publication
system for a second-hand goods (buyback) business.

This repository implements the **complete backend** for the project — covering
both delivery stages described in the plan:

- **Stage 1 (AI generation foundation):** FastAPI backend, PostgreSQL + pgvector
  schema, image upload, product-info entry, AI image analysis, product-info
  extraction, article draft generation, prompt assembly and generation history.
- **Stage 2 (operational flow):** dashboard data, buyback/article lists,
  publication waiting list, minor editing, regeneration, similarity checking,
  search/filtering, job & error history, WordPress REST integration (draft,
  update, publish) and the approval workflow.

The frontend (Stage 2 UI) is a separate application that consumes this API.

---

## Architecture

```
Frontend (separate)
      │  HTTPS / JSON
      ▼
FastAPI main backend ───────────────┐  synchronous, fast operations
  (auth, CRUD, validation, approval) │  (auth, stores, personas, purchases,
      │ creates Job row              │   article edit, approval, dashboards)
      ▼
Redis (ARQ) job queue
      │
      ▼
Background worker(s) ────────────────┐  slow / external operations
  (image analysis, generation,       │  (OpenAI + WordPress calls)
   validation, similarity, WP sync)   │
      ▼
PostgreSQL + pgvector   OpenAI API    WordPress REST API   S3 / MinIO storage
```

Every long-running action follows the same contract (workflow 16):
FastAPI validates the request → creates a `Job` row (source of truth) →
enqueues it on Redis → returns a `job_id`. A worker picks it up, transitions the
job `PENDING → QUEUED → RUNNING → COMPLETED` (with `RETRYING`/`FAILED`
branches), saves the result and updates entity status. The frontend polls
`GET /api/v1/jobs/{id}`.

### Why this stack

- **PostgreSQL + pgvector** — one database for relational data *and* vector
  similarity search (no separate vector DB to operate). Cosine distance over
  OpenAI embeddings powers the "< 50% similarity" requirement (workflow 7).
- **Redis + ARQ** — async-native job queue that fits FastAPI's async stack, with
  explicit DB-backed status/retry handling for full auditability.
- **S3 / MinIO** — product images live in object storage, not the DB.

---

## Project structure

```
cw1/
├── docker-compose.yml         # db (pgvector) + redis + minio + api + worker
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── .env.example
│
├── migrations/                # Alembic (async) migration environment
│   ├── env.py
│   └── versions/
│
├── scripts/
│   ├── init_db.py             # create pgvector extension + tables + vector index
│   └── seed.py                # first admin, demo store, persona, content rules
│
└── app/
    ├── main.py                # FastAPI app + lifespan
    ├── enums.py               # all status/type enumerations (single source)
    │
    ├── core/                  # infrastructure
    │   ├── config.py          # env-driven settings (pydantic-settings)
    │   ├── database.py        # async SQLAlchemy engine/session
    │   ├── redis.py           # ARQ pool helpers
    │   ├── storage.py         # S3/MinIO async client
    │   ├── security.py        # JWT, password hashing, credential encryption
    │   ├── logging.py
    │   └── deps.py            # auth dependencies + RBAC guards
    │
    ├── models/                # SQLAlchemy ORM (one file per domain)
    │   ├── user.py  store.py  persona.py  content_rule.py
    │   ├── purchase.py        # Purchase + PurchaseImage
    │   ├── article.py         # Article + ArticleVersion (history)
    │   ├── embedding.py       # PublishedCorpus + CorpusEmbedding (pgvector)
    │   ├── similarity.py  job.py  log.py
    │
    ├── schemas/               # Pydantic request/response models
    │
    ├── integrations/
    │   ├── openai_client.py   # vision analysis, generation, embeddings
    │   └── wordpress_client.py# WP REST API (media, posts, taxonomy, sync)
    │
    ├── services/              # business logic reused by API + workers
    │   ├── job_service.py     # create/enqueue/retry jobs
    │   ├── article_service.py # versioning + generation context loading
    │   ├── prompt_builder.py  # persona + rules + structure -> prompt
    │   ├── validation.py      # article validation (workflow 6)
    │   └── text_utils.py      # normalize / chunk / text similarity
    │
    ├── api/
    │   ├── router.py
    │   └── v1/
    │       ├── auth.py  users.py  stores.py  personas.py
    │       ├── content_rules.py  purchases.py  articles.py
    │       ├── approval.py  wordpress.py  jobs.py  dashboard.py
    │
    └── workers/
        ├── settings.py        # ARQ WorkerSettings + cron (scheduled sync)
        ├── base.py            # process_job dispatcher + retry/status logic
        └── handlers/
            ├── image_analysis.py     # workflow 4
            ├── generation.py         # workflows 5, 6, 8
            ├── similarity.py         # workflow 7
            └── wordpress.py          # workflows 11-15
```

---

## Data model (high level)

| Table                | Purpose |
|----------------------|---------|
| `users`              | Accounts + roles (ADMIN / STORE_MANAGER / STORE_STAFF) |
| `stores`             | Stores; scope for staff/managers |
| `wordpress_sites`    | Per-store WordPress connection (app password encrypted) |
| `personas`           | AI writing personas (global or per-store) |
| `content_rules`      | Prohibited words/contexts, brand rules, structure rules |
| `purchases`          | Buyback records + product info (AI-extracted & manual) |
| `purchase_images`    | Uploaded images (article/eye-catch + detail) in S3 |
| `articles`           | Lifecycle status + current version + WordPress mapping |
| `article_versions`   | Immutable version history (generation, regeneration, edits) |
| `published_corpus`   | Published articles used as similarity comparison target |
| `corpus_embeddings`  | pgvector embeddings for the corpus |
| `similarity_results` | Similarity score, most-similar articles, repeated sections |
| `jobs`               | Background job status/history (source of truth) |
| `activity_logs`      | Audit / posting / error history for dashboards |

---

## Running locally (Docker — recommended, full stack)

Starts **PostgreSQL + Redis + MinIO + API + worker + frontend** together.

```bash
cp .env.example .env
# Generate real secrets:
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
# Put the two values, plus your OPENAI_API_KEY, into .env

docker compose up --build
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/docs
# MinIO UI: http://localhost:9001  (minioadmin / minioadmin)

# Seed the first admin + パワトレ stores/personas (in another terminal):
docker compose exec api python -m scripts.seed
```

Login: `admin@corefighter.local` / `admin12345` (override via `FIRST_ADMIN_*` in `.env`).

The frontend container serves the built React app via nginx and proxies `/api` to the API service.
## Running locally (without Docker)

Requires PostgreSQL 16 with the `vector` extension, Redis and a MinIO/S3 endpoint.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt

cp .env.example .env              # then edit values

python -m scripts.init_db         # create extension + tables + vector index
python -m scripts.seed            # baseline data

uvicorn app.main:app --reload                     # API
arq app.workers.settings.WorkerSettings           # worker (separate terminal)
```

### Simple test frontend (optional)

A minimal React UI for manual testing (image upload → analyze → generate → preview):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — login with the seed admin, upload images, enter text,
run **Analyze images** then **Generate article**. The Vite dev server proxies `/api`
to the FastAPI backend on port 8000.

### Database migrations (Alembic)

`scripts/init_db.py` is the quick-start path. For versioned schema changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

---

## End-to-end flow (matches the specification workflows)

1. `POST /auth/login` → obtain access token.
2. `POST /purchases` → create buyback record (status `UNSTARTED`). *(wf 3)*
3. `POST /purchases/{id}/images` → upload article + detail images. *(wf 3)*
4. `POST /purchases/{id}/analyze` → `IMAGE_ANALYSIS` job; worker extracts
   manufacturer/product/model/category/condition/characteristics. *(wf 4)*
5. `PATCH /purchases/{id}` → staff reviews/corrects extracted info. *(wf 4)*
6. `POST /purchases/{id}/generate` → `ARTICLE_GENERATION` job → validation
   (wf 6) → auto `SIMILARITY_CHECK` (wf 7). *(wf 5)*
7. `GET /articles/waiting-list` → review; `POST /articles/{id}/edit` (minor edit,
   new version) or `POST /articles/{id}/regenerate` (wf 8).
8. `POST /approval/{id}/submit` → `WAITING_APPROVAL`. *(wf 9-10)*
9. `POST /approval/{id}/decision` (admin) → approve creates `WORDPRESS_DRAFT`
   job (wf 11) / return / hold / reject. *(wf 10)*
10. Editing an approved draft → `WORDPRESS_UPDATE` (same post id). *(wf 12)*
11. `POST /wordpress/{id}/publish` → verifies approval + similarity + existing
    draft, then `WORDPRESS_PUBLISH`; saves URL & date; refreshes corpus. *(wf 13)*
12. On WordPress failure → job `RETRYING` → `FAILED`, article `WORDPRESS_ERROR`,
    admin `POST /wordpress/{id}/retry`. *(wf 14)*
13. `POST /wordpress/sync` and the daily cron rebuild the similarity corpus. *(wf 15)*
14. `GET /jobs/{id}` polls any job; `GET /dashboard/summary` and
    `GET /dashboard/logs` power the admin dashboard. *(wf 16)*

Interactive API docs (with every endpoint and schema) are served at `/docs`.

---

## Roles

| Role            | Capabilities |
|-----------------|--------------|
| `ADMIN`         | Everything, including approval & publishing across all stores |
| `STORE_MANAGER` | Manage own store's personas/rules, submit for approval |
| `STORE_STAFF`   | Register purchases, generate/edit drafts for own store |
