import logging

import discord
from discord.ext import commands

from config import TOKEN, load_config
from storage import Store
from cogs.tickets import (
    PartnershipQuestionsView,
    TicketChannelView,
    TicketPanelView,
)
from cogs.applications import ApplyPanelView
from cogs.partners import PartnerPanelView

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class Portalis(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="SMP Portal"
            ),
        )
        self.cfg = load_config()
        self.store = Store()

    async def setup_hook(self):
        await self.store.connect()

        self.add_view(TicketPanelView())
        self.add_view(TicketChannelView())
        self.add_view(PartnershipQuestionsView())
        self.add_view(ApplyPanelView())
        self.add_view(PartnerPanelView())

        for ext in ("cogs.tickets", "cogs.applications", "cogs.partners", "cogs.admin"):
            await self.load_extension(ext)

        guild_id = self.cfg.get("guild_id")
        if guild_id:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
        else:
            await self.tree.sync()

    async def on_ready(self):
        logging.getLogger("portalis").info("Logged in as %s", self.user)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in .env (see .env.example)")
    Portalis().run(TOKEN)
