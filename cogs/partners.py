import discord
from discord.ext import commands

from branding import RED
from cogs.tickets import open_ticket


class PartnerPanelView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        ui = discord.ui

        ad_btn = ui.Button(
            label="Advertise your server", style=discord.ButtonStyle.danger,
            emoji="📣", custom_id="portal:partner_open",
        )
        ad_btn.callback = lambda i: open_ticket(i, "partnership")

        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem(
                "attachment://partner.gif"
            )),
            ui.Separator(),
            ui.TextDisplay(
                "## 📣 Partner & Advertise\n"
                "Get your server posted in our partner forums and on the "
                "SMP Portal website.\n"
                "-# Opens a Partnership ticket — pick your server type "
                "and send your ad"
            ),
            ui.ActionRow(ad_btn),
            ui.Separator(),
            ui.TextDisplay("-# SMP Portal · Official Discord"),
            accent_color=RED,
        ))


class Partners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(Partners(bot))
