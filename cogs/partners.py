import discord
from discord import app_commands
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


class PartnerAdModal(discord.ui.Modal, title="Post partner ad"):
    server = discord.ui.TextInput(
        label="Server name", placeholder="Their Discord server name",
        max_length=90,
    )
    ad = discord.ui.TextInput(
        label="Their ad", style=discord.TextStyle.paragraph,
        max_length=1900, placeholder="Paste their ad here",
    )

    def __init__(self, category: str):
        super().__init__()
        self.category = category

    async def on_submit(self, interaction: discord.Interaction):
        forum = interaction.guild.get_channel(
            interaction.client.cfg["forum_channels"].get(self.category, 0)
        )
        if forum is None:
            await interaction.response.send_message(
                "Missing forum channel in config.", ephemeral=True
            )
            return
        posted = await forum.create_thread(
            name=self.server.value.strip(),
            content=self.ad.value.strip(),
        )
        await posted.thread.edit(locked=True)
        await interaction.response.send_message(
            f"Posted to {forum.mention}: {posted.thread.jump_url}",
            ephemeral=True,
        )


class Partners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="partner",
        description="Post a partner ad straight to a forum (PM only)",
    )
    @app_commands.describe(category="Which partner forum to post in")
    @app_commands.choices(category=[
        app_commands.Choice(name="SMPs", value="smps"),
        app_commands.Choice(name="Public", value="public"),
        app_commands.Choice(name="Bedrock", value="bedrock"),
        app_commands.Choice(name="Other", value="other"),
    ])
    async def partner(self, interaction: discord.Interaction,
                      category: str):
        if interaction.user.get_role(
            self.bot.cfg["partnership_manager_role_id"]
        ) is None:
            await interaction.response.send_message(
                "Partnership Manager only.", ephemeral=True
            )
            return
        await interaction.response.send_modal(PartnerAdModal(category))


async def setup(bot):
    await bot.add_cog(Partners(bot))
