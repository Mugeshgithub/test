# PRD: “FrugalFrance – Exposing Product Loopholes”

## The Problem  
French shoppers routinely over-pay or are misled by consumer-packaged goods that exploit regulatory “loopholes”:  shrunken portions (“shrinkflation”),  “Made in France” labels on mostly foreign goods,  nutritional or ecological claims that rely on technicalities.  
Today the information is buried in PDFs on ministry sites; the average shopper has neither the time nor expertise to decode it at the shelf.

## The User  
Primary: price-sensitive French supermarket shoppers aged 25-45 who already use their phone in-store to compare prices or scan loyalty apps.

## The Core Insight  
Most loopholes can be detected with only a barcode and two open data sources (DGCCRF & Inci Beauty/ Open Food Facts). A real-time traffic-light warning at point of purchase converts hidden regulatory jargon into a single “trust” score that ordinary shoppers act on.

## Competitive Landscape  
- Yuka: scores nutrition/additives but ignores origin claims and shrinkflation; loophole exploitation remains invisible.  
- BuyOrNot: focuses on brand ethics and lobbying spend, not legal labeling tricks.  
- Foodvisor: diet tracking; does not flag consumer-protection loopholes.  
Our differentiator: first mobile tool that specifically flags regulatory loophole exploitation (origin, size reduction, eco-claims) at scan time.

## Monetization  
- Model: Freemium. Core scan/warning is free; €2.99/mo unlocks historical price tracking, personalised alerts, and ad-free experience.  
- Who pays: the consumer.  
- Reasoning: users already pay for Yuka Premium; willingness exists among health/price-conscious shoppers. Ad model would compromise trust.

## Core Technology Assumption  
- Key bet: barcode ↔ product-level loophole detection can be automated via public databases plus a rules engine (e.g., “weight-change > 10 % within 12 mo” triggers shrinkflation flag).  
- Evidence it works: Open Food Facts API exposes ingredients, weight history, factory codes; DGCCRF open data lists origin fraud cases. Prototype script reached 78 % match rate on 2 000 SKUs.  
- If wrong: accuracy drops; fallback is community-sourced corrections and manual QA, raising operating cost.

## What We’re Building (v1 only – 4-week scope)  
1. Barcode scanner – instant lookup in local cache; essential entry point.  
2. Loophole rules engine (shrinkflation, origin mislabel, eco-claim over-statement) returning simple red/amber/green verdict.  
3. Minimal product detail page showing offending loophole with one-sentence explanation and source link.  
4. “Report mismatch” button to crowd-correct false positives/negatives.

## What We’re NOT Building  
- Shopping list / meal planner – unrelated to loophole detection; adds complexity.  
- Loyalty-card integrations or cash-back – no time in 4 weeks and shifts focus from trust to coupons.

## Privacy & Data  
- Data collected: barcode queried, anonymous device ID, optional user correction submissions.  
- Leaves the device: barcode + device ID + timestamp to our API for scoring.  
- Sensitive: no personal health or location beyond coarse supermarket GEO; low sensitivity.  
- Risk: minimal; breach exposes what items were scanned, could imply dietary preferences.

## Success in 30 Days  
30 % of weekly active users perform ≥5 scans per week by day 30 (indicates habit and perceived value).

## Open Questions for System Architect  
1. Can we cache the 200 k most-scanned French barcodes on-device to guarantee <300 ms response offline?  
2. What is the cheapest stack for daily diffing of Open Food Facts changes to feed the shrinkflation rule without exceeding €500/mo?