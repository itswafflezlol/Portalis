from pathlib import Path

import discord

RED = 0xED1C24

ASSETS = Path(__file__).parent / "assets"
PANELS_DIR = ASSETS / "panels"
BANNER = ASSETS / "banner.webp"
PFP = ASSETS / "pfp.webp"

FOOTER = "SMP Portal · Official Discord"


def brand_embed(title: str = None, description: str = "", images: bool = True,
                banner: str = None) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=RED)
    if banner:
        e.set_image(url=f"attachment://{banner}")
    elif images:
        e.set_image(url="attachment://banner.webp")
    if images:
        e.set_thumbnail(url="attachment://pfp.webp")
    e.set_footer(text=FOOTER)
    return e


def brand_files(banner: str = None) -> list[discord.File]:
    files = [discord.File(PFP, filename="pfp.webp")]
    if banner:
        files.append(discord.File(PANELS_DIR / banner, filename=banner))
    else:
        files.append(discord.File(BANNER, filename="banner.webp"))
    return files
