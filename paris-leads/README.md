# Paris Leads Scraper

## Setup (2 minutes)

```bash
pip install requests
```

Get a free Google Maps API key:
1. Go to console.cloud.google.com
2. Create project → Enable **Places API**
3. Create API key → paste it in `scraper.py` line 8

## Run

```bash
python scraper.py
```

## Output: `paris_leads.csv`

| Column | What it means |
|--------|--------------|
| name | Business name |
| sector | Search category |
| address | Full Paris address |
| phone | Phone number |
| website | Their site (empty = no site) |
| email | Found on their website (if any) |
| google_maps_url | Direct Google Maps link |
| score | HIGH / MEDIUM / LOW |
| score_reason | Why they got that score |

## Scoring Logic

| Score | Meaning | Action |
|-------|---------|--------|
| 🔥 HIGH | No website + email found | Send cold email now |
| 🔥 HIGH | No website, no email | DM on Instagram / call |
| 🟡 MEDIUM | Has basic site + email found | Pitch a redesign |
| ⚪ LOW | Has site, no easy email | Skip for now |
