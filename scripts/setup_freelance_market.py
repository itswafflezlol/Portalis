"""One-time: build the freelance marketplace channels.

- 🛍️・services forum inside Freelancers cat (public view, freelancers post)
- Freelance Orders category (hidden, tickets land here)
- ⭐・reviews channel in SMP Market (bot posts reviews only)
"""
import asyncio
import sys
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TOKEN, load_config  # noqa: E402

FREELANCERS_CAT = 1575319788245229618
SMP_MARKET_CAT = 1575311074549567719

SKILL_TAGS = [
    ("art", "🎨"), ("plugins", "🔌"), ("skripts", "⌨️"),
    ("thumbnails", "🖼️"), ("models", "📐"), ("datapacks", "📦"),
    ("web development", "🌐"),
]

GUIDELINES = (
    "ONE post per freelancer — extra posts get deleted.\n"
    "You MUST pick the tag matching your service.\n"
    "Include: what you do, portfolio/examples, prices, turnaround time.\n"
    "Buyers press 'Hire this freelancer' to open an order with you."
)


async def main():
    client = discord.Client(intents=discord.Intents.default())
    cfg = load_config()

    @client.event
    async def on_ready():
        guild = client.get_guild(cfg["guild_id"])
        everyone = guild.default_role
        staff = guild.get_role(cfg["staff_role_id"])
        fl = guild.get_role(cfg["freelancer_role_id"])
        cat = guild.get_channel(FREELANCERS_CAT)

        forum = await guild.create_forum(
            name="🛍️・services",
            category=cat,
            topic=GUIDELINES,
            available_tags=[
                discord.ForumTag(name=n, emoji=e) for n, e in SKILL_TAGS
            ],
            overwrites={
                everyone: discord.PermissionOverwrite(
                    view_channel=True, send_messages=False,
                    create_public_threads=False,
                    send_messages_in_threads=True,
                ),
                fl: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    create_public_threads=True,
                    send_messages_in_threads=True,
                ),
                staff: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    manage_messages=True, manage_threads=True,
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    manage_channels=True, manage_threads=True,
                ),
            },
        )
        print("services forum:", forum.id, flush=True)
        try:
            await forum.edit(require_tag=True)
            print("require_tag set", flush=True)
        except Exception as e:
            print("require_tag failed:", e, flush=True)

        orders = await guild.create_category(
            "Freelance Orders",
            overwrites={
                everyone: discord.PermissionOverwrite(view_channel=False),
                staff: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    manage_channels=True,
                ),
            },
        )
        print("orders category:", orders.id, flush=True)

        market = guild.get_channel(SMP_MARKET_CAT)
        reviews = await guild.create_text_channel(
            "⭐・reviews",
            category=market,
            topic="Customer reviews for our freelancers.",
            overwrites={
                everyone: discord.PermissionOverwrite(
                    view_channel=True, send_messages=False
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True
                ),
            },
        )
        print("reviews channel:", reviews.id, flush=True)

        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
