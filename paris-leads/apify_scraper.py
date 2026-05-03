"""
Paris leads via Apify Google Maps Scraper
Run: pip install apify-client && python3 apify_scraper.py
"""

import csv, time, re
from apify_client import ApifyClient

# ── CONFIG ────────────────────────────────────────────────────────────────────
import os
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")  # set: export APIFY_TOKEN=your_token_here

# High-profile creative + health solo practitioners — say YES fast
SEARCHES = [
    # Wellness / health (solo practitioners)
    "ostéopathe Paris",
    "sophrologue Paris",
    "naturopathe Paris",
    "hypnothérapeute Paris",
    "coach de vie Paris",
    "psychologue libéral Paris",
    "acupuncteur Paris",
    # Creative (portfolio-driven, value aesthetics)
    "architecte d'intérieur Paris",
    "décorateur intérieur Paris",
    "photographe professionnel Paris",
    "graphiste freelance Paris",
    "illustrateur Paris",
]

OUTPUT = "paris_leads.csv"

# ── SKIP LOGIC ────────────────────────────────────────────────────────────────
# Tech/corporate keywords in title → they'll build it themselves
SKIP_KEYWORDS = [
    "sarl", "sas", "groupe", "clinique", "hôpital", "centre médical",
    "cabinet médical", "agence", "studio", "holding", "corporate",
    "international", "institute", "formation", "ecole", "école",
]

# Social/directory = not a real website → still HIGH priority
FAKE_WEBSITES = [
    "facebook.", "instagram.", "doctolib.", "linkedin.",
    "pagesjaunes.", "yelp.", "google.", "annuaire.", "rdvmedicaux.",
    "mondocteur.", "maiia.", "livi.", "keldoc.",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# ── SCORING ───────────────────────────────────────────────────────────────────
def score(place: dict) -> tuple[str, str]:
    website = place.get("website", "") or ""
    title   = (place.get("title", "") or "").lower()

    # Skip big institutions / tech-savvy businesses
    if any(k in title for k in SKIP_KEYWORDS):
        return "SKIP", "Institution or group practice"

    has_real_site = website and not any(f in website for f in FAKE_WEBSITES)

    if not has_real_site:
        return "HIGH", "🔥 No website — perfect cold email target"
    elif len(website) < 30 and "." in website:
        return "MEDIUM", "🟡 Minimal site — pitch a redesign"
    else:
        return "LOW", "⚪ Has site — lower priority"

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    client = ApifyClient(APIFY_TOKEN)
    all_leads = []
    seen = set()

    for query in SEARCHES:
        print(f"\n🔍  {query}")

        run = client.actor("compass/crawler-google-places").call(run_input={
            "searchStringsArray": [query],
            "maxCrawledPlacesPerSearch": 40,
            "language": "fr",
            "countryCode": "fr",
            "city": "Paris",
            "exportPlaceUrls": False,
            "includeHistogram": False,
            "includeOpeningHours": False,
            "includePeopleAlsoSearch": False,
            "additionalInfo": False,
        })

        items = client.dataset(run["defaultDatasetId"]).iterate_items()

        count = 0
        for place in items:
            name = place.get("title", "").strip()
            if not name or name in seen:
                continue
            seen.add(name)

            s, reason = score(place)
            if s == "SKIP":
                continue

            # Extract email from website or description
            email = ""
            for field in ["website", "description"]:
                val = place.get(field, "") or ""
                found = EMAIL_RE.findall(val)
                if found:
                    email = found[0].lower()
                    break

            lead = {
                "score":           s,
                "reason":          reason,
                "name":            name,
                "sector":          query,
                "address":         place.get("address", ""),
                "arrondissement":  extract_arr(place.get("address", "")),
                "phone":           place.get("phone", "") or place.get("phoneUnformatted", ""),
                "website":         place.get("website", ""),
                "email":           email,
                "google_maps":     place.get("url", ""),
                "rating":          place.get("totalScore", ""),
                "reviews":         place.get("reviewsCount", ""),
                "category":        place.get("categoryName", ""),
            }
            all_leads.append(lead)
            count += 1

            icon = {"HIGH": "🔥", "MEDIUM": "🟡"}.get(s, "⚪")
            print(f"  {icon} {name} | {lead['address'][:50]} | {lead['phone'] or '—'} | {lead['website'] or 'NO SITE'}")

        print(f"  → {count} leads from this search")
        time.sleep(1)

    if not all_leads:
        print("\n❌  No leads collected.")
        return

    # Sort: HIGH → MEDIUM → LOW
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_leads.sort(key=lambda x: order.get(x["score"], 9))

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_leads[0].keys())
        writer.writeheader()
        writer.writerows(all_leads)

    high    = sum(1 for l in all_leads if l["score"] == "HIGH")
    medium  = sum(1 for l in all_leads if l["score"] == "MEDIUM")
    low     = sum(1 for l in all_leads if l["score"] == "LOW")
    w_email = sum(1 for l in all_leads if l["email"])

    print(f"\n{'═'*55}")
    print(f"✅  {len(all_leads)} leads → {OUTPUT}")
    print(f"   🔥 HIGH   : {high}   (no website — cold email now)")
    print(f"   🟡 MEDIUM : {medium}   (weak site — pitch redesign)")
    print(f"   ⚪ LOW    : {low}   (has site)")
    print(f"   ✉️  With email : {w_email}")
    print(f"{'═'*55}")

def extract_arr(address: str) -> str:
    m = re.search(r"750(\d{2})", address)
    if m:
        return f"Paris {int(m.group(1))}e"
    return ""

if __name__ == "__main__":
    main()
