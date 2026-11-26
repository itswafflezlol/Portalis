"""One-time: build the SMP Market category + channels (all locked)."""
import asyncio
import sys
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TOKEN, load_config  # noqa: E402

FREELANCER_TAGS = [
    ("art", "🎨"), ("plugins", "🔌"), ("skripts", "⌨️"),
    ("thumbnails", "🖼️"), ("models", "📐"), ("datapacks", "📦"),
    ("web development", "🌐"),
]


async def main():
    client = discord.Client(intents=discord.Intents.default())
    cfg = load_config()

    @client.event
    async def on_ready():
        guild = client.get_guild(cfg["guild_id"])
        lock = {
            guild.default_role: discord.PermissionOverwrite(
                send_messages=False,
                send_messages_in_threads=False,
                create_public_threads=False,
                create_private_threads=False,
            )
        }

        cat = await guild.create_category("SMP Market")
        print("category:", cat.id)

        fl = await guild.create_forum(
            name="💼・freelancers", category=cat, overwrites=lock,
            available_tags=[
                discord.ForumTag(name=n, emoji=e)
                for n, e in FREELANCER_TAGS
            ],
        )
        print("freelancers forum:", fl.id)

        orders = await guild.create_text_channel(
            name="🛒・orders", category=cat, overwrites=lock,
        )
        print("orders:", orders.id)

        portfolio = await guild.create_forum(
            name="🖼️・portfolio", category=cat, overwrites=lock,
        )
        print("portfolio forum:", portfolio.id)

        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
