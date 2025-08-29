
#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://huskers.com/sports/football/schedule"
OUT = Path("data/huskers_schedule.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "huskers-schedule-scraper/1.0 (+https://example.com)"
}

def text_or_none(node):
    return node.get_text(strip=True) if node else None

def attr_or_none(node, attr):
    return node.get(attr) if node and node.has_attr(attr) else None

def clean_space(s):
    return " ".join(s.split()) if isinstance(s, str) else s

def parse_event(div):
    venue_type = text_or_none(div.select_one(".schedule-event-venue__type-label"))

    weekday = text_or_none(div.select_one(".schedule-event-date__time time"))
    date_text = text_or_none(div.select_one(".schedule-event-date__label"))

    result_block = div.select_one(".schedule-event-item-result")
    status = "tbd"
    result = None
    kickoff = None

    if result_block:
        win_str = result_block.select_one(".schedule-event-item-result__win")
        loss_str = result_block.select_one(".schedule-event-item-result__loss")
        tie_str = result_block.select_one(".schedule-event-item-result__tie")

        if win_str or loss_str or tie_str:
            status = "final"
            outcome = "W" if win_str else "L" if loss_str else "T"
            label = result_block.select_one(".schedule-event-item-result__label, .schedule-event-item-result__wrapper")
            score = None
            if label:
                t = " ".join(label.get_text(" ", strip=True).split())
                parts = t.split()
                hyphen_parts = [p for p in parts if "-" in p]
                score = hyphen_parts[-1] if hyphen_parts else t
            result = {"outcome": outcome, "score": score}
        else:
            time_label = result_block.select_one(".schedule-event-item-result__label")
            kickoff_text = text_or_none(time_label)
            if kickoff_text:
                status = "upcoming"
                kickoff = kickoff_text

    nebraska_logo_url = None
    opponent_logo_url = None

    img_wrappers = div.select(".schedule-event-item-default__images .schedule-event-item-default__image-wrapper")
    if img_wrappers:
        husker_wrapper = img_wrappers[0] if len(img_wrappers) >= 1 else None
        opp_wrapper = img_wrappers[1] if len(img_wrappers) >= 2 else None
        if husker_wrapper:
            nebraska_logo_url = attr_or_none(husker_wrapper.select_one("img"), "src")
        if opp_wrapper:
            opponent_logo_url = attr_or_none(opp_wrapper.select_one("img"), "src")

    divider_text = text_or_none(div.select_one(".schedule-event-item-default__divider"))
    opponent_name = text_or_none(div.select_one(".schedule-event-item-default__opponent-name"))

    location = None
    loc_span = div.select_one(".schedule-event-item-default__location .schedule-event-location")
    if loc_span:
        location = clean_space(loc_span.get_text(" ", strip=True))

    tv_network_logo_url = None
    bottom_link_img = div.select_one(".schedule-event-bottom__link img, .schedule-event-item-links__image")
    if bottom_link_img:
        tv_network_logo_url = attr_or_none(bottom_link_img, "src")

    links = []
    for a in div.select(".schedule-event-bottom__link"):
        title_node = a.select_one(".schedule-event-item-links__title")
        title = (title_node.get_text(strip=True) if title_node else a.get_text(" ", strip=True))
        href = attr_or_none(a, "href")
        if href:
            if href.startswith("/"):
                href = "https://huskers.com" + href
            links.append({"title": title, "href": href})

    return {
        "venue_type": venue_type,
        "weekday": weekday,
        "date_text": date_text,
        "status": status,
        "result": result,
        "kickoff": kickoff,
        "divider_text": divider_text,
        "nebraska_logo_url": nebraska_logo_url,
        "opponent_logo_url": opponent_logo_url,
        "opponent_name": opponent_name,
        "location": location,
        "tv_network_logo_url": tv_network_logo_url,
        "links": links,
    }

def scrape():
    r = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    items = soup.select(".schedule-event-item")
    games = [parse_event(div) for div in items]

    payload = {
        "source_url": SOURCE_URL,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "games": games,
    }

    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT} with {len(games)} games.")

if __name__ == "__main__":
    try:
        scrape()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
