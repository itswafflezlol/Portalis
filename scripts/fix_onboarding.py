"""One-time: fix onboarding prompt (labels didn't match roles) + add News."""
import asyncio
import sys
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TOKEN, load_config  # noqa: E402


async def main():
    client = discord.Client(intents=discord.Intents.default())
    cfg = load_config()
    ping = cfg["ping_roles"]

    @client.event
    async def on_ready():
        guild = client.get_guild(cfg["guild_id"])

        prompt = discord.OnboardingPrompt(
            type=discord.OnboardingPromptType.multiple_choice,
            title="Pick what you want to be pinged for!",
            single_select=False,
            required=True,
            in_onboarding=True,
            options=[
                discord.OnboardingPromptOption(
                    title="News", emoji="📰",
                    description="Server updates & announcements",
                    roles=[ping["news"]],
                ),
                discord.OnboardingPromptOption(
                    title="Giveaways", emoji="🎉",
                    description="New giveaways & winner draws",
                    roles=[ping["giveaway"]],
                ),
                discord.OnboardingPromptOption(
                    title="Polls", emoji="📊",
                    description="Community votes & polls",
                    roles=[ping["polls"]],
                ),
                discord.OnboardingPromptOption(
                    title="Events", emoji="🎪",
                    description="Server events & competitions",
                    roles=[ping["event"]],
                ),
            ],
        )

        ob = await guild.edit_onboarding(
            prompts=[prompt], reason="Fix mismatched roles + add all ping roles"
        )
        print("enabled:", ob.enabled, flush=True)
        for p in ob.prompts:
            print(f"prompt: {p.title!r}", flush=True)
            for o in p.options:
                print(f"  - {o.title!r} roles={o.role_ids}", flush=True)

        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
