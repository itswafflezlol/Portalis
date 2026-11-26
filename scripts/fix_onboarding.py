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

        GENERAL = 1458555454295904331  # 💬・general — already public, no-op grant

        found = discord.OnboardingPrompt(
            type=discord.OnboardingPromptType.multiple_choice,
            title="How did you find us?",
            single_select=True,
            required=False,
            in_onboarding=True,
            options=[
                discord.OnboardingPromptOption(
                    title="Discord Discovery", emoji="🔍",
                    description="Found us in server discovery",
                    channels=[GENERAL],
                ),
                discord.OnboardingPromptOption(
                    title="A friend invited me", emoji="👋",
                    description="Someone sent me the invite",
                    channels=[GENERAL],
                ),
                discord.OnboardingPromptOption(
                    title="Partner server", emoji="🤝",
                    description="Saw our ad in another server",
                    channels=[GENERAL],
                ),
                discord.OnboardingPromptOption(
                    title="Social media", emoji="📱",
                    description="TikTok, YouTube, Twitter, etc.",
                    channels=[GENERAL],
                ),
                discord.OnboardingPromptOption(
                    title="Other", emoji="✨",
                    description="Somewhere else",
                    channels=[GENERAL],
                ),
            ],
        )

        try:
            ob = await guild.edit_onboarding(
                prompts=[prompt, found],
                reason="Fix roles + add ping roles + find-us prompt",
            )
            print("enabled:", ob.enabled, flush=True)
            for p in ob.prompts:
                print(f"prompt: {p.title!r}", flush=True)
                for o in p.options:
                    print(f"  - {o.title!r} roles={o.role_ids}", flush=True)
        except Exception as e:
            print("FAILED:", type(e).__name__, e, flush=True)

        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
