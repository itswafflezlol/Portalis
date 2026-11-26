"""Freelance marketplace: service posts, hire button, order tickets,
delivery + reviews."""
import io
import re

import discord
from discord import app_commands
from discord.ext import commands

from branding import RED
from cogs.tickets import can_staff, close_ticket

HIRE_FORUM_ID = 1575566376138055780   # 🛍️・services
ORDERS_CATEGORY_ID = 1575566377111003186  # Freelance Orders
REVIEWS_CHANNEL_ID = 1575566378247790714  # ⭐・reviews
PORTFOLIO_FORUM_ID = 1575311077585977424  # 🖼️・portfolio


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9\-_]", "", name.lower().replace(" ", "-")) or "user"


class HireView(discord.ui.LayoutView):
    """Posted inside every service thread — opens an order ticket."""

    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui
        btn = ui.Button(
            label="Hire this freelancer", emoji="🛒",
            style=discord.ButtonStyle.danger,
            custom_id="portal:fl:hire",
        )
        btn.callback = self._hire
        self.add_item(ui.Container(
            ui.TextDisplay(
                "## 🛒 Like what you see?\n"
                "Press the button to open a private order with this "
                "freelancer."
            ),
            ui.ActionRow(btn),
            accent_color=RED,
        ))

    async def _hire(self, interaction: discord.Interaction):
        bot, guild, buyer = (
            interaction.client, interaction.guild, interaction.user
        )
        thread = interaction.channel
        if not isinstance(thread, discord.Thread) \
                or thread.parent_id != HIRE_FORUM_ID:
            await interaction.response.send_message(
                "Use this inside a service post.", ephemeral=True
            )
            return
        fl = guild.get_member(thread.owner_id)
        if fl is None or fl.get_role(bot.cfg["freelancer_role_id"]) is None:
            await interaction.response.send_message(
                "This freelancer is no longer available.", ephemeral=True
            )
            return
        if fl.id == buyer.id:
            await interaction.response.send_message(
                "You can't hire yourself.", ephemeral=True
            )
            return
        for cid, t in bot.store.data["tickets"].items():
            if t["owner"] == buyer.id and t["type"] == "freelance":
                await interaction.response.send_message(
                    f"You already have an open order: <#{cid}>",
                    ephemeral=True,
                )
                return

        await interaction.response.defer(ephemeral=True)
        num = await bot.store.new_id()
        everyone = guild.default_role
        staff = guild.get_role(bot.cfg["staff_role_id"])
        overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            buyer: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, attach_files=True,
            ),
            fl: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, attach_files=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True,
            ),
        }
        if staff:
            overwrites[staff] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True,
            )

        channel = await guild.create_text_channel(
            name=f"order-{num}-{_slug(fl.display_name)}",
            category=guild.get_channel(ORDERS_CATEGORY_ID),
            overwrites=overwrites,
        )
        bot.store.data["tickets"][str(channel.id)] = {
            "owner": buyer.id, "type": "freelance", "claimed_by": None,
            "freelancer": fl.id, "order": num, "state": "pending",
        }
        await bot.store.save()

        await channel.send(
            view=OrderView(num, buyer.mention, fl.mention),
            allowed_mentions=discord.AllowedMentions(users=[buyer, fl]),
        )
        await interaction.followup.send(
            f"Order opened: {channel.mention}", ephemeral=True
        )


class OrderView(discord.ui.LayoutView):
    """First card in an order ticket — freelancer accepts or declines."""

    def __init__(self, num: int = 0, buyer: str = "", fl: str = "",
                 done: str = ""):
        super().__init__(timeout=None)
        ui = discord.ui

        accept = ui.Button(
            label="Accept order", emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id="portal:fl:accept", disabled=bool(done),
        )
        accept.callback = self._accept
        decline = ui.Button(
            label="Decline", emoji="❌",
            style=discord.ButtonStyle.secondary,
            custom_id="portal:fl:decline", disabled=bool(done),
        )
        decline.callback = self._decline

        text = (
            f"## 🧾 Order #{num}\n{fl} {buyer}\n\n"
            f"**{buyer}** — explain what you want **thoroughly** and "
            "attach **reference images** so the freelancer knows "
            "exactly what to make.\n\n"
            f"**{fl}** — review the request, then accept or decline."
        )
        if done == "declined":
            text = f"## 🧾 Order #{num}\n❌ Declined by the freelancer."
        self.add_item(ui.Container(
            ui.TextDisplay(text),
            ui.ActionRow(accept, decline),
            accent_color=RED,
        ))

    def _guard(self, interaction: discord.Interaction):
        t = interaction.client.store.data["tickets"].get(
            str(interaction.channel.id)
        )
        if t is None or t.get("type") != "freelance" \
                or t.get("state") != "pending" \
                or interaction.user.id != t.get("freelancer"):
            return None
        return t

    async def _accept(self, interaction: discord.Interaction):
        t = self._guard(interaction)
        if t is None:
            await interaction.response.send_message(
                "Only the freelancer can accept a pending order.",
                ephemeral=True,
            )
            return
        t["state"] = "awaiting_payment"
        await interaction.client.store.save()
        buyer = interaction.guild.get_member(t["owner"])
        await interaction.response.edit_message(
            view=PaidView(t["order"], fl=interaction.user.mention,
                          buyer=buyer.mention if buyer else "the buyer")
        )

    async def _decline(self, interaction: discord.Interaction):
        t = self._guard(interaction)
        if t is None:
            await interaction.response.send_message(
                "Only the freelancer can decline a pending order.",
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            view=OrderView(t["order"], done="declined")
        )
        await interaction.channel.send(
            "This order was declined — closing the ticket."
        )
        await close_ticket(interaction)


class PaidView(discord.ui.LayoutView):
    """Payment gate — buyer pays first, freelancer presses Continue."""

    def __init__(self, num: int = 0, fl: str = "", buyer: str = "",
                 done: bool = False):
        super().__init__(timeout=None)
        ui = discord.ui
        cont = ui.Button(
            label="Continue — payment received", emoji="💳",
            style=discord.ButtonStyle.success,
            custom_id="portal:fl:continue", disabled=done,
        )
        cont.callback = self._continue
        text = (
            f"## 💳 Payment first\n"
            f"**{buyer}** — pay the agreed price now. "
            "**Work doesn't start until payment is sent.**\n\n"
            f"**{fl}** — press Continue once the payment lands."
        )
        if done:
            text = "## 💳 Payment confirmed — commission started."
        self.add_item(ui.Container(
            ui.TextDisplay(text),
            ui.ActionRow(cont),
            accent_color=RED,
        ))

    async def _continue(self, interaction: discord.Interaction):
        bot = interaction.client
        t = bot.store.data["tickets"].get(str(interaction.channel.id))
        if t is None or t.get("type") != "freelance" \
                or t.get("state") != "awaiting_payment" \
                or interaction.user.id != t.get("freelancer"):
            await interaction.response.send_message(
                "Only the freelancer can confirm payment.",
                ephemeral=True,
            )
            return
        t["state"] = "active"
        await bot.store.save()
        await interaction.response.edit_message(
            view=PaidView(t["order"], done=True)
        )
        buyer = interaction.guild.get_member(t["owner"])
        await interaction.channel.send(
            f"🛠️ **Commission #{t['order']} started!**\n"
            f"{buyer.mention if buyer else 'The buyer'} — your "
            "freelancer is on it.\n"
            "Freelancer — deliver the finished work with "
            "`/deliver` (attach the file).",
            allowed_mentions=discord.AllowedMentions(
                users=[buyer] if buyer else []
            ),
        )


class ReviewModal(discord.ui.Modal, title="Leave a review"):
    note = discord.ui.TextInput(
        label="Your review (optional)",
        placeholder="How was the work? Fast? Good communication?",
        style=discord.TextStyle.paragraph,
        required=False, max_length=400,
    )

    def __init__(self, stars: int):
        super().__init__()
        self.stars = stars

    async def on_submit(self, interaction: discord.Interaction):
        bot = interaction.client
        pending = bot.store.data.get("pending_reviews", {}).pop(
            str(interaction.user.id), None
        )
        if pending is None:
            await interaction.response.send_message(
                "Nothing to review.", ephemeral=True
            )
            return
        await bot.store.save()

        guild = bot.get_guild(bot.cfg["guild_id"])
        fl = guild.get_member(pending["freelancer"]) if guild else None
        stars = "⭐" * self.stars + "☆" * (5 - self.stars)
        note = self.note.value.strip() if self.note.value else ""

        ui = discord.ui
        card = discord.ui.LayoutView(timeout=None)
        card.add_item(ui.Container(
            ui.TextDisplay(
                f"## {stars}\n"
                f"**{self.stars}/5** for **{fl.display_name if fl else 'a freelancer'}**\n"
                + (f"> {note}\n\n" if note else "\n")
                + f"-# Order #{pending['order']} · by "
                f"{interaction.user.display_name}"
            ),
            accent_color=RED,
        ))

        reviews = guild.get_channel(REVIEWS_CHANNEL_ID) if guild else None
        if reviews is not None:
            await reviews.send(view=card)

        # also push into the freelancer's portfolio review thread
        if guild is not None:
            tid = await _review_thread(bot, guild, fl)
            if tid:
                thread = guild.get_channel(tid)
                if thread is not None:
                    await thread.send(view=card)

        await interaction.response.send_message(
            "Thanks for the review! ⭐", ephemeral=True
        )


async def _review_thread(bot, guild, fl) -> int:
    """Find-or-create the freelancer's review thread in 🖼️・portfolio."""
    if fl is None:
        return 0
    threads = bot.store.data.setdefault("fl_review_threads", {})
    tid = threads.get(str(fl.id), 0)
    if tid and guild.get_channel(tid) is not None:
        return tid
    forum = guild.get_channel(PORTFOLIO_FORUM_ID)
    if forum is None:
        return 0
    thread = await forum.create_thread(
        name=f"⭐ {fl.display_name} — reviews",
        content="Reviews from this freelancer's orders.",
    )
    threads[str(fl.id)] = thread.id
    await bot.store.save()
    return thread.id


class StarsView(discord.ui.View):
    """1–5 star buttons sent with the delivered file."""

    def __init__(self):
        super().__init__(timeout=None)
        for n in range(1, 6):
            btn = discord.ui.Button(
                label=f"{n}⭐", style=discord.ButtonStyle.secondary,
                custom_id=f"portal:fl:star:{n}",
            )
            btn.callback = self._make(n)
            self.add_item(btn)

    def _make(self, n: int):
        async def cb(interaction: discord.Interaction):
            await interaction.response.send_modal(ReviewModal(n))
        return cb


class Freelance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if thread.parent_id != HIRE_FORUM_ID:
            return
        guild = thread.guild
        fl_role = guild.get_role(self.bot.cfg["freelancer_role_id"])
        member = guild.get_member(thread.owner_id)

        if member is None or (fl_role and fl_role not in member.roles):
            await thread.delete()
            return
        if not thread.applied_tags:
            await thread.delete()
            try:
                await member.send(
                    "Your service post was removed — you must pick a "
                    "tag matching your service."
                )
            except discord.HTTPException:
                pass
            return
        dupe = next(
            (t for t in thread.parent.threads
             if t.id != thread.id and t.owner_id == thread.owner_id),
            None,
        )
        if dupe is not None:
            await thread.delete()
            try:
                await member.send(
                    f"Only one service post allowed — yours is here: "
                    f"{dupe.jump_url}"
                )
            except discord.HTTPException:
                pass
            return

        await thread.send(view=HireView())

    @app_commands.command(
        name="deliver",
        description="Deliver finished work to the buyer (attach the file)",
    )
    @app_commands.describe(file="The finished work to deliver")
    async def deliver(self, interaction: discord.Interaction,
                      file: discord.Attachment):
        t = self.bot.store.data["tickets"].get(str(interaction.channel.id))
        if t is None or t.get("type") != "freelance" \
                or interaction.user.id != t.get("freelancer"):
            await interaction.response.send_message(
                "Only the freelancer can deliver in their order ticket.",
                ephemeral=True,
            )
            return

        buyer = interaction.guild.get_member(t["owner"])
        if buyer is None:
            await interaction.response.send_message(
                "The buyer left the server.", ephemeral=True
            )
            return
        try:
            data = io.BytesIO(await file.read())
        except discord.HTTPException:
            await interaction.response.send_message(
                "Couldn't read that file — too big?", ephemeral=True
            )
            return

        self.bot.store.data.setdefault("pending_reviews", {})[
            str(buyer.id)
        ] = {"freelancer": interaction.user.id, "order": t["order"]}
        await self.bot.store.save()

        try:
            await buyer.send(
                f"📦 **Order #{t['order']} delivered** by "
                f"**{interaction.user.display_name}**!\n"
                "Here's your file — and please rate the work:",
                file=discord.File(data, filename=file.filename),
                view=StarsView(),
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Their DMs are closed — can't deliver.", ephemeral=True
            )
            return
        t["state"] = "delivered"
        await self.bot.store.save()
        await interaction.response.send_message(
            f"📦 Delivered to {buyer.mention} — they got a review "
            "request too.",
            allowed_mentions=discord.AllowedMentions(users=[buyer]),
        )


async def setup(bot):
    await bot.add_cog(Freelance(bot))
