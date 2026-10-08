import asyncio
import logging
import sys
import discord
from discord.ext import commands

import config
from ai_service import AIService
import db

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Set up logging with expressive formatting
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DramaticNarrator")

class DramaticNarratorBot(commands.Bot):
    def __init__(self):
        # Configure Intents
        # NOTE: 'message_content' intent is required to fetch channel history!
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        super().__init__(
            command_prefix="!", # Fallback prefix
            intents=intents,
            help_command=None
        )

        self.ai_service = AIService()

    async def setup_hook(self):
        # Initialize SQLite database
        db.init_db()
        logger.info("Initialized SQLite database in data/vault.db")

        # Load Cogs
        initial_extensions = [
            "cogs.narrator",
            "cogs.roast",
            "cogs.historian",
            "cogs.quotes",
            "cogs.economy",
            "cogs.help"
        ]
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded Cog: {ext}")
            except Exception as e:
                logger.error(f"Failed to load cog {ext}: {e}")

        # Sync Slash Commands globally
        logger.info("Synchronizing application slash commands with Discord...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} Slash command(s).")
        except Exception as e:
            logger.error(f"Error syncing application commands: {e}")

    async def on_ready(self):
        logger.info(f"🗣️ The Yapper has entered the realm as {self.user} (ID: {self.user.id})")
        logger.info(f"Serving across {len(self.guilds)} guild(s). Ready to yap about your drama!")

        # Sync commands directly to every currently connected guild
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Synced {len(synced)} commands directly to guild: {guild.name} (ID: {guild.id})")
            except Exception as e:
                logger.warning(f"Could not direct-sync guild {guild.name}: {e}")

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="everyone's yapping | /yapper_help"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"🎉 Joined new guild: {guild.name} (ID: {guild.id}). Syncing commands...")
        try:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(f"Successfully synced {len(synced)} command(s) to new guild: {guild.name}")
        except Exception as e:
            logger.error(f"Failed to sync commands to new guild {guild.name}: {e}")

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        logger.error(f"Command error in {interaction.command.name if interaction.command else 'Unknown'}: {error}")
        msg = f"⚡ The dramatic tension caused an unexpected anomaly: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Instant manual sync trigger: type '!sync' in any server where the bot has joined
        if message.content.strip().lower() == "!sync" and message.guild:
            try:
                self.tree.copy_global_to(guild=message.guild)
                synced = await self.tree.sync(guild=message.guild)
                await message.channel.send(f"✅ **Instant Guild Sync Complete!** Synced {len(synced)} slash commands directly to **{message.guild.name}**!\n*(If commands still don't show, press Ctrl+R to reload Discord)*")
            except Exception as e:
                await message.channel.send(f"❌ Sync failed: `{e}`")
            return

        await self.process_commands(message)

async def main():
    missing_vars = config.validate_config()
    if missing_vars:
        logger.warning(
            "⚠️  Configuration incomplete!\n"
            f"The following variables are missing in your .env:\n  - " + "\n  - ".join(missing_vars) + "\n\n"
            "Please copy .env.example to .env and insert your tokens.\n"
        )

    if not config.DISCORD_TOKEN:
        logger.error("❌ Cannot start bot without DISCORD_TOKEN. Exiting.")
        return

    bot = DramaticNarratorBot()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("The Narrator bows and exits the stage gracefully.")
