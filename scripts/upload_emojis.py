"""Upload assets/emojis/*.png to the guild as portal_<name> emoji."""
import asyncio
import sys
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TOKEN, load_config  # noqa: E402

EMOJI_DIR = Path(__file__).resolve().parent.parent / "assets" / "emojis"


async def main():
    client = discord.Client(intents=discord.Intents.default())
    cfg = load_config()

    @client.event
    async def on_ready():
        guild = client.get_guild(cfg["guild_id"])
        if guild is None:
            print("Bot isn't in the configured guild")
            await client.close()
            return
        for png in sorted(EMOJI_DIR.glob("[!_]*.png")):
            name = f"portal_{png.stem}"
            if discord.utils.get(guild.emojis, name=name):
                print("skip (exists)", name)
                continue
            try:
                e = await guild.create_custom_emoji(
                    name=name, image=png.read_bytes()
                )
                print("uploaded", e)
            except discord.HTTPException as ex:
                print("FAIL", name, ex.status, ex.text)
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
