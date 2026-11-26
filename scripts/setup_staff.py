"""One-time: restyle staff channels to emoji・name and add missing ones."""
import asyncio
import sys
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TOKEN, load_config  # noqa: E402

STAFF_CAT = 1575244982305165362

RENAMES = {
    1575245391371436102: "📄・transcripts",
    1575246968748253295: "📋・app-reviews",
    1575247018027253882: "🤝・partner-reviews",
    1575295051305721966: "💬・chat",
    1575295076366688366: "🐛・bugs",
}

NEW = [
    ("text", "💰・payments"),
    ("text", "🗒️・staff-notes"),
    ("text", "✅・staff-todo"),
    ("text", "📚・guides"),
    ("voice", "🎙️・staff-meeting"),
]


async def main():
    client = discord.Client(intents=discord.Intents.default())
    cfg = load_config()

    @client.event
    async def on_ready():
        guild = client.get_guild(cfg["guild_id"])
        cat = guild.get_channel(STAFF_CAT)

        existing = {ch.name for ch in cat.channels}

        for cid, name in RENAMES.items():
            ch = guild.get_channel(cid)
            if ch is None:
                print("missing channel:", cid, flush=True)
                continue
            if ch.name == name:
                print("already:", name, flush=True)
                continue
            await ch.edit(name=name)
            print("renamed:", name, flush=True)

        for kind, name in NEW:
            if name in existing:
                print("exists:", name, flush=True)
                continue
            if kind == "voice":
                ch = await guild.create_voice_channel(name, category=cat)
            else:
                ch = await guild.create_text_channel(name, category=cat)
            print("created:", name, ch.id, flush=True)

        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
