#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

SOURCE_URL = "https://huskers.com/sports/football/schedule"
OUT = Path("data/huskers_schedule.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

# -------- Helpers --------

def clean(s):
    return " ".join(s.split()) if isinstance(s, str) else s

def safe_text(locator, timeout=1000):
    """Return innerText of the FIRST match, or None if no match."""
    try:
        if not locator or locator.count() == 0:
            return None
        return locator.first.inner_text(timeout=timeout).strip()
    except PWTimeout:
        return None

def safe_attr(locator, name, timeout=1000):
    """Return attribute of the FIRST match, or None if no match."""
    try:
        if not locator or locator.count() == 0:
            return None
        return locator.first.get_attribute(name, timeout=timeout)
    except PWTimeout:
        return None

def get_img_src(locator):
    """Return best-available image URL after lazy-load, or None."""
    if not locator or locator.count() == 0:
        return None
    img = locator.first
    try:
        # prefer currentSrc since they may use srcset/picture
        current = img.evaluate("(el) => el.currentSrc || el.src || el.getAttribute('data-src') || ''")
        if current and not current.startswith("data:image"):
            return current
        src = safe_attr(locator, "src")
        if src and not src.startswith("data:image"):
            return src
        data_src = safe_attr(locator, "data-src")
        if data_src and not data_src.startswith("data:image"):
            return data_src
    except PWTimeout:
        pass
    return None

# -------- Per-event parsing --------

def parse_event(event):
    # Venue, date
    venue_type = safe_text(event.locator(".schedule-event-venue__type-label"))
    weekday = safe_text(event.locator(".schedule-event-date__time time"))
    date_text = safe_text(event.locator(".schedule-event-date__label"))

    # Result / kickoff
    status = "tbd"
    result = None
    kickoff = None

    has_win = event.locator(".schedule-event-item-result__win").count() > 0
    has_loss = event.locator(".schedule-event-item-result__loss").count() > 0
    has_tie = event.locator(".schedule-event-item-result__tie").count() > 0

    if has_win or has_loss or has_tie:
        status = "final"
        outcome = "W" if has_win else "L" if has_loss else "T"
        label_text = safe_text(event.locator(".schedule-event-item-result__label")) or ""
        parts = label_text.split()
        score = next((p for p in parts if "-" in p), label_text)
        result = {"outcome": outcome, "score": score}
    else:
        kickoff_text = safe_text(event.locator(".schedule-event-item-result__label"))
        if kickoff_text:
            status = "upcoming"
            kickoff = kickoff_text

    # Make sure the event is in view to trigger lazy-loaded images
    try:
        event.scroll_into_view_if_needed(timeout=2000)
    except PWTimeout:
        pass

    # Logos
    wrappers = event.locator(".schedule-event-item-default__images .schedule-event-item-default__image-wrapper")
    nebraska_logo_url = opponent_logo_url = None
    if wrappers.count() >= 1:
        nebraska_logo_url = get_img_src(wrappers.nth(0).locator("img"))
    if wrappers.count() >= 2:
        opponent_logo_url = get_img_src(wrappers.nth(1).locator("img"))

    divider_text = safe_text(event.locator(".schedule-event-item-default__divider"))
    opponent_name = safe_text(event.locator(".schedule-event-item-default__opponent-name"))

    location = clean(safe_text(event.locator(".schedule-event-item-default__location .schedule-event-location")))

    # TV logo (first image inside the bottom links)
    tv_logo = event.locator(".schedule-event-bottom__link img, .schedule-event-item-links__image")
    tv_network_logo_url = get_img_src(tv_logo) if tv_logo.count() > 0 else None

    # Links (Box Score, Recap, Photos, PDFs…)
    links = []
    link_nodes = event.locator(".schedule-event-bottom__link")
    for i in range(link_nodes.count()):
        a = link_nodes.nth(i)
        title = safe_text(a.locator(".schedule-event-item-links__title")) or clean(safe_text(a))
        href = safe_attr(a, "href")
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

# -------- Main scrape --------

def scrape_with_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="huskers-schedule-scraper/1.0 (+https://example.com)",
            viewport={"width": 1400, "height": 2400},
        )
        page = ctx.new_page()
        page.goto(SOURCE_URL, wait_until="networkidle")  # wait for network to settle
        page.wait_for_timeout(400)  # micro settle

        # Scroll every event into view to trigger lazy loading
        events = page.locator(".schedule-event-item")
        for i in range(events.count()):
            ev = events.nth(i)
            try:
                ev.scroll_into_view_if_needed(timeout=2000)
            except PWTimeout:
                pass
            page.wait_for_timeout(120)

        # Parse
        events = page.locator(".schedule-event-item")
        games = [parse_event(events.nth(i)) for i in range(events.count())]

        payload = {
            "source_url": SOURCE_URL,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "games": games,
        }
        OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

        ctx.close()
        browser.close()

if __name__ == "__main__":
    scrape_with_playwright()
    print(f"Wrote {OUT}")
