import io
import re
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from branding import RED, panel_file

TICKET_TYPES = {
    "support": ("🛠️ Support", "Problems or questions for the staff team."),
    "partnership": ("🤝 Partnership", "Partner or advertise with SMP Portal."),
}

CATEGORIES = {
    "public": ("Public", "🌍"),
    "bedrock": ("Bedrock", "🪨"),
    "smps": ("SMP", "⚔️"),
    "other": ("Other", "📦"),
}

PING_RE = re.compile(r"@everyone|@here|<@!?\d+>|<@&\d+>")

INVITE_RE = re.compile(
    r"(?:discord\.gg|discord\.com/invite|discordapp\.com/invite)/[\w-]+", re.I
)

BLOCK_RE = re.compile(
    r"\b(fuck|shit|bitch|bastard|cunt|nigger|nigga|faggot|retard|whore|slut"
    r"|porn|hentai|nudes?|nsfw|onlyfans|xxx|sex|gore|18\+)\b", re.I
)


def can_review(member: discord.Member, cfg: dict) -> bool:
    return is_staff(member, cfg) or any(
        r.id == cfg["partnership_manager_role_id"] for r in member.roles
    )


def is_staff(member: discord.Member, cfg: dict) -> bool:
    return member.guild_permissions.manage_guild or any(
        r.id == cfg["staff_role_id"] for r in member.roles
    )


class TicketPanelView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui

        support = ui.Button(
            label="Support Ticket", style=discord.ButtonStyle.danger,
            emoji="🛠️", custom_id="portal:ticket:support",
        )
        support.callback = lambda i: open_ticket(i, "support")
        partner = ui.Button(
            label="Partnership Ticket", style=discord.ButtonStyle.danger,
            emoji="🤝", custom_id="portal:ticket:partnership",
        )
        partner.callback = lambda i: open_ticket(i, "partnership")

        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem(
                "attachment://tickets.webp"
            )),
            ui.Separator(),
            ui.TextDisplay(
                "## 🛠️ Support\n"
                "Problems or questions for the staff team — open a ticket "
                "and we'll help.\n"
                "-# • Only 1 ticket open at a time"
            ),
            ui.ActionRow(support),
            ui.Separator(),
            ui.TextDisplay(
                "## 🤝 Partnership\n"
                "Partner with SMP Portal or advertise your server — "
                "terms, paid ads, and proof."
            ),
            ui.ActionRow(partner),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))


async def open_ticket(interaction: discord.Interaction, kind: str):
    bot = interaction.client
    cfg, store, guild, user = bot.cfg, bot.store, interaction.guild, interaction.user

    stale = [
        cid for cid in store.data["tickets"] if guild.get_channel(int(cid)) is None
    ]
    for cid in stale:
        del store.data["tickets"][cid]
    if stale:
        await store.save()

    for cid, t in store.data["tickets"].items():
        if t["owner"] == user.id:
            await interaction.response.send_message(
                f"You already have a ticket open: <#{cid}>", ephemeral=True
            )
            return

    if kind == "partnership" and user.id not in cfg["cooldown_exempt"]:
        until = store.data.get("partner_cooldowns", {}).get(str(user.id))
        if until:
            exp = datetime.fromisoformat(until)
            if exp > datetime.now(timezone.utc):
                await interaction.response.send_message(
                    "You've already partnered recently — you can partner "
                    f"again <t:{int(exp.timestamp())}:R>.", ephemeral=True,
                )
                return

    category = guild.get_channel(cfg["ticket_category_id"])
    if category is None:
        await interaction.response.send_message(
            "Tickets aren't set up yet — set `ticket_category_id` in config.json.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    staff = guild.get_role(cfg["staff_role_id"])
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            attach_files=True, embed_links=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_channels=True,
        ),
    }
    if staff:
        overwrites[staff] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
        )
    if kind == "partnership":
        pm = guild.get_role(cfg["partnership_manager_role_id"])
        if pm:
            overwrites[pm] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True,
            )

    channel = await guild.create_text_channel(
        name=f"{kind}-{user.name}", category=category, overwrites=overwrites,
    )
    store.data["tickets"][str(channel.id)] = {
        "owner": user.id, "type": kind, "claimed_by": None,
    }
    await store.save()

    label, blurb = TICKET_TYPES[kind]
    mention = f"{user.mention}" + (f" {staff.mention}" if staff else "")
    await channel.send(
        view=TicketChannelView(kind, mention),
        files=[panel_file(f"{kind}.webp")],
        allowed_mentions=discord.AllowedMentions(
            users=[user], roles=[staff] if staff else []
        ),
    )
    if kind == "partnership":
        await channel.send(view=PartnershipQuestionsView())
    await interaction.followup.send(
        f"Ticket opened: {channel.mention}", ephemeral=True
    )


class TicketChannelView(discord.ui.LayoutView):
    """Branded welcome message inside a ticket channel, with claim/close
    controls inside the container."""

    def __init__(self, kind: str = "support", opener: str = ""):
        super().__init__(timeout=None)
        ui = discord.ui
        label, blurb = TICKET_TYPES.get(kind, TICKET_TYPES["support"])

        self.claim_btn = ui.Button(
            label="Claim", style=discord.ButtonStyle.danger, emoji="🚩",
            custom_id="portal:ticket_claim",
        )
        self.claim_btn.callback = self._claim
        close_btn = ui.Button(
            label="Close", style=discord.ButtonStyle.secondary, emoji="🔒",
            custom_id="portal:ticket_close",
        )
        close_btn.callback = self._close

        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem(
                f"attachment://{kind}.webp"
            )),
            ui.Separator(),
            ui.TextDisplay(
                f"## {label} Ticket\n"
                f"Hey {opener} — {blurb}\n\n"
                "Describe your request below and the team will be with "
                "you shortly.\n"
                "-# • One ticket open at a time · Staff can claim · "
                "anyone here can close"
            ),
            ui.ActionRow(self.claim_btn, close_btn),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))

    async def _claim(self, interaction: discord.Interaction):
        bot = interaction.client
        if not is_staff(interaction.user, bot.cfg):
            await interaction.response.send_message(
                "Only staff can claim tickets.", ephemeral=True
            )
            return
        ticket = bot.store.data["tickets"].get(str(interaction.channel.id))
        if ticket is None:
            await interaction.response.send_message(
                "This isn't a ticket channel.", ephemeral=True
            )
            return
        ticket["claimed_by"] = interaction.user.id
        await bot.store.save()
        self.claim_btn.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(
            f"🚩 {interaction.user.mention} claimed this ticket."
        )

    async def _close(self, interaction: discord.Interaction):
        bot = interaction.client
        ticket = bot.store.data["tickets"].get(str(interaction.channel.id))
        if ticket is None:
            await interaction.response.send_message(
                "This isn't a ticket channel.", ephemeral=True
            )
            return
        if interaction.user.id != ticket["owner"] and not is_staff(
            interaction.user, bot.cfg
        ):
            await interaction.response.send_message(
                "Only the ticket owner or staff can close this.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "Close this ticket?", view=ConfirmCloseView(), ephemeral=True
        )


class PartnershipQuestionsView(discord.ui.LayoutView):
    """Second message inside partnership tickets: pick a server type,
    then submit the ad."""

    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui

        sel = ui.Select(
            placeholder="What describes your server?",
            custom_id="portal:ticket:q1",
            options=[
                discord.SelectOption(label=label, value=key, emoji=emoji)
                for key, (label, emoji) in CATEGORIES.items()
            ],
        )
        sel.callback = self._pick_category
        ad_btn = ui.Button(
            label="Send your ad", style=discord.ButtonStyle.danger, emoji="📣",
            custom_id="portal:ticket:sendad",
        )
        ad_btn.callback = lambda i: i.response.send_modal(AdModal())

        self.add_item(ui.Container(
            ui.TextDisplay(
                "## 📋 Partnership Questions\n"
                "**1.** What describes your server? Pick one below.\n"
                "**2.** Press **Send your ad** and paste it — "
                "**no pings** or it won't be posted.\n"
                "-# Reply with your FINAL answer only — don't say \"Hi\" "
                "or \"Okay\"."
            ),
            ui.ActionRow(sel),
            ui.ActionRow(ad_btn),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))

    async def _pick_category(self, interaction: discord.Interaction):
        bot = interaction.client
        ticket = bot.store.data["tickets"].get(str(interaction.channel.id))
        if ticket is None or ticket["type"] != "partnership":
            await interaction.response.send_message(
                "This isn't a partnership ticket.", ephemeral=True
            )
            return
        if interaction.user.id != ticket["owner"]:
            await interaction.response.send_message(
                "Only the ticket owner answers this.", ephemeral=True
            )
            return
        select = interaction.data["values"][0]
        ticket["category"] = select
        await bot.store.save()
        label, emoji = CATEGORIES[select]
        await interaction.response.send_message(
            f"{emoji} Server type: **{label}** — now press **Send your ad** "
            "and paste your ad (no pings)."
        )


class AdModal(discord.ui.Modal, title="Your server ad"):
    server = discord.ui.TextInput(
        label="Server name", max_length=100,
    )
    ad = discord.ui.TextInput(
        label="Paste your ad — no pings, must include invite",
        style=discord.TextStyle.paragraph, max_length=4000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        bot = interaction.client
        text = self.ad.value

        if PING_RE.search(text):
            await interaction.response.send_message(
                "Your ad contains a ping — take out `@everyone`, `@here` "
                "and any user/role mentions, then press **Send your ad** "
                "again.", ephemeral=True,
            )
            return
        if not INVITE_RE.search(text):
            await interaction.response.send_message(
                "Your ad needs a Discord invite link "
                "(`discord.gg/...`) — add one and send it again.",
                ephemeral=True,
            )
            return
        if BLOCK_RE.search(text) or BLOCK_RE.search(self.server.value):
            await interaction.response.send_message(
                "Your ad contains language or content we don't allow "
                "(profanity / NSFW terms). Clean it up and send it again.",
                ephemeral=True,
            )
            return

        ticket = bot.store.data["tickets"].get(str(interaction.channel.id))
        if ticket is None or ticket["type"] != "partnership":
            await interaction.response.send_message(
                "This isn't a partnership ticket.", ephemeral=True
            )
            return
        if interaction.user.id != ticket["owner"]:
            await interaction.response.send_message(
                "Only the ticket owner sends the ad.", ephemeral=True
            )
            return
        if not ticket.get("category"):
            await interaction.response.send_message(
                "Pick your server type first (question 1).", ephemeral=True
            )
            return
        if ticket.get("pending_ad"):
            await interaction.response.send_message(
                "Your ad is already waiting for staff review.",
                ephemeral=True,
            )
            return

        pending = {"server": self.server.value, "text": text, "proof": None}
        ticket["pending_ad"] = pending
        await bot.store.save()

        await interaction.response.send_message(
            "Last step — **send a screenshot** of our ad posted in your "
            "server. Upload the image in this channel and staff will "
            "review everything."
        )


class AdReviewView(discord.ui.LayoutView):
    """Review card posted inside the partnership ticket."""

    def __init__(self, channel_id: int, server: str = "", ad: str = "",
                 proof: str = None, status: str = None, actor: str = "",
                 extra: str = ""):
        super().__init__(timeout=None)
        ui = discord.ui
        self.channel_id = channel_id

        ok = ui.Button(
            label="Confirm & Post", style=discord.ButtonStyle.success,
            emoji="✅", custom_id=f"portal:ad:{channel_id}:ok",
        )
        ok.callback = self._approve
        no = ui.Button(
            label="Deny", style=discord.ButtonStyle.danger, emoji="✖️",
            custom_id=f"portal:ad:{channel_id}:no",
        )
        no.callback = self._deny

        if status == "approved":
            ok.disabled = no.disabled = True
            header = f"## ✅ Ad posted — approved by {actor}\n**{server}**"
            body = f"{ad}\n-# {extra}"
        elif status == "denied":
            ok.disabled = no.disabled = True
            header = f"## ✖️ Ad denied by {actor}\n**{server}**"
            body = f"{ad}\n-# Reason: {extra}"
        else:
            header = "## 🔍 Ad pending review"
            body = (
                f"**Server:** {server}\n\n{ad}\n\n"
                "**Staff to-do**\n"
                "• Check out their Discord — make sure it's appropriate "
                "and follows guidelines\n"
                "• Check they posted our ad in their server "
                "(screenshot below)\n"
                "• Confirm or deny"
            )

        children = [ui.TextDisplay(f"{header}\n{body}")]
        if proof:
            children.append(ui.MediaGallery(
                discord.MediaGalleryItem(proof)
            ))
        children.append(ui.ActionRow(ok, no))
        self.add_item(ui.Container(*children, accent_color=RED))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not can_review(interaction.user, interaction.client.cfg):
            await interaction.response.send_message(
                "Staff / Partnership Manager only.", ephemeral=True
            )
            return False
        return True

    async def _approve(self, interaction: discord.Interaction):
        bot = interaction.client
        ticket = bot.store.data["tickets"].get(str(self.channel_id))
        pending = ticket and ticket.get("pending_ad")
        if pending is None:
            await interaction.response.send_message(
                "This ad was already handled.", ephemeral=True
            )
            return

        forum = interaction.guild.get_channel(
            bot.cfg["forum_channels"].get(ticket["category"], 0)
        )
        if forum is None:
            await interaction.response.send_message(
                "Missing forum channel in config.", ephemeral=True
            )
            return

        posted = await forum.create_thread(
            name=pending["server"], content=pending["text"]
        )
        thread = posted.thread
        await thread.edit(locked=True)
        ticket["posted_thread"] = thread.id
        del ticket["pending_ad"]
        bot.store.data.setdefault("partner_cooldowns", {})[
            str(ticket["owner"])
        ] = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        await bot.store.save()

        await interaction.response.edit_message(
            view=AdReviewView(
                self.channel_id, pending["server"], pending["text"],
                proof=pending.get("proof"),
                status="approved", actor=interaction.user.mention,
                extra=f"Live: {thread.jump_url}",
            )
        )
        await interaction.channel.send(
            f"📣 Ad approved and live: {thread.jump_url}"
        )

    async def _deny(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DenyAdModal(self.channel_id))


class DenyAdModal(discord.ui.Modal, title="Deny ad"):
    reason = discord.ui.TextInput(
        label="Reason (shown in the ticket)",
        style=discord.TextStyle.paragraph, max_length=300, required=False,
    )

    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction):
        bot = interaction.client
        ticket = bot.store.data["tickets"].get(str(self.channel_id))
        pending = ticket and ticket.get("pending_ad")
        if pending is None:
            await interaction.response.send_message(
                "This ad was already handled.", ephemeral=True
            )
            return
        reason = self.reason.value or "No reason given."
        del ticket["pending_ad"]
        await bot.store.save()

        await interaction.response.edit_message(
            view=AdReviewView(
                self.channel_id, pending["server"], pending["text"],
                proof=pending.get("proof"),
                status="denied", actor=interaction.user.mention,
                extra=reason,
            )
        )
        await interaction.followup.send(
            f"Ad denied — {reason}\nThe owner can press **Send your ad** "
            "again with a fixed version."
        )


class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Confirm close", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Closing ticket…", view=None
        )
        await close_ticket(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Cancelled.", view=None)


async def close_ticket(interaction: discord.Interaction):
    bot, channel, guild = interaction.client, interaction.channel, interaction.guild
    ticket = bot.store.data["tickets"].pop(str(channel.id), None)
    await bot.store.save()

    log = guild.get_channel(bot.cfg["ticket_log_channel_id"])
    if log is not None:
        lines = [
            f"[{m.created_at:%Y-%m-%d %H:%M}] {m.author}: {m.content}"
            async for m in channel.history(limit=None, oldest_first=True)
        ]
        transcript = discord.File(
            io.BytesIO("\n".join(lines).encode("utf-8")),
            filename=f"transcript-{channel.name}.txt",
        )
        owner = guild.get_member(ticket["owner"]) if ticket else None
        embed = discord.Embed(
            title="🔒 Ticket closed",
            color=0xED1C24,
            description=(
                f"**Channel:** `{channel.name}`\n"
                f"**Owner:** {owner.mention if owner else 'unknown'}\n"
                f"**Closed by:** {interaction.user.mention}"
            ),
        )
        await log.send(embed=embed, file=transcript)

    await channel.delete(reason=f"Ticket closed by {interaction.user}")


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        ticket = self.bot.store.data["tickets"].get(str(message.channel.id))
        if not ticket or ticket["type"] != "partnership":
            return
        pending = ticket.get("pending_ad")
        if not pending or pending.get("proof"):
            return
        if message.author.id != ticket["owner"]:
            return

        image = next(
            (a for a in message.attachments
             if a.content_type and a.content_type.startswith("image/")),
            None,
        )
        if image is None:
            await message.reply(
                "That doesn't look like a screenshot — upload the image "
                "file directly."
            )
            return

        pending["proof"] = image.url
        await self.bot.store.save()
        await message.channel.send(
            view=AdReviewView(
                message.channel.id, pending["server"], pending["text"],
                pending["proof"],
            )
        )


async def setup(bot):
    for cid, t in bot.store.data["tickets"].items():
        pending = t.get("pending_ad")
        if pending and pending.get("proof"):
            bot.add_view(AdReviewView(
                int(cid), pending["server"], pending["text"],
                pending["proof"],
            ))
    await bot.add_cog(Tickets(bot))
