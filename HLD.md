# HLD: ClearSign

## Architecture Overview

ClearSign is a document-ingestion-to-structured-analysis pipeline wrapped in a consumer SaaS shell. A user uploads a PDF or DOCX, the backend extracts clean text, classifies the contract type, chunks it into clause-level segments, sends those chunks through a typed LLM prompt chain, and returns a structured JSON risk report rendered as a scannable UI. The system has four meaningful components: a frontend (upload + report UI), a backend API server (orchestration, auth, billing), a document processing worker (parsing + chunking), and an LLM gateway layer (prompt dispatch, retry logic, structured output parsing). Stripe handles payments. PostgreSQL stores documents, reviews, and user accounts. Redis handles job queuing for async processing. The whole thing is deployable by one developer in 6 weeks on a single cloud provider with no exotic infrastructure — and should be.

---

## Component Diagram

```
User Browser
    │
    │ HTTPS
    ▼
┌─────────────────────────────────┐
│         Next.js Frontend        │  (Upload UI, Report View, Dashboard)
│         (Vercel or Fly.io)      │
└────────────┬────────────────────┘
             │ REST / JSON
             ▼
┌─────────────────────────────────┐
│      Backend API Server         │  (Node/Express or Python/FastAPI)
│      (Fly.io or Railway)        │
│                                 │
│  - Auth (JWT + email magic link)│
│  - Billing (Stripe webhooks)    │
│  - Document CRUD                │
│  - Job dispatch                 │
└──────┬──────────────┬───────────┘
       │              │
       ▼              ▼
┌────────────┐  ┌─────────────────────────────────────┐
│  PostgreSQL │  │     Document Processing Worker       │
│  (Supabase  │  │     (same server or separate queue)  │
│  or Fly.io) │  │                                      │
└────────────┘  │  1. PDF/DOCX → raw text (pdfplumber  │
       ▲        │     / python-docx)                    │
       │        │  2. Contract type classification      │
       │        │  3. Clause segmentation + chunking    │
       │        │  4. LLM prompt dispatch (per-chunk)   │
       │        │  5. Structured JSON assembly          │
       │        │  6. Risk report written to DB         │
       │        └──────────────┬──────────────────────┘
       │                       │
       │              ┌────────▼────────┐
       │              │   LLM Gateway   │
       │              │                 │
       │              │  OpenAI GPT-4o  │
       │              │  (primary)      │
       │              │                 │
       │              │  Claude 3.5     │
       │              │  Sonnet         │
       │              │  (fallback /    │
       │              │   comparison)   │
       │              └─────────────────┘
       │
       │ (results written back)
       └──────────────────────────────┐
                                      │
                              ┌───────▼──────┐
                              │  Redis Queue │
                              │  (BullMQ)    │
                              │  Job status  │
                              └──────────────┘

External services:
  Stripe → billing/webhooks → Backend API
  ContractsCounsel/Lawfully → upsell deeplink (v1: just a link, no API)
  PostHog → product analytics
  Resend/Postmark → transactional email
```

---

## Data Flow

### Happy path: User uploads a lease

1. **User uploads PDF** via frontend drag-drop or file picker. File is POST'd as multipart to `/api/documents/upload`. File size validated client-side and server-side (max 10MB, v1).

2. **Backend receives file**, authenticates user (JWT), checks entitlement (free tier: has this user already used their 1 free review this month?). If quota exceeded, return 402 with upgrade prompt. If ok, store raw file in **object storage** (S3 or Supabase Storage), create a `documents` DB record with status `QUEUED`, enqueue a processing job in Redis via BullMQ. Return `{ documentId, status: "processing" }` immediately. Do NOT make the user wait synchronously — LLM calls will take 15–45 seconds for a long contract.

3. **Frontend polls** `/api/documents/:id/status` every 3 seconds (or uses a Supabase Realtime subscription) to show a progress indicator. Acknowledge this is a solved UX problem — show "Analyzing clause 3 of 12..." estimated progress.

4. **Worker picks up job**, fetches raw file from object storage, runs **text extraction**:
   - PDF: `pdfplumber` (Python) — handles most PDFs. Fallback: `PyMuPDF`. Scanned PDFs (images only) are a known failure mode — see Failure Modes section.
   - DOCX: `python-docx`. Mostly reliable.
   - Output: clean UTF-8 string.

5. **Contract type classification**: Send first 2,000 tokens to GPT-4o with a lightweight classification prompt. Returns one of: `lease | employment | nda | freelance | service_agreement | terms_of_service | other`. This costs ~$0.002 per document and takes 1–2 seconds. Cheap, do it.

6. **Clause segmentation**: Chunk the full contract into logical clause units. Strategy:
   - Primary: regex + heuristic section-header detection (numbered clauses, ALL-CAPS headers). Fast, free.
   - Secondary: for irregular formatting, use a small LLM call to identify clause boundaries.
   - Target: 10–40 chunks per document. Each chunk ≤ 800 tokens.

7. **Risk analysis — the core LLM call**: For each chunk, dispatch a typed prompt to GPT-4o:
   - System prompt: contract-type-specific risk rubric (e.g., for leases: check for auto-renewal traps, landlord entry rights, penalty clauses, security deposit forfeiture conditions, early termination fees)
   - User message: the clause text
   - Output schema (JSON mode): `{ clause_title, clause_text_excerpt, risk_level: "HIGH|MEDIUM|LOW|NONE", risk_category, plain_english_summary, why_it_matters, what_to_ask_for }`
   - **These calls are parallelized** (Promise.all / asyncio.gather with concurrency limit of 5). A 20-clause contract should complete in 10–15 seconds total LLM time after parallelization.

8. **Assembly**: Collect all clause responses, sort by risk_level DESC, write structured `reviews` record to PostgreSQL. Update document status to `COMPLETE`.

9. **Frontend renders report**: User sees a scannable risk dashboard — HIGH flags at top in red, medium in amber, low in green. Each clause card shows: plain-English summary, severity badge, the original clause text (collapsible), and a "What to ask for instead" suggestion. "Book a real lawyer" CTA appears on any HIGH-risk finding.

10. **Document stored**: User can return to any past review from their dashboard. For free tier, reviews expire after 30 days. Pro tier: permanent.

---

## Key Technical Decisions

| Decision | Choice | Why | Trade-off |
|---|---|---|---|
| **Backend language** | Python (FastAPI) | Best-in-class PDF parsing libraries (pdfplumber, PyMuPDF, python-docx) live in Python. LLM SDK quality is parity. Document processing and API in same language reduces context switching. | Slightly more verbose than Node for REST boilerplate. JavaScript devs will feel friction. |
| **Frontend** | Next.js (App Router) | Full-stack option, good file upload UX primitives, Vercel deployment is trivial. One dev can own it. | App Router has rough edges; RSC adds complexity that's unnecessary in v1. Use Pages Router or keep RSC usage minimal. |
| **Database** | PostgreSQL via Supabase | Relational model fits (users → documents → reviews → clauses). Supabase gives you auth, storage, and Realtime out of the box, collapsing 3 infrastructure decisions into 1. Row-level security handles multi-tenancy. | Supabase vendor lock-in. At scale, you'll want direct Postgres on RDS. Migration is doable but annoying. |
| **Job queue** | BullMQ + Redis | Document processing is async and can fail. You need retries, visibility, dead-letter handling. BullMQ is the standard for Node/Python hybrid setups. | Adds Redis as a dependency. Upstash Redis makes this zero-ops at low scale. |
| **LLM provider** | GPT-4o primary, Claude 3.5 Sonnet secondary | GPT-4o has better JSON mode reliability and faster structured output. Claude is the fallback for rate limit situations and can be toggled per contract type if quality varies. Don't bet on one provider. | Two API keys to manage. Cost monitoring gets more complex. Worth it. |
| **File storage** | Supabase Storage (S3-compatible) | Co-located with DB, trivial setup, row-level security policies apply. | If you leave Supabase, migration is easy (it's S3-compatible). Non-issue. |
| **Auth** | Supabase Auth (magic link + Google OAuth) | Magic link removes password management. Google OAuth covers ~70% of target demographic. Supabase Auth integrates with RLS policies so you don't write auth middleware. | Magic links have deliverability failure modes. Always have a fallback (OTP code). |
| **Payments** | Stripe | Industry standard. Supports subscriptions, one-time payments, webhooks, and customer portal (let users manage their own subscription without you building it). | Stripe's webhook handling is boilerplate you must get right. Use a library or their official guide. |
| **Hosting** | Fly.io for API + worker, Ver