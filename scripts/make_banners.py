"""Regenerate the per-panel banners from the SMP Portal brand assets.

Animated GIFs: the satin background drifts in a smooth loop while the
text and logo stay still — same look as the reference style.

Run:  python scripts/make_banners.py
"""

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

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


def make_boost(out: Path):
    """Nitro-pink beams + particles — Liner-style giveaway look."""
    rng = random.Random(7)
    word = "BOOST"

    # base: dark plum -> deep magenta vertical gradient
    col = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        col.putpixel((0, y), (
            int(74 + (26 - 74) * t),
            int(14 + (4 - 14) * t),
            int(70 + (36 - 70) * t),
        ))
    base = col.resize((W, H)).convert("RGBA")

    beams = [
        (rng.randint(-100, W), rng.randint(110, 240), rng.randint(45, 85))
        for _ in range(7)
    ]
    particles = [
        (rng.randint(0, W), rng.randint(0, H), rng.uniform(1.5, 3.5),
         rng.uniform(0, 2 * math.pi))
        for _ in range(60)
    ]

    logo = circle(Image.open(ASSETS / "pfp.webp"), 84)
    f_big, f_mark = font(160), font(54)
    SLANT = 260  # horizontal offset of each beam's bottom edge

    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        ang = 2 * math.pi * t
        frame = base.copy()

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for i, (bx, bw, ba) in enumerate(beams):
            shift = int(120 * math.sin(ang + i * 1.3))
            alpha = int(ba * (0.7 + 0.3 * math.sin(ang * 2 + i)))
            x0 = bx + shift
            ld.polygon(
                [(x0, -50), (x0 + bw, -50),
                 (x0 + bw - SLANT, H + 50), (x0 - SLANT, H + 50)],
                fill=(255, 170, 240, alpha),
            )
        frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(38)))

        pd = ImageDraw.Draw(frame)
        for px, py, pr, ph in particles:
            a = int(110 * (0.45 + 0.55 * math.sin(ang * 2 + ph)))
            yy = (py - t * H) % (H + 20) - 10
            pd.ellipse([px - pr, yy - pr, px + pr, yy + pr],
                       fill=(255, 205, 245, a))

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
        if name == "boost":
            make_boost(OUT / "boost.gif")
        else:
            make(word, OUT / f"{name}.gif")
