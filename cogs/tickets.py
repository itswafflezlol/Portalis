import io
import re
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from PIL import Image

from branding import RED, panel_file

TICKET_TYPES = {
    "support": ("🛠️ Support", "Problems or questions for the staff team."),
    "partnership": ("🤝 Partnership", "Partner or advertise with SMP Portal."),
    "paid_ad": ("💎 Paid Ad", "Buy a custom ad channel for your server."),
    "ping": ("📣 Ping Ad", "Buy an @here or @everyone ping for your ad."),
}

PLANS = {"1w": ("1 Week", "$10", 7), "1m": ("1 Month", "$25", 30)}

CATEGORIES = {
    "public": ("Public", "🌍"),
    "bedrock": ("Bedrock", "🪨"),
    "smps": ("SMP", "⚔️"),
    "other": ("Other", "📦"),
}

PING_RE = re.compile(r"@everyone|@here|<@!?\d+>|<@&\d+>")
SELF_PROMO_CHANNEL = 1575250716417720420  # 🔗・self-promo
PROMO_COOLDOWN = 600  # 10 minutes between ads

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


def can_staff(member: discord.Member, cfg: dict) -> bool:
    """Staff, partnership manager or paid-ads manager."""
    return can_review(member, cfg) or member.get_role(
        cfg["paid_ads_manager_role_id"]
    ) is not None


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
                "attachment://tickets.gif"
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

    # exempt if the user's ID *or* any of their role IDs is listed
    exempt = user.id in cfg["cooldown_exempt"] or any(
        r.id in cfg["cooldown_exempt"] for r in user.roles
    )
    if kind == "partnership" and not exempt:
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
    if kind in ("paid_ad", "ping"):
        payer = guild.get_role(cfg["paid_ads_manager_role_id"])
        if payer:
            overwrites[payer] = discord.PermissionOverwrite(
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
    mention, ping_roles, ping_users = user.mention, [], [user]
    if kind in ("paid_ad", "ping", "partnership"):
        mgr = guild.get_role(
            cfg["paid_ads_manager_role_id"]
            if kind in ("paid_ad", "ping")
            else cfg["partnership_manager_role_id"]
        )
        if mgr:
            mention += f" {mgr.mention}"
            ping_roles = [mgr]
        else:
            mention += " the manager"
    elif staff:
        ping_roles = [staff]
        mention += f" {staff.mention}"
    await channel.send(
        view=TicketChannelView(kind, mention),
        files=[panel_file(f"{kind}.gif")],
        allowed_mentions=discord.AllowedMentions(
            users=ping_users, roles=ping_roles
        ),
    )
    if kind == "partnership":
        await channel.send(view=PartnershipQuestionsView())
    elif kind == "paid_ad":
        await channel.send(view=PaidAdPlanView())
    elif kind == "ping":
        await channel.send(view=PingPlanView())
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
                f"attachment://{kind}.gif"
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
        invite_match = INVITE_RE.search(text)
        if not invite_match:
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

        try:
            invite = await bot.fetch_invite(invite_match.group(0))
        except (discord.NotFound, discord.HTTPException):
            await interaction.response.send_message(
                "That invite link doesn't work — make sure it's a "
                "permanent invite (`discord.gg/...`) and send it again.",
                ephemeral=True,
            )
            return
        members = invite.approximate_member_count or 0
        if members < 25:
            await interaction.response.send_message(
                "Partnerships need **25+ members** — that server has "
                f"~{members}. Come back when it grows! 🌱", ephemeral=True,
            )
            return

        pending = {
            "server": self.server.value, "text": text,
            "proof": None, "members": members,
        }
        ticket["pending_ad"] = pending
        await bot.store.save()

        await interaction.response.send_message(
            "Last step — post **our ad** (below) in your server with "
            "an `@everyone` ping added to it, then **send a "
            "screenshot** of it here. Staff will review everything."
        )
        if bot.cfg.get("our_ad"):
            await interaction.followup.send(bot.cfg["our_ad"])


class AdReviewView(discord.ui.LayoutView):
    """Review card posted inside the partnership ticket."""

    def __init__(self, channel_id: int, server: str = "", ad: str = "",
                 proof: str = None, status: str = None, actor: str = "",
                 extra: str = "", members: int = 0):
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
                f"**Server:** {server}"
                + (f" · ~{members} members" if members else "")
                + f"\n\n{ad}\n\n"
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

        review_msgs = pending.get("review_msgs", [])
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

        done = AdReviewView(
            self.channel_id, pending["server"], pending["text"],
            proof=pending.get("proof"),
            status="approved", actor=interaction.user.display_name,
            extra=f"Live: {thread.jump_url}",
        )
        await interaction.response.edit_message(view=done)
        await _sync_review_cards(
            bot, interaction.guild, review_msgs, done,
            skip=interaction.message.id,
        )
        ticket_ch = bot.get_channel(self.channel_id) \
            or await bot.fetch_channel(self.channel_id)
        await ticket_ch.send(f"📣 Ad approved and live: {thread.jump_url}")

    async def _deny(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DenyAdModal(self.channel_id))


async def _sync_review_cards(bot, guild, msgs, view, skip):
    """Edit every posted copy of a review card except the one clicked."""
    for cid, mid in msgs:
        if mid == skip:
            continue
        try:
            ch = guild.get_channel(cid) or await bot.fetch_channel(cid)
            msg = await ch.fetch_message(mid)
            await msg.edit(view=view)
        except discord.HTTPException:
            pass


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
        review_msgs = pending.get("review_msgs", [])
        del ticket["pending_ad"]
        await bot.store.save()

        done = AdReviewView(
            self.channel_id, pending["server"], pending["text"],
            proof=pending.get("proof"),
            status="denied", actor=interaction.user.display_name,
            extra=reason,
        )
        await interaction.response.edit_message(view=done)
        await _sync_review_cards(
            bot, interaction.guild, review_msgs, done,
            skip=interaction.message.id,
        )
        ticket_ch = bot.get_channel(self.channel_id) \
            or await bot.fetch_channel(self.channel_id)
        await ticket_ch.send(
            f"Ad denied — {reason}\nThe owner can press **Send your ad** "
            "again with a fixed version."
        )


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9\-_]", "", name.lower().replace(" ", "-"))
    return s or "channel"


class PaidAdPlanView(discord.ui.LayoutView):
    """First message in paid-ad tickets: pick a plan."""

    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui

        sel = ui.Select(
            placeholder="What do you want to pay for?",
            custom_id="portal:paid:plan",
            options=[
                discord.SelectOption(label="1 Week — $10", value="1w",
                                     emoji="📅"),
                discord.SelectOption(label="1 Month — $25", value="1m",
                                     emoji="🗓️"),
            ],
        )
        sel.callback = self._pick

        self.add_item(ui.Container(
            ui.TextDisplay(
                "## 💎 Custom Channel\n"
                "Get your own ad channel in the Partners category — "
                "only you and staff can type in it.\n\n"
                "**1.** What do you want to pay for?"
            ),
            ui.ActionRow(sel),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))

    async def _pick(self, interaction: discord.Interaction):
        bot = interaction.client
        ticket = bot.store.data["tickets"].get(str(interaction.channel.id))
        if ticket is None or ticket["type"] != "paid_ad":
            await interaction.response.send_message(
                "This isn't a paid ad ticket.", ephemeral=True
            )
            return
        if interaction.user.id != ticket["owner"]:
            await interaction.response.send_message(
                "Only the ticket owner picks this.", ephemeral=True
            )
            return

        plan = interaction.data["values"][0]
        ticket["plan"] = plan
        await bot.store.save()
        label, price, _ = PLANS[plan]

        payer = interaction.guild.get_role(
            bot.cfg["paid_ads_manager_role_id"]
        )
        payer_txt = payer.mention if payer else "the payment manager"
        await interaction.response.send_message(
            f"Plan: **{label} ({price})**"
        )
        await interaction.channel.send(view=PaymentConfirmView(
            label, price, bot.cfg["kofi_link"], payer_txt,
        ))


PING_PLANS = {"here": ("@here", "$7"), "everyone": ("@everyone", "$10")}


class PingPlanView(discord.ui.LayoutView):
    """First message in ping tickets: pick @here or @everyone."""

    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui

        sel = ui.Select(
            placeholder="Pick your ping…",
            custom_id="portal:ping:plan",
            options=[
                discord.SelectOption(label="@here — $7", value="here",
                                     emoji="📣"),
                discord.SelectOption(label="@everyone — $10", value="everyone",
                                     emoji="🔊"),
            ],
        )
        sel.callback = self._pick

        self.add_item(ui.Container(
            ui.TextDisplay(
                "## 📣 Pay for a Ping\n"
                "Get an `@here` or `@everyone` ping with your ad.\n\n"
                "**1.** Pick your ping:"
            ),
            ui.ActionRow(sel),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))

    async def _pick(self, interaction: discord.Interaction):
        bot = interaction.client
        ticket = bot.store.data["tickets"].get(str(interaction.channel.id))
        if ticket is None or ticket["type"] != "ping":
            await interaction.response.send_message(
                "This isn't a ping ticket.", ephemeral=True
            )
            return
        if interaction.user.id != ticket["owner"]:
            await interaction.response.send_message(
                "Only the ticket owner picks this.", ephemeral=True
            )
            return

        plan = interaction.data["values"][0]
        ticket["plan"] = plan
        await bot.store.save()
        label, price = PING_PLANS[plan]

        payer = interaction.guild.get_role(
            bot.cfg["paid_ads_manager_role_id"]
        )
        payer_txt = payer.mention if payer else "the payment manager"
        await interaction.response.send_message(
            f"Ping: **{label} ({price})**"
        )
        await interaction.channel.send(
            f"## 💳 Payment\n"
            f"Pay **{price} — {label} ping** here:\n"
            f"{bot.cfg['kofi_link']}\n\n"
            f"{payer_txt} — your ping goes in **your paid ad channel** "
            "if you bought one, otherwise in our **partner forum**.\n"
            "-# Payments are final — no refunds."
        )


class PaymentConfirmView(discord.ui.LayoutView):
    """Ko-fi link + confirm button for the payment manager."""

    def __init__(self, label: str = "", price: str = "", link: str = "",
                 payer: str = ""):
        super().__init__(timeout=None)
        ui = discord.ui

        confirm = ui.Button(
            label="Confirm payment received", style=discord.ButtonStyle.success,
            emoji="💰", custom_id="portal:paid:confirm",
        )
        confirm.callback = self._confirm

        self.add_item(ui.Container(
            ui.TextDisplay(
                "## 💳 Payment\n"
                f"Pay **{price} — {label}** here:\n{link}\n\n"
                f"{payer} press **Confirm payment** once the payment "
                "arrives.\n"
                "-# Payments are final — no refunds."
            ),
            ui.ActionRow(confirm),
            accent_color=RED,
        ))

    async def _confirm(self, interaction: discord.Interaction):
        bot = interaction.client
        if interaction.user.get_role(
            bot.cfg["paid_ads_manager_role_id"]
        ) is None:
            await interaction.response.send_message(
                "Only the payment manager confirms payments.",
                ephemeral=True,
            )
            return
        ticket = bot.store.data["tickets"].get(str(interaction.channel.id))
        if ticket is None or ticket["type"] != "paid_ad":
            await interaction.response.send_message(
                "This isn't a paid ad ticket.", ephemeral=True
            )
            return
        if ticket.get("paid_confirmed"):
            await interaction.response.send_message(
                "Payment already confirmed.", ephemeral=True
            )
            return
        ticket["paid_confirmed"] = True
        days = PLANS.get(ticket.get("plan"), (None, None, 7))[2]
        exp = datetime.now(timezone.utc) + timedelta(days=days)
        ticket["paid_expires"] = exp.isoformat()
        await bot.store.save()

        owner = interaction.guild.get_member(ticket["owner"])
        await interaction.response.send_message("✅ Payment confirmed.")
        await interaction.channel.send(view=ChannelSetupView(
            owner.mention if owner else "the buyer",
            f"⏳ Plan ends <t:{int(exp.timestamp())}:F> "
            f"(<t:{int(exp.timestamp())}:R>) — the channel deletes "
            "itself when time runs out.",
        ))


class ChannelSetupView(discord.ui.LayoutView):
    """Guidelines + emoji/name picker after payment."""

    def __init__(self, opener: str = "", duration: str = ""):
        super().__init__(timeout=None)
        ui = discord.ui

        setup_btn = ui.Button(
            label="Choose emoji & name", style=discord.ButtonStyle.danger,
            emoji="🏷️", custom_id="portal:paid:setup",
        )
        setup_btn.callback = lambda i: i.response.send_modal(
            ChannelNameModal()
        )

        self.add_item(ui.Container(
            ui.TextDisplay(
                "## 🏷️ Your channel\n"
                f"{opener} — payment confirmed ✅\n{duration}\n\n"
                "**Channel guidelines**\n"
                "• Do **not** ping `@everyone`, `@here`, or anyone — "
                "messages with pings get **deleted**\n"
                "• Only you and staff can type in your channel\n\n"
                "Press the button to pick your channel emoji and name."
            ),
            ui.ActionRow(setup_btn),
            accent_color=RED,
        ))


class ChannelNameModal(discord.ui.Modal, title="Channel emoji & name"):
    emoji = discord.ui.TextInput(
        label="Channel emoji", placeholder="e.g. 🔥", max_length=30,
    )
    name = discord.ui.TextInput(
        label="Channel name", placeholder="e.g. my-smp", max_length=30,
    )

    async def on_submit(self, interaction: discord.Interaction):
        bot = interaction.client
        ticket = bot.store.data["tickets"].get(str(interaction.channel.id))
        if ticket is None or ticket["type"] != "paid_ad":
            await interaction.response.send_message(
                "This isn't a paid ad ticket.", ephemeral=True
            )
            return
        if interaction.user.id != ticket["owner"]:
            await interaction.response.send_message(
                "Only the ticket owner picks this.", ephemeral=True
            )
            return

        ticket["pending_channel"] = {
            "emoji": self.emoji.value.strip(),
            "name": self.name.value.strip(),
        }
        await bot.store.save()

        payer = interaction.guild.get_role(
            bot.cfg["paid_ads_manager_role_id"]
        )
        payer_txt = payer.mention if payer else "the payment manager"
        owner = interaction.user.mention
        await interaction.channel.send(view=NameApprovalView(
            self.emoji.value.strip(), self.name.value.strip(), owner,
            payer_txt,
        ))
        await interaction.response.send_message(
            "Sent for approval.", ephemeral=True
        )


class NameApprovalView(discord.ui.LayoutView):
    """Payment manager approves the emoji + channel name."""

    def __init__(self, emoji: str = "", name: str = "", opener: str = "",
                 payer: str = "", status: str = None,
                 actor: str = "", extra: str = ""):
        super().__init__(timeout=None)
        ui = discord.ui

        ok = ui.Button(
            label="Approve", style=discord.ButtonStyle.success, emoji="✅",
            custom_id="portal:paid:nameok",
        )
        ok.callback = self._approve
        no = ui.Button(
            label="Reject", style=discord.ButtonStyle.danger, emoji="✖️",
            custom_id="portal:paid:nameno",
        )
        no.callback = self._deny

        if status == "approved":
            ok.disabled = no.disabled = True
            header = f"## ✅ Channel approved by {actor}"
            body = f"**{emoji}・{name}**\n-# {extra}"
        elif status == "denied":
            ok.disabled = no.disabled = True
            header = f"## ✖️ Channel rejected by {actor}"
            body = f"**{emoji}・{name}**\n-# {extra}"
        else:
            header = "## 🏷️ Channel name approval"
            body = (
                f"**{emoji}・{name}**\nFor {opener}\n"
                f"-# {payer} — approve to create the channel."
            )

        self.add_item(ui.Container(
            ui.TextDisplay(f"{header}\n{body}"),
            ui.ActionRow(ok, no),
            accent_color=RED,
        ))

    async def _check(self, interaction: discord.Interaction):
        bot = interaction.client
        if interaction.user.get_role(
            bot.cfg["paid_ads_manager_role_id"]
        ) is None:
            await interaction.response.send_message(
                "Only the payment manager approves names.", ephemeral=True
            )
            return None
        ticket = bot.store.data["tickets"].get(str(interaction.channel.id))
        pending = ticket and ticket.get("pending_channel")
        if pending is None:
            await interaction.response.send_message(
                "This was already handled.", ephemeral=True
            )
            return None
        return ticket, pending

    async def _approve(self, interaction: discord.Interaction):
        got = await self._check(interaction)
        if got is None:
            return
        bot = interaction.client
        ticket, pending = got
        guild = interaction.guild

        emoji, name = pending["emoji"], _slugify(pending["name"])
        category = guild.get_channel(bot.cfg["paid_category_id"])
        if category is None:
            await interaction.response.send_message(
                "Missing `paid_category_id` in config.", ephemeral=True
            )
            return

        owner = guild.get_member(ticket["owner"])
        staff = guild.get_role(bot.cfg["staff_role_id"])
        pm = guild.get_role(bot.cfg["partnership_manager_role_id"])
        payer = guild.get_role(bot.cfg["paid_ads_manager_role_id"])

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True, send_messages=False,
                mention_everyone=False,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_messages=True, manage_channels=True,
            ),
        }
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, attach_files=True,
                embed_links=True, mention_everyone=False,
            )
        for extra in (staff, pm, payer):
            if extra:
                overwrites[extra] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    read_message_history=True, mention_everyone=False,
                )

        channel = await guild.create_text_channel(
            name=f"{emoji}・{name}", category=category, overwrites=overwrites,
        )
        bot.store.data.setdefault("paid_channels", []).append(channel.id)
        # plan clock started at payment confirmation
        expires = (
            datetime.fromisoformat(ticket["paid_expires"])
            if ticket.get("paid_expires")
            else datetime.now(timezone.utc) + timedelta(
                days=PLANS.get(ticket.get("plan"), (None, None, 7))[2]
            )
        )
        bot.store.data.setdefault("paid_channel_expiry", {})[
            str(channel.id)
        ] = expires.isoformat()
        ticket["paid_channel"] = channel.id
        del ticket["pending_channel"]
        await bot.store.save()

        await interaction.response.edit_message(
            view=NameApprovalView(
                emoji, name, status="approved",
                actor=interaction.user.mention,
                extra=f"Created: {channel.mention}",
            )
        )
        await interaction.channel.send(
            f"💎 {channel.mention} is live — post your ad, "
            f"{owner.mention if owner else 'buyer'}. No pings allowed.\n"
            f"Expires <t:{int(expires.timestamp())}:R> — the channel "
            "is deleted automatically when time runs out."
        )

    async def _deny(self, interaction: discord.Interaction):
        got = await self._check(interaction)
        if got is None:
            return
        bot = interaction.client
        ticket, pending = got
        del ticket["pending_channel"]
        await bot.store.save()

        await interaction.response.edit_message(
            view=NameApprovalView(
                pending["emoji"], pending["name"], status="denied",
                actor=interaction.user.mention,
                extra="Press **Choose emoji & name** to try again.",
            )
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


def _cv2_text(components):
    for c in components:
        content = getattr(c, "content", None)
        if isinstance(content, str) and content:
            yield content
        url = getattr(getattr(c, "media", None), "url", None)
        if url:
            yield f"[media: {url}]"
        for item in getattr(c, "items", None) or []:
            iurl = getattr(getattr(item, "media", None), "url", None)
            if iurl:
                yield f"[media: {iurl}]"
        yield from _cv2_text(getattr(c, "children", None) or [])


def _transcript_line(m: discord.Message) -> str:
    parts = [m.content] if m.content else []
    parts += [f"[{a.filename}]({a.url})" for a in m.attachments]
    parts += [f"[embed: {e.title or 'untitled'}]" for e in m.embeds]
    parts += [f"[sticker: {s.name}]" for s in m.stickers]
    parts += _cv2_text(m.components)
    body = " | ".join(parts) or "(no text)"
    return f"[{m.created_at:%Y-%m-%d %H:%M}] {m.author}: {body}"


class CloseRequestView(discord.ui.LayoutView):
    """Asks the ticket owner if the ticket can be closed."""

    def __init__(self, channel_id: int = 0, ping: str = "",
                 done: bool = False):
        super().__init__(timeout=None)
        ui = discord.ui
        self.channel_id = channel_id

        yes = ui.Button(
            label="Yes, close it", style=discord.ButtonStyle.danger,
            emoji="🔒", custom_id=f"portal:closereq:{channel_id}:yes",
            disabled=done,
        )
        yes.callback = self._yes
        no = ui.Button(
            label="Still need help", style=discord.ButtonStyle.secondary,
            emoji="✋", custom_id=f"portal:closereq:{channel_id}:no",
            disabled=done,
        )
        no.callback = self._no

        self.add_item(ui.Container(
            ui.TextDisplay(
                f"## 🔒 Close request\n{ping}\n"
                "Staff asked if this ticket can be closed. "
                + ("*(answered)*" if done else "Are you good to go?")
            ),
            ui.ActionRow(yes, no),
            accent_color=RED,
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        ticket = interaction.client.store.data["tickets"].get(
            str(self.channel_id)
        )
        if (ticket and interaction.user.id == ticket["owner"]) \
                or can_staff(interaction.user, interaction.client.cfg):
            return True
        await interaction.response.send_message(
            "Only the ticket owner answers this.", ephemeral=True
        )
        return False

    async def _yes(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=CloseRequestView(self.channel_id, done=True)
        )
        await close_ticket(interaction)

    async def _no(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=CloseRequestView(self.channel_id, done=True)
        )
        await interaction.followup.send("Keeping the ticket open. 👍")


async def close_ticket(interaction: discord.Interaction):
    bot, channel, guild = interaction.client, interaction.channel, interaction.guild
    ticket = bot.store.data["tickets"].pop(str(channel.id), None)
    await bot.store.save()

    log = guild.get_channel(bot.cfg["ticket_log_channel_id"])
    if log is not None:
        lines = [
            _transcript_line(m)
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

    async def cog_load(self):
        self._expire_paid.start()

    async def cog_unload(self):
        self._expire_paid.cancel()

    @tasks.loop(minutes=5)
    async def _expire_paid(self):
        """Delete paid-ad channels whose plan ran out."""
        store = self.bot.store
        expiry = store.data.get("paid_channel_expiry", {})
        now = datetime.now(timezone.utc)
        expired = [
            (int(cid), iso) for cid, iso in expiry.items()
            if datetime.fromisoformat(iso) <= now
        ]
        if not expired:
            return

        guild = self.bot.get_guild(self.bot.cfg["guild_id"])
        log = guild and guild.get_channel(
            self.bot.cfg["ticket_log_channel_id"]
        )
        for cid, _ in expired:
            del expiry[str(cid)]
            if cid in store.data.get("paid_channels", []):
                store.data["paid_channels"].remove(cid)
            owner_id = None
            for t in store.data["tickets"].values():
                if t.get("paid_channel") == cid:
                    owner_id = t["owner"]
                    t.pop("paid_channel", None)

            ch = guild.get_channel(cid) if guild else None
            name = ch.name if ch else str(cid)
            if ch is not None:
                try:
                    await ch.delete(reason="Paid ad plan expired")
                except discord.HTTPException:
                    pass
            if log is not None:
                await log.send(
                    f"⏰ Paid ad channel `{name}` expired and was deleted."
                )
            member = guild.get_member(owner_id) if owner_id else None
            if member is not None:
                try:
                    await member.send(
                        f"⏰ Your paid ad channel **{name}** in "
                        "**SMP Portal** expired and was deleted.\n"
                        "Open a new paid-ad ticket in 「🎫」support to "
                        "renew anytime."
                    )
                except discord.HTTPException:
                    pass  # DMs closed
        await store.save()

    @_expire_paid.before_loop
    async def _before_expire(self):
        await self.bot.wait_until_ready()

    async def _ticket_guard(self, interaction: discord.Interaction):
        """Ticket-channel + staff check for the ticket commands."""
        ticket = self.bot.store.data["tickets"].get(
            str(interaction.channel.id)
        )
        if ticket is None:
            await interaction.response.send_message(
                "Use this inside a ticket channel.", ephemeral=True
            )
            return None
        if not can_staff(interaction.user, self.bot.cfg):
            await interaction.response.send_message(
                "Staff only.", ephemeral=True
            )
            return None
        return ticket

    @app_commands.command(
        name="closeticket", description="Close this ticket"
    )
    async def closeticket(self, interaction: discord.Interaction):
        if await self._ticket_guard(interaction) is None:
            return
        await interaction.response.send_message("🔒 Closing ticket…")
        await close_ticket(interaction)

    @app_commands.command(
        name="closerequest",
        description="Ask the ticket owner if it can be closed",
    )
    async def closerequest(self, interaction: discord.Interaction):
        ticket = await self._ticket_guard(interaction)
        if ticket is None:
            return
        owner = interaction.guild.get_member(ticket["owner"])
        await interaction.response.send_message(
            "Close request sent.", ephemeral=True
        )
        await interaction.channel.send(
            view=CloseRequestView(
                interaction.channel.id,
                ping=owner.mention if owner else "",
            ),
            allowed_mentions=discord.AllowedMentions(
                users=[owner] if owner else []
            ),
        )

    @app_commands.command(
        name="pinguser",
        description="Ping the ticket owner to check they're still here",
    )
    async def pinguser(self, interaction: discord.Interaction):
        ticket = await self._ticket_guard(interaction)
        if ticket is None:
            return
        owner = interaction.guild.get_member(ticket["owner"])
        if owner is None:
            await interaction.response.send_message(
                "The ticket owner left the server.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"{owner.mention} — are you still here? 👀 "
            "Staff is waiting on you.",
            allowed_mentions=discord.AllowedMentions(users=[owner]),
        )

    async def _paid_guard(self, interaction: discord.Interaction):
        """Payment-manager + paid-channel check for paid ad commands."""
        if interaction.user.get_role(
            self.bot.cfg["paid_ads_manager_role_id"]
        ) is None:
            await interaction.response.send_message(
                "Payment manager only.", ephemeral=True
            )
            return False
        if interaction.channel.id not in self.bot.store.data.get(
            "paid_channels", []
        ):
            await interaction.response.send_message(
                "Use this inside a paid ad channel.", ephemeral=True
            )
            return False
        return True

    def _paid_owner(self, cid: int):
        for t in self.bot.store.data["tickets"].values():
            if t.get("paid_channel") == cid:
                return t["owner"]
        return None

    @app_commands.command(
        name="cancelpaid",
        description="Cancel this paid ad — deletes the channel now",
    )
    async def cancelpaid(self, interaction: discord.Interaction):
        if not await self._paid_guard(interaction):
            return
        store = self.bot.store
        cid, name = interaction.channel.id, interaction.channel.name

        store.data.get("paid_channel_expiry", {}).pop(str(cid), None)
        if cid in store.data.get("paid_channels", []):
            store.data["paid_channels"].remove(cid)
        owner_id = self._paid_owner(cid)
        for t in store.data["tickets"].values():
            if t.get("paid_channel") == cid:
                t.pop("paid_channel", None)
        await store.save()

        await interaction.response.send_message(
            "🗑️ Cancelling — deleting channel…"
        )
        log = interaction.guild.get_channel(
            self.bot.cfg["ticket_log_channel_id"]
        )
        if log is not None:
            await log.send(
                f"🗑️ Paid ad channel `{name}` cancelled by "
                f"{interaction.user.mention}."
            )
        member = interaction.guild.get_member(owner_id) if owner_id else None
        if member is not None:
            try:
                await member.send(
                    f"Your paid ad channel **{name}** in **SMP Portal** "
                    "was cancelled by staff."
                )
            except discord.HTTPException:
                pass
        await interaction.channel.delete(
            reason=f"Paid ad cancelled by {interaction.user}"
        )

    @app_commands.command(
        name="extendpaid",
        description="Extend this paid ad channel by N days",
    )
    @app_commands.describe(days="How many days to add")
    async def extendpaid(self, interaction: discord.Interaction,
                       days: int):
        if not await self._paid_guard(interaction):
            return
        if not 1 <= days <= 365:
            await interaction.response.send_message(
                "Days must be 1–365.", ephemeral=True
            )
            return

        store = self.bot.store
        cid = str(interaction.channel.id)
        expiry = store.data.setdefault("paid_channel_expiry", {})
        now = datetime.now(timezone.utc)
        base = (
            datetime.fromisoformat(expiry[cid])
            if cid in expiry else now
        )
        new = max(base, now) + timedelta(days=days)
        expiry[cid] = new.isoformat()
        await store.save()

        ts = int(new.timestamp())
        await interaction.response.send_message(
            f"✅ Extended **{days}** day(s) — now expires "
            f"<t:{ts}:F> (<t:{ts}:R>)."
        )
        owner_id = self._paid_owner(interaction.channel.id)
        member = interaction.guild.get_member(owner_id) if owner_id else None
        if member is not None:
            try:
                await member.send(
                    f"📅 Your paid ad channel **{interaction.channel.name}** "
                    f"in **SMP Portal** was extended — new expiry "
                    f"<t:{ts}:F> (<t:{ts}:R>)."
                )
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """Catch pings edited into messages in paid channels."""
        if payload.channel_id not in self.bot.store.data.get(
            "paid_channels", []
        ):
            return
        content = payload.data.get("content") or ""
        if not PING_RE.search(content):
            return
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        try:
            msg = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            return
        if msg.author.bot:
            return
        await msg.delete()
        await channel.send(
            f"{msg.author.mention} — no pings allowed here. "
            "Message deleted.", delete_after=5,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        if message.channel.id == SELF_PROMO_CHANNEL:
            if can_staff(message.author, self.bot.cfg):
                return
            now = datetime.now(timezone.utc).timestamp()
            cd = self.bot.store.data.setdefault("promo_cooldowns", {})
            left = int(PROMO_COOLDOWN - (now - cd.get(str(message.author.id), 0)))
            if left > 0:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} — slow down! One ad "
                    f"every 10 minutes. Try again in {left // 60}m"
                    f"{left % 60:02d}s.",
                    delete_after=10,
                )
                return
            cd[str(message.author.id)] = now
            await self.bot.store.save()
            return

        if message.channel.id in self.bot.store.data.get(
            "paid_channels", []
        ):
            if PING_RE.search(message.content):
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} — no pings allowed here. "
                    "Message deleted.", delete_after=5,
                )
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
        if image is not None:
            # actually decode it — extension/content-type can be faked
            try:
                Image.open(io.BytesIO(await image.read())).verify()
            except Exception:
                image = None
        if image is None:
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} — that's not a valid image. "
                "Upload the screenshot file directly.", delete_after=5,
            )
            return

        pending["proof"] = image.url
        view = AdReviewView(
            message.channel.id, pending["server"], pending["text"],
            pending["proof"], members=pending.get("members", 0),
        )
        card = await message.channel.send(view=view)
        pending["review_msgs"] = [[message.channel.id, card.id]]

        review_ch = message.guild.get_channel(
            self.bot.cfg.get("partners_channel_id", 0)
        )
        if review_ch is not None:
            mirror = await review_ch.send(
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            pending["review_msgs"].append([review_ch.id, mirror.id])
        await self.bot.store.save()


async def setup(bot):
    for cid, t in bot.store.data["tickets"].items():
        bot.add_view(CloseRequestView(int(cid)))
        pending = t.get("pending_ad")
        if pending and pending.get("proof"):
            bot.add_view(AdReviewView(
                int(cid), pending["server"], pending["text"],
                pending["proof"], members=pending.get("members", 0),
            ))
    await bot.add_cog(Tickets(bot))
