import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
from datetime import datetime, timezone
import logging

logger = logging.getLogger("DramaticNarrator.Historian")
CHRONICLES_FILE = "data/chronicles.json"

def load_chronicles():
    if not os.path.exists(CHRONICLES_FILE):
        return []
    try:
        with open(CHRONICLES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading chronicles: {e}")
        return []

def save_chronicles(chronicles):
    os.makedirs(os.path.dirname(CHRONICLES_FILE), exist_ok=True)
    with open(CHRONICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(chronicles, f, indent=2, ensure_ascii=False)

class HistorianCog(commands.Cog, name="Server Historian"):
    def __init__(self, bot):
        self.bot = bot
        self.ai = bot.ai_service

    @app_commands.command(
        name="chronicle",
        description="Immortalize an epic server event into the Sacred Archives forever."
    )
    @app_commands.describe(
        title="Title of the legendary incident (e.g., 'The Great Pizza Hawaiian War')",
        description="What transpired during this fateful moment in mortal history?"
    )
    async def chronicle(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str
    ):
        await interaction.response.defer(thinking=True)

        try:
            saga_text = await self.ai.generate_chronicle(
                title=title,
                description=description,
                recorder_name=interaction.user.display_name
            )
        except Exception as e:
            logger.error(f"AI Chronicle generation failed: {e}")
            await interaction.followup.send(f"⚠️ The quill slipped and tore the parchment: {e}", ephemeral=True)
            return

        chronicles = load_chronicles()
        entry_id = len(chronicles) + 1
        record = {
            "id": entry_id,
            "title": title,
            "description_raw": description,
            "saga_text": saga_text,
            "author_id": interaction.user.id,
            "author_name": interaction.user.display_name,
            "guild_id": interaction.guild_id,
            "channel_name": interaction.channel.name if hasattr(interaction.channel, "name") else "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        chronicles.append(record)
        save_chronicles(chronicles)

        embed = discord.Embed(
            title=f"📜 Tome Entry #{entry_id}: {title}",
            description=saga_text,
            color=0xD4AF37 # Royal Gold
        )
        embed.set_footer(text=f"Etched into eternity by Scribe {interaction.user.display_name} • The Sacred Archives")

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="lore",
        description="Recites legendary lore from the Server's Sacred Archives."
    )
    @app_commands.describe(
        entry_number="Specific chronicle number to recall (leave blank for a random tale)"
    )
    async def lore(
        self,
        interaction: discord.Interaction,
        entry_number: int = None
    ):
        chronicles = load_chronicles()
        if not chronicles:
            await interaction.response.send_message(
                "📜 The Sacred Archives are presently devoid of recorded sagas! Use /chronicle to record the first myth.",
                ephemeral=True
            )
            return

        if entry_number is not None:
            entry = next((c for c in chronicles if c["id"] == entry_number), None)
            if not entry:
                await interaction.response.send_message(
                    f"🧐 Chronicle #{entry_number} does not exist in the archives! The current collection spans #1 to #{len(chronicles)}.",
                    ephemeral=True
                )
                return
        else:
            entry = random.choice(chronicles)

        embed = discord.Embed(
            title=f"🏛️ From the Annals of History: Tome #{entry['id']} — {entry['title']}",
            description=entry["saga_text"],
            color=0x9B59B6
        )
        embed.set_footer(text=f"Chronicled by {entry['author_name']} • Total Annals Recorded: {len(chronicles)}")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(HistorianCog(bot))
