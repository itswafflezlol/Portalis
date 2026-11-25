import random
import re
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from branding import RED, panel_file
from cogs.tickets import is_staff

DUR_RE = re.compile(r"^(\d+)\s*([smhdw])$", re.I)
MULT = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def has_tag(member: discord.Member, guild_id: int) -> bool:
    """True if the member wears this guild's server tag."""
    pg = getattr(member, "primary_guild", None)
    return bool(
        pg and pg.identity_enabled and pg.id == guild_id
    )


def _card(gid: str, gw: dict) -> "GiveawayView":
    if gw.get("ended"):
        winners = " ".join(f"<@{w}>" for w in gw.get("result", [])) \
            or "nobody"
        return GiveawayView(
            gid, gw["prize"], winners=winners, host=gw["host"],
        )
    ends = int(datetime.fromisoformat(gw["ends_at"]).timestamp())
    return GiveawayView(
        gid, gw["prize"], str(ends), len(gw["entries"]),
        gw["tag_required"], host=gw["host"],
        paused=gw.get("paused", False),
    )


class GiveawayView(discord.ui.LayoutView):
    """Giveaway card with a join button inside the embed."""

    def __init__(self, gid: str = "0", prize: str = "", ends: str = "",
                 entries: int = 0, tag: bool = True,
                 winners: str = None, host: str = "",
                 paused: bool = False):
        super().__init__(timeout=None)
        ui = discord.ui
        self.gid = gid

        join = ui.Button(
            label="Join giveaway", style=discord.ButtonStyle.danger,
            emoji="🎉", custom_id=f"portal:gw:{gid}",
        )
        join.callback = self._join

        if winners is not None:
            join.disabled = True
            body = (
                f"## 🎊 {prize}\n"
                f"Ended — winner(s): {winners}\n"
                f"-# Hosted by {host}"
            )
        elif paused:
            body = (
                f"## ⏸️ {prize}\n"
                f"**Paused** — the timer is frozen until staff resume "
                f"it · **{entries}** entered\n"
                f"-# Hosted by {host}"
            )
        else:
            body = (
                f"## 🎉 {prize}\n"
                f"Ends <t:{ends}:R> · **{entries}** entered"
                + (
                    "\n🔖 **Server tag required** — wear the SMP Portal "
                    "tag on your profile to join."
                    if tag else ""
                )
                + f"\n-# Hosted by {host} · press again to leave"
            )

        self.add_item(ui.Container(
            ui.TextDisplay(body),
            ui.ActionRow(join),
            accent_color=RED,
        ))

    async def _join(self, interaction: discord.Interaction):
        bot = interaction.client
        gw = bot.store.data.get("giveaways", {}).get(self.gid)
        if gw is None or gw.get("ended"):
            await interaction.response.send_message(
                "This giveaway is over.", ephemeral=True
            )
            return
        if gw.get("paused"):
            await interaction.response.send_message(
                "This giveaway is paused — try again later.",
                ephemeral=True,
            )
            return

        uid = interaction.user.id
        if uid in gw["entries"]:
            gw["entries"].remove(uid)
            await bot.store.save()
            await interaction.response.edit_message(
                view=_card(self.gid, gw)
            )
            await interaction.followup.send(
                "You left the giveaway.", ephemeral=True
            )
            return

        if gw["tag_required"] and not has_tag(
            interaction.user, interaction.guild.id
        ):
            await interaction.response.send_message(
                "You need the **SMP Portal server tag** on your profile "
                "to enter — enable it in your profile settings, then "
                "join.", ephemeral=True,
            )
            return

        gw["entries"].append(uid)
        await bot.store.save()
        await interaction.response.edit_message(view=_card(self.gid, gw))
        await interaction.followup.send("You're in! 🎉", ephemeral=True)


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self._sweeper.start()

    async def cog_unload(self):
        self._sweeper.cancel()

    @app_commands.command(
        name="giveaway", description="Start a giveaway in this channel"
    )
    @app_commands.describe(
        prize="What you're giving away",
        duration="e.g. 30m, 12h, 3d, 1w",
        winners="Number of winners",
        tag_required="Require wearing the SMP Portal server tag",
    )
    async def giveaway(self, interaction: discord.Interaction,
                       prize: str, duration: str, winners: int = 1,
                       tag_required: bool = True):
        if not is_staff(interaction.user, self.bot.cfg):
            await interaction.response.send_message(
                "Staff only.", ephemeral=True
            )
            return
        m = DUR_RE.match(duration.strip())
        if m is None:
            await interaction.response.send_message(
                "Duration looks off — use `30m`, `12h`, `3d` or `1w`.",
                ephemeral=True,
            )
            return
        if not 1 <= winners <= 20:
            await interaction.response.send_message(
                "Winners must be 1–20.", ephemeral=True
            )
            return
        secs = int(m.group(1)) * MULT[m.group(2).lower()]
        if secs < 60:
            await interaction.response.send_message(
                "Minimum duration is 1 minute.", ephemeral=True
            )
            return

        ends = datetime.now(timezone.utc) + timedelta(seconds=secs)
        gw = {
            "channel_id": interaction.channel.id, "prize": prize,
            "ends_at": ends.isoformat(), "tag_required": tag_required,
            "n_winners": winners, "host": interaction.user.display_name,
            "entries": [], "ended": False,
        }
        await interaction.response.send_message(
            "Giveaway posted.", ephemeral=True
        )
        msg = await interaction.channel.send(
            view=GiveawayView(
                "0", prize, str(int(ends.timestamp())), 0,
                tag_required, host=gw["host"],
            ),
            files=[panel_file("giveaway.gif")],
        )
        gid = str(msg.id)
        self.bot.store.data.setdefault("giveaways", {})[gid] = gw
        await self.bot.store.save()
        await msg.edit(view=_card(gid, gw))

    def _find_gw(self, interaction: discord.Interaction,
                 message_id: str = None, need_active: bool = True):
        """Locate a giveaway by message ID, or newest in this channel."""
        gws = self.bot.store.data.get("giveaways", {})
        if message_id:
            return message_id, gws.get(message_id)
        cands = [
            (gid, gw) for gid, gw in gws.items()
            if gw["channel_id"] == interaction.channel.id
            and (not need_active or not gw.get("ended"))
        ]
        if not cands:
            return None, None
        return max(cands, key=lambda kv: int(kv[0]))

    @app_commands.command(
        name="giveawayend", description="End a giveaway right now"
    )
    @app_commands.describe(
        message_id="Giveaway message ID (default: newest in this channel)"
    )
    async def giveawayend(self, interaction: discord.Interaction,
                          message_id: str = None):
        if not is_staff(interaction.user, self.bot.cfg):
            await interaction.response.send_message(
                "Staff only.", ephemeral=True
            )
            return
        gid, gw = self._find_gw(interaction, message_id)
        if gw is None or gw.get("ended"):
            await interaction.response.send_message(
                "No active giveaway found — pass the message ID if "
                "it's in another channel.", ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "Ending it now…", ephemeral=True
        )
        await self._end(gid, gw)
        await self.bot.store.save()

    @app_commands.command(
        name="giveawaypause",
        description="Pause a giveaway — run again to resume",
    )
    @app_commands.describe(
        message_id="Giveaway message ID (default: newest in this channel)"
    )
    async def giveawaypause(self, interaction: discord.Interaction,
                            message_id: str = None):
        if not is_staff(interaction.user, self.bot.cfg):
            await interaction.response.send_message(
                "Staff only.", ephemeral=True
            )
            return
        gid, gw = self._find_gw(interaction, message_id)
        if gw is None or gw.get("ended"):
            await interaction.response.send_message(
                "No active giveaway found.", ephemeral=True
            )
            return

        now = datetime.now(timezone.utc)
        if gw.get("paused"):
            # resume — push the deadline out by the paused time
            paused_at = datetime.fromisoformat(gw["paused_at"])
            ends = datetime.fromisoformat(gw["ends_at"])
            gw["ends_at"] = (ends + (now - paused_at)).isoformat()
            gw["paused"] = False
            gw.pop("paused_at", None)
            text = "▶️ Resumed — timer is running again."
        else:
            gw["paused"] = True
            gw["paused_at"] = now.isoformat()
            text = "⏸️ Paused — timer frozen, joins blocked."
        await self.bot.store.save()
        await self._edit_card(gid, gw)
        await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command(
        name="giveawayreroll",
        description="Pick new winner(s) for an ended giveaway",
    )
    @app_commands.describe(
        message_id="Giveaway message ID (default: newest in this channel)"
    )
    async def giveawayreroll(self, interaction: discord.Interaction,
                             message_id: str = None):
        if not is_staff(interaction.user, self.bot.cfg):
            await interaction.response.send_message(
                "Staff only.", ephemeral=True
            )
            return
        gid, gw = self._find_gw(interaction, message_id, need_active=False)
        if gw is None or not gw.get("ended"):
            await interaction.response.send_message(
                "No ended giveaway found — pass the message ID if "
                "it's in another channel.", ephemeral=True,
            )
            return
        pool = self._eligible(gw, interaction.guild)
        if not pool:
            await interaction.response.send_message(
                "No eligible entries to reroll — everyone left or "
                "dropped the tag.", ephemeral=True,
            )
            return
        random.shuffle(pool)
        gw["result"] = pool[:gw["n_winners"]]
        await self.bot.store.save()
        await self._edit_card(gid, gw)
        winners = " ".join(f"<@{w}>" for w in gw["result"]) or "nobody"
        await interaction.response.send_message(
            f"🔁 **{gw['prize']}** rerolled — new winner(s): {winners}"
        )

    async def _edit_card(self, gid: str, gw: dict):
        ch = self.bot.get_channel(gw["channel_id"])
        if ch is None:
            return
        try:
            msg = await ch.fetch_message(int(gid))
            await msg.edit(view=_card(gid, gw))
        except discord.HTTPException:
            pass

    def _eligible(self, gw: dict, guild) -> list:
        """Entry pool with leavers/tag-removers filtered out."""
        pool = []
        for uid in gw["entries"]:
            member = guild.get_member(uid) if guild else None
            if member is None:
                continue
            if gw["tag_required"] and not has_tag(member, guild.id):
                continue
            pool.append(uid)
        return pool

    async def _end(self, gid: str, gw: dict):
        gw["ended"] = True
        pool = self._eligible(
            gw, self.bot.get_guild(self.bot.cfg["guild_id"])
        )
        random.shuffle(pool)
        gw["result"] = pool[:gw["n_winners"]]
        await self._edit_card(gid, gw)
        ch = self.bot.get_channel(gw["channel_id"])
        if ch is not None:
            winners = " ".join(f"<@{w}>" for w in gw["result"]) or "nobody"
            await ch.send(
                f"🎊 **{gw['prize']}** — winner(s): {winners}"
            )

    @tasks.loop(seconds=60)
    async def _sweeper(self):
        gws = self.bot.store.data.get("giveaways", {})
        if not gws:
            return
        guild = self.bot.get_guild(self.bot.cfg["guild_id"])
        now = datetime.now(timezone.utc)
        dirty = False
        for gid, gw in gws.items():
            if gw.get("ended"):
                continue
            # kick entrants who removed the server tag
            if gw["tag_required"] and guild is not None:
                kicked = False
                for uid in list(gw["entries"]):
                    member = guild.get_member(uid)
                    if member is None or not has_tag(member, guild.id):
                        gw["entries"].remove(uid)
                        kicked = dirty = True
                if kicked:
                    await self._edit_card(gid, gw)
            if not gw.get("paused") and \
                    datetime.fromisoformat(gw["ends_at"]) <= now:
                await self._end(gid, gw)
                dirty = True
        if dirty:
            await self.bot.store.save()

    @_sweeper.before_loop
    async def _before_sweeper(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    for gid, gw in bot.store.data.get("giveaways", {}).items():
        if not gw.get("ended"):
            bot.add_view(GiveawayView(gid))
    await bot.add_cog(Giveaways(bot))
