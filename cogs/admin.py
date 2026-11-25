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
