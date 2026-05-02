"""
Paris leads scraper — no API key needed.
Sources: PagesJaunes (French Yellow Pages) per sector/arrondissement
Output:  paris_leads.csv  with HIGH / MEDIUM / LOW scoring
"""

import requests, csv, re, time, json
from dataclasses import dataclass, asdict

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# ── TARGETS ───────────────────────────────────────────────────────────────────
SECTORS = [
    ("osteopathe",            "Ostéopathe"),
    ("sophrologue",           "Sophrologue"),
    ("naturopathe",           "Naturopathe"),
    ("hypnotherapeute",       "Hypnothérapeute"),
    ("kinesitherapeute",      "Kinésithérapeute"),
    ("psychologue",           "Psychologue"),
    ("coach-de-vie",          "Coach de vie"),
    ("architecte-interieur",  "Architecte d'intérieur"),
    ("decorateur-interieur",  "Décorateur intérieur"),
]
LOCATION = "Paris+75"
MAX_PAGES = 3   # 3 pages × ~20 results = ~60 per sector

# ── DATA ──────────────────────────────────────────────────────────────────────
@dataclass
class Lead:
    name:         str = ""
    sector:       str = ""
    address:      str = ""
    arrondissement: str = ""
    phone:        str = ""
    website:      str = ""
    email:        str = ""
    pagesjaunes:  str = ""
    score:        str = ""
    reason:       str = ""

# ── EMAIL FINDER ──────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
SKIP_PREFIXES = ("noreply", "no-reply", "support", "admin", "webmaster",
                 "newsletter", "contact@pagesjaunes", "contact@doctolib")

def find_email_on_site(url: str) -> str:
    if not url:
        return ""
    base = url.rstrip("/")
    for path in ["", "/contact", "/nous-contacter", "/contact.html"]:
        try:
            r = requests.get(base + path, headers=HEADERS, timeout=7)
            if r.status_code != 200:
                continue
            emails = EMAIL_RE.findall(r.text)
            for e in emails:
                el = e.lower()
                if any(el.startswith(s) for s in SKIP_PREFIXES):
                    continue
                if any(x in el for x in [".png", ".jpg", ".gif", ".js", ".css", "example."]):
                    continue
                return el
            if emails:
                return emails[0].lower()
        except Exception:
            pass
    return ""

# ── SCORING ───────────────────────────────────────────────────────────────────
SOCIAL_DIRS = ["facebook.", "instagram.", "doctolib.", "linkedin.",
               "pagesjaunes.", "yelp.", "google.", "annuaire.", "pages24."]

def score_lead(website: str, email: str) -> tuple[str, str]:
    is_real = website and not any(d in website for d in SOCIAL_DIRS)
    if not is_real:
        return (("HIGH",   "🔥 No real website — email found, reach out now") if email
                else ("HIGH", "🔥 No real website — contact by phone / Instagram"))
    return (("MEDIUM", "🟡 Has site — email found, pitch a redesign") if email
            else ("LOW",  "⚪ Has site — no email found, lower priority"))

# ── PAGESJAUNES SCRAPER ───────────────────────────────────────────────────────
ARR_RE   = re.compile(r"Paris\s*(\d{1,2}(?:e|er)?(?:\s*arrondissement)?)", re.I)
PHONE_RE = re.compile(r"0[1-9](?:[\s.\-]?\d{2}){4}")

def scrape_pagesjaunes(slug: str, label: str) -> list[Lead]:
    leads = []
    seen  = set()

    for page in range(1, MAX_PAGES + 1):
        url = (f"https://www.pagesjaunes.fr/annuaire/chercherlespros"
               f"?quoiqui={slug}&ou={LOCATION}&page={page}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
        except Exception as e:
            print(f"    ⚠️  Request failed p{page}: {e}")
            break

        if r.status_code != 200:
            print(f"    ⚠️  HTTP {r.status_code} on page {page}")
            break

        html = r.text

        # Each listing block starts with a data-sc-position attribute
        blocks = re.split(r'(?=class="bi-content")', html)
        found_on_page = 0

        for block in blocks:
            # Name
            nm = re.search(r'class="denomination-links[^"]*"[^>]*>\s*<[^>]+>\s*([^<]{3,80})', block)
            if not nm:
                nm = re.search(r'<span[^>]+class="[^"]*name[^"]*"[^>]*>([^<]{3,80})', block)
            if not nm:
                continue
            name = nm.group(1).strip()
            if name in seen or len(name) < 3:
                continue
            seen.add(name)

            # Address
            addr_m = re.search(r'<address[^>]*>(.*?)</address>', block, re.S)
            address = re.sub(r'<[^>]+>', ' ', addr_m.group(1)).strip() if addr_m else ""
            address = re.sub(r'\s+', ' ', address)

            # Arrondissement
            arr_m = ARR_RE.search(address)
            arr   = arr_m.group(0).strip() if arr_m else ""

            # Phone
            ph_m  = PHONE_RE.search(block)
            phone = ph_m.group(0).replace(" ", "").replace(".", "").replace("-", "") if ph_m else ""
            if phone:
                phone = phone[:2] + " " + phone[2:4] + " " + phone[4:6] + " " + phone[6:8] + " " + phone[8:]

            # Website
            ws_m    = re.search(r'href="(https?://(?!www\.pagesjaunes)[^"]{4,100})"[^>]*>.*?(?:site|web|www)', block, re.I)
            website = ws_m.group(1).strip() if ws_m else ""

            # PagesJaunes detail URL
            pj_m  = re.search(r'href="(/pros/[^"]+)"', block)
            pj_url = ("https://www.pagesjaunes.fr" + pj_m.group(1)) if pj_m else ""

            # Email (from their site if they have one)
            email = find_email_on_site(website) if website else ""

            s, reason = score_lead(website, email)

            leads.append(Lead(
                name=name, sector=label, address=address,
                arrondissement=arr, phone=phone,
                website=website, email=email,
                pagesjaunes=pj_url, score=s, reason=reason,
            ))
            found_on_page += 1

        print(f"    page {page}: {found_on_page} listings")
        if found_on_page == 0:
            break
        time.sleep(1.2)

    return leads

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    all_leads: list[Lead] = []

    for slug, label in SECTORS:
        print(f"\n{'─'*55}")
        print(f"🔍  {label}")
        leads = scrape_pagesjaunes(slug, label)
        all_leads.extend(leads)
        print(f"   → {len(leads)} leads collected")
        time.sleep(1.5)

    if not all_leads:
        print("\n❌  No data collected. PagesJaunes may have blocked the request.")
        return

    # Sort: HIGH first, then MEDIUM, then LOW
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_leads.sort(key=lambda l: order.get(l.score, 9))

    with open("paris_leads.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=asdict(all_leads[0]).keys())
        writer.writeheader()
        writer.writerows(asdict(l) for l in all_leads)

    high   = sum(1 for l in all_leads if l.score == "HIGH")
    medium = sum(1 for l in all_leads if l.score == "MEDIUM")
    low    = sum(1 for l in all_leads if l.score == "LOW")
    w_email = sum(1 for l in all_leads if l.email)

    print(f"\n{'═'*55}")
    print(f"✅  {len(all_leads)} total leads  →  paris_leads.csv")
    print(f"   🔥 HIGH   : {high}   (no website)")
    print(f"   🟡 MEDIUM : {medium}   (has site, email found)")
    print(f"   ⚪ LOW    : {low}   (has site, no email)")
    print(f"   ✉️  With email : {w_email}")
    print(f"{'═'*55}")

    # Preview top 10
    print("\n── TOP 10 LEADS PREVIEW ──")
    for l in all_leads[:10]:
        print(f"\n  [{l.score}] {l.name}  ({l.sector})")
        print(f"  📍 {l.address}")
        print(f"  📞 {l.phone or '—'}")
        print(f"  🌐 {l.website or 'NO WEBSITE'}")
        print(f"  ✉️  {l.email or '—'}")

if __name__ == "__main__":
    main()
