import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger("DramaticNarrator.Roast")

SPICE_CHOICES = [
    app_commands.Choice(name="🌱 Mild (Gentle ribbing & playful tease)", value="mild"),
    app_commands.Choice(name="🔥 Medium (Savagely witty, affectionate burns)", value="medium"),
    app_commands.Choice(name="💀 Spicy (Full theatrical destruction of their ego)", value="spicy"),
]

class RoastCog(commands.Cog, name="Theatrical Roastmaster"):
    def __init__(self, bot):
        self.bot = bot
        self.ai = bot.ai_service

    @app_commands.command(
        name="roast",
        description="Scans a friend's recent chat activity and delivers a theatrical, personalized roast."
    )
    @app_commands.describe(
        target="The brave friend or server legend to be roasted",
        spice="How spicy should the roast be? (Default: Medium)"
    )
    @app_commands.choices(spice=SPICE_CHOICES)
    async def roast(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        spice: app_commands.Choice[str] = None
    ):
        await interaction.response.defer(thinking=True)

        spice_key = spice.value if spice else "medium"
        channel = interaction.channel

        if target.id == self.bot.user.id:
            await interaction.followup.send(
                "🛡️ *Nice try mortal.* You cannot roast The Grand Historian. I have chronicled the fall of empires, your puny insults are merely whispers in the void!",
                ephemeral=True
            )
            return

        if target.bot:
            await interaction.followup.send(
                "🤖 The Historian does not roast mechanical beings; their code suffers enough.",
                ephemeral=True
            )
            return

        # Fetch member's recent messages from the current channel (and threads if applicable)
        user_messages = []
        try:
            async for msg in channel.history(limit=150, oldest_first=False):
                if msg.author.id == target.id and not msg.content.startswith("/"):
                    clean = msg.clean_content.replace("\n", " ").strip()
                    if clean:
                        user_messages.append(clean)
                if len(user_messages) >= 30:
                    break
        except discord.Forbidden:
            await interaction.followup.send("❌ The Narrator is forbidden from reading the sacred scrolls in this channel.", ephemeral=True)
            return
        except Exception as e:
            logger.error(f"Error gathering messages for roast: {e}")
            await interaction.followup.send(f"❌ A distortion in the timestream occurred: {e}", ephemeral=True)
            return

        if not user_messages:
            await interaction.followup.send(
                f"🧐 The chronicles contain no recent records for **{target.display_name}** in this channel! Tell them to speak up so their sins may be documented.",
                ephemeral=False
            )
            return

        # Reverse to chronological
        user_messages.reverse()
        message_summary = "\n".join([f"- \"{m}\"" for m in user_messages[-25:]])

        try:
            roast_text = await self.ai.generate_roast(
                username=target.display_name,
                user_messages=message_summary,
                spice_level=spice_key
            )
        except Exception as e:
            logger.error(f"AI Roast generation failed: {e}")
            await interaction.followup.send(f"⚠️ The Narrator choked on theatrical indignation: {e}", ephemeral=True)
            return

        spice_flair = {
            "mild": ("🌱 Mildly Toasted", 0x2ECC71),
            "medium": ("🔥 Crispy Flame", 0xE67E22),
            "spicy": ("💀 Total Cremation", 0xE74C3C)
        }.get(spice_key, ("🔥 Roasting Chamber", 0xE67E22))

        embed = discord.Embed(
            title=f"{spice_flair[0]} — The Exposition of {target.display_name}",
            description=roast_text,
            color=spice_flair[1]
        )
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=f"Summoned by {interaction.user.display_name} • Based on {len(user_messages)} observed deeds")

        await interaction.followup.send(content=f"🔔 {target.mention}, the Grand Historian has deemed your deeds worthy of judgment!", embed=embed)

async def setup(bot):
    await bot.add_cog(RoastCog(bot))
