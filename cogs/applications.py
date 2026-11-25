import discord
from discord.ext import commands

from branding import RED
from cogs.tickets import is_staff


def review_embed(app: dict, status: str, by: str = "", reason: str = "") -> discord.Embed:
    e = discord.Embed(title="💼 Freelancer Application", color=RED)
    e.add_field(name="Applicant", value=f"<@{app['user_id']}>", inline=True)
    e.add_field(name="Service", value=app["service"], inline=True)
    e.add_field(name="Portfolio / links", value=app["portfolio"], inline=False)
    e.add_field(name="Experience", value=app["experience"], inline=False)
    e.add_field(name="Why pick them", value=app["why"], inline=False)
    e.set_footer(text=f"Application #{app['id']} · {status}" + (f" by {by}" if by else ""))
    if reason:
        e.add_field(name="Reason", value=reason, inline=False)
    return e


class ApplyPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Apply to be a Freelancer", style=discord.ButtonStyle.danger,
        emoji="💼", custom_id="portal:apply_open",
    )
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal())


class ApplicationModal(discord.ui.Modal, title="Freelancer Application"):
    service = discord.ui.TextInput(
        label="What do you do?",
        placeholder="e.g. Plugin dev, builder, designer, video editor",
        max_length=100,
    )
    portfolio = discord.ui.TextInput(
        label="Portfolio / links",
        placeholder="Show us your work",
        style=discord.TextStyle.paragraph, max_length=500,
    )
    experience = discord.ui.TextInput(
        label="Experience",
        placeholder="How long, past projects or clients",
        style=discord.TextStyle.paragraph, max_length=500,
    )
    why = discord.ui.TextInput(
        label="Why should we pick you?",
        style=discord.TextStyle.paragraph, max_length=500, required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        bot = interaction.client
        channel = interaction.guild.get_channel(bot.cfg["applications_channel_id"])
        if channel is None:
            await interaction.response.send_message(
                "Applications aren't set up yet — set `applications_channel_id` "
                "in config.json.", ephemeral=True,
            )
            return

        app = {
            "id": bot.store.new_id(),
            "user_id": interaction.user.id,
            "service": self.service.value,
            "portfolio": self.portfolio.value,
            "experience": self.experience.value,
            "why": self.why.value or "—",
            "status": "pending",
        }
        bot.store.data["applications"][str(app["id"])] = app
        bot.store.save()

        await channel.send(
            embed=review_embed(app, "Pending"),
            view=ApplicationReviewView(app["id"]),
        )
        await interaction.response.send_message(
            "Application submitted — the team will review it soon.", ephemeral=True
        )


class DenyModal(discord.ui.Modal, title="Deny application"):
    reason = discord.ui.TextInput(
        label="Reason (sent to the applicant)",
        style=discord.TextStyle.paragraph, max_length=300, required=False,
    )

    def __init__(self, app_id: int):
        super().__init__()
        self.app_id = app_id

    async def on_submit(self, interaction: discord.Interaction):
        await decide(interaction, self.app_id, approved=False,
                     reason=self.reason.value or "No reason given.")


async def decide(interaction: discord.Interaction, app_id: int,
                 approved: bool, reason: str = ""):
    bot = interaction.client
    app = bot.store.data["applications"].get(str(app_id))
    if app is None or app["status"] != "pending":
        await interaction.response.send_message(
            "This application was already handled.", ephemeral=True
        )
        return

    app["status"] = "accepted" if approved else "denied"
    bot.store.save()

    user = interaction.guild.get_member(app["user_id"])
    if approved:
        role = interaction.guild.get_role(bot.cfg["freelancer_role_id"])
        if role and user:
            await user.add_roles(role, reason="Freelancer application accepted")
        if user:
            try:
                await user.send(
                    "🎉 Your freelancer application to **SMP Portal** was "
                    "**accepted**! Welcome aboard."
                )
            except discord.Forbidden:
                pass
        status = "Accepted"
    else:
        if user:
            try:
                await user.send(
                    "Your freelancer application to **SMP Portal** was "
                    f"**denied**.\nReason: {reason}"
                )
            except discord.Forbidden:
                pass
        status = "Denied"

    view = discord.ui.View()
    for action_row in interaction.message.components:
        for comp in action_row.children:
            view.add_item(discord.ui.Button(
                label=comp.label, style=comp.style, emoji=comp.emoji, disabled=True,
            ))
    await interaction.response.edit_message(
        embed=review_embed(app, status, str(interaction.user), reason), view=view,
    )


class ApplicationReviewView(discord.ui.View):
    def __init__(self, app_id: int):
        super().__init__(timeout=None)
        self.app_id = app_id
        self._add("Approve", discord.ButtonStyle.success, "ok", self._approve)
        self._add("Deny", discord.ButtonStyle.danger, "no", self._deny)

    def _add(self, label, style, suffix, cb):
        b = discord.ui.Button(
            label=label, style=style,
            custom_id=f"portal:app:{self.app_id}:{suffix}",
        )
        b.callback = cb
        self.add_item(b)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_staff(interaction.user, interaction.client.cfg):
            await interaction.response.send_message(
                "Staff only.", ephemeral=True
            )
            return False
        return True

    async def _approve(self, interaction: discord.Interaction):
        await decide(interaction, self.app_id, approved=True)

    async def _deny(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DenyModal(self.app_id))


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    for app in bot.store.data["applications"].values():
        if app["status"] == "pending":
            bot.add_view(ApplicationReviewView(app["id"]))
    await bot.add_cog(Applications(bot))
