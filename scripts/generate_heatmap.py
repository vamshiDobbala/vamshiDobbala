"""
Scrape real daily contribution counts from GitHub's public, unauthenticated
contributions endpoint (no token needed) and render a GitHub-style heatmap
SVG: a 53-week x 7-day grid of rounded boxes inside a fake terminal window
(matching the ASCII portrait card's chrome), revealed once with a diagonal
line-after-line cascade, a Less->More legend, and a real stats footer
(total contributions, streaks, best day).

Usage:
    python scripts/generate_heatmap.py vamshiDobbala assets/contrib-heatmap.svg
"""
import re
import sys
from datetime import date

import requests
from bs4 import BeautifulSoup

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

CELL = 12
GAP = 3
STEP = CELL + GAP
PAD = 22
LEFT_LABEL_W = 30
TOP_LABEL_H = 20
TITLEBAR_H = 30

BG_TOP = "#111722"
BG_BOTTOM = "#0d1117"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#7d8590"
ACCENT = "#36BCF7"
GREEN = "#39d353"
GOLD = "#f2cc60"
DOTS = ["#ff5f56", "#ffbd2e", "#27c93f"]

TITLE = "vamsi@github: ~/contributions --graph"

# reveal timing (one-shot, diagonal cascade)
COL_T = 0.018
ROW_T = 0.045
CELL_DUR = 0.42


def level_for(count: int) -> int:
    if count == 0:
        return 0
    if count <= 5:
        return 1
    if count <= 15:
        return 2
    if count <= 30:
        return 3
    if count <= 50:
        return 4
    return 5


def fetch_days(username: str):
    url = f"https://github.com/users/{username}/contributions"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        raise RuntimeError("Could not parse contribution cells; GitHub markup may have changed")

    days = []
    for td in cells:
        d = td.get("data-date")
        if not d:
            continue
        td_id = td.get("id")
        tooltip = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
        text = tooltip.get_text(strip=True) if tooltip else ""
        if re.search(r"no contributions", text, re.I):
            count = 0
        else:
            m = re.match(r"(\d+)", text)
            count = int(m.group(1)) if m else 0
        days.append({"date": d, "count": count})

    days.sort(key=lambda x: x["date"])
    return days


def compute_current_streak(days):
    idx = len(days) - 1
    if days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet -- don't break the streak on it
    streak = 0
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    return streak


def compute_longest_streak(days):
    longest = run = 0
    for d in days:
        if d["count"] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest


def build_grid(days):
    first = date.fromisoformat(days[0]["date"])
    lead_pad = (first.weekday() + 1) % 7  # Sunday=0
    grid = []
    col = [None] * lead_pad
    for d in days:
        dt = date.fromisoformat(d["date"])
        weekday = (dt.weekday() + 1) % 7
        while len(col) < weekday:
            col.append(None)
        col.append((d["date"], d["count"], level_for(d["count"])))
        if len(col) == 7:
            grid.append(col)
            col = []
    if col:
        while len(col) < 7:
            col.append(None)
        grid.append(col)
    return grid


def build_svg(days, username: str, static: bool) -> str:
    grid = build_grid(days)
    n_cols = len(grid)
    art_w = n_cols * STEP
    art_h = 7 * STEP

    month_labels = []
    seen_months = set()
    for ci, column in enumerate(grid):
        for cell in column:
            if cell is None:
                continue
            dt = date.fromisoformat(cell[0])
            key = (dt.year, dt.month)
            if key not in seen_months and dt.day <= 7:
                seen_months.add(key)
                month_labels.append((ci, dt.strftime("%b")))
            break

    canvas_w = PAD + LEFT_LABEL_W + art_w + PAD
    stats_h = 88
    canvas_h = TITLEBAR_H + TOP_LABEL_H + art_h + stats_h + PAD

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
    ]

    if not static:
        parts.append(f"""<style>
@keyframes cell {{
  0%   {{ opacity: 0; transform: translateY(-6px); }}
  100% {{ opacity: 1; transform: translateY(0); }}
}}
.c {{ opacity: 0; animation: cell {CELL_DUR:.2f}s cubic-bezier(.2,.8,.2,1) both; }}
</style>""")

    parts += [
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOTTOM}"/></linearGradient></defs>',
        f'<rect width="{canvas_w}" height="{canvas_h}" rx="12" fill="url(#bg)"/>',
        f'<rect x="0.5" y="0.5" width="{canvas_w - 1}" height="{canvas_h - 1}" rx="12" fill="none" stroke="{BORDER}"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{canvas_w}" y2="{TITLEBAR_H}" stroke="{BORDER}"/>',
        f'<circle cx="20" cy="15" r="5" fill="{DOTS[0]}"/>',
        f'<circle cx="36" cy="15" r="5" fill="{DOTS[1]}"/>',
        f'<circle cx="52" cy="15" r="5" fill="{DOTS[2]}"/>',
        f'<text x="{canvas_w / 2}" y="19" fill="{MUTED}" font-size="12" text-anchor="middle">{TITLE}</text>',
    ]

    grid_top = TITLEBAR_H + TOP_LABEL_H
    grid_left = PAD + LEFT_LABEL_W

    for ci, label in month_labels:
        x = grid_left + ci * STEP
        parts.append(f'<text x="{x}" y="{TITLEBAR_H + 14}" fill="{MUTED}" font-size="10">{label}</text>')

    for wi, wname in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = grid_top + wi * STEP + CELL * 0.78
        parts.append(f'<text x="{PAD}" y="{y:.1f}" fill="{MUTED}" font-size="9">{wname}</text>')

    for ci, column in enumerate(grid):
        gx = grid_left + ci * STEP
        for ri, cell in enumerate(column):
            if cell is None:
                continue
            date_s, count, lvl = cell
            gy = grid_top + ri * STEP
            plural = "s" if count != 1 else ""
            attrs = ""
            if not static:
                delay = ci * COL_T + ri * ROW_T
                attrs = f'class="c" style="animation-delay:{delay:.3f}s"'
            parts.append(
                f'<rect {attrs} x="{gx}" y="{gy}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{PALETTE[lvl]}"><title>{date_s}: {count} contribution{plural}</title></rect>'
            )

    leg_y = grid_top + art_h + 6
    leg_x = canvas_w - PAD - (len(PALETTE) * (CELL - 1) + 70)
    parts.append(f'<text x="{leg_x}" y="{leg_y + CELL * 0.8:.1f}" fill="{MUTED}" font-size="10" text-anchor="end">Less</text>')
    lx = leg_x + 8
    for lvl, color in enumerate(PALETTE):
        parts.append(f'<rect x="{lx}" y="{leg_y}" width="{CELL - 1}" height="{CELL - 1}" rx="2.2" fill="{color}"/>')
        lx += CELL
    parts.append(f'<text x="{lx + 4}" y="{leg_y + CELL * 0.8:.1f}" fill="{MUTED}" font-size="10">More</text>')

    sep_y = leg_y + CELL + 14
    parts.append(f'<line x1="0" y1="{sep_y}" x2="{canvas_w}" y2="{sep_y}" stroke="{BORDER}"/>')

    total = sum(d["count"] for d in days)
    cur_streak = compute_current_streak(days)
    longest_streak = compute_longest_streak(days)
    best = max(days, key=lambda d: d["count"])
    start, end = days[0]["date"], days[-1]["date"]

    ly = sep_y + 24
    parts.append(
        f'<text x="{PAD}" y="{ly}" font-size="13" fill="{GREEN}">'
        f'<tspan font-weight="700">{total:,}</tspan>'
        f'<tspan fill="{MUTED}"> contributions in the last year</tspan></text>'
    )
    parts.append(
        f'<text x="{canvas_w - PAD}" y="{ly}" font-size="12" fill="{MUTED}" text-anchor="end">'
        f'{start} &#8594; {end}</text>'
    )
    ly += 24
    parts.append(
        f'<text x="{PAD}" y="{ly}" font-size="13" fill="{MUTED}">current streak '
        f'<tspan fill="{ACCENT}" font-weight="700">{cur_streak} days</tspan>'
        f'<tspan fill="{MUTED}">   &#183;   longest </tspan>'
        f'<tspan fill="{ACCENT}" font-weight="700">{longest_streak} days</tspan></text>'
    )
    parts.append(
        f'<text x="{canvas_w - PAD}" y="{ly}" font-size="12" fill="{MUTED}" text-anchor="end">'
        f'best day <tspan fill="{GOLD}" font-weight="700">{best["count"]}</tspan> on {best["date"]}</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_heatmap.py <username> <output-svg> [--static]")
        sys.exit(1)
    username, dst = sys.argv[1], sys.argv[2]
    static = "--static" in sys.argv

    days = fetch_days(username)
    svg = build_svg(days, username, static)

    with open(dst, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {dst} ({len(days)} days, {sum(d['count'] for d in days)} contributions)")


if __name__ == "__main__":
    main()
