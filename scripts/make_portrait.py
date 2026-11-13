"""One-off: turn an "HB" monogram (or a photo) into ASCII art at data/portrait.txt.

    python scripts/make_portrait.py              # serif HB monogram
    python scripts/make_portrait.py me.jpg       # a photo instead (needs Pillow)

The daily renderer only reads data/portrait.txt, so the Action never needs Pillow.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
COLS, ROWS = 64, 36
CELL_W, CELL_H = 4.2, 7.3          # the mono cell the hero card draws at 7px
RAMP = " .:-=+*#%@"
SCALE = 8


def monogram():
    w, h = int(COLS * CELL_W * SCALE), int(ROWS * CELL_H * SCALE)
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    # ring
    pad = int(h * 0.04)
    cx, cy, r = w // 2, h // 2, min(w, h) // 2 - pad
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=60, width=int(r * 0.05))
    d.ellipse([cx - r * 0.86, cy - r * 0.86, cx + r * 0.86, cy + r * 0.86], fill=255)
    font = ImageFont.truetype(str(ROOT / "fonts" / "src" / "InstrumentSerif-Italic.ttf"), int(r * 1.45))
    box = d.textbbox((0, 0), "hb", font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text((cx - tw / 2 - box[0], cy - th / 2 - box[1]), "hb", font=font, fill=0)
    return img


def photo(path, gamma=0.55):
    img = ImageOps.grayscale(Image.open(path).convert("RGB"))
    # crop to the subject: anything clearly darker than the (light) background
    mask = img.point(lambda p: 255 if p < 200 else 0)
    box = mask.getbbox()
    if box:
        pad = int(0.03 * img.width)
        img = img.crop((max(box[0] - pad, 0), max(box[1] - pad, 0),
                        min(box[2] + pad, img.width), min(box[3] + pad, img.height)))
    img = ImageOps.pad(img, (int(COLS * CELL_W * SCALE), int(ROWS * CELL_H * SCALE)), color=255)
    img = ImageOps.autocontrast(img, cutoff=1)
    # lift midtones so skin reads as light and lines/hair/beard stay dark
    return img.point(lambda p: int(255 * (p / 255) ** gamma))


def to_ascii(img):
    small = img.resize((COLS, ROWS), Image.LANCZOS)
    px = small.load()
    lines = []
    for y in range(ROWS):
        row = "".join(RAMP[int((255 - px[x, y]) / 256 * len(RAMP))] for x in range(COLS))
        lines.append(row.rstrip())
    return "\n".join(lines)


if __name__ == "__main__":
    img = photo(sys.argv[1]) if len(sys.argv) > 1 else monogram()
    art = to_ascii(img)
    (ROOT / "data" / "portrait.txt").write_text(art + "\n")
    print(art)
