"""
Scrape a public GitHub contributions calendar (no token needed) and render
it as an animated SVG heatmap with a diagonal, line-by-line reveal.

Usage:
    python scripts/generate_heatmap.py vamshiDobbala assets/contrib-heatmap.svg
"""
import sys
from datetime import date
import requests
from bs4 import BeautifulSoup

CELL = 11
GAP = 3
LEVEL_COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
BG = "#0d1117"
TEXT_COLOR = "#8b949e"


def fetch_contributions(username: str):
    url = f"https://github.com/users/{username}/contributions"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    days = []
    cells = soup.select("td.ContributionCalendar-day")
    if cells:
        for td in cells:
            d = td.get("data-date")
            level = td.get("data-level")
            count_text = td.get("aria-label", "") or (td.find("tool-tip").text if td.find("tool-tip") else "")
            if d is None:
                continue
            days.append({
                "date": d,
                "level": int(level) if level is not None else 0,
                "label": count_text.strip(),
            })
    else:
        # fallback: newer markup uses <table> with td[data-date] but no ContributionCalendar-day class
        for td in soup.select("td[data-date]"):
            d = td.get("data-date")
            level = td.get("data-level", "0")
            days.append({"date": d, "level": int(level), "label": ""})

    if not days:
        raise RuntimeError("Could not parse contribution cells; GitHub markup may have changed")

    days.sort(key=lambda x: x["date"])
    return days


def to_weeks(days):
    weeks = []
    week = []
    for d in days:
        y, m, dd = map(int, d["date"].split("-"))
        weekday = date(y, m, dd).weekday()  # Mon=0..Sun=6
        gh_weekday = (weekday + 1) % 7  # Sun=0..Sat=6, matches GitHub calendar
        if gh_weekday == 0 and week:
            weeks.append(week)
            week = []
        week.append(d)
    if week:
        weeks.append(week)
    return weeks


def build_svg(weeks, username: str, static: bool) -> str:
    cols = len(weeks)
    width = cols * (CELL + GAP) + GAP + 30
    height = 7 * (CELL + GAP) + GAP + 34

    total = sum(d["level"] > 0 for w in weeks for d in w)
    contrib_total = sum(1 for w in weeks for d in w if d["level"] > 0)

    style = f"""
  <style>
    text {{ font-family: 'SFMono-Regular', Consolas, Menlo, monospace; fill: {TEXT_COLOR}; }}
    rect.bg {{ fill: {BG}; }}
    rect.cell {{ stroke: rgba(255,255,255,0.04); }}"""
    if not static:
        style += """
    .cell { animation: reveal 0.5s ease-out forwards; opacity: 0; }
    @keyframes reveal {
      0%   { opacity: 0; transform: translate(-6px, -6px); }
      100% { opacity: 1; transform: translate(0, 0); }
    }"""
    style += "\n  </style>"

    body = []
    for wi, week in enumerate(weeks):
        for di, d in enumerate(week):
            x = 30 + wi * (CELL + GAP)
            y = 20 + di * (CELL + GAP)
            color = LEVEL_COLORS[min(d["level"], len(LEVEL_COLORS) - 1)]
            delay = round((wi + di * 0.15) * 0.012, 3)
            attrs = f'class="cell" style="animation-delay:{delay}s"' if not static else ""
            title = d["label"].replace("&", "&amp;").replace("<", "&lt;")
            title_el = f"<title>{title}</title>" if title else ""
            body.append(
                f'    <rect {attrs} x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                f'rx="2" fill="{color}">{title_el}</rect>'
            )

    caption = f"{contrib_total} active days shown &middot; @{username}"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{style}
  <rect class="bg" x="0" y="0" width="{width}" height="{height}" rx="10"/>
  <text x="10" y="{height - 8}" font-size="10">{caption}</text>
{chr(10).join(body)}
</svg>
"""
    return svg


def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_heatmap.py <username> <output-svg> [--static]")
        sys.exit(1)
    username, dst = sys.argv[1], sys.argv[2]
    static = "--static" in sys.argv

    days = fetch_contributions(username)
    weeks = to_weeks(days)
    svg = build_svg(weeks, username, static)

    with open(dst, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {dst} ({len(weeks)} weeks)")


if __name__ == "__main__":
    main()
