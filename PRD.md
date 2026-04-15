# PRD: ClearSign

## The Problem
Consumers sign legally binding contracts — leases, employment agreements, freelance contracts, Terms of Service, car purchase agreements — without understanding what they're agreeing to, because real lawyers cost $300–$500/hour and most people won't pay that for a $40/month gym contract. The asymmetry is brutal: the other party had a lawyer draft it; you didn't have one read it.

## The User
A 28–42 year old professional — renter, freelancer, first-time homebuyer, or small business owner — who regularly signs contracts with real financial stakes but treats legal review as an unaffordable luxury, not a standard step.

## The Core Insight
People don't need legal *advice* — they need legal *literacy*. They don't want to know what the law says; they want to know what *they're agreeing to* and whether it's normal. The gap isn't access to lawyers, it's access to a trusted translator. LLMs are exceptionally good at exactly this task — reading dense text and producing plain-English summaries — and contract review is one of the few domains where the model doesn't need to be right 100% of the time to deliver enormous value over the current baseline of "user signs without reading anything."

---

## Competitive Landscape

- **DoNotPay**: Started as consumer rights automation, moved into contract review. Overpromised, underdelivered, had a very public credibility collapse in 2023, and tried to do too many things (sue anyone, fight parking tickets, etc.). Users don't trust it for high-stakes documents. Its contract review is shallow and not the core product.

- **LegalZoom**: Offers lawyer-assisted review for $100–$300+ per document. Real lawyers, real cost, real wait times (24–72 hours). This is the premium competitor — it's correct but inaccessible for routine contracts. Nobody uses LegalZoom to review their gym membership.

- **Ironclad / Contract Lifecycle Management (CLM) tools**: B2B tools built for legal teams at companies. Require procurement, onboarding, integration. Consumer-hostile by design. Solve the wrong problem for our user.

- **ChatGPT / Claude (direct)**: Users already do this — paste contracts into GPT and ask what's wrong. It works, but there's zero structure, no consistent risk-flagging framework, no document management, no UX designed for the workflow, and most users don't know to do this or don't know how to prompt it well. This is the real baseline threat: a free tool that's "good enough" for sophisticated users.

**Our differentiator**: A structured, contract-type-aware review workflow — with pre-trained risk rubrics per contract category (lease, employment, freelance, NDA, etc.) — that surfaces specific red-flag clauses in plain English with severity ratings, not just a wall of AI text.

---

## Monetization

- **Model**: Freemium → Paid subscription, with a per-document option as the entry point.
- **Who pays**: The consumer, directly.
- **Pricing structure**:
  - **Free tier**: 1 contract review/month, basic flag summary only (no clause-level detail, no recommendations)
  - **Pro — $12/month**: Unlimited reviews, clause-level breakdown, severity scoring, red flag explanations, and comparison to "market standard" language
  - **Per-document**: $7/document for users who don't sign contracts regularly — captures renters, car buyers, one-time users
- **Reasoning**: $12/month is an impulse-purchase price point for someone staring at a lease they're about to sign. It's a rounding error compared to what bad contracts cost. Per-document pricing removes commitment friction. Freemium drives top-of-funnel via the exact moment users need it (a contract lands in their inbox).
- **Path to expansion**: B2B-lite tier — freelancers, small agencies, and solo operators who process contracts weekly. This is $40–$80/month territory and requires almost no additional product work in v2.

**Hard question addressed**: Yes, the free tier of ChatGPT competes. Our response: (1) structured output is substantially better UX; (2) most users don't know how to use raw LLMs for this; (3) ClearSign owns the workflow, not just the answer — upload, analyze, track, revisit. We win on experience, not raw capability.

---

## Core Technology Assumption

**Key bet**: A well-prompted frontier LLM (GPT-4o or Claude 3.5 Sonnet) with contract-type-specific system prompts and a structured output schema can reliably identify materially risky clauses — auto-renewal traps, unilateral amendment clauses, broad IP assignment, unlimited liability, non-compete overreach — with low enough false-negative rates to be genuinely useful and low enough false-positive rates to maintain trust.

**Evidence it works**:
- Published benchmarks show GPT-4o and Claude perform at or above the median human lawyer on contract clause identification tasks (Lawyer.com / LegalBench, 2023).
- User behavior already validates the demand: "review my contract ChatGPT" is a high-volume search query.
- Structured extraction via JSON schema from LLM APIs is production-proven and well-documented.

**If wrong**:
- If the model hallucinates clause risks or misses critical red flags consistently, user trust collapses fast and the product is actively harmful.
- **Fallback**: Every output carries a mandatory, un-dismissable disclaimer that this is not legal advice and the user should consult a licensed attorney for high-stakes decisions. Tier 2 mitigation: integrate a "book a lawyer review" upsell via a marketplace API (e.g., Lawfully, ContractsCounsel) for users who want a human second opinion — this becomes a revenue share opportunity.

**Existential risk acknowledged**: If OpenAI or Anthropic launches a native "review my contract" feature in their consumer products, differentiation must come from workflow, trust, and specialization — not model quality. Build the moat in UX and rubric quality, not in the LLM.

---

## What We're Building (v1 only)

1. **Document upload and parsing** — PDF/DOCX upload, clean text extraction, automatic contract-type detection (lease, employment, NDA, freelance, service agreement). Essential because the workflow must be zero-friction from the first second.

2. **Clause