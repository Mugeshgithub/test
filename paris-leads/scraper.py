import requests
import csv
import time
import re
from dataclasses import dataclass, asdict

# ── CONFIG ────────────────────────────────────────────────────────────────────
GOOGLE_API_KEY = "AIzaSyCeGKMDsNuCm--VGUs3DcI9ElFZxL1y6fo"

SEARCHES = [
    "ostéopathe Paris",
    "sophrologue Paris",
    "naturopathe Paris",
    "hypnothérapeute Paris",
    "kinésithérapeute Paris",
    "coach de vie Paris",
    "psychologue libéral Paris",
    "acupuncteur Paris",
    "architecte d'intérieur Paris",
    "décorateur intérieur Paris",
]

SEARCH_URL  = "https://places.googleapis.com/v1/places:searchText"
OUTPUT_FILE = "paris_leads.csv"

FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.googleMapsUri",
    "nextPageToken",
])

# ── DATA MODEL ────────────────────────────────────────────────────────────────
@dataclass
class Lead:
    name:            str = ""
    sector:          str = ""
    address:         str = ""
    phone:           str = ""
    website:         str = ""
    email:           str = ""
    google_maps_url: str = ""
    score:           str = ""
    score_reason:    str = ""

# ── EMAIL FINDER ──────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
SKIP_PREFIXES = ("noreply", "no-reply", "support", "admin", "webmaster",
                 "newsletter", "abuse", "postmaster")

def find_email(url: str) -> str:
    if not url:
        return ""
    base = url.rstrip("/")
    for path in ["", "/contact", "/nous-contacter", "/contact.html"]:
        try:
            r = requests.get(base + path, timeout=7,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                continue
            for email in EMAIL_RE.findall(r.text):
                el = email.lower()
                if any(el.startswith(s) for s in SKIP_PREFIXES):
                    continue
                if any(x in el for x in [".png", ".jpg", ".js", ".css"]):
                    continue
                return el
        except Exception:
            pass
    return ""

# ── SCORING ───────────────────────────────────────────────────────────────────
SOCIAL_DIRS = ["facebook.", "instagram.", "doctolib.", "linkedin.",
               "pagesjaunes.", "yelp.", "google.", "annuaire."]

def score(website: str, email: str) -> tuple[str, str]:
    has_real_site = website and not any(d in website for d in SOCIAL_DIRS)
    if not has_real_site:
        return (("HIGH",   "No website — email found, send now")    if email
                else ("HIGH",  "No website — contact by phone/social"))
    return     (("MEDIUM", "Has site — email found, pitch redesign") if email
                else ("LOW",   "Has site — no email found"))

# ── PLACES API (NEW) ──────────────────────────────────────────────────────────
def search_places(query: str) -> list[dict]:
    results   = []
    page_token = None
    headers   = {
        "Content-Type":    "application/json",
        "X-Goog-Api-Key":  GOOGLE_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    while True:
        body = {"textQuery": query, "languageCode": "fr", "pageSize": 20}
        if page_token:
            body["pageToken"] = page_token

        resp = requests.post(SEARCH_URL, json=body, headers=headers, timeout=10)
        data = resp.json()

        if "error" in data:
            print(f"  API error: {data['error'].get('message', data['error'])}")
            break

        results.extend(data.get("places", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(2)

    return results

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    leads: list[Lead] = []
    seen:  set[str]   = set()

    for query in SEARCHES:
        print(f"\n🔍  {query}")
        places = search_places(query)
        print(f"    {len(places)} results from API")

        for p in places:
            pid = p.get("id", "")
            if pid in seen:
                continue
            seen.add(pid)

            website = p.get("websiteUri", "")
            email   = find_email(website)
            s, reason = score(website, email)

            lead = Lead(
                name            = p.get("displayName", {}).get("text", ""),
                sector          = query,
                address         = p.get("formattedAddress", ""),
                phone           = p.get("nationalPhoneNumber", ""),
                website         = website,
                email           = email,
                google_maps_url = p.get("googleMapsUri", ""),
                score           = s,
                score_reason    = reason,
            )
            leads.append(lead)
            icon = {"HIGH": "🔥", "MEDIUM": "🟡", "LOW": "⚪"}.get(s, "")
            print(f"  {icon} [{s}] {lead.name}")
            print(f"       📍 {lead.address}")
            print(f"       📞 {lead.phone or '—'}  |  🌐 {lead.website or 'NO WEBSITE'}  |  ✉️  {lead.email or '—'}")

        time.sleep(1)

    if not leads:
        print("\n❌  No leads collected.")
        return

    # Sort HIGH first
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    leads.sort(key=lambda l: order.get(l.score, 9))

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=asdict(leads[0]).keys())
        writer.writeheader()
        writer.writerows(asdict(l) for l in leads)

    high    = sum(1 for l in leads if l.score == "HIGH")
    medium  = sum(1 for l in leads if l.score == "MEDIUM")
    low     = sum(1 for l in leads if l.score == "LOW")
    w_email = sum(1 for l in leads if l.email)

    print(f"\n{'═'*55}")
    print(f"✅  {len(leads)} leads saved to {OUTPUT_FILE}")
    print(f"   🔥 HIGH   : {high}  (no website)")
    print(f"   🟡 MEDIUM : {medium}  (has site, email found)")
    print(f"   ⚪ LOW    : {low}  (has site, no email)")
    print(f"   ✉️  With email : {w_email}")
    print(f"{'═'*55}")

if __name__ == "__main__":
    main()
