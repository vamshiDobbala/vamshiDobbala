"""
Generate an animated ASCII-art SVG portrait from a photo, styled as a fake
terminal window: title bar with traffic-light dots, each row typed in
left-to-right one at a time (clip-path width animation + a sweeping cursor
block), and a blinking prompt cursor once typing finishes.

Usage:
    python scripts/generate_ascii.py Image.jpg assets/vamsi-ascii.svg
"""
import sys
import numpy as np
from PIL import Image
import cv2

DENSITY_RAMP = " .`:-=+*cs#%@"
GAMMA = 1.18       # pushes midtones down so the face lands in sparser characters
WHITE_FLOOR = 0.80  # luminance at/above this is forced blank -- cleanly clears the background

MARGIN = 20
ROW_H = 15
FONT_SIZE = 12.9
BASELINE_OFFSET = 11.1
ROW_DUR = 0.11  # seconds per row reveal, matches cursor sweep speed
TITLEBAR_H = 30
FOOTER_H = 32

BG_TOP = "#111722"
BG_BOTTOM = "#0d1117"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#7d8590"
DOTS = ["#ff5f56", "#ffbd2e", "#27c93f"]

TITLE = "vamsi@github: ~$ ./portrait.sh"
PROMPT_LABEL = "vamsi@github:~$ whoami"
PROMPT_VALUE = "Vamsi Dobbala"


def remove_background(img: Image.Image) -> Image.Image:
    try:
        from rembg import remove
        return remove(img).convert("RGBA")
    except Exception as e:
        print(f"[warn] rembg unavailable ({e}); continuing without background removal", file=sys.stderr)
        return img.convert("RGBA")


def composite_on_white(img: Image.Image) -> Image.Image:
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    white.alpha_composite(img)
    return white.convert("RGB")


def to_ascii_grid(img: Image.Image, cols: int, cell_w: float, cell_h: float) -> list[str]:
    aspect = img.height / img.width
    rows = max(1, int(cols * aspect * (cell_w / cell_h)))
    small = img.resize((cols, rows), Image.LANCZOS)

    gray = cv2.cvtColor(np.array(small), cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    ramp_len = len(DENSITY_RAMP)
    grid = []
    for r in range(rows):
        line = []
        for c in range(cols):
            lum = pow(gray[r, c] / 255.0, GAMMA)
            if lum >= WHITE_FLOOR:
                line.append(" ")
                continue
            idx = min(ramp_len - 1, int((1.0 - lum) * (ramp_len - 1) + 0.5))
            line.append(DENSITY_RAMP[idx])
        grid.append("".join(line))
    return grid


def escape_xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(grid: list[str], static: bool) -> str:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    text_width = cols * 8  # approximate cell width, stretched exactly via textLength
    width = text_width + MARGIN * 2
    body_h = rows * ROW_H
    height = TITLEBAR_H + body_h + FOOTER_H

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOTTOM}"/></linearGradient></defs>',
        f'<rect width="{width}" height="{height}" rx="12" fill="url(#bg)"/>',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="none" stroke="{BORDER}"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{width}" y2="{TITLEBAR_H}" stroke="{BORDER}"/>',
        f'<circle cx="20" cy="15" r="5" fill="{DOTS[0]}"/>',
        f'<circle cx="36" cy="15" r="5" fill="{DOTS[1]}"/>',
        f'<circle cx="52" cy="15" r="5" fill="{DOTS[2]}"/>',
        f'<text x="{width / 2}" y="19" fill="{MUTED}" font-size="12" text-anchor="middle">{escape_xml(TITLE)}</text>',
    ]

    for r, line in enumerate(grid):
        row_top = TITLEBAR_H + 7 + r * ROW_H
        baseline = row_top + BASELINE_OFFSET
        safe = escape_xml(line)
        begin = round(r * ROW_DUR, 3)

        if static:
            parts.append(
                f'<text xml:space="preserve" x="{MARGIN}" y="{baseline}" fill="{TEXT}" '
                f'font-size="{FONT_SIZE}" textLength="{text_width}" lengthAdjust="spacing">{safe}</text>'
            )
            continue

        clip_id = f"r{r}"
        parts.append(
            f'<clipPath id="{clip_id}"><rect x="{MARGIN}" y="{row_top}" height="{ROW_H}" width="0">'
            f'<animate attributeName="width" from="0" to="{text_width}" begin="{begin}s" dur="{ROW_DUR}s" fill="freeze"/>'
            f'</rect></clipPath>'
        )
        parts.append(
            f'<g clip-path="url(#{clip_id})"><text xml:space="preserve" x="{MARGIN}" y="{baseline}" '
            f'fill="{TEXT}" font-size="{FONT_SIZE}" textLength="{text_width}" lengthAdjust="spacing">{safe}</text></g>'
        )
        cursor_y = row_top + 1
        parts.append(
            f'<rect y="{cursor_y}" width="8" height="13" fill="{TEXT}" opacity="0">'
            f'<animate attributeName="x" from="{MARGIN}" to="{MARGIN + text_width}" begin="{begin}s" dur="{ROW_DUR}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.85" begin="{begin}s"/>'
            f'<set attributeName="opacity" to="0" begin="{round(begin + ROW_DUR, 3)}s"/>'
            f'</rect>'
        )

    footer_y = TITLEBAR_H + body_h
    prompt_baseline = footer_y + 19
    parts.append(f'<line x1="0" y1="{footer_y}" x2="{width}" y2="{footer_y}" stroke="{BORDER}"/>')
    parts.append(
        f'<text x="{MARGIN}" y="{prompt_baseline}" fill="{MUTED}" font-size="13">'
        f'{escape_xml(PROMPT_LABEL)} <tspan fill="{TEXT}">{escape_xml(PROMPT_VALUE)}</tspan></text>'
    )

    if not static:
        end_time = round(rows * ROW_DUR, 3)
        cursor_x = MARGIN + 8 * (len(PROMPT_LABEL) + 1 + len(PROMPT_VALUE))
        parts.append(
            f'<rect x="{cursor_x}" y="{footer_y + 7}" width="8" height="14" fill="{TEXT}" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{end_time}s"/>'
            f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
            f'begin="{end_time}s" dur="1s" repeatCount="indefinite"/>'
            f'</rect>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_ascii.py <input-image> <output-svg> [--cols N] [--static]")
        sys.exit(1)

    src, dst = sys.argv[1], sys.argv[2]
    cols = 100
    static = "--static" in sys.argv
    if "--cols" in sys.argv:
        cols = int(sys.argv[sys.argv.index("--cols") + 1])

    img = Image.open(src).convert("RGBA")
    img = remove_background(img)
    img = composite_on_white(img)
    grid = to_ascii_grid(img, cols, cell_w=8, cell_h=ROW_H)
    svg = build_svg(grid, static)

    with open(dst, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {dst} ({len(grid)} rows x {len(grid[0]) if grid else 0} cols)")


if __name__ == "__main__":
    main()
