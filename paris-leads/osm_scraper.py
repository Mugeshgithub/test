"""
Paris leads via OpenStreetMap Overpass API — free, no key, no blocks.
Fetches health practitioners + interior designers in Paris,
checks website field, finds emails, scores HIGH/MEDIUM/LOW.
"""

import requests, csv, re, time
from dataclasses import dataclass, asdict

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT_FILE  = "paris_leads.csv"

# ── OSM QUERIES ───────────────────────────────────────────────────────────────
# Each tuple: (label, overpass_filter)
QUERIES = [
    ("Ostéopathe",           '"healthcare"="osteopath"'),
    ("Kinésithérapeute",     '"healthcare"="physiotherapist"'),
    ("Médecin libéral",      '"healthcare"="doctor"'),
    ("Alternative medicine", '"healthcare"="alternative"'),
    ("Architecte/Décorateur",'["office"="architect"]'),
    ("Salon beauté",         '"shop"="beauty"'),
    ("Coiffeur",             '"shop"="hairdresser"'),
]

def overpass_query(osm_filter: str) -> str:
    return f"""
[out:json][timeout:30];
area["name"="Paris"]["admin_level"="8"]->.paris;
(
  node[{osm_filter}](area.paris);
  way[{osm_filter}](area.paris);
);
out body center;
"""

# ── EMAIL FINDER ──────────────────────────────────────────────────────────────
EMAIL_RE     = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
SKIP_PREFIX  = ("noreply","no-reply","support","admin","webmaster","newsletter","abuse")

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
            for e in EMAIL_RE.findall(r.text):
                el = e.lower()
                if any(el.startswith(s) for s in SKIP_PREFIX):
                    continue
                if any(x in el for x in [".png",".jpg",".js",".css"]):
                    continue
                return el
        except Exception:
            pass
    return ""

# ── SCORING ───────────────────────────────────────────────────────────────────
SOCIAL = ["facebook.","instagram.","doctolib.","linkedin.","pagesjaunes.","yelp.","google."]

def score(website: str, email: str) -> tuple[str, str]:
    real = website and not any(s in website for s in SOCIAL)
    if not real:
        return (("HIGH",   "🔥 No website + email found — send now")   if email
                else ("HIGH", "🔥 No website — call or DM on social"))
    return     (("MEDIUM", "🟡 Has site + email — pitch redesign")      if email
                else ("LOW",  "⚪ Has site, no email found"))

# ── DATA MODEL ────────────────────────────────────────────────────────────────
@dataclass
class Lead:
    name:    str = ""
    sector:  str = ""
    address: str = ""
    phone:   str = ""
    website: str = ""
    email:   str = ""
    osm_id:  str = ""
    score:   str = ""
    reason:  str = ""

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    all_leads: list[Lead] = []
    seen: set[str] = set()

    for label, osm_filter in QUERIES:
        print(f"\n🔍  {label}")
        q = overpass_query(osm_filter)
        try:
            resp = requests.post(OVERPASS_URL, data={"data": q}, timeout=35)
            elements = resp.json().get("elements", [])
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            continue

        print(f"    {len(elements)} OSM elements found")
        count = 0

        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name", tags.get("operator", "")).strip()
            if not name or name in seen:
                continue
            seen.add(name)

            # Build address from OSM tags
            addr_parts = [
                tags.get("addr:housenumber", ""),
                tags.get("addr:street", ""),
                tags.get("addr:postcode", ""),
                tags.get("addr:city", "Paris"),
            ]
            address = " ".join(p for p in addr_parts if p).strip()

            phone   = tags.get("phone", tags.get("contact:phone", "")).strip()
            website = tags.get("website", tags.get("contact:website", "")).strip()
            email_tag = tags.get("email", tags.get("contact:email", "")).strip()

            # Try scraping email from site if not in OSM tags
            email = email_tag or find_email(website)

            s, reason = score(website, email)

            lead = Lead(
                name    = name,
                sector  = label,
                address = address,
                phone   = phone,
                website = website,
                email   = email,
                osm_id  = str(el.get("id", "")),
                score   = s,
                reason  = reason,
            )
            all_leads.append(lead)
            count += 1

            icon = {"HIGH": "🔥", "MEDIUM": "🟡", "LOW": "⚪"}.get(s, "")
            print(f"  {icon} [{s}] {name}")
            print(f"       📍 {address or '(no address in OSM)'}")
            print(f"       📞 {phone or '—'}  |  🌐 {website or 'NO WEBSITE'}  |  ✉️  {email or '—'}")

        print(f"  → {count} unique leads")
        time.sleep(1)

    if not all_leads:
        print("\n❌  No leads collected.")
        return

    # Sort HIGH first
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_leads.sort(key=lambda l: order.get(l.score, 9))

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=asdict(all_leads[0]).keys())
        w.writeheader()
        w.writerows(asdict(l) for l in all_leads)

    high    = sum(1 for l in all_leads if l.score == "HIGH")
    medium  = sum(1 for l in all_leads if l.score == "MEDIUM")
    low     = sum(1 for l in all_leads if l.score == "LOW")
    w_email = sum(1 for l in all_leads if l.email)

    print(f"\n{'═'*55}")
    print(f"✅  {len(all_leads)} leads  →  {OUTPUT_FILE}")
    print(f"   🔥 HIGH   : {high}   (no real website)")
    print(f"   🟡 MEDIUM : {medium}   (has site, email found)")
    print(f"   ⚪ LOW    : {low}   (has site, no email)")
    print(f"   ✉️  With email : {w_email}")
    print(f"{'═'*55}")

if __name__ == "__main__":
    main()
