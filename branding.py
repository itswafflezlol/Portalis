from pathlib import Path

import discord

RED = 0xED1C24

ASSETS = Path(__file__).parent / "assets"
BANNER = ASSETS / "banner.webp"
PFP = ASSETS / "pfp.webp"

FOOTER = "SMP Portal · Official Discord"


def brand_embed(title: str, description: str = "", images: bool = True) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=RED)
    if images:
        e.set_image(url="attachment://banner.webp")
        e.set_thumbnail(url="attachment://pfp.webp")
    e.set_footer(text=FOOTER)
    return e


def brand_files() -> list[discord.File]:
    return [
        discord.File(BANNER, filename="banner.webp"),
        discord.File(PFP, filename="pfp.webp"),
    ]
