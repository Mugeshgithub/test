# HLD: FrugalFrance

## Architecture Overview
FrugalFrance is a mobile-first barcode-scanning app backed by a light but resilient cloud platform.  
On-device we keep a read-only SQLite/LiteDB cache of the ~200 k most-scanned French grocery GTINs with pre-computed loophole scores. When the user scans a barcode, the app tries the local cache first; a miss or stale entry triggers a call to our HTTPS API. In the cloud, an API Gateway fronts a stateless Scan Service that queries a Postgres/Timescale cluster, returns the latest loophole verdict, and records the scan (device-ID, GTIN, timestamp). A Rules Engine micro-service computes scores on new or updated products. Nightly ETL pipelines ingest Open Food Facts, DGCCRF and INCI Beauty CSV/JSON dumps into S3, diff them, and push changes to Postgres + the mobile delta feed. User “report mismatch” submissions are queued in SQS/Kafka for manual triage and, if accepted, feed back into the rules engine.

The entire backend is containerised (AWS Fargate/ECS) with Terraform IaC; one small Fargate service can comfortably handle v1 load and auto-scales horizontally as scans grow.

## Component Diagram (text)

User → Mobile App  
    │ (scan)  
    │ offline hit ➜ Local SQLite cache  
    │ miss/stale  
    ▼ HTTPS  
[API Gateway]  
    │  
    ▼  
[Scan Service (REST)] ───▶ Postgres/TimescaleDB  
    │                  │  
    │ enqueue               │  
    ▼                  ▼  
[Feedback Queue]  [Rules Engine]  
                  │  
                  ▼  
                Product Scores table  
                  │  
Nightly             │  
ETL / Differs ←──── S3 Raw Dumps ← Open Food Facts, DGCCRF, INCI  

Admin Dashboard → Postgres (readonly)  
CloudWatch/Datadog for logs & metrics

## Data Flow
1. User scans barcode.  
2. App hashes GTIN → looks up in local SQLite; if entry exists & “last_update” ≤ 7 days, return score immediately (<50 ms).  
3. If miss/stale, app calls /scan?gtin=X with anonymous device_id.  
4. Scan Service queries Postgres:  
   a. If product found ‑> return latest score JSON.  
   b. If not found ‑> enqueue GTIN for background enrichment, return “grey / unknown” to user.  
5. Response stored in App’s LRU cache.  
6. User can tap “report mismatch” → POST /feedback {gtin, reason}. Entry pushed to Feedback Queue (SQS).  
7. ETL job 03:00 CET:  
   a. Pull full / incremental dumps from each datasource into S3.  
   b. Diff vs previous snapshot.  
   c. For changed/new products feed Rules Engine container, which recalculates loophole flags & writes to Postgres.  
   d. Export delta (GTIN, verdict, last_update) file signed + GZIP.  
8. Mobile app on launch checks delta manifest; if under 20 MB downloads it to refresh local cache.

## Key Technical Decisions
| Decision | Choice | Why | Trade-off |
|---|---|---|---|
| Database | Postgres + TimescaleDB extension | relational integrity for product meta + time-series weight history; Timescale for efficient shrinkflation queries | Higher memory footprint vs pure KV; need DBA diligence |
| Mobile cache | SQLite with FTS index | Mature, built-in iOS/Android, easy delta import | 40-60 MB app size; older phones limited storage |
| Hosting | AWS Fargate + S3 + RDS | Pay-per-second, zero server patching, scales later | Slightly pricier than Hetzner bare-metal at >1 M scans/day |
| ETL | Python on AWS Batch Spot | Cheap, flexible, cron-like | Cold-start latency; must manage spot terminations |
| Auth | Anonymous UUID v4 stored in SecureStorage; optional email + Firebase Auth for premium later | Fast v1, no PII | Harder to merge histories if user reinstalls |
| Barcode scan lib | Google ML Kit on-device | Fast, offline | Adds 5 MB per platform; not OSS |

## External API & Data Source Audit
| API / Source | What it provides | Free tier limits | Paid tier cost | Coverage gaps | Uptime / reliability | Fallback if unavailable |
|---|---|---|---|---|---|---|
| Open Food Facts API + CSV dump | Product fields, GTIN, weight history, ingredients | Free, volunteer-run; rate-limit 100 req/min; CSV dump daily | Donation; no SLA | ~18 % of French SKUs missing weight history; some GTINs duplicated | Community-maintained ~99 % but no formal SLA | Keep last successful dump on S3; mark data stale in UI after 7 days |
| DGCCRF “Rappel Conso” & fraud rulings CSV | Official recalls & origin fraud caselist | Free; weekly CSV | Free | Only reported/ prosecuted cases; many infractions undetected | Government site; occasional weekend downtime | Cache locally; if >14 days old, suppress origin-fraud flag |
| INCI Beauty dump | Ingredient origin & eco-claims | Free; monthly JSON | Free | Cosmetics only, not food | Volunteer run | Same caching strategy |
| Google ML Kit | On-device barcode scanning | Free offline | N/A | None | N/A – offline | Fallback is server-side ZXing but would add latency |

(unverified columns must be checked before building; DGCCRF uptime not documented—PM to confirm)

## Cost Projection
Assumptions  
• Average scan payload 1 KB in/out.  
• 5 scans/user/day (aligned with success metric).  
• RDS t3.micro for Postgres until 10 k users.  
• Fargate 0.25 vCPU/0.5 GB, 20 % avg CPU, auto-scale every 5 k concurrent scans.  
• Data dumps: 1 GB/day on S3.  

| Scale | Users | Key cost drivers | Estimated €/month | Breaks at |
|---|---|---|---|---|
| v1 launch | 100 | RDS t3.micro €14, Fargate min one task €18, S3 €1, CloudWatch €5, Data Transfer €1 | ≈ €39 | none |
| Growth | 1 000 | RDS t3.small €29, Fargate avg 2 tasks €35, S3 €5, transfer €8 | ≈ €77 | RDS IOPS on t-class |
| Scale | 10 000 | RDS db.t3.medium + 100 GB gp3 €96, Fargate 4 tasks €70, S3 €15, transfer €80 | ≈ €261 | RDS storage & read replica need |
| Viable | 100 000 | RDS db.r6g.large + 1 read replica €500, Fargate 16 tasks €280, S3 €50, transfer €700 | ≈ €1 530 | cache miss rate grows → need Redis or Dynamo; delta downloads hit app store size limits |

Stays under the €500/mo asked for diffing; whole infra crosses €500 only past 50 k WAU.

## Privacy Architecture
• Data reaching backend: GTIN, anonymous device UUID, timestamp, optional feedback text.  
• Logged for analytics: scan count, verdict, latency. Retention 90 days rolling in CloudWatch; aggregated metrics kept.  
• Never leaves device: camera image, precise GPS, personal identifiers. Enforced by not requesting permissions beyond coarse location.  
• Sensitive inference risk: dietary habits. Mitigation: store GTINs hashed with HMAC(key) when >30 days old; retain mapping only recent.  
• GDPR: Using anonymous identifiers → “pseudonymous” data. Support DSAR by deleting UUID rows. Privacy policy must state potential inference.  
• Government subpoena: RDS holds scan logs; purge >90 d reduces liability.

## Scale Analysis
1 k users: all fits in single AZ; cache miss rate 30 %; cold starts fine.  
10 k users: add CloudFront in front of delta files; introduce read replica or enable RDS performance-insights; may add Redis for hot GTINs.  
100 k users: SQLite cache size ≈ 80 MB; won’t auto-update over cellular easily. Need hierarchical cache (top 50 k on device, rest via API) and CDN for verdicts. Backend moves to Aurora Serverless v2 for bursts.

## Failure Modes
1. Data source silent schema change — ETL fails, scores freeze. Mitigation: contract tests + alert if no deltas for >24 