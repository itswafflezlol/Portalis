"""Welcomer: greets new members with a personalised banner card."""
import io
import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from branding import RED
from config import save_config

# the only role allowed to run /welcome-channel
WELCOME_ADMIN_ROLE_ID = 1458558939758198877

ASSETS = Path(__file__).resolve().parent.parent / "assets"
W, H = 1400, 480
RED_RGB = (0xED, 0x1C, 0x24)

CHANNELS = [
    ("📜 Read the rules", 1458561172411514993),
    ("🎭 Grab your ping roles", 1502790219232186500),
    ("🎉 Enter giveaways", 1575283338745221241),
    ("🤝 Advertise your server — open a partner ticket", 1458568057873240125),
    ("💬 Say hi", 1458555454295904331),
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    bundled = ASSETS / "fonts"
    for name in ("DejaVuSans-Bold.ttf", "segoeuib.ttf", "arialbd.ttf"):
        for p in (bundled / name,
                  Path(r"C:\Windows\Fonts") / name,
                  Path("/usr/share/fonts/truetype/dejavu") / name):
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _tracked(draw: ImageDraw.ImageDraw, xy, text: str,
             f: ImageFont.FreeTypeFont, tracking: int = 10):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill="white")
        x += int(draw.textlength(ch, font=f)) + tracking


def welcome_banner(member: discord.Member, avatar: bytes) -> io.BytesIO:
    """Satin bg + member avatar + their name — a personal welcome card."""
    bg = Image.open(ASSETS / "banner_bg.jpg").convert("RGB")
    ratio = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * ratio), int(bg.height * ratio)),
                   Image.LANCZOS)
    x = (bg.width - W) // 2
    y = (bg.height - H) // 2
    bg = ImageEnhance.Brightness(
        bg.crop((x, y, x + W, y + H))
    ).enhance(0.6)

    # darken from the right so the left side reads clean behind text
    grad = Image.new("L", (W, 1))
    for i in range(W):
        grad.putpixel((i, 0), int(120 * i / W))
    bg = Image.composite(Image.new("RGB", (W, H)), bg,
                         grad.resize((W, H))).convert("RGBA")

    # avatar in a red ring, left side
    size = 300
    av = Image.open(io.BytesIO(avatar)).convert("RGBA") \
        .resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    av.putalpha(mask)
    ring = Image.new("RGBA", (size + 20, size + 20), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((0, 0, size + 19, size + 19),
                                 outline=RED_RGB, width=8)
    ax, ay = 80, (H - size - 20) // 2
    bg.alpha_composite(ring, (ax, ay))
    bg.alpha_composite(av, (ax + 10, ay + 10))

    d = ImageDraw.Draw(bg)
    tx = ax + size + 70
    _tracked(d, (tx, 96), "WELCOME", _font(120))
    name = member.display_name
    f_name = _font(64 if len(name) <= 18 else 48)
    d.text((tx + 4, 260), name, font=f_name, fill="white")
    d.text((tx + 4, 350),
           f"member #{member.guild.member_count:,}",
           font=_font(38), fill=(255, 255, 255, 180))
    brand_f = _font(46)
    d.text((W - 60 - d.textlength("smpportal", font=brand_f), H - 80),
           "smpportal", font=brand_f, fill="white")

    buf = io.BytesIO()
    bg.convert("RGB").save(buf, "PNG")
    buf.seek(0)
    return buf


def welcome_view(member: discord.Member) -> discord.ui.LayoutView:
    ui = discord.ui
    view = discord.ui.LayoutView(timeout=None)
    links = "\n".join(f"• {t} — <#{cid}>" for t, cid in CHANNELS)
    view.add_item(ui.Container(
        ui.MediaGallery(discord.MediaGalleryItem(
            "attachment://welcome.png"
        )),
        ui.Separator(),
        ui.TextDisplay(
            f"## 👋 Welcome to SMP Portal, {member.mention}!\n"
            "Find servers. Promote yours. Get work done.\n\n"
            f"**Get started**\n{links}"
        ),
        ui.Separator(),
        ui.TextDisplay("-# SMP Portal · Official Discord"),
        accent_color=RED,
    ))
    return view


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        rid = self.bot.cfg.get("join_role_id")
        role = member.guild.get_role(rid) if rid else None
        if role is not None:
            try:
                await member.add_roles(role, reason="auto role on join")
            except discord.Forbidden:
                pass

        cid = self.bot.cfg.get("welcome_channel_id")
        ch = member.guild.get_channel(cid) if cid else None
        if ch is None:
            return
        try:
            avatar = await member.display_avatar.read()
            file = discord.File(
                welcome_banner(member, avatar), "welcome.png"
            )
            await ch.send(view=welcome_view(member), file=file)
        except discord.Forbidden:
            logging.getLogger("portalis").warning(
                "Welcome card blocked — no send/attach perms in #%s",
                ch.name,
            )
        except discord.HTTPException:
            logging.getLogger("portalis").exception(
                "Welcome card failed for %s", member
            )

    @app_commands.command(
        name="welcome-channel-test",
        description="Preview the welcome card in the set channel",
    )
    async def welcome_channel_test(self, interaction: discord.Interaction):
        if interaction.user.get_role(WELCOME_ADMIN_ROLE_ID) is None:
            await interaction.response.send_message(
                "You can't use this.", ephemeral=True
            )
            return
        cid = self.bot.cfg.get("welcome_channel_id")
        ch = interaction.guild.get_channel(cid) if cid else None
        if ch is None:
            await interaction.response.send_message(
                "No welcome channel set — use `/welcome-channel` first.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        avatar = await interaction.user.display_avatar.read()
        file = discord.File(
            welcome_banner(interaction.user, avatar), "welcome.png"
        )
        await ch.send(
            view=welcome_view(interaction.user), file=file,
        )
        await interaction.followup.send(
            f"Test welcome posted in {ch.mention}.", ephemeral=True
        )

    @app_commands.command(
        name="welcome-channel",
        description="Set where new members get welcomed",
    )
    @app_commands.describe(channel="Channel welcomes are posted in")
    async def welcome_channel(self, interaction: discord.Interaction,
                              channel: discord.TextChannel):
        if interaction.user.get_role(WELCOME_ADMIN_ROLE_ID) is None:
            await interaction.response.send_message(
                "You can't use this.", ephemeral=True
            )
            return
        self.bot.cfg["welcome_channel_id"] = channel.id
        save_config(self.bot.cfg)
        await interaction.response.send_message(
            f"New members will be welcomed in {channel.mention}.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Welcome(bot))
