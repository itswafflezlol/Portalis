import discord
from discord import app_commands
from discord.ext import commands

from branding import brand_embed, brand_files
from cogs.applications import ApplyPanelView
from cogs.partners import PartnerPanelView
from cogs.tickets import TicketPanelView

PANELS = {
    "tickets": (
        "Support Panel",
        "**Choose a ticket option**\n\n"
        "🛠️ **Support** — problems you may have, or questions to staff\n"
        "🤝 **Partnership** — partner with SMP Portal and advertise here\n\n"
        "• Only 1 ticket open at a time",
        TicketPanelView,
    ),
    "apply": (
        "Freelancer Applications",
        "**💼 Become a Freelancer**\n\n"
        "Sign up to offer your services through SMP Portal — devs, builders, "
        "designers, editors and more.\n\n"
        "Press the button below and fill out the short application. Staff will "
        "review it and get back to you.",
        ApplyPanelView,
    ),
    "partner": (
        "Partner & Advertise",
        "**📣 Advertise your server**\n\n"
        "Get your server posted on our Discord and on the SMP Portal website.\n\n"
        "Press the button below to submit your server — staff will review it "
        "and your ad goes live once approved.",
        PartnerPanelView,
    ),
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
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction, kind: str):
        title, desc, view_cls = PANELS[kind]
        await interaction.channel.send(
            embed=brand_embed(title, desc), view=view_cls(), files=brand_files(),
        )
        await interaction.response.send_message("Panel posted.", ephemeral=True)

    @app_commands.command(name="ping", description="Check Portalis latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"🏓 {round(interaction.client.latency * 1000)}ms", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Admin(bot))
