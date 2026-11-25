import discord
from discord.ext import commands

from branding import RED, brand_embed, brand_files
from cogs.tickets import is_staff


def review_embed(req: dict, status: str, by: str = "",
                 reason: str = "") -> discord.Embed:
    e = discord.Embed(title="🤝 Partner / Advertising Request", color=RED)
    e.add_field(name="Server", value=req["server"], inline=True)
    e.add_field(name="Members", value=req["members"], inline=True)
    e.add_field(name="Owner", value=f"<@{req['user_id']}>", inline=True)
    e.add_field(name="Invite", value=req["invite"], inline=False)
    e.add_field(name="Ad text", value=req["ad"], inline=False)
    e.set_footer(text=f"Request #{req['id']} · {status}" + (f" by {by}" if by else ""))
    if reason:
        e.add_field(name="Reason", value=reason, inline=False)
    return e


class PartnerPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Advertise your server", style=discord.ButtonStyle.danger,
        emoji="📣", custom_id="portal:partner_open",
    )
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PartnerModal())


class PartnerModal(discord.ui.Modal, title="Partner / Advertise with us"):
    server = discord.ui.TextInput(
        label="Server name", max_length=100,
    )
    invite = discord.ui.TextInput(
        label="Permanent invite link",
        placeholder="https://discord.gg/…", max_length=100,
    )
    members = discord.ui.TextInput(
        label="Member count", max_length=20,
    )
    ad = discord.ui.TextInput(
        label="Ad text — what should we post?",
        style=discord.TextStyle.paragraph, max_length=900,
    )

    async def on_submit(self, interaction: discord.Interaction):
        bot = interaction.client
        channel = interaction.guild.get_channel(bot.cfg["partners_channel_id"])
        if channel is None:
            await interaction.response.send_message(
                "Partnerships aren't set up yet — set `partners_channel_id` "
                "in config.json.", ephemeral=True,
            )
            return

        req = {
            "id": await bot.store.new_id(),
            "user_id": interaction.user.id,
            "server": self.server.value,
            "invite": self.invite.value,
            "members": self.members.value,
            "ad": self.ad.value,
            "status": "pending",
        }
        bot.store.data["partners"][str(req["id"])] = req
        await bot.store.save()

        await channel.send(
            embed=review_embed(req, "Pending"), view=PartnerReviewView(req["id"]),
        )
        await interaction.response.send_message(
            "Request submitted — the team will review it soon.", ephemeral=True
        )


class PartnerDenyModal(discord.ui.Modal, title="Deny partner request"):
    reason = discord.ui.TextInput(
        label="Reason (sent to the user)",
        style=discord.TextStyle.paragraph, max_length=300, required=False,
    )

    def __init__(self, req_id: int):
        super().__init__()
        self.req_id = req_id

    async def on_submit(self, interaction: discord.Interaction):
        await decide(interaction, self.req_id, approved=False,
                     reason=self.reason.value or "No reason given.")


async def decide(interaction: discord.Interaction, req_id: int,
                 approved: bool, reason: str = ""):
    bot = interaction.client
    req = bot.store.data["partners"].get(str(req_id))
    if req is None or req["status"] != "pending":
        await interaction.response.send_message(
            "This request was already handled.", ephemeral=True
        )
        return

    req["status"] = "accepted" if approved else "denied"
    await bot.store.save()

    user = interaction.guild.get_member(req["user_id"])
    if approved:
        role = interaction.guild.get_role(bot.cfg["partner_role_id"])
        if role and user:
            await user.add_roles(role, reason="Partner request accepted")

        ads = interaction.guild.get_channel(bot.cfg["ads_channel_id"])
        if ads is not None:
            ad = brand_embed(
                f"🤝 {req['server']}",
                f"{req['ad']}\n\n**Join:** {req['invite']}\n"
                f"**Members:** {req['members']}",
            )
            ad.set_footer(text="SMP Portal · Partner")
            await ads.send(embed=ad, files=brand_files())

        if user:
            try:
                await user.send(
                    f"🎉 Your server **{req['server']}** was accepted as a "
                    "**SMP Portal partner** — your ad is live!"
                )
            except discord.Forbidden:
                pass
        status = "Accepted"
    else:
        if user:
            try:
                await user.send(
                    f"Your partner request for **{req['server']}** was "
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
        embed=review_embed(req, status, str(interaction.user), reason), view=view,
    )


class PartnerReviewView(discord.ui.View):
    def __init__(self, req_id: int):
        super().__init__(timeout=None)
        self.req_id = req_id
        self._add("Approve", discord.ButtonStyle.success, "ok", self._approve)
        self._add("Deny", discord.ButtonStyle.danger, "no", self._deny)

    def _add(self, label, style, suffix, cb):
        b = discord.ui.Button(
            label=label, style=style,
            custom_id=f"portal:partner:{self.req_id}:{suffix}",
        )
        b.callback = cb
        self.add_item(b)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_staff(interaction.user, interaction.client.cfg):
            await interaction.response.send_message("Staff only.", ephemeral=True)
            return False
        return True

    async def _approve(self, interaction: discord.Interaction):
        await decide(interaction, self.req_id, approved=True)

    async def _deny(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PartnerDenyModal(self.req_id))


class Partners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    for req in bot.store.data["partners"].values():
        if req["status"] == "pending":
            bot.add_view(PartnerReviewView(req["id"]))
    await bot.add_cog(Partners(bot))
