# Build Plan: FrugalFrance (MVP – 4-week “loophole scanner”)

## Build Sequence
0. Repo & CI skeleton — one mono-repo, ESLint/Ruff/Mypy/GitHub Actions.  
   Why 0? Everything else plugs into this; changing linters later = mass churn.

1. Backend bootstrap (`backend/`)  
   • FastAPI app factory + `/health` route + Dockerfile.  
   Why first: lets every other component hit a live URL immediately; unblocks mobile.

2. Pydantic `settings.py` + Terraform remote‐state stubs  
   Why now: every module imports config; infra IDs become constants early to avoid string hunt later.

3. Database schema + Alembic migration 001  
   Why: Rule engine & ETL both depend on tables; rebuilding data model late wrecks two other modules.

4. ETL “happy-path” job  
   • Pull last Open Food Facts dump, load 1 000 GTINs into `products` + `weight_history`.  
   Why before rules: gives real data for scoring unit tests; isolates parsing headaches early.

5. RuleEngine (pure Python, no API yet) + unit tests  
   Why: trickiest logic; develop in isolation with fixtures generated in step 4.

6. ScanService API `/scan` (sync) returning hard-coded “grey” until rules wired.  
   Why: mobile can integrate & iterate UX while backend logic still evolving.

7. Mobile skeleton (Expo)  
   • Navigation, camera permission, barcode read → fetch `/scan` → render verdict stub.  
   Why here: shows end-to-end path works on-device while everything is still small.

8. Wire RuleEngine into ScanService; add latency logging.  
   Now real verdicts flow to mobile demo app.

9. Local GTIN SQLite cache generator (Python script) + React-Native read helper.  
   Why after remote flow proven: avoids premature 80 MB bundle while still guarantees offline later.

10. “Report mismatch” API + SQS enqueue + basic admin SQL.  
    Why near the end: only valuable once verdicts exist.

11. Celery worker + nightly ETL diff scheduler.  
    Why late: live scoring proven; background jobs can fail without blocking user path during demo.

12. Rate limiting & Device UUID signature verification.  
    Why last mile: security/perf harden once core happy path no longer shifting.

## Day 1 Starting Point
Open: `backend/settings.py`  

Goal: runnable FastAPI container that returns `200 OK` on `/health` via Docker Compose.

Prompt to give Claude Code / Cursor:  
```
Generate a Python 3.11 file `settings.py` for a FastAPI project that uses Pydantic v2 BaseSettings.

Requirements:
- Environment variables with defaults for: APP_ENV, POSTGRES_URI, REDIS_URI, SQS_QUEUE_URL, ED25519_PUBLIC_KEY_PEM, ED25519_PRIVATE_KEY_PEM, RATE_LIMIT_PER_MIN, RATE_LIMIT_PER_DAY.
- Provide a `Settings` singleton pattern (`get_settings()`) that caches the load.
- Validate that POSTGRES_URI starts with "postgres://".
- Include a nested `class Config:` with `env_file = ".env"`.
```

Paste output, add to git, commit `feat: settings bootstrap`.

## The 3 Hard Problems
1. Shrinkflation detection accuracy  
   – Weight fluctuations from promo packs & seasonal editions; Open Food Facts often miss 30 % of historic weights.  
   Prep: experiment in notebook, create synthetic edge-case fixtures before writing production code.

2. Shipping & updating 80 MB SQLite on mobile  
   – iOS OTA limits, Android asset decompression quirks, Expo bare/managed differences.  
   Prep: prove zstd-compressed file decompresses in Expo FileSystem in <2 s on mid-range Android.

3. Ed25519 device signature round-trip  
   – Need deterministic cross-platform signature; RN expo-crypto has no Ed25519; must use tweetnacl-js and match PyNaCl server verification.  
   Prep: build spike script signing UUID in JS, verify in Python before baking into auth middleware.

## Don’t Build This Yourself
| What you need | Use this instead | Why not build it | Link |
|---------------|-----------------|------------------|------|
| Barcode scanner | expo-barcode-scanner | Battle-tested, supports EAN-8/13 out-of-box | https://docs.expo.dev/versions/latest/sdk/bar-code-scanner/ |
| Ed25519 crypto (RN) | tweetnacl-js + expo-crypto random | Native modules are a week of pain | https://github.com/dchest/tweetnacl-js |
| Rate limiting | slowapi + Redis | Reinventing token buckets is error-prone | https://slowapi.readthedocs.io |
| Background jobs | Celery + SQS transport | DIY thread pools die on deploy | https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html#amazon-sqs |
| Diffing large CSVs | DuckDB | Pandas alone will OOM on 10 GB dumps | https://duckdb.org/docs/api/python |
| Mobile SQLite bindings | react-native-sqlite-2 | Writing native modules delays store review | https://github.com/GreactNative/react-native-sqlite-2 |

## Validation Checkpoints
- After Step 3 (DB): Run `alembic upgrade head`; psql `\dt`` shows 6 tables – proves schema correct.
- After Step 4 (ETL v0): `SELECT COUNT(*) FROM products;` returns ≥1 000 – ingest works.
- After Step 5 (RuleEngine): `pytest tests/test_rules.py` all green; coverage ≥90 % lines in `rule_engine.py`.
- After Step 6 (API stub): `curl localhost:8000/scan -d '{"gtin":"3033490001401"}'` returns HTTP 200 JSON with verdict `"grey"`.
- After Step 8 (wired rules): Same curl now returns red/amber/green matching fixture GTIN list.
- After Step 9 (local cache): Switch phone to airplane mode, scan cached GTIN – verdict returned in <300 ms.
- Full integration: New GTIN unseen in cache → app calls API online → receives verdict; mismatch tap pushes message to SQS visible in AWS console.

## Minimum Shippable Version
Cut:  
– Offline SQLite cache (ship only top 10 k → 4 MB)  
– Ed25519 signature (use plain UUIDv4 + HTTPS until week 5)  
– Celery scheduler (run ETL manually)  

Keep (non-negotiable):  
– Barcode scan → remote verdict (rules engine) → traffic-light UI  
– Feedback button stores row in DB (sync call; queue later)

Timeline realistic: 18 calendar days for single senior dev + one mobile dev.

## Environment Setup
```bash
# Prereqs
brew install direnv pre-commit
pyenv install 3.11.8
nvm install 20
npm i -g yarn

# Clone & bootstrap
git clone git@github.com:yourorg/frugalfrance.git
cd frugalfrance
direnv allow        # auto-loads .envrc with PYTHONPATH

# Python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pre-commit install

# JS
cd mobile-app
yarn install
expo start          # runs on localhost:19000

# Services via docker-compose
cd ..
docker compose up -d postgres redis localstack
alembic upgrade head
```
Required accounts / keys:
- [ ] AWS (root) – create IAM user & programmatic keys – free tier covers EB, S3, SQS
- [ ] Expo – publish OTA updates – free
- [ ] GitHub – Actions minutes (private repo? 2 000 free)

## Deployment Path
Platform: AWS Elastic Beanstalk single Docker container  

Why not Heroku: Post-Nov-22 free tier gone; EU traffic latency; GPU for ML later pricey.

First deploy:
1. `eb init frugalfrance --platform docker --region eu-west-3`
2. `eb create ff-prod --single --instance_type t3.micro`
3. Set env vars in EB console or `eb setenv` from `.env.prod`
4. `eb deploy`
5. Verify `https://ff-prod.eu-west-3.elasticbeanstalk.com/health`

Domain: buy `frugalfrance.app` at Gandi → Route 53 A-ALIAS → EB CloudFront URL.

## Pushback on LLD
1. TimescaleDB on RDS‐Custom is weeks of ops; for MVP drop to vanilla Postgres + index on `(gtin, recorded_at)`; 12-month diff query runs in <200 ms on 200 k rows.  
2. Terraform managing Elastic Beanstalk leads to drift; manage RDS/Redis/S3 with Terraform, but keep EB via `eb cli`.  
3. SQLite 200 k GTIN (80 MB) busts App Store cellular download cap (200 MB) after a few releases; start with 50 k (20 MB) + lazy remote lookups; measure miss rate before scaling bundle.

This plan gets a usable, demo-ready loophole scanner into real shoppers’ hands inside 3 weeks, with clear guard-rails against yak-shaving and 2 AM rewrites.