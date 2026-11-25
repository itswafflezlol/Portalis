import discord
from discord import app_commands
from discord.ext import commands

from branding import brand_embed, brand_files
from cogs.applications import ApplyPanelView
from cogs.partners import PartnerPanelView
from cogs.tickets import TicketPanelView


def info_embeds() -> list[discord.Embed]:
    info = brand_embed(
        description=(
            "**🤝 Partnerships**\n"
            "Hello valued member(s), in this embed we will cover the "
            "requirements you must meet to partner with SMP Portal. Please "
            "note that your partnership process can be put on pause at any "
            "moment of partnering.\n\n"
            "If your server meets these requirements, open a **Partnership** "
            "ticket. When the bot asks a question, only respond with your "
            "**final** answer — you can't take back a message. (E.g. don't "
            "say \"Hi\" or \"Okay\".)"
        ),
        banner="info.webp",
    )
    info.add_field(
        name="Requirements",
        value=(
            "• 25+ Members\n"
            "• Server Owner must be the one to partner\n"
            "• 3-day partnership cooldown\n"
            "• Must ping `@everyone` and send valid proof"
        ),
        inline=False,
    )

    ads = brand_embed(
        description=(
            "**📣 Paid Ads**\n"
            "In this embed we will discuss our paid ad conditions and "
            "prices. Prices are subject to change. If you have any "
            "questions, ask a Staff Member or Manager.\n\n"
            "To discuss premium options — role pings, different category "
            "channels, higher channel order — open a **Partnership** ticket."
        ),
        images=True, banner=None,
    )
    ads.set_image(url=None)
    ads.add_field(
        name="Payment Conditions",
        value=(
            "All payments are **final** — zero refunds. Payments are made "
            "via a payment site sent to you when you open a paid ad "
            "ticket. Accepts Credit + Debit and PayPal."
        ),
        inline=False,
    )
    ads.add_field(
        name="Prices",
        value=(
            "**Custom channel** in the SMP-Partner category\n"
            "• $15 — one week\n"
            "• $45 — one month"
        ),
        inline=False,
    )
    return [info, ads]


# kind -> (banner file, description, view)
PANELS = {
    "tickets": (
        "tickets.webp",
        "**🛠️ Support**\n"
        "Problems or questions for the staff team — open a ticket and "
        "we'll help.\n\n"
        "**🤝 Partnership**\n"
        "Partner with SMP Portal or advertise your server — terms, paid "
        "ads, and proof.\n\n"
        "• Only 1 ticket open at a time",
        TicketPanelView,
    ),
    "apply": (
        "apply.webp",
        "**💼 Freelancer**\n"
        "Offer your services through SMP Portal — devs, builders, "
        "designers, editors and more.\n\n"
        "Press the button and fill the short application; staff will "
        "review it and get back to you.",
        ApplyPanelView,
    ),
    "partner": (
        "partner.webp",
        "**📣 Partner & Advertise**\n"
        "Get your server posted on our Discord and on the SMP Portal "
        "website.\n\n"
        "Press the button to submit your server — your ad goes live once "
        "staff approve it.",
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
        app_commands.Choice(name="Partnership info & paid ads", value="info"),
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction, kind: str):
        if kind == "info":
            await interaction.channel.send(
                embeds=info_embeds(), files=brand_files("info.webp")
            )
        else:
            banner, desc, view_cls = PANELS[kind]
            await interaction.channel.send(
                embed=brand_embed(description=desc, banner=banner),
                view=view_cls(),
                files=brand_files(banner),
            )
        await interaction.response.send_message("Panel posted.", ephemeral=True)

    @app_commands.command(name="ping", description="Check Portalis latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"🏓 {round(interaction.client.latency * 1000)}ms", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Admin(bot))
