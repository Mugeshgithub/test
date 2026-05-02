import requests
import csv
import time
import re
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── CONFIG ────────────────────────────────────────────────────────────────────
GOOGLE_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"   # https://console.cloud.google.com

SEARCHES = [
    # Therapists / wellness solo practitioners
    "ostéopathe Paris",
    "sophrologue Paris",
    "naturopathe Paris",
    "hypnothérapeute Paris",
    "kinésithérapeute Paris",
    "coach de vie Paris",
    "psychologue libéral Paris",
    "acupuncteur Paris",
    # Interior design / décor
    "architecte d'intérieur Paris",
    "décorateur intérieur Paris",
]

PLACES_URL  = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
OUTPUT_FILE = "paris_leads.csv"

# ── DATA MODEL ────────────────────────────────────────────────────────────────
@dataclass
class Lead:
    name:            str  = ""
    sector:          str  = ""
    address:         str  = ""
    phone:           str  = ""
    website:         str  = ""
    email:           str  = ""
    google_maps_url: str  = ""
    score:           str  = ""
    score_reason:    str  = ""

# ── GOOGLE MAPS ───────────────────────────────────────────────────────────────
def search_places(query: str) -> list[dict]:
    """Pull all pages of results for a query."""
    results, params = [], {"query": query, "key": GOOGLE_API_KEY, "language": "fr"}
    while True:
        data = requests.get(PLACES_URL, params=params, timeout=10).json()
        results.extend(data.get("results", []))
        token = data.get("next_page_token")
        if not token:
            break
        time.sleep(2)           # Google requires a short delay before using the token
        params = {"pagetoken": token, "key": GOOGLE_API_KEY}
    return results


def get_details(place_id: str) -> dict:
    """Fetch name, address, phone, website, maps URL for one place."""
    params = {
        "place_id": place_id,
        "fields":   "name,formatted_address,formatted_phone_number,website,url",
        "key":      GOOGLE_API_KEY,
        "language": "fr",
    }
    return requests.get(DETAILS_URL, params=params, timeout=10).json().get("result", {})


# ── EMAIL FINDER ──────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SKIP_EMAILS = {
    # Generic / non-owner addresses to ignore
    "contact@", "info@", "hello@", "bonjour@", "admin@",
    "support@", "noreply@", "no-reply@",
}

def scrape_email(website: str) -> str:
    """
    Try homepage then /contact to find a real email address.
    Returns first non-generic email found, or empty string.
    """
    if not website:
        return ""

    base = website.rstrip("/")
    pages_to_try = [base, f"{base}/contact", f"{base}/contact.html", f"{base}/nous-contacter"]

    for url in pages_to_try:
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                continue
            emails = EMAIL_RE.findall(r.text)
            for email in emails:
                # Skip images, CSS files, common noise
                if any(ext in email for ext in [".png", ".jpg", ".gif", ".css", ".js"]):
                    continue
                # Prefer specific (non-generic) addresses
                if not any(email.startswith(skip) for skip in SKIP_EMAILS):
                    return email.lower()
            # Fall back to first generic one if nothing better found
            if emails:
                return emails[0].lower()
        except Exception:
            continue
    return ""


# ── SCORING ───────────────────────────────────────────────────────────────────
# Keywords in the website URL that signal the "site" is just a directory
DIRECTORY_DOMAINS = [
    "facebook.com", "instagram.com", "doctolib.fr",
    "pagesjaunes.fr", "linkedin.com", "google.com",
    "yelp.fr", "annuaire", "bottin", "118",
]

def score(website: str, email: str) -> tuple[str, str]:
    """
    HIGH   – No real website + we have an email     → reach out now
    HIGH   – No real website, no email              → find on social / phone
    MEDIUM – Has basic website + we found email     → pitch a redesign
    LOW    – Has website but couldn't find email    → lower priority
    SKIP   – Directory/social only counts as no-site (still HIGH)
    """
    is_directory = website and any(d in website for d in DIRECTORY_DOMAINS)
    has_real_site = website and not is_directory

    if not has_real_site:
        if email:
            return "HIGH",   "No website — email found ✓"
        else:
            return "HIGH",   "No website — reach via phone/social"
    else:
        if email:
            return "MEDIUM", "Has site but email found — pitch upgrade"
        else:
            return "LOW",    "Has site — no easy email found"


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    leads: list[Lead] = []
    seen:  set[str]   = set()

    for query in SEARCHES:
        print(f"\n🔍  {query}")
        places = search_places(query)

        for place in places:
            pid = place["place_id"]
            if pid in seen:
                continue
            seen.add(pid)

            details = get_details(pid)
            time.sleep(0.15)    # stay within free-tier rate limits

            website = details.get("website", "")
            email   = scrape_email(website)
            s, reason = score(website, email)

            lead = Lead(
                name            = details.get("name", ""),
                sector          = query,
                address         = details.get("formatted_address", ""),
                phone           = details.get("formatted_phone_number", ""),
                website         = website,
                email           = email,
                google_maps_url = details.get("url", ""),
                score           = s,
                score_reason    = reason,
            )
            leads.append(lead)

            icon = {"HIGH": "🔥", "MEDIUM": "🟡", "LOW": "⚪"}.get(s, "")
            print(f"  {icon} [{s}] {lead.name}")
            print(f"       📍 {lead.address}")
            print(f"       📞 {lead.phone or '—'}  |  🌐 {lead.website or 'NO WEBSITE'}  |  ✉️  {lead.email or '—'}")

    # ── Export CSV ─────────────────────────────────────────────────────────
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=asdict(leads[0]).keys())
        writer.writeheader()
        writer.writerows(asdict(l) for l in leads)

    # ── Summary ────────────────────────────────────────────────────────────
    high   = sum(1 for l in leads if l.score == "HIGH")
    medium = sum(1 for l in leads if l.score == "MEDIUM")
    low    = sum(1 for l in leads if l.score == "LOW")

    print(f"\n{'─'*50}")
    print(f"✅  Done.  {len(leads)} total leads saved to {OUTPUT_FILE}")
    print(f"   🔥 HIGH   : {high}")
    print(f"   🟡 MEDIUM : {medium}")
    print(f"   ⚪ LOW    : {low}")
    print(f"{'─'*50}")


if __name__ == "__main__":
    main()
