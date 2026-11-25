import discord
from discord import app_commands
from discord.ext import commands

from branding import RED, panel_file
from cogs.applications import ApplyPanelView
from cogs.partners import PartnerPanelView
from cogs.tickets import TicketPanelView, open_ticket


class InfoPanelView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui
        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem(
                "attachment://info.gif"
            )),
            ui.Separator(),
            ui.TextDisplay(
                "## 🤝 Partnerships\n"
                "Hello valued member(s), in this embed we will cover the "
                "requirements you must meet to partner with SMP Portal. "
                "Please note that your partnership process can be put on "
                "pause at any moment of partnering.\n\n"
                "**Requirements**\n"
                "• 25+ Members\n"
                "• Server Owner must be the one to partner\n"
                "• 3-day partnership cooldown\n"
                "• Must ping `@everyone` and send valid proof\n"
                "-# If you meet these, open a Partnership ticket — and "
                "reply with your FINAL answer only (don't say \"Hi\" or "
                "\"Okay\")."
            ),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))


class ServerInfoPanelView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui
        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem(
                "attachment://server.gif"
            )),
            ui.Separator(),
            ui.TextDisplay(
                "## 🌐 About SMP Portal\n"
                "SMP Portal is a community built around Minecraft SMPs "
                "— find servers to join, promote your own, or get work "
                "done.\n\n"
                "**What we offer**\n"
                "💼 **Commissions** — our freelancers take paid work: "
                "plugins, builds, graphics, bots, server setups & more. "
                "Open a ticket to hire, or apply to join the team.\n"
                "🤝 **Partnerships** — advertise your server in our "
                "partner forums (25+ members required)\n"
                "💎 **Paid ads** — your own channel in the Partners "
                "category, pinned at the top\n"
                "🎪 **Events** — we host 100+ player events with money "
                "or Nitro prizes\n"
                "🎁 **Nitro giveaways** — order a Nitro giveaway for "
                "*your* server — we host & fund it\n"
                "🎉 **Community giveaways** — grab the ping roles so "
                "you never miss one\n\n"
                "-# Questions? Open a Support ticket — staff are happy "
                "to help."
            ),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))


class RulesPanelView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui
        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem(
                "attachment://rules.gif"
            )),
            ui.Separator(),
            ui.TextDisplay(
                "## 📜 Server Rules\n"
                "**1.** No toxicity — keep it respectful.\n"
                "**2.** No doxxing — in any way, shape or form.\n"
                "**3.** Listen to staff guidelines.\n"
                "**4.** Keep the chat clean.\n"
                "**5.** Use common sense.\n"
                "**6.** No NSFW.\n"
                "**7.** Spam pinging mods gets you a timeout.\n"
                "**8.** Follow Discord's Terms of Service.\n"
                "**9.** No promoting your own Discord or anything else "
                "without higher-staff permission — do it in self-promo "
                "only, or it's a mute/ban.\n\n"
                "Please — use common sense. ⚖️"
            ),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))


class BoosterPanelView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui
        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem(
                "attachment://boost.gif"
            )),
            ui.Separator(),
            ui.TextDisplay(
                "## 🚀 Booster Perks\n"
                "Boost SMP Portal and unlock:\n\n"
                "🚀 **Booster role** — exclusive color, hoisted above "
                "the member list\n"
                "💬 **Booster lounge** — private channel just for "
                "boosters\n"
                "🖼️ **Media perks** — post images & embeds anywhere\n"
                "🎫 **Priority support** — your tickets get answered "
                "first\n"
                "✨ **Early access** — sneak peeks at events, drops & "
                "features\n"
                "🎁 **Nitro extras** — first dibs on giveaway entries "
                "and event spots\n\n"
                "-# 2 boosts = shoutout in announcements. Boosts keep "
                "the Portal running — thank you ❤️"
            ),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))


class PaidAdsPanelView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui

        buy = ui.Button(
            label="Get a custom channel", style=discord.ButtonStyle.danger,
            emoji="💎", custom_id="portal:paidads_open",
        )
        buy.callback = lambda i: open_ticket(i, "paid_ad")

        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem(
                "attachment://paidads.gif"
            )),
            ui.Separator(),
            ui.TextDisplay(
                "## 💎 Paid Ads\n"
                "Get a **custom channel** in the Partners category — your "
                "ad pinned at the top, only you and staff can type.\n\n"
                "**Prices**\n"
                "• $10 — one week\n"
                "• $25 — one month\n"
                "-# Payments via Ko-fi, final — no refunds."
            ),
            ui.ActionRow(buy),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))


class PingRolesView(discord.ui.LayoutView):
    """Toggleable ping roles — press to get/lose the role."""

    KEYS = [
        ("news", "📰", "News Ping"),
        ("giveaway", "🎉", "Giveaway Ping"),
        ("polls", "📊", "Polls Ping"),
        ("event", "🎪", "Event Ping"),
    ]

    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui

        buttons = []
        for key, emoji, label in self.KEYS:
            b = ui.Button(
                label=label, style=discord.ButtonStyle.secondary,
                emoji=emoji, custom_id=f"portal:pingrole:{key}",
            )
            b.callback = self._toggle(key)
            buttons.append(b)

        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem(
                "attachment://pings.gif"
            )),
            ui.Separator(),
            ui.TextDisplay(
                "## 🔔 Ping roles\n"
                "Press a button to get pinged — press again to turn "
                "it off.\n\n"
                "📰 **News Ping** — server updates & announcements\n"
                "🎉 **Giveaway Ping** — new giveaways\n"
                "📊 **Polls Ping** — community votes\n"
                "🎪 **Event Ping** — server events"
            ),
            ui.ActionRow(*buttons),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))

    def _toggle(self, key: str):
        async def cb(interaction: discord.Interaction):
            rid = interaction.client.cfg.get("ping_roles", {}).get(key)
            role = interaction.guild.get_role(rid) if rid else None
            if role is None:
                await interaction.response.send_message(
                    "That role isn't set up yet.", ephemeral=True
                )
                return
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(
                    f"**{role.name}** removed — no more pings.",
                    ephemeral=True,
                )
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(
                    f"**{role.name}** added — you'll get pinged.",
                    ephemeral=True,
                )
        return cb


# kind -> (banner file, view class)
PANELS = {
    "tickets": ("tickets.gif", TicketPanelView),
    "apply": ("apply.gif", ApplyPanelView),
    "partner": ("partner.gif", PartnerPanelView),
    "info": ("info.gif", InfoPanelView),
    "paidads": ("paidads.gif", PaidAdsPanelView),
    "pings": ("pings.gif", PingRolesView),
    "server": ("server.gif", ServerInfoPanelView),
    "rules": ("rules.gif", RulesPanelView),
    "boost": ("boost.gif", BoosterPanelView),
}


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="panel", description="Post a Portalis panel here")
    @app_commands.describe(kind="Which panel to post")
    @app_commands.choices(kind=[
        app_commands.Choice(name="Tickets", value="tickets"),
        app_commands.Choice(name="Freelancer applications", value="apply"),
        app_commands.Choice(name="Partner / advertise", value="partner"),
        app_commands.Choice(name="Partnership info", value="info"),
        app_commands.Choice(name="Paid ads", value="paidads"),
        app_commands.Choice(name="Ping roles", value="pings"),
        app_commands.Choice(name="Server info", value="server"),
        app_commands.Choice(name="Rules", value="rules"),
        app_commands.Choice(name="Booster perks", value="boost"),
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction, kind: str):
        await interaction.response.defer(ephemeral=True)
        banner, view_cls = PANELS[kind]
        await interaction.channel.send(
            view=view_cls(), files=[panel_file(banner)]
        )
        await interaction.followup.send("Panel posted.", ephemeral=True)

    @app_commands.command(name="ping", description="Check Portalis latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"🏓 {round(interaction.client.latency * 1000)}ms", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Admin(bot))
