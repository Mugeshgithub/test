"""
Scrape party-wise results for every state/UT from the ECI results portal
and merge into a single CSV.

Run on mobile via Google Colab:
    1. colab.research.google.com -> New notebook
    2. Paste this file's contents into a cell, run it
    3. Download eci_partywise_all.csv from the file panel
"""

import time
from io import StringIO

import pandas as pd
import requests

BASE = "https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-{code}.htm"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://results.eci.gov.in/",
}

# ECI uses S01..S30ish for states and U01..U08 for UTs. Not every code exists
# in every cycle, so we just probe and skip 404s.
CODES = [f"S{i:02d}" for i in range(1, 31)] + [f"U{i:02d}" for i in range(1, 9)]


def fetch_one(code: str) -> pd.DataFrame | None:
    url = BASE.format(code=code)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as exc:
        print(f"{code}: network error ({exc})")
        return None

    if resp.status_code != 200:
        print(f"{code}: HTTP {resp.status_code} - skipped")
        return None

    try:
        tables = pd.read_html(StringIO(resp.text))
    except ValueError:
        print(f"{code}: no tables found - skipped")
        return None

    df = tables[0].copy()
    df.insert(0, "state_code", code)
    print(f"{code}: {len(df)} rows")
    return df


def main(out_path: str = "eci_partywise_all.csv") -> None:
    frames = []
    for code in CODES:
        df = fetch_one(code)
        if df is not None:
            frames.append(df)
        time.sleep(1)  # be polite to the ECI server

    if not frames:
        raise SystemExit("No data fetched. Check network / URL pattern.")

    merged = pd.concat(frames, ignore_index=True)
    merged.to_csv(out_path, index=False)
    print(f"\nSaved {len(merged)} rows across {len(frames)} states to {out_path}")


if __name__ == "__main__":
    main()
