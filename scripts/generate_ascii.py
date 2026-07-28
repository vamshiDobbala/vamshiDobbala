"""
Generate an animated ASCII-art SVG portrait from a photo.

Pipeline: background removal (rembg, optional) -> CLAHE contrast enhancement
-> composite on white -> map grayscale to a character density ramp -> emit
an SVG where each row of characters sweeps in left-to-right, staggered
top-to-bottom.

Usage:
    python scripts/generate_ascii.py Image.jpg assets/vamsi-ascii.svg
"""
import sys
import numpy as np
from PIL import Image
import cv2

DENSITY_RAMP = " .`:-=+*cs#%@"
CELL_W = 6
CELL_H = 12
FONT_SIZE = 11
ACCENT = "#36BCF7"  # matches the typing-SVG header color
BG = "#0d1117"  # GitHub dark background


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


def to_ascii_grid(img: Image.Image, cols: int) -> list[str]:
    aspect = img.height / img.width
    rows = max(1, int(cols * aspect * (CELL_W / CELL_H)))
    small = img.resize((cols, rows), Image.LANCZOS)

    gray = cv2.cvtColor(np.array(small), cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    ramp_len = len(DENSITY_RAMP)
    grid = []
    for r in range(rows):
        line = []
        for c in range(cols):
            # brightness -> darker pixel = denser character (portrait on light bg)
            v = 255 - int(gray[r, c])
            idx = min(ramp_len - 1, v * ramp_len // 256)
            line.append(DENSITY_RAMP[idx])
        grid.append("".join(line))
    return grid


def escape_xml(ch: str) -> str:
    return {"&": "&amp;", "<": "&lt;", ">": "&gt;"}.get(ch, ch)


def build_svg(grid: list[str], static: bool) -> str:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    width = cols * CELL_W
    height = rows * CELL_H

    style = f"""
  <style>
    text {{
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: {FONT_SIZE}px;
      fill: {ACCENT};
    }}
    rect.bg {{ fill: {BG}; }}"""

    if not static:
        style += """
    .row { animation: reveal 0.9s ease-out forwards; opacity: 0; }
    @keyframes reveal {
      0%   { opacity: 0; transform: translateX(-14px); }
      100% { opacity: 1; transform: translateX(0); }
    }"""
    style += "\n  </style>"

    body = []
    for r, line in enumerate(grid):
        y = (r + 1) * CELL_H - 2
        delay = round(r * 0.035, 3)
        attrs = f'class="row" style="animation-delay:{delay}s"' if not static else ""
        safe = "".join(escape_xml(ch) for ch in line)
        body.append(f'    <text x="0" y="{y}" xml:space="preserve" {attrs}>{safe}</text>')

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{style}
  <rect class="bg" x="0" y="0" width="{width}" height="{height}" rx="10"/>
  <g transform="translate(14,4)">
{chr(10).join(body)}
  </g>
</svg>
"""
    return svg


def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_ascii.py <input-image> <output-svg> [--cols N] [--static]")
        sys.exit(1)

    src, dst = sys.argv[1], sys.argv[2]
    cols = 90
    static = "--static" in sys.argv
    if "--cols" in sys.argv:
        cols = int(sys.argv[sys.argv.index("--cols") + 1])

    img = Image.open(src).convert("RGBA")
    img = remove_background(img)
    img = composite_on_white(img)
    grid = to_ascii_grid(img, cols)
    svg = build_svg(grid, static)

    with open(dst, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {dst} ({len(grid)} rows x {len(grid[0]) if grid else 0} cols)")


if __name__ == "__main__":
    main()
