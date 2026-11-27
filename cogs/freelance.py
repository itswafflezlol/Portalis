"""Freelance marketplace: profile setup, service ads, order tickets,
delivery + reviews."""
import asyncio
import io
import re

import discord
from discord import app_commands
from discord.ext import commands

from branding import RED, panel_file
from cogs.tickets import can_staff, close_ticket

SETUP_CHANNEL_ID = 1575661190502158430    # set-up (freelancers only)
SERVICE_FORUM_ID = 1575311075778240592    # 💼・freelancers (public)
ORDERS_CATEGORY_ID = 1575566377111003186  # Freelance Orders
REVIEWS_CHANNEL_ID = 1575566378247790714  # ⭐・reviews

SKILL_TAGS = [
    "art", "plugins", "skripts", "thumbnails",
    "models", "datapacks", "web development",
]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9\-_]", "", name.lower().replace(" ", "-")) or "user"


def _fl_posts(bot) -> dict:
    return bot.store.data.setdefault("fl_posts", {})


def _owner_of(bot, thread_id: int) -> int:
    for uid, p in _fl_posts(bot).items():
        if p.get("thread") == thread_id:
            return int(uid)
    return 0


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
                or thread.parent_id != SERVICE_FORUM_ID:
            await interaction.response.send_message(
                "Use this inside a service post.", ephemeral=True
            )
            return
        fl_id = _owner_of(bot, thread.id)
        fl = guild.get_member(fl_id) if fl_id else None
        if fl is None or fl.get_role(bot.cfg["freelancer_role_id"]) is None:
            await interaction.response.send_message(
                "This freelancer is no longer available.", ephemeral=True
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


class ProfileModal(discord.ui.Modal, title="Your service ad"):
    ad = discord.ui.TextInput(
        label="Your ad — write it how you want",
        placeholder="What you do, portfolio links, prices, "
                    "turnaround — it's your ad.",
        style=discord.TextStyle.paragraph, required=True,
        max_length=1800,
    )

    def __init__(self, tag: str):
        super().__init__()
        self.tag = tag

    async def on_submit(self, interaction: discord.Interaction):
        bot = interaction.client
        if interaction.user.get_role(bot.cfg["freelancer_role_id"]) is None:
            await interaction.response.send_message(
                "Freelancers only.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Got it — **send your images now** (up to 4 in one "
            "message), or type `skip`. You have 60 seconds.",
            ephemeral=True,
        )

        files = []
        try:
            msg = await bot.wait_for(
                "message",
                check=lambda m: m.author.id == interaction.user.id
                and m.channel.id == SETUP_CHANNEL_ID,
                timeout=60,
            )
            if msg.content.strip().lower() != "skip":
                files = [
                    discord.File(
                        io.BytesIO(await a.read()), filename=a.filename
                    )
                    for a in msg.attachments[:4]
                ]
            try:
                await msg.delete()  # keep set-up clean
            except discord.HTTPException:
                pass
        except asyncio.TimeoutError:
            pass

        name = interaction.user.display_name
        ad = (
            f"# 🛍️ {name} — {self.tag.title()}\n"
            f"{self.ad.value}\n\n"
            "-# Order via the button below — payments go "
            "through SMP Portal."
        )

        forum = interaction.guild.get_channel(SERVICE_FORUM_ID)
        if forum is None:
            await interaction.followup.send(
                "Services forum not found.", ephemeral=True
            )
            return
        tag_obj = next(
            (t for t in forum.available_tags if t.name == self.tag), None
        )
        posts = _fl_posts(bot)
        me = posts.setdefault(str(interaction.user.id), {})

        thread = None
        tid = me.get("thread")
        if tid:
            thread = interaction.guild.get_channel(tid)
        if thread is not None:
            try:
                await thread.edit(
                    name=f"{name} — {self.tag.title()}",
                    applied_tags=[tag_obj] if tag_obj else [],
                )
                starter = await thread.fetch_message(thread.id)
                await starter.edit(content=ad)
                if files:
                    await thread.send(files=files)
            except discord.HTTPException:
                thread = None
        if thread is None:
            thread, _msg = await forum.create_thread(
                name=f"{name} — {self.tag.title()}",
                content=ad,
                applied_tags=[tag_obj] if tag_obj else [],
            )
            me["thread"] = thread.id
            if files:
                await thread.send(files=files)
            await thread.send(view=HireView())
        me["tag"] = self.tag
        await bot.store.save()
        await interaction.followup.send(
            f"Your ad is live: {thread.jump_url}", ephemeral=True
        )


class TagSelect(discord.ui.View):
    """Ephemeral: pick the skill tag before the profile form."""

    def __init__(self):
        super().__init__(timeout=180)
        sel = discord.ui.Select(
            placeholder="What do you do? (matches the forum tags)",
            options=[discord.SelectOption(label=t.title(), value=t)
                     for t in SKILL_TAGS],
        )
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ProfileModal(interaction.data["values"][0])
        )


class SetUpView(discord.ui.LayoutView):
    """Posted in set-up — freelancers press to create/edit their ad."""

    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui
        btn = ui.Button(
            label="Set up my profile", emoji="🛍️",
            style=discord.ButtonStyle.danger,
            custom_id="portal:fl:setup",
        )
        btn.callback = self._setup
        self.add_item(ui.Container(
            ui.TextDisplay(
                "## 🛍️ Set up your freelancer ad\n"
                "Pick a tag, write your ad however you want, "
                "attach your images — it gets posted to "
                "**💼・freelancers** where buyers can hire you.\n\n"
                "-# One ad per freelancer — re-run this anytime "
                "to update it."
            ),
            ui.ActionRow(btn),
            accent_color=RED,
        ))

    async def _setup(self, interaction: discord.Interaction):
        if interaction.user.get_role(
            interaction.client.cfg["freelancer_role_id"]
        ) is None:
            await interaction.response.send_message(
                "Freelancers only.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "Pick your tag first:", view=TagSelect(), ephemeral=True
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

        # push the review into the freelancer's own ad thread
        if guild is not None:
            tid = _fl_posts(bot).get(
                str(pending["freelancer"]), {}
            ).get("thread")
            thread = guild.get_channel(tid) if tid else None
            if thread is not None:
                await thread.send(view=card)

        await interaction.response.send_message(
            "Thanks for the review! ⭐", ephemeral=True
        )


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
