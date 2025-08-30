#!/usr/bin/env python3
import json
from pathlib import Path

DATA_PATH = Path("data/current.json")          # produced by your scraper
STADIUM_DIR = Path("stadiums")                 # where you will drop images
OUT_JSON = Path("data/stadium_manifest.json")  # machine-readable
OUT_MD = Path("STADIUMS.md")                   # human-readable status

def slugify(s: str) -> str:
    s = (s or "").lower().replace("&", "and")
    out = []
    dash = False
    for ch in s:
        if ch.isalnum():
            out.append(ch); dash = False
        else:
            if not dash:
                out.append("-"); dash = True
    res = "".join(out).strip("-")
    while "--" in res:
        res = res.replace("--","-")
    return res

def parse_location(loc: str):
    # e.g. "Lincoln, Neb. / Memorial Stadium"
    if not loc:
        return None, None, None
    parts = [p.strip() for p in loc.split("/")]
    city = parts[0] if parts else None
    stadium = parts[1] if len(parts) > 1 else None
    base = f"{stadium}-{city}" if stadium else (city or loc)
    return city, stadium, slugify(base)

def main():
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        raise SystemExit(f"Missing {DATA_PATH}. Run the scraper first.")

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    games = data.get("games", [])

    # de-dupe stadiums by slug
    uniq = {}
    for g in games:
        loc = g.get("location")
        city, stadium, slug = parse_location(loc)
        if not slug:
            continue
        if slug not in uniq:
            uniq[slug] = {
                "slug": slug,
                "location_raw": loc,
                "city": city,
                "stadium": stadium,
                "example_game": g.get("opponent_name"),
                "files_present": [],
                "suggested_filenames": [f"{slug}.jpg", f"{slug}.png", f"{slug}.webp"],
            }

    # check which files you already have
    exts = [".jpg", ".png", ".webp"]
    for rec in uniq.values():
        for ext in exts:
            p = STADIUM_DIR / f"{rec['slug']}{ext}"
            if p.exists():
                rec["files_present"].append(p.as_posix())

    found = sorted([r for r in uniq.values() if r["files_present"]], key=lambda r: r["slug"])
    missing = sorted([r for r in uniq.values() if not r["files_present"]], key=lambda r: r["slug"])

    # write JSON
    manifest = {
        "generated_from": DATA_PATH.as_posix(),
        "stadium_dir": STADIUM_DIR.as_posix(),
        "found": found,
        "missing": missing,
        "notes": {
            "naming_rule": "stadiums/<slug>.jpg|.png|.webp",
            "slug_source": "Prefer <stadium> + <city>. If no stadium, use <city>.",
            "slug_rules": "lowercase; non-alphanumerics -> '-'; '&' -> 'and'; collapse repeats."
        }
    }
    OUT_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT_JSON}  (found={len(found)} missing={len(missing)})")

    # write Markdown
    lines = []
    lines.append("# Stadium Images Status\n")
    lines.append("Drop images in `stadiums/` named by the **slug** below. Any of `.jpg`, `.png`, `.webp` works.\n")
    lines.append("## Missing\n")
    if missing:
        lines.append("| Opponent (example) | City / Stadium | File to add |\n|---|---|---|\n")
        for r in missing:
            want = r["suggested_filenames"][0]
            lines.append(f"| {r['example_game'] or ''} | {r['location_raw'] or ''} | `stadiums/{want}` |\n")
    else:
        lines.append("_None — you have them all!_\n")

    lines.append("\n## Found\n")
    if found:
        lines.append("| Opponent (example) | City / Stadium | Files present |\n|---|---|---|\n")
        for r in found:
            have = ", ".join(f"`{x}`" for x in r["files_present"])
            lines.append(f"| {r['example_game'] or ''} | {r['location_raw'] or ''} | {have} |\n")
    else:
        lines.append("_No stadium images found yet._\n")

    OUT_MD.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}")

if __name__ == "__main__":
    main()
