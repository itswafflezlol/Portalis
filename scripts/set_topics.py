"""One-time: set topics on every channel except the Tickets category."""
import asyncio
import sys
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TOKEN, load_config  # noqa: E402

TICKETS_CAT = 1575245092963229747
PARTNERS_CAT = 1458566236936867951

TOPICS = {
    # About Us
    1458561036876648481: "Welcome to SMP Portal — find servers, promote yours, get work done.",
    1458561172411514993: "Server rules — read before chatting.",
    1464478255326298158: "Everything we offer: partnerships, paid ads, commissions, events & giveaways.",
    1458565709029183578: "Support the server — drop a boost!",
    1464408182439809252: "What you get for boosting the server.",
    # Important
    1458565327871934484: "Server news & announcements.",
    1489954969451888641: "Vote on community polls.",
    1502790219232186500: "Grab your ping roles — pick what you want to be notified about.",
    1575283338745221241: "Giveaways — press the button to enter.",
    1575283138903539913: "Server events & competitions.",
    1458568057873240125: "Open a ticket — partnerships, paid ads, applications, support.",
    # Partnerships
    1458566311033704478: "Our ad — copy it and post it in your server to partner with us.",
    1575253685582430268: "Partner ads — SMP servers.",
    1575254055037444116: "Partner ads — public & community servers.",
    1575254126697128136: "Partner ads — Bedrock servers.",
    1575254214370660587: "Partner ads — everything else.",
    # SMP Market
    1575313578733342835: "Apply to join the freelancer team.",
    1575311076759703703: "Order commissions from our freelancers.",
    1575311075778240592: "Browse freelancers by skill — art, plugins, skripts & more.",
    1575311077585977424: "Freelancer portfolios — see the work before you hire.",
    # Community
    1458555454295904331: "Chat with the community.",
    1575250765969236190: "Share screenshots, clips & creations.",
    1575250744184021013: "Bot commands go here.",
    1575250716417720420: "Promote your stuff — keep it in this channel.",
    1575250689079246898: "Suggest ideas for the server.",
    # Archive
    1512468788879298681: "Archived editing competition.",
    1473651480849285130: "Ban records.",
    # Staff
    1507402749694840872: "Staff announcements.",
    1575245391371436102: "Ticket transcripts & logs.",
    1575246968748253295: "Freelancer application reviews.",
    1575247018027253882: "Partnership proof reviews — approve or deny.",
    1575295051305721966: "Staff chat.",
    1575295076366688366: "Bug reports & bot issues.",
    1575316304154591425: "Payment tracking — paid ads & pings.",
    1575316305462960211: "Notes on members — warnings, history.",
    1575316306515730442: "Staff task list.",
    1575316311637102762: "Staff guides — how everything works.",
    # Freelancers
    1575319789583208578: "Freelancer rules — read before taking a job.",
    1575319794477957160: "Freelancer & staff chat.",
}

PAID_AD_TOPIC = "💎 Paid ad channel."


async def main():
    client = discord.Client(intents=discord.Intents.default())
    cfg = load_config()

    @client.event
    async def on_ready():
        guild = client.get_guild(cfg["guild_id"])
        print("guild:", guild.name, "channels:", len(guild.channels), flush=True)
        done = skipped_n = 0
        for ch in guild.channels:
            if not isinstance(ch, (discord.TextChannel, discord.ForumChannel)):
                continue
            if ch.category_id == TICKETS_CAT:
                continue
            topic = TOPICS.get(ch.id)
            if topic is None:
                # leftover paid-ad channels in the Partnerships category
                if ch.category_id == PARTNERS_CAT:
                    topic = PAID_AD_TOPIC
                else:
                    print("skipped:", ch.name, flush=True)
                    skipped_n += 1
                    continue
            if ch.topic == topic:
                print("same:", ch.name, flush=True)
                continue
            try:
                await ch.edit(topic=topic)
            except discord.HTTPException as e:
                print("FAILED:", ch.name, e, flush=True)
                continue
            done += 1
            print("set:", ch.name, flush=True)
        print(f"DONE. set={done} skipped={skipped_n}", flush=True)
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
