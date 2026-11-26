"""One-time: post the freelancer profile setup card in set-up."""
import asyncio
import sys
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cogs.freelance import SETUP_CHANNEL_ID, SetUpView  # noqa: E402
from config import TOKEN, load_config  # noqa: E402


async def main():
    client = discord.Client(intents=discord.Intents.default())
    cfg = load_config()

    @client.event
    async def on_ready():
        guild = client.get_guild(cfg["guild_id"])
        ch = guild.get_channel(SETUP_CHANNEL_ID)
        async for msg in ch.history(limit=10):
            if msg.author == client.user:
                await msg.delete()
                print("deleted old card", flush=True)
        await ch.send(view=SetUpView())
        print("posted setup card", flush=True)
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
