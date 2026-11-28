"""One-time: replace plain-text freelance rules with a styled card."""
import asyncio
import sys
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from branding import RED  # noqa: E402
from config import TOKEN, load_config  # noqa: E402

RULES_CHANNEL = 1575319789583208578  # 📜・freelance-rules


def rules_view() -> discord.ui.LayoutView:
    ui = discord.ui
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(ui.Container(
        ui.TextDisplay(
            "## 📜 Freelancer Rules\n"
            "Read these before taking a job."
        ),
        ui.Separator(),
        ui.TextDisplay(
            "### 💳 Payment methods\n"
            "Payments go **directly** between buyer and freelancer — "
            "SMP Portal does **not** handle payments.\n"
            "You **must** be able to receive **Ko-fi**, **PayPal**, or "
            "another legit payment method — nothing sketchy.\n"
            "If you can't get any of those, we can't offer your "
            "services until you do."
        ),
        ui.Separator(),
        ui.TextDisplay(
            "### ✅ The rules\n"
            "• Payments are **your** deal with the buyer — SMP Portal "
            "just connects you two and isn't responsible for "
            "disputes.\n"
            "• Deliver what you promise. If you can't finish a job, "
            "tell the client and staff right away.\n"
            "• No scamming, no stolen work, no selling other people's "
            "stuff as yours.\n"
            "• Keep client work private until it's delivered — don't "
            "leak WIPs in public channels.\n"
            "• Deadlines matter. If you'll be late, say so *before* "
            "the deadline, not after.\n"
            "• Be respectful to clients — rude freelancers get warned, "
            "then removed.\n"
            "• Inactivity = role removal. If you're not taking jobs, "
            "the spot goes to someone who will."
        ),
        ui.Separator(),
        ui.TextDisplay(
            "### 🛍️ Your service ad\n"
            "Set up your profile in the **💼・setup** channel — your ad "
            "gets posted to **💼・freelancers** where buyers can "
            "find you.\n"
            "**One ad per freelancer** — re-run setup anytime to "
            "update it. Include what you do, portfolio, prices and "
            "turnaround time. Buyers press **Hire this freelancer** "
            "to open an order with you."
        ),
        ui.Separator(),
        ui.TextDisplay(
            "### 🧾 Orders\n"
            "• Buyer explains the job + sends reference images\n"
            "• You **accept** or **decline** the order\n"
            "• **Buyer always pays first** — press Continue once "
            "the payment lands, then the commission starts\n"
            "• Finish it → `/deliver` with the file attached — the "
            "buyer gets it in DMs and rates you 1–5 ⭐\n"
            "• Reviews post to ⭐・reviews and your portfolio thread\n\n"
            "**Commands in your order tickets**\n"
            "`/deliver` — send the finished file · `/closeticket` — "
            "close it · `/closerequest` — ask the buyer to close"
        ),
        ui.Separator(),
        ui.TextDisplay(
            "### ⚠️ Consequences\n"
            "Breaking the rules = warning, then role removal. "
            "Serious stuff (scamming, stealing) = instant removal + ban.\n\n"
            "-# Questions? Ask in 💬・freelancer-chat or open a ticket."
        ),
        accent_color=RED,
    ))
    return view


async def main():
    client = discord.Client(intents=discord.Intents.default())
    cfg = load_config()

    @client.event
    async def on_ready():
        guild = client.get_guild(cfg["guild_id"])
        ch = guild.get_channel(RULES_CHANNEL)

        async for msg in ch.history(limit=10):
            if msg.author == client.user:
                await msg.delete()
                print("deleted old rules post", flush=True)

        await ch.send(view=rules_view())
        print("posted rules card", flush=True)
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
