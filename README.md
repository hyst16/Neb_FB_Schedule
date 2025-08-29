# Huskers Football Schedule Scraper

Scrapes https://huskers.com/sports/football/schedule and pulls per-game info from each
`.schedule-event-item`, including:
- venue_type (Home/Away/Neutral)
- weekday (e.g. "Saturday")
- date_text (e.g. "Sep 6")
- status: "final" | "upcoming" | "tbd"
- result: { outcome: "W"/"L"/"T", score: "20-17" } (if final)
- kickoff (if upcoming) (e.g. "6:30 PM CDT")
- divider_text ("vs." or "@")
- nebraska_logo_url
- opponent_logo_url
- opponent_name
- location (e.g., "Lincoln, Neb. / Memorial Stadium")
- tv_network_logo_url (if present)
- links: array of {title, href} for common CTAs (Box Score, Recap, Photos, PDFs)

## Run locally (optional)
If you ever do run this locally:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scrape.py
