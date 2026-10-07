import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger("DramaticNarrator.Narrator")

STYLE_CHOICES = [
    app_commands.Choice(name="🍷 Reality TV Confessional (Trashy Drama & Gossip)", value="reality_tv"),
    app_commands.Choice(name="⚖️ Courtroom Trial (Judge Judy / Crimes Against Chat)", value="courtroom"),
    app_commands.Choice(name="🚨 Breaking News Broadcast (Live Anchors & Crisis Alerts)", value="breaking_news"),
    app_commands.Choice(name="🏰 Medieval Fantasy Drama (Game of Thrones Parody)", value="medieval"),
    app_commands.Choice(name="🎙️ Nature Documentary (David Attenborough Wildlife)", value="nature_doc"),
]

STYLE_ICONS = {
    "reality_tv": ("🍷 Reality TV Episode Dispatch", 0xE91E63),
    "courtroom": ("⚖️ The High Court of Chat Shenanigans", 0xE67E22),
    "breaking_news": ("🚨 CHANNEL 6 BREAKING NEWS DISPATCH", 0xE74C3C),
    "medieval": ("🏰 Medieval Chronicle", 0x8B5A2B),
    "nature_doc": ("🎙️ Wildlife Field Observation", 0x2ECC71),
}

class NarratorCog(commands.Cog, name="Dramatic Narrator"):
    def __init__(self, bot):
        self.bot = bot
        self.ai = bot.ai_service

    @app_commands.command(
        name="recap",
        description="Dramatically summarizes recent server chatter in your chosen theatrical style."
    )
    @app_commands.describe(
        style="The theatrical narrative genre to chronicle the conversation in",
        limit="Number of recent messages to inspect (between 10 and 100, default: 50)"
    )
    @app_commands.choices(style=STYLE_CHOICES)
    async def recap(
        self,
        interaction: discord.Interaction,
        style: app_commands.Choice[str] = None,
        limit: app_commands.Range[int, 10, 100] = 50
    ):
        await interaction.response.defer(thinking=True)

        style_key = style.value if style else "medieval"
        channel = interaction.channel

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.followup.send("⚠️ The Narrator can only chronicle text channels and threads!", ephemeral=True)
            return

        messages = []
        try:
            async for msg in channel.history(limit=limit, oldest_first=False):
                # Skip bot commands, empty messages, or system messages
                if msg.author.bot or msg.content.startswith("/") or not msg.content.strip():
                    continue
                author_name = msg.author.display_name
                clean_text = msg.clean_content.replace("\n", " ")
                messages.append(f"{author_name}: {clean_text}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Alas! The Narrator lacks the sacred Read Message History permission in this realm.", ephemeral=True)
            return
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
            await interaction.followup.send(f"❌ A cosmic anomaly occurred while gathering scrolls: {e}", ephemeral=True)
            return

        if not messages:
            await interaction.followup.send("📜 The archives are empty! No mortal chatter was detected to narrate.", ephemeral=True)
            return

        # Reverse to chronological order
        messages.reverse()
        transcript = "\n".join(messages[-80:]) # Limit transcript window for optimal token usage

        try:
            recap_text = await self.ai.generate_recap(transcript, style_key=style_key)
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            await interaction.followup.send(f"⚠️ The muses have deserted the Narrator: {e}", ephemeral=True)
            return

        title_prefix, color = STYLE_ICONS.get(style_key, ("📜 Server Chronicle", 0x7289DA))

        # Discord embeds have a 4096 character limit for descriptions
        if len(recap_text) <= 4000:
            embed = discord.Embed(
                title=f"{title_prefix} — #{channel.name}",
                description=recap_text,
                color=color
            )
            embed.set_footer(text=f"Recapped from {len(messages)} messages • The Grand Server Historian")
            await interaction.followup.send(embed=embed)
        else:
            # Chunking for long essays
            chunks = [recap_text[i:i+3800] for i in range(0, len(recap_text), 3800)]
            for idx, chunk in enumerate(chunks):
                embed = discord.Embed(
                    title=f"{title_prefix} (Part {idx + 1}/{len(chunks)}) — #{channel.name}",
                    description=chunk,
                    color=color
                )
                if idx == len(chunks) - 1:
                    embed.set_footer(text=f"Recapped from {len(messages)} messages • The Grand Server Historian")
                if idx == 0:
                    await interaction.followup.send(embed=embed)
                else:
                    await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(NarratorCog(bot))
