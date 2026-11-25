"""Generate Portalis custom emoji: red app-icon tiles, white glyphs."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "emojis"

SIZE = 256
SS = 4
S = SIZE * SS
LW = int(S * 0.045)
TOP, BOT = (237, 28, 36), (125, 8, 14)
CX = CY = S / 2
R = S * 0.30


def base() -> Image.Image:
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, S - 1, S - 1], radius=int(S * 0.24), fill=255
    )
    col = Image.new("RGB", (1, S))
    for y in range(S):
        t = y / (S - 1)
        col.putpixel((0, y), tuple(
            int(TOP[i] + (BOT[i] - TOP[i]) * t) for i in range(3)
        ))
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(col.resize((S, S)), (0, 0), mask)

    # soft top gloss
    gloss = Image.new("L", (1, S))
    for y in range(S):
        gloss.putpixel((0, y), int(50 * max(0.0, 1 - (y / S) * 2.4)))
    ga = Image.composite(gloss.resize((S, S)), Image.new("L", (S, S), 0), mask)
    gimg = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    gimg.putalpha(ga)
    img.alpha_composite(gimg)
    return img


def glyph(img: Image.Image, fn):
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fn(ImageDraw.Draw(sh), (90, 5, 8, 170), LW)
    sh = sh.filter(ImageFilter.GaussianBlur(S * 0.008))
    img.alpha_composite(sh, (0, int(S * 0.012)))
    fn(ImageDraw.Draw(img), (255, 255, 255, 255), LW)


def g_clock(d, f, w):
    d.ellipse([CX - R, CY - R, CX + R, CY + R], outline=f, width=w)
    d.line([CX, CY, CX, CY - R * 0.55], fill=f, width=w)
    d.line([CX, CY, CX + R * 0.42, CY + R * 0.1], fill=f, width=w)


def g_check(d, f, w):
    d.line([CX - R * 0.8, CY + R * 0.05, CX - R * 0.15, CY + R * 0.6,
            CX + R * 0.85, CY - R * 0.55], fill=f, width=w, joint="curve")


def g_x(d, f, w):
    d.line([CX - R * 0.7, CY - R * 0.7, CX + R * 0.7, CY + R * 0.7],
           fill=f, width=w)
    d.line([CX - R * 0.7, CY + R * 0.7, CX + R * 0.7, CY - R * 0.7],
           fill=f, width=w)


def g_lock(d, f, w):
    d.arc([CX - R * 0.55, CY - R * 0.95, CX + R * 0.55, CY + R * 0.3],
          180, 360, fill=f, width=w)
    d.rounded_rectangle([CX - R * 0.75, CY - R * 0.1, CX + R * 0.75,
                         CY + R * 0.8], radius=R * 0.18, outline=f, width=w)
    d.line([CX, CY + R * 0.25, CX, CY + R * 0.5], fill=f, width=w)


def g_bell(d, f, w):
    d.arc([CX - R * 0.7, CY - R * 0.8, CX + R * 0.7, CY + R * 0.6],
          180, 360, fill=f, width=w)
    d.line([CX - R * 0.7, CY - R * 0.1, CX - R * 0.7, CY + R * 0.4],
           fill=f, width=w)
    d.line([CX + R * 0.7, CY - R * 0.1, CX + R * 0.7, CY + R * 0.4],
           fill=f, width=w)
    d.arc([CX - R * 0.9, CY + R * 0.2, CX + R * 0.9, CY + R * 0.6],
          0, 180, fill=f, width=w)
    d.arc([CX - R * 0.25, CY + R * 0.6, CX + R * 0.25, CY + R],
          0, 180, fill=f, width=w)


def g_gift(d, f, w):
    d.rounded_rectangle([CX - R * 0.8, CY - R * 0.3, CX + R * 0.8,
                         CY + R * 0.75], radius=R * 0.12, outline=f, width=w)
    d.line([CX, CY - R * 0.3, CX, CY + R * 0.75], fill=f, width=w)
    d.line([CX - R * 0.8, CY - R * 0.05, CX + R * 0.8, CY - R * 0.05],
           fill=f, width=w)
    d.arc([CX - R * 0.55, CY - R * 0.75, CX - R * 0.05, CY - R * 0.3],
          100, 300, fill=f, width=w)
    d.arc([CX + R * 0.05, CY - R * 0.75, CX + R * 0.55, CY - R * 0.3],
          240, 80, fill=f, width=w)


def g_diamond(d, f, w):
    pts = [(CX, CY - R * 0.7), (CX + R * 0.75, CY - R * 0.1),
           (CX, CY + R * 0.8), (CX - R * 0.75, CY - R * 0.1)]
    d.polygon(pts, outline=f, width=w)
    d.line([CX - R * 0.75, CY - R * 0.1, CX + R * 0.75, CY - R * 0.1],
           fill=f, width=w)
    d.line([CX - R * 0.3, CY - R * 0.1, CX, CY + R * 0.8], fill=f, width=w)
    d.line([CX + R * 0.3, CY - R * 0.1, CX, CY + R * 0.8], fill=f, width=w)


def g_ticket(d, f, w):
    d.rounded_rectangle([CX - R * 0.95, CY - R * 0.55, CX + R * 0.95,
                         CY + R * 0.55], radius=R * 0.18, outline=f, width=w)
    d.line([CX + R * 0.35, CY - R * 0.4, CX + R * 0.35, CY + R * 0.4],
           fill=f, width=int(w * 0.7))


def g_calendar(d, f, w):
    d.rounded_rectangle([CX - R * 0.8, CY - R * 0.65, CX + R * 0.8,
                         CY + R * 0.75], radius=R * 0.15, outline=f, width=w)
    d.line([CX - R * 0.8, CY - R * 0.3, CX + R * 0.8, CY - R * 0.3],
           fill=f, width=w)
    d.line([CX - R * 0.4, CY - R * 0.85, CX - R * 0.4, CY - R * 0.5],
           fill=f, width=w)
    d.line([CX + R * 0.4, CY - R * 0.85, CX + R * 0.4, CY - R * 0.5],
           fill=f, width=w)
    for yy in (0.08, 0.42):
        for dx in (-0.42, 0.0, 0.42):
            d.ellipse([CX + R * dx - R * 0.08, CY + R * yy,
                       CX + R * dx + R * 0.08, CY + R * yy + R * 0.16],
                      fill=f)


def g_doc(d, f, w):
    d.rounded_rectangle([CX - R * 0.6, CY - R * 0.85, CX + R * 0.6,
                         CY + R * 0.85], radius=R * 0.12, outline=f, width=w)
    for i, span in enumerate((0.38, 0.38, 0.22)):
        y = CY - R * 0.45 + i * R * 0.32
        d.line([CX - R * 0.38, y, CX + R * span, y], fill=f, width=w)


def g_mega(d, f, w):
    d.polygon([(CX - R * 0.2, CY - R * 0.45),
               (CX + R * 0.7, CY - R * 0.8),
               (CX + R * 0.7, CY + R * 0.8),
               (CX - R * 0.2, CY + R * 0.45)], outline=f, width=w)
    d.rounded_rectangle([CX - R * 0.75, CY - R * 0.45, CX - R * 0.2,
                         CY + R * 0.45], radius=R * 0.1, outline=f, width=w)


def g_star(d, f, w):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = R if i % 2 == 0 else R * 0.45
        pts.append((CX + rad * math.cos(ang), CY + rad * math.sin(ang)))
    d.polygon(pts, outline=f, width=w)


def g_globe(d, f, w):
    d.ellipse([CX - R, CY - R, CX + R, CY + R], outline=f, width=w)
    d.ellipse([CX - R * 0.45, CY - R, CX + R * 0.45, CY + R],
              outline=f, width=w)
    d.line([CX - R, CY, CX + R, CY], fill=f, width=w)


ICONS = {
    "clock": g_clock, "check": g_check, "x": g_x, "lock": g_lock,
    "bell": g_bell, "gift": g_gift, "diamond": g_diamond,
    "ticket": g_ticket, "calendar": g_calendar, "doc": g_doc,
    "mega": g_mega, "star": g_star, "globe": g_globe,
}


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, fn in ICONS.items():
        img = base()
        glyph(img, fn)
        img.resize((SIZE, SIZE), Image.LANCZOS).save(OUT / f"{name}.png")
        print("wrote", name)
