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
FRAMES = 30
FPS = 15
DRIFT_X, DRIFT_Y = 200, 110  # ellipse the crop window travels around
ZOOM = 0.07                  # extra scale at the loop's widest point

WORDS = {
    "tickets": "TICKETS",
    "support": "SUPPORT",
    "partnership": "PARTNERSHIP",
    "apply": "FREELANCE",
    "partner": "PARTNERS",
    "info": "INFO",
    "paid_ad": "PAID AD",
    "paidads": "PAID ADS",
    "pings": "PING ME",
    "giveaway": "GIVEAWAY",
    "server": "WELCOME",
    "rules": "RULES",
    "boost": "BOOST",
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
    # source must cover W/H plus the drift ellipse plus zoom headroom
    need_w, need_h = (W + 2 * DRIFT_X) * (1 + ZOOM), \
                     (H + 2 * DRIFT_Y) * (1 + ZOOM)
    ratio = max(need_w / bg.width, need_h / bg.height)
    bg = bg.resize((int(bg.width * ratio), int(bg.height * ratio)),
                   Image.LANCZOS)

    dim = ImageEnhance.Brightness(bg).enhance(0.55)
    grad = Image.new("L", (bg.width, 1))
    for i in range(bg.width):
        grad.putpixel((i, 0), int(90 * i / bg.width))
    grad = grad.resize(bg.size)
    dim = Image.composite(Image.new("RGB", bg.size), dim, grad)

    logo = circle(Image.open(ASSETS / "pfp.webp"), 84)
    f_big, f_mark = font(160), font(54)

    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        ang = 2 * math.pi * t
        scale = 1 + ZOOM * (0.5 - 0.5 * math.cos(ang))
        sw, sh = int(W * scale), int(H * scale)

        cx = (dim.width - sw) // 2 + int(DRIFT_X * math.cos(ang))
        cy = (dim.height - sh) // 2 + int(DRIFT_Y * math.sin(ang))
        cx = max(0, min(cx, dim.width - sw))
        cy = max(0, min(cy, dim.height - sh))

        frame = dim.crop((cx, cy, cx + sw, cy + sh)) \
                   .resize((W, H), Image.LANCZOS).convert("RGBA")
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
