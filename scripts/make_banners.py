"""Regenerate the per-panel banners from the SMP Portal brand assets.

Animated GIFs: the satin background drifts in a smooth loop while the
text and logo stay still — same look as the reference style.

Run:  python scripts/make_banners.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "assets"
OUT = ASSETS / "panels"

W, H = 1400, 480
FRAMES = 24
FPS = 12
PAN = 160  # px of horizontal drift, eased out and back for a clean loop

WORDS = {
    "tickets": "TICKETS",
    "support": "SUPPORT",
    "partnership": "PARTNERSHIP",
    "apply": "FREELANCE",
    "partner": "PARTNERS",
    "info": "INFO",
    "paid_ad": "PAID AD",
    "paidads": "PAID ADS",
}


def font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("segoeuib.ttf", "arialbd.ttf"):
        p = Path(r"C:\Windows\Fonts") / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def circle(img: Image.Image, size: int) -> Image.Image:
    img = img.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    img.putalpha(mask)
    return img


def draw_tracked(draw: ImageDraw.ImageDraw, xy, text: str,
                 f: ImageFont.FreeTypeFont, tracking: int = 8):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill="white")
        x += int(draw.textlength(ch, font=f)) + tracking


def make(word: str, out: Path):
    bg = Image.open(ASSETS / "banner_bg.jpg").convert("RGB")
    ratio = max((W + PAN) / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * ratio) + PAN,
                    int(bg.height * ratio)), Image.LANCZOS)

    dim = ImageEnhance.Brightness(bg).enhance(0.55)
    grad = Image.new("L", (bg.width, 1))
    for i in range(bg.width):
        grad.putpixel((i, 0), int(90 * i / bg.width))
    grad = grad.resize(bg.size)
    dim = Image.composite(Image.new("RGB", bg.size), dim, grad)

    logo = circle(Image.open(ASSETS / "pfp.webp"), 84)
    f_big, f_mark = font(160), font(54)
    y = (dim.height - H) // 2

    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        x = int((1 - math.cos(2 * math.pi * t)) / 2 * PAN)
        frame = dim.crop((x, y, x + W, y + H)).convert("RGBA")
        d = ImageDraw.Draw(frame)
        draw_tracked(d, (70, 120), word, f_big)
        frame.alpha_composite(logo, (70, H - 154))
        d.text((178, H - 140), "smpportal", font=f_mark, fill="white")
        frames.append(frame.convert("P", palette=Image.ADAPTIVE,
                                    colors=256))

    frames[0].save(
        out, save_all=True, append_images=frames[1:],
        duration=int(1000 / FPS), loop=0, optimize=True,
    )
    print("wrote", out, f"({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, word in WORDS.items():
        make(word, OUT / f"{name}.gif")
