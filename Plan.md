# Build Plan: ClearSign

## Build Sequence

**The core logic here**: Build the pipeline first, prove it works end-to-end on real contracts before touching auth, billing, or UI polish. The biggest risk isn't "can we build a dashboard?" — it's "does the LLM reliably extract structured risk data from messy real-world contract PDFs?" Validate that first. Everything else is plumbing.

1. **Backend environment + database schema** — Everything else writes to or reads from this. Schema migrations are painful to undo. Define the data model once, correctly, before writing a single service layer. Alembic from day one, not "we'll add migrations later."

2. **Document extraction pipeline (extractor + segmenter)** — The unsexy foundation that determines whether the entire product works. PDF parsing on real-world contracts is nasty. Scanned PDFs, two-column layouts, headers baked into text, tables that destroy clause boundaries — you need to know what your actual text quality looks like before you write a single LLM prompt. Build this in isolation, test it with 10 real contracts, read the output manually.

3. **LLM gateway + classification prompt** — The provider abstraction layer before any prompt work. Once this exists, you can swap providers, add retries, and log everything in one place. Classification (what type of contract is this?) is the cheapest LLM call and the fastest way to prove the gateway works.

4. **Risk rubrics + analyzer (core value)** — The thing the whole product exists to do. Build one rubric completely (lease), validate the structured output quality, then template the others. Do not build all 7 rubrics before testing one end-to-end — you'll discover the schema is wrong on rubric 1 and throw away 6 rubrics' worth of work.

5. **Celery worker + task orchestration** — Wire the pipeline into an async job. At this point you should be able to drop a PDF into a function call and get a structured risk report back. No API, no UI, no auth. Just: file in → JSON out.

6. **FastAPI routers (documents, reviews, health)** — Now that the pipeline works, expose it via HTTP. Start with the happy path only: upload a file, get back a job ID, poll for status, retrieve results.

7. **Supabase auth + RLS** — Auth comes after the API works, not before. Why: you'll iterate on the pipeline structure constantly in the first week. Auth adds a mandatory header to every test call, which slows you down when the thing you're iterating on has nothing to do with auth. Add it once the core routes are stable.

8. **Entitlement + quota system** — Depends on auth (need a user identity) and the review flow (need to know what you're gating). Build this as a single `entitlement_service.py` that the dependencies layer calls — it should be easy to stub during development and easy to test in isolation.

9. **Stripe integration** — Billing after entitlements because entitlements define what billing unlocks. Stripe webhooks before the portal UI — the webhook is what actually grants access; the portal is just convenience.

10. **Next.js frontend (upload flow first)** — Upload → polling → results view. This is the critical path for a real user. Dashboard, history, and profile are secondary.

11. **Dashboard + document history** — Useful but not blocking the first user. Ship after the core flow works.

12. **Disclaimer, LawyerUpsell, error states, edge case UI** — Last. These matter but they're all wrappers around a working core.

---

## Day 1 Starting Point

- **Open**: `backend/app/db/migrations/env.py` after running `alembic init`
- **Goal**: Postgres is running locally via Docker Compose, all four tables exist (`users`, `documents`, `reviews`, `clauses`), and `alembic upgrade head` runs without errors. You can connect with a DB client and see the schema.

**Prompt to give Claude Code / Cursor:**

```
I'm building a contract review SaaS called ClearSign. I need you to set up the full database schema and migration.

Tech stack: Python FastAPI backend, SQLAlchemy 2.0 async, Alembic, PostgreSQL 16, Supabase (but we're using Supabase as a managed Postgres — we'll access it via SQLAlchemy directly in the backend, not via the Supabase client library in Python).

Create the following files with complete, production-ready content:

1. backend/app/models/user.py
   - UserProfile table (id: UUID PK, supabase_user_id: UUID unique not null, email: str, tier: enum [FREE, PRO, PER_DOC], stripe_customer_id: str nullable, created_at, updated_at)
   - Tier is a Python Enum. Use SQLAlchemy mapped_column syntax (SQLAlchemy 2.0 style, not legacy declarative).

2. backend/app/models/document.py
   - Document table (id: UUID PK, user_id: UUID FK → user_profiles.id, filename: str, storage_path: str, contract_type: enum nullable [LEASE, EMPLOYMENT, NDA, FREELANCE, SERVICE_AGREEMENT, TERMS_OF_SERVICE, OTHER], status: enum [PENDING, PROCESSING, COMPLETE, FAILED], raw_text: Text nullable, error_message: str nullable, created_at, updated_at)

3. backend/app/models/review.py
   - Review table (id: UUID PK, document_id: UUID FK → documents.id unique, high_count: int default 0, medium_count: int default 0, low_count: int default 0, summary: Text nullable, created_at)

4. backend/app/models/clause.py
   - ClauseAnalysis table (id: UUID PK, review_id: UUID FK → reviews.id, clause_index: int, original_text: Text, plain_english: Text, severity: enum [HIGH, MEDIUM, LOW, NONE], category: str, recommendation: Text nullable, is_standard: bool default false, created_at)

5. backend/app/db/session.py
   - Async SQLAlchemy engine using DATABASE_URL from environment
   - AsyncSession factory
   - Base declarative class that all models import from
   - get_db() async generator for FastAPI Depends()

6. backend/alembic.ini and backend/app/db/migrations/env.py
   - Configured for async Alembic (use AsyncAdaptedQueuePool)
   - Imports all four models so autogenerate sees them
   - Reads DATABASE_URL from environment

7. docker-compose.yml at the project root
   - postgres:16 service with persistent volume, port 5432, credentials via environment
   - redis:7-alpine service, port 6379
   - No application containers yet — just infrastructure

8. backend/.env.example with all required variables including DATABASE_URL format for local Docker Postgres

After creating these files, show me the exact commands to:
- Start Docker Compose
- Run the first Alembic autogenerate migration
- Apply it
- Verify the tables exist

Use SQLAlchemy 2.0 async patterns throughout. No legacy Session, no old-style Column() syntax.
```

---

## The 3 Hard Problems

### 1. PDF Text Extraction Quality on Real Consumer Contracts

**Why it's harder than it looks**: The LLD mentions pdfplumber + PyMuPDF as if this is a solved problem. It is not. Consumer contracts arrive in four forms, and two of them are brutal:

- **Text-layer PDFs** (e.g., e-signed DocuSign output): pdfplumber handles these fine.
- **Scanned-to-PDF** (e.g., a lease photographed and saved as PDF, a car dealership fax): These contain zero extractable text. You get an image. pdfplumber returns an empty string. PyMuPDF returns an empty string. You need OCR (Tesseract via pytesseract, or AWS Textract for accuracy). The LLD doesn't mention this at all.
- **Multi-column PDFs** (e.g., some employment agreements): pdfplumber extracts text left-to-right across the full page width, which interleaves columns and produces nonsense. You need explicit column detection logic.
- **DOCX with tracked changes** (e.g., a negotiated contract with revision history): python-docx will extract both the original and revised text as one blob unless you explicitly handle revision runs.

**What to research before starting**:
- `pdfplumber` layout analysis: the `words` extraction with `x_tolerance` parameters for column detection.
- `pytesseract` + `pdf2image` pipeline for scanned document fallback — and whether to use it yourself or just call AWS Textract ($0.0015/page, essentially free at your scale).
- `python-docx` revision/track-changes handling.

**The specific failure mode**: A user uploads a scanned lease (very common — landlords use PDFs from 2009 scan jobs), your extractor returns empty string, the LLM receives empty input, the LLM either hallucinates a review or returns an error. User sees "analysis failed" on the most important contract type your product serves. This needs to be caught at the extraction layer with a confidence score, not at the LLM layer.

**Estimate**: The LLD implies extraction is 2–3 days. Budget 8–10 days to handle scanned PDFs properly and to build a text-quality validation step that rejects or OCRs low-confidence extractions before they hit the LLM.

---

### 2. Clause Segmentation — The Boundary Problem

**Why it's harder than it looks**: Contracts don't have clean clause boundaries. The LLD lists `segmenter.py` as one file with no complexity noted. In reality:

- **Numbered sections work fine**. Section 12. Termination. Easy.
- **Run-on provisions don't**. A single paragraph in a residential lease can contain: rent amount, due date, late fee policy, grace period, and a unilateral rent increase clause — all in one sentence. Does that get chunked as one clause or five? If you send it as one, the LLM risk flag for "unilateral rent increase" gets conflated with "standard rent amount clause." If you chunk it as five, you lose context that makes the late fee clause risky.
- **Cross-references break context**. "Subject to Section 14(b)" in Section 3 is meaningless without Section 14(b). Clause-level analysis misses this.
- **Recitals and definitions sections** generate false positives if fed to the risk analyzer — the LLM will flag "WHEREAS the Tenant..." as suspicious language.

**The specific edge case that will bite you**: Your segmenter confidently splits a 40-page employment agreement into 200 "clauses" and sends 200 LLM calls. At ~$0.005/call, that's $1 per document, which destroys your margin at $7 per-document pricing. You need a batching strategy: group short related clauses into chunks of ~800 tokens, not individual sentences. The segmenter needs token-awareness.

**What to research before starting**: LangChain's `RecursiveCharacterTextSplitter` with overlap — it's not perfect for contracts but it's a proven starting point. Build your own boundary detection on top of it, using regex for numbered section headers as hard split points and the text splitter as the fallback.

---

### 3. Stripe Webhooks + Entitlement State Sync

**Why it's always the integration point that breaks**:

Stripe's subscription lifecycle has ~15 distinct webhook events. The LLD lists `billing_service.py` handles webhook events. The actual failure modes:

- **`checkout.session.completed`** fires before **`customer.subscription.created`** in some flows. If your webhook handler upgrades the user on `checkout.session.completed` and your worker reads their tier 200ms later, the subscription record may not exist yet. Race condition.
- **`invoice.payment_failed`** can fire multiple times with retry logic. Your handler needs to be **idempotent** — processing the same webhook twice should not double-downgrade a user or send two "payment failed" emails.
- **Webhook signature verification** requires the raw request body, not the parsed JSON. FastAPI's `Request` body is read as a stream. If you run the request body through Pydantic before reaching the webhook handler, you've consumed the stream and Stripe's `construct_event()` will fail with a signature mismatch. This is a subtle and common bug that produces confusing errors.
- **Local testing**: Stripe webhooks require the Stripe CLI (`stripe listen --forward-to localhost:8000/billing/webhook`) for local development. This is a non-obvious dev dependency that every new developer on the project needs to know about. Document it in the README from day one.

**What to research before starting**: The Stripe Python docs specifically on [webhook signature verification with FastAPI](https://stripe.com/docs/webhooks/signatures) — note the `await request.body()` pattern required to preserve the raw bytes. Set up the Stripe CLI as part of environment setup, not as an afterthought.

---

## Don't Build This Yourself

| What you need | Use this instead | Why not build it | Link |
|---|---|---|---|
| PDF text extraction (clean PDFs) | `pdfplumber` | Battle-tested, handles layout analysis, active maintenance | `pip install pdfplumber` |
| PDF text extraction (scanned/image PDFs) | `pytesseract` + `pdf2image` OR AWS Textract API | OCR is a research problem; Tesseract took decades to build; Textract handles tables and multi-column natively | Search: "aws textract python boto3" |
| DOCX parsing | `python-docx` | No viable alternative exists | `pip install python-docx` |
| Text chunking / clause segmentation baseline | `langchain-text-splitters` (`RecursiveCharacterTextSplitter`) | Token-aware splitting with overlap is subtle to implement correctly; this handles the math | `pip install langchain-text-splitters` |
| LLM structured output validation | Pydantic v2 + OpenAI JSON mode | You will get malformed JSON from the LLM on ~2% of calls; Pydantic catches it before it writes garbage to your DB | Already in stack |
| LLM retry + fallback logic | `tenacity` | Exponential backoff with jitter is a solved problem; rolling it yourself introduces subtle bugs | `pip install tenacity` |
| Background jobs | Celery + Redis (already in LLD) | Correct choice | Already in stack |
|