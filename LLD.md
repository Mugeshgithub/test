# LLD: ClearSign

## Tech Stack

| Layer | Choice | Version | Reason |
|---|---|---|---|
| Frontend | Next.js (Pages Router) | 14.2 | App Router RSC adds complexity with no v1 payoff. Pages Router is stable, well-documented, and one developer can ship it. Vercel deployment is zero-config. |
| Backend API | FastAPI | 0.111 | Co-locates with Python document processing workers. Async-native. Auto-generates OpenAPI docs. Pydantic v2 validation is fast and catches malformed LLM output before it hits the DB. |
| Background Workers | Celery | 5.4 | BullMQ (HLD choice) is Node-native. Since the backend is Python, Celery + Redis is the idiomatic choice. Same language, same deploy unit, no cross-language queue bridging. |
| Database | PostgreSQL | 16 via Supabase | Relational model is correct here. Supabase bundles auth, row-level security, storage, and Realtime — collapses 4 infrastructure decisions for a 1–2 dev team. |
| Auth | Supabase Auth | latest | Magic link + Google OAuth. RLS enforces data isolation without custom middleware. |
| Object Storage | Supabase Storage | latest | S3-compatible. RLS policies apply. Zero additional vendor. |
| Job Queue / Cache | Redis via Upstash | 7.x | Zero-ops Redis. Celery broker + result backend. Rate limiting state. |
| LLM — Primary | OpenAI GPT-4o | gpt-4o-2024-08-06 | Best structured output (JSON mode) reliability. Parallel function calling. Pin the model date-string — "gpt-4o" alias drifts. |
| LLM — Fallback | Anthropic Claude 3.5 Sonnet | claude-3-5-sonnet-20241022 | Provider redundancy. Toggle per contract type if quality diverges. |
| PDF Parsing | pdfplumber + PyMuPDF | 0.11.1 / 1.24 | pdfplumber for text-layer PDFs. PyMuPDF as fallback for malformed PDFs. Both are battle-tested. |
| DOCX Parsing | python-docx | 1.1 | Standard. No viable alternative. |
| Payments | Stripe | stripe-python 10.x | Subscriptions + one-time payments + customer portal. Webhooks handled via FastAPI endpoint. |
| Email | Resend | resend-python 2.x | Transactional email. Simple API. Good deliverability. Postmark is an equally valid swap. |
| Analytics | PostHog | posthog-python 3.x / posthog-js 1.x | Product analytics. Self-hostable later if privacy becomes a concern. |
| Frontend HTTP | Axios | 1.7 | Consistent interceptor pattern for auth headers and error normalization. Could use fetch; Axios wins on retry/interceptor ergonomics at this scale. |
| Frontend State | Zustand | 4.5 | Lightweight. No boilerplate. React Query handles server state (document polling); Zustand handles UI state (upload progress, modal state). |
| Frontend Server State | TanStack Query | 5.x | Document status polling, review data fetching, cache invalidation. Replaces manual setInterval polling suggested in HLD. |
| Hosting — Frontend | Vercel | — | Zero-config Next.js deployment. Edge caching for static assets. |
| Hosting — API + Worker | Fly.io | — | Single Dockerfile, two process types (API + Celery worker). Cheap at this scale. |
| Containerization | Docker + Docker Compose | — | Local dev parity. Fly.io deploys from Dockerfile. |
| Monitoring | Sentry | sentry-sdk 2.x (Python), @sentry/nextjs 8.x | Error tracking in both layers. Captures LLM failures, parsing errors, job failures. |

---

## Folder Structure

```
clearsign/
│
├── frontend/                          # Next.js 14 (Pages Router)
│   ├── pages/
│   │   ├── _app.tsx                   # Global providers: QueryClient, PostHog, Sentry
│   │   ├── _document.tsx              # HTML shell
│   │   ├── index.tsx                  # Landing page / marketing
│   │   ├── login.tsx                  # Magic link + Google OAuth
│   │   ├── dashboard.tsx              # User's document history
│   │   ├── upload.tsx                 # Upload flow (drag-drop + file picker)
│   │   ├── review/
│   │   │   └── [documentId].tsx       # Risk report view
│   │   └── api/
│   │       └── auth/
│   │           └── [...supabase].ts   # Supabase Auth callback handler
│   ├── components/
│   │   ├── upload/
│   │   │   ├── DropZone.tsx           # Drag-drop file input, file type + size validation
│   │   │   ├── UploadProgress.tsx     # Progress indicator during analysis
│   │   │   └── ContractTypeSelector.tsx  # Manual override for contract type
│   │   ├── review/
│   │   │   ├── RiskSummaryCard.tsx    # Top-level counts: X HIGH, Y MEDIUM, Z LOW
│   │   │   ├── ClauseCard.tsx         # Individual clause: severity badge, summary, collapsible original text
│   │   │   ├── SeverityBadge.tsx      # HIGH/MEDIUM/LOW/NONE styled chip
│   │   │   ├── DisclaimerBanner.tsx   # Mandatory, un-dismissable legal disclaimer — see Security section
│   │   │   └── LawyerUpsellCTA.tsx    # Shown on HIGH-risk findings; links to ContractsCounsel
│   │   ├── dashboard/
│   │   │   ├── DocumentList.tsx       # Paginated list of past reviews
│   │   │   └── DocumentCard.tsx       # Status, contract type, date, risk summary
│   │   ├── billing/
│   │   │   ├── PricingTable.tsx       # Free / Pro / Per-doc plans
│   │   │   └── ManageBillingButton.tsx  # Opens Stripe Customer Portal
│   │   └── shared/
│   │       ├── Navbar.tsx
│   │       ├── LoadingSpinner.tsx
│   │       ├── ErrorBoundary.tsx
│   │       └── Modal.tsx
│   ├── hooks/
│   │   ├── useDocumentStatus.ts       # TanStack Query polling hook — polls until COMPLETE or FAILED
│   │   ├── useUpload.ts               # Upload mutation + optimistic state
│   │   └── useUser.ts                 # Supabase Auth session wrapper
│   ├── lib/
│   │   ├── supabaseClient.ts          # Browser Supabase client (anon key only)
│   │   ├── apiClient.ts               # Axios instance with auth header injection
│   │   └── constants.ts               # Risk levels, contract types, plan limits
│   ├── types/
│   │   └── index.ts                   # Shared TypeScript types matching backend Pydantic schemas
│   ├── styles/
│   │   └── globals.css                # Tailwind base
│   ├── public/
│   ├── .env.local                     # NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                           # Python FastAPI + Celery
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory, middleware registration, router mounting
│   │   ├── config.py                  # Pydantic Settings — reads all env vars, single source of truth
│   │   ├── dependencies.py            # FastAPI Depends() functions: get_current_user, require_pro, check_quota
│   │   │
│   │   ├── routers/
│   │   │   ├── documents.py           # POST /documents/upload, GET /documents, GET /documents/{id}/status
│   │   │   ├── reviews.py             # GET /reviews/{document_id} — returns full structured report
│   │   │   ├── billing.py             # POST /billing/checkout, POST /billing/portal, POST /billing/webhook
│   │   │   └── health.py              # GET /health — liveness probe for Fly.io
│   │   │
│   │   ├── services/
│   │   │   ├── document_service.py    # Business logic: create document record, check quota, dispatch job
│   │   │   ├── review_service.py      # Fetch + format review data for API response
│   │   │   ├── billing_service.py     # Stripe checkout session, portal session, webhook event handling
│   │   │   └── entitlement_service.py # "Can this user submit a review?" — tier, quota, expiry logic
│   │   │
│   │   ├── workers/
│   │   │   ├── celery_app.py          # Celery app init, broker/backend config, task routing
│   │   │   ├── tasks.py               # process_document task — orchestrates the full pipeline
│   │   │   └── pipeline/
│   │   │       ├── extractor.py       # PDF/DOCX → clean UTF-8 text
│   │   │       ├── classifier.py      # LLM contract type classification
│   │   │       ├── segmenter.py       # Text → clause chunks
│   │   │       ├── analyzer.py        # LLM risk analysis per chunk (parallelized)
│   │   │       └── assembler.py       # Clause results → structured DB records
│   │   │
│   │   ├── llm/
│   │   │   ├── gateway.py             # Provider abstraction: route to GPT-4o or Claude, retry logic, fallback
│   │   │   ├── prompts/
│   │   │   │   ├── classification.py  # System + user prompt for contract type detection
│   │   │   │   ├── segmentation.py    # Prompt for irregular clause boundary detection
│   │   │   │   └── risk_rubrics/
│   │   │   │       ├── base.py        # Shared risk analysis prompt scaffold
│   │   │   │       ├── lease.py       # Lease-specific rubric: auto-renewal, landlord entry, penalties
│   │   │   │       ├── employment.py  # Employment: non-compete, IP assignment, at-will carve-outs
│   │   │   │       ├── nda.py         # NDA: scope, duration, exclusions, jurisdiction
│   │   │   │       ├── freelance.py   # Freelance: payment terms, IP, kill fees, IP reversion
│   │   │   │       ├── service_agreement.py
│   │   │   │       ├── terms_of_service.py
│   │   │   │       └── other.py       # Generic fallback rubric
│   │   │   └── schemas.py             # Pydantic models for LLM output validation
│   │   │
│   │   ├── models/
│   │   │   ├── user.py                # User — mirrors Supabase auth.users with extended profile
│   │   │   ├── document.py            # Document entity
│   │   │   ├── review.py              # Review entity
│   │   │   └── clause.py             # ClauseAnalysis entity
│   │   │
│   │   ├── db/
│   │   │   ├── session.py             # SQLAlchemy async engine + session factory
│   │   │   └── migrations/            # Alembic migrations
│   │   │       ├── env.py
│   │   │       └── versions/          # Migration files (never edit, only add)
│   │   │
│   │   └── utils/
│   │       ├── storage.py             # Supabase Storage upload/download wrappers
│   │       ├── rate_limiter.py        # Redis-backed sliding window rate limiter
│   │       └── errors.py              # Custom exception classes + FastAPI exception handlers
│   │
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_extractor.py      # Parser unit tests with real PDF fixtures
│   │   │   ├── test_segmenter.py
│   │   │   ├── test_classifier.py     # Mock LLM calls
│   │   │   └── test_entitlement.py    # Quota + tier logic — no external deps, must be fast
│   │   ├── integration/
│   │   │   ├── test_upload_flow.py    # Full upload → queue → mock worker → status check
│   │   │   └── test_billing_webhook.py  # Stripe webhook event replay tests
│   │   └── fixtures/
│   │       ├── sample_lease.pdf
│   │       ├── sample_nda.docx
│   │       └── llm_responses/         # Canned LLM responses for deterministic tests
│   │
│   ├── Dockerfile                     # Multi-stage: base → api (uvicorn) / worker (celery)
│   ├── requirements.txt
│   ├── alembic.ini
│   └── .env                           # Never committed. See .env.example
│
├