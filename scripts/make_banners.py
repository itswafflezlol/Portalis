"""Regenerate the per-panel banners from the SMP Portal brand assets.

Run:  python scripts/make_banners.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "assets"
OUT = ASSETS / "panels"

W, H = 1400, 480

WORDS = {
    "tickets": "TICKETS",
    "apply": "FREELANCE",
    "partner": "PARTNERS",
    "info": "INFO",
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
    ratio = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * ratio), int(bg.height * ratio)),
                   Image.LANCZOS)
    x, y = (bg.width - W) // 2, (bg.height - H) // 2
    bg = bg.crop((x, y, x + W, y + H))

    dim = ImageEnhance.Brightness(bg).enhance(0.55)
    grad = Image.new("L", (W, 1))
    for i in range(W):
        grad.putpixel((i, 0), int(90 * i / W))
    grad = grad.resize((W, H))
    img = Image.composite(Image.new("RGB", (W, H)), dim, grad).convert("RGBA")

    d = ImageDraw.Draw(img)
    draw_tracked(d, (70, 120), word, font(160))

    logo = circle(Image.open(ASSETS / "pfp.webp"), 84)
    img.alpha_composite(logo, (70, H - 154))
    d.text((178, H - 140), "smpportal", font=font(54), fill="white")

    img.save(out, "WEBP", quality=90)
    print("wrote", out)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, word in WORDS.items():
        make(word, OUT / f"{name}.webp")
