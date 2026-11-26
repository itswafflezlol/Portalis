"""One-time: build the Freelancers category (top position, staff+freelancers only)."""
import asyncio
import sys
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TOKEN, load_config  # noqa: E402

RULES = """# 📜 Freelancer Rules

**💰 Payment split**
• **85%** of every payment goes straight to **you**
• **15%** goes to SMP Portal

**The rules**
• All payments go through staff as middleman — **never** take direct payment. Freelancers caught going around us lose the role.
• Deliver what you promise. If you can't finish a job, tell the client and staff right away.
• No scamming, no stolen work, no selling other people's stuff as yours.
• Keep everything you make for clients private until it's delivered — don't leak WIPs in public channels.
• Deadlines matter. If you'll be late, say so *before* the deadline, not after.
• Be respectful to clients — rude freelancers get warned, then removed.
• Inactivity = role removal. If you're not taking jobs, the spot goes to someone who will.

Breaking the rules = warning, then role removal. Serious stuff (scamming, stealing) = instant removal + ban.

-# Questions? Ask in 💬・freelancer-chat or open a ticket.
"""


async def main():
    client = discord.Client(intents=discord.Intents.default())
    cfg = load_config()

    @client.event
    async def on_ready():
        guild = client.get_guild(cfg["guild_id"])
        everyone = guild.default_role
        staff = guild.get_role(cfg["staff_role_id"])
        fl = guild.get_role(cfg["freelancer_role_id"])

        overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            fl: discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            ),
            staff: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
        }

        cat = await guild.create_category(
            "Freelancers", overwrites=overwrites, position=0
        )
        print("category:", cat.id, flush=True)

        rules = await guild.create_text_channel(
            "📜・freelance-rules",
            category=cat,
            overwrites={
                fl: discord.PermissionOverwrite(
                    view_channel=True, send_messages=False
                )
            },
        )
        print("rules:", rules.id, flush=True)
        await rules.send(RULES)
        print("rules posted", flush=True)

        chat = await guild.create_text_channel(
            "💬・freelancer-chat", category=cat
        )
        print("chat:", chat.id, flush=True)

        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
