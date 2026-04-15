# LLD: FrugalFrance – v1 (4-week build)

## Tech Stack
| Layer | Choice | Version | Reason |
|---|---|---|---|
| Mobile | React-Native (Expo SDK 50) | RN 0.73 | 1 code-base, built-in SQLite, camera + ML-Kit modules are pre-integrated |
| Backend API | Python 3.11 + FastAPI 0.110 | 0.110 | Async, type hints, automatic OpenAPI, <500 LOC to deliver 3 endpoints |
| Rules / ETL | Python 3.11 + Pandas 2.2 + DuckDB 0.9 | 0.9 | Vectorised diffing, zero external DB in batch job; keeps infra ≤ €500 |
| DB | Postgres 15 + TimescaleDB 2.13 | 2.13 | Mature, shrinkflation queries need time-series; Timescale adds hypertables |
| Queue | AWS SQS | latest | Fully-managed, dead-simple for mismatch feedback |
| Auth | Signed device-UUID (Ed25519) + JWT schematic reserved for premium | N/A | No PII, can be revoked; signature prevents forged UUIDs |
| Hosting | AWS Elastic Beanstalk Docker single-container + RDS-Postgres | EB 3 | Cheaper & simpler than ECS/Fargate for one service, auto-scales later |

🏷️  Push-back Applied: The HLD splits “Scan Service” & “Rules Engine” into micro-services. For a 4-week MVP we collapse them into one FastAPI container with a background Celery worker. Fewer deployables, fewer things to monitor.

## Folder Structure
```
frugalfrance/
├── mobile-app/                 # React-Native (Expo) project
│   ├── App.tsx                 # Entry; navigation & camera screen
│   ├── screens/
│   │   ├── ScannerScreen.tsx   # ML-Kit barcode scan + cache lookup
│   │   ├── ProductScreen.tsx   # Verdict display
│   │   └── ReportScreen.tsx    # “report mismatch”
│   ├── data/
│   │   ├── sqlite.db           # Pre-bundled 200 k GTIN cache
│   │   └── delta/              # Incremental cache updates
│   └── utils/
│       └── cache.ts            # LRU + stale logic
├── backend/
│   ├── Dockerfile
│   ├── main.py                 # FastAPI app factory
│   ├── api/
│   │   ├── routes.py           # /scan, /feedback, /health
│   │   └── schemas.py          # Pydantic request / response
│   ├── services/
│   │   ├── scan_service.py     # GTIN lookup, rate-limit guard
│   │   ├── rule_engine.py      # shrinkflation/origin/eco logic
│   │   └── feedback_service.py # enqueue + admin review helper
│   ├── models/                 # SQLAlchemy ORM
│   │   ├── base.py
│   │   ├── product.py
│   │   ├── loophole_score.py
│   │   ├── scan_log.py
│   │   └── mismatch_report.py
│   ├── tasks/                  # Celery async jobs
│   │   ├── etl_ingest.py       # nightly dump pull + diff
│   │   └── recalc_scores.py    # triggered by diff or unknown GTIN
│   ├── settings.py             # Pydantic-based config loader
│   └── alembic/                # DB migrations
└── infra/
    ├── terraform/              # RDS, SQS, S3, Beanstalk
    └── monitor/                # CloudWatch alarms, dashboards
```

## Data Model (Postgres 15)
1. products  
   • gtin              VARCHAR(14)  PK  
   • name              TEXT  
   • brand             TEXT  
   • category          TEXT NULL  
   • created_at        TIMESTAMPTZ DEFAULT now()  
   • updated_at        TIMESTAMPTZ  

2. weight_history  (Timescale hypertable)  
   • gtin              VARCHAR(14) FK → products  
   • recorded_at       TIMESTAMPTZ  
   • net_weight_g      NUMERIC(6,1)  
   PK = (gtin, recorded_at)

3. loophole_scores  
   • gtin              VARCHAR(14) PK  
   • verdict           verdict_enum  -- red | amber | green | grey  
   • shrinkflation     BOOLEAN NOT NULL  
   • origin_mislabel   BOOLEAN NOT NULL  
   • eco_claim_issue   BOOLEAN NOT NULL  
   • evidence_json     JSONB         -- links & textual explanation  
   • computed_at       TIMESTAMPTZ  

4. scans  
   • id                BIGSERIAL PK  
   • device_uuid       CHAR(44)  -- Ed25519-signed UUID (base64)  
   • gtin              VARCHAR(14)  
   • verdict           verdict_enum  
   • latency_ms        INT  
   • scanned_at        TIMESTAMPTZ DEFAULT now()  

5. mismatch_reports  
   • id                BIGSERIAL PK  
   • device_uuid       CHAR(44)  
   • gtin              VARCHAR(14)  
   • reason            TEXT  
   • status            status_enum  -- pending | accepted | rejected  
   • created_at        TIMESTAMPTZ  
   • reviewed_at       TIMESTAMPTZ NULL  
   • reviewer_id       TEXT NULL

6. etl_source_files  
   • id                BIGSERIAL PK  
   • source            TEXT   -- openfoodfacts | dgccrf | inci  
   • file_date         DATE  
   • checksum_sha256   CHAR(64)  
   • processed_at      TIMESTAMPTZ  

Enums:
verdict_enum, status_enum

Indexes:
• weight_history (gtin, recorded_at DESC)  
• scans (device_uuid, scanned_at DESC)  

## Core Abstractions
1. ScanService  
   Responsibility: single public method `get_verdict(gtin, device_uuid)` returning verdict & details.  
   Why: centralised rate-limit, logging, and cache layer—mobile & admin tools must yield identical scores.

2. RuleEngine  
   Responsibility: stateless function `score_product(ProductSnapshot) -> LoopholeScore`.  
   Why: pure, unit-testable; can later be spawned into its own micro-service or Lambda with zero refactor.

3. ETLJob (Ingest)  
   Responsibility: download dump, store on S3, diff via DuckDB SQL, push changed GTINs to Celery queue.  
   Why: decouples ingestion schedule from scoring throughput; isolates parsing quirks per data source.

4. DeviceUUIDVerifier  
   Responsibility: verify Ed25519 signature once per request.  
   Why: prevents malicious scripts from faking millions of UUIDs; keeps rate-limit meaningful.

## Security & Rate Limiting
Authentication  
• Each app install generates UUIDv4 → signed server-held Ed25519 private key.  
• Mobile attaches header `X-Device-ID: <uuid>.<signatureBase64>`.  
• Backend verifies signature; rejects on failure (HTTP 401).

Rate Limiting  
• Library: `slowapi` for FastAPI, Redis-backed (ElastiCache t4g.small)  
• Limits:  
  - 30 requests / minute per device UUID  
  - 1000 requests / day per IP (catches rotated UUID attacks)  
• On limit breach: HTTP 429 with `Retry-After`; **fail closed** (no score).

Transport & Storage  
• All traffic TLS 1.2+.  
• RDS encryption at rest (AES-256); S3 buckets SSE-S3.  
• weight_history & loophole_scores non-personal.  
• `device_uuid` salted SHA-256 in scans table after 90 days via scheduled DB job.

Data-minimisation  
• Camera frame never leaves device.  
• No precise GPS collected—only coarse supermarket GEO pulled from France open dataset, entirely client-side.

## Coding Standards
1. Naming: snake_case for Python, camelCase for TypeScript; DB columns lowercase with underscores.  
2. Error handling: Every API route returns RFC 7807 Problem JSON on errors; never expose stack trace.  
3. Linting / CI: `ruff + mypy --strict` for Python; `eslint + typescript --noImplicitAny` for RN. Test coverage gate 80 %.

## What NOT to Abstract Yet
• Multi-tenant data partitions — unnecessary until enterprise white-label becomes real.  
• Pluggable datastore interface — Postgres is fine; swapping now wastes time.  
• Premium subscription flow — stub JWT claims but don’t build payment integration this sprint.

## Pushback on HLD
1. Micro-services for v1 add AWS Fargate, IAM roles, extra CI pipelines—burns week 3. A single FastAPI + Celery worker in one Docker image is enough. Split later.  
2. 200 k GTIN SQLite (~80 MB) may exceed OTA download quota. Compress with zstd, ship only top 50 k (≈18 MB) plus delta API; upgrade in v2.  
3. TimescaleDB good call, but ensure RDS-Custom supports extensions; regular RDS-Postgres does not. Alternative: self-host Timescale on EC2 or drop to plain Postgres and compute 12-month diffs in pipeline.  
4. Terraform for full infra is fine, but EB environments emit their own CloudFormation; double IaC causes drift. Keep Terraform for RDS/S3/Redis only.

## Instructions for Programmer
1. First file: `backend/settings.py` (Pydantic BaseSettings). Every module imports config; CI, tests and Docker all depend on it.  
2. Trickiest part: shrinkflation detection. Edge cases: weight change due to seasonal promotion packs; ignore changes <10 % or lasting <30 days. Unit-tests with fixtures from Open Food Facts.  
3. Gotchas:  
   • EAN-8 barcodes must be left-padded to EAN-13 before DB lookup.  
   • Some DGCCRF rows list multiple GTINs in one cell ↔ split during ETL.  
   • Device clocks may be wrong; use server time for scans.  
4. Defer: admin reviewer UI; for now accept mismatch via psql or Retool. Payment & premium gating postponed until MAU > 5000.

Done – this blueprint is executable, lean, and keeps the team inside 4-week scope while leaving growth levers open.