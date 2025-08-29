#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

SOURCE_URL = "https://huskers.com/sports/football/schedule"
OUT = Path("data/huskers_schedule.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

def clean(s):
    return " ".join(s.split()) if isinstance(s, str) else s

def safe_text(el):
    return el.inner_text().strip() if el else None

def safe_attr(el, name):
    return el.get_attribute(name) if el else None

def get_img_src(el):
    """Return best-available image URL after lazy-load."""
    if not el:
        return None
    # Try currentSrc (covers <picture> and responsive srcset)
    current = el.evaluate("img => img.currentSrc || img.src || img.getAttribute('data-src') || ''")
    if current and not current.startswith("data:image"):
        return current
    # Fallbacks
    src = safe_attr(el, "src")
    if src and not src.startswith("data:image"):
        return src
    data_src = safe_attr(el, "data-src")
    if data_src and not data_src.startswith("data:image"):
        return data_src
    return None

def parse_event(event):
    # Venue type
    venue_type = safe_text(event.locator(".schedule-event-venue__type-label").first)

    # Date bits
    weekday = safe_text(event.locator(".schedule-event-date__time time").first)
    date_text = safe_text(event.locator(".schedule-event-date__label").first)

    # Result / kickoff
    status = "tbd"
    result = None
    kickoff = None

    has_win = event.locator(".schedule-event-item-result__win")
    has_loss = event.locator(".schedule-event-item-result__loss")
    has_tie = event.locator(".schedule-event-item-result__tie")

    if has_win.count() or has_loss.count() or has_tie.count():
        status = "final"
        outcome = "W" if has_win.count() else "L" if has_loss.count() else "T"
        label_el = event.locator(".schedule-event-item-result__label").first
        label_text = safe_text(label_el) or ""
        # Common form: "W 20-17"
        parts = label_text.split()
        score = next((p for p in parts if "-" in p), label_text)
        result = {"outcome": outcome, "score": score}
    else:
        kickoff_el = event.locator(".schedule-event-item-result__label").first
        kt = safe_text(kickoff_el)
        if kt:
            status = "upcoming"
            kickoff = kt

    # Teams / images
    # Scroll into view to trigger lazy-load
    try:
        event.scroll_into_view_if_needed(timeout=2000)
    except PWTimeout:
        pass

    img_wrappers = event.locator(".schedule-event-item-default__images .schedule-event-item-default__image-wrapper")
    nebraska_logo_url = opponent_logo_url = None

    count = img_wrappers.count()
    if count >= 1:
        husker_img = img_wrappers.nth(0).locator("img").first
        # wait a tick for lazy load
        try:
            husker_img.wait_for(state="attached", timeout=2000)
        except PWTimeout:
            pass
        nebraska_logo_url = get_img_src(husker_img)
    if count >= 2:
        opp_img = img_wrappers.nth(1).locator("img").first
        try:
            opp_img.wait_for(state="attached", timeout=2000)
        except PWTimeout:
            pass
        opponent_logo_url = get_img_src(opp_img)

    divider_text = safe_text(event.locator(".schedule-event-item-default__divider").first)
    opponent_name = safe_text(event.locator(".schedule-event-item-default__opponent-name").first)

    loc_span = event.locator(".schedule-event-item-default__location .schedule-event-location").first
    location = clean(safe_text(loc_span)) if loc_span else None

    # TV network logo (first image in the bottom links area)
    tv_img = event.locator(".schedule-event-bottom__link img, .schedule-event-item-links__image").first
    tv_network_logo_url = get_img_src(tv_img) if tv_img.count() else None

    # Collect bottom links
    links = []
    for i in range(event.locator(".schedule-event-bottom__link").count()):
        a = event.locator(".schedule-event-bottom__link").nth(i)
        title_node = a.locator(".schedule-event-item-links__title").first
        title = safe_text(title_node) or clean(safe_text(a))
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

def scrape_with_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="huskers-schedule-scraper/1.0 (+https://example.com)",
            viewport={"width": 1400, "height": 2000},
        )
        page = ctx.new_page()
        page.goto(SOURCE_URL, wait_until="domcontentloaded")
        # Let lazy scripts settle; then we’ll scroll the whole page to wake every image.
        page.wait_for_timeout(500)

        # Scroll through all events to trigger lazy loading
        events = page.locator(".schedule-event-item")
        n = events.count()
        for i in range(n):
            ev = events.nth(i)
            try:
                ev.scroll_into_view_if_needed(timeout=2000)
            except PWTimeout:
                pass
            page.wait_for_timeout(120)  # brief yield for image swap

        # Re-query after scrolling (DOM can update)
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
