import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import logging
from datetime import datetime, timezone
import db

logger = logging.getLogger("DramaticNarrator.Quotes")

VAULT_EMOJIS = {"📸", "💬"}

class QuoteTriviaView(discord.ui.View):
    def __init__(self, correct_author_id: int, options: list):
        super().__init__(timeout=45.0)
        self.correct_author_id = correct_author_id
        self.answered_users = set()

        # Add buttons for choices
        for author_id, author_name in options:
            btn = discord.ui.Button(
                label=author_name[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"trivia_{author_id}"
            )
            btn.callback = self.make_callback(author_id, author_name)
            self.add_item(btn)

    def make_callback(self, author_id: int, author_name: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.answered_users:
                await interaction.response.send_message("❌ You have already cast your guess for this round!", ephemeral=True)
                return

            self.answered_users.add(interaction.user.id)

            if author_id == self.correct_author_id:
                # Award points to the guesser!
                awarded = 100
                new_bal = db.add_points(interaction.user.id, interaction.guild_id, awarded)
                await interaction.response.send_message(
                    f"🎉 **CORRECT!** {interaction.user.mention} identified the speaker (**{author_name}**)!\n"
                    f"💰 You were rewarded **{awarded} Gold Coins**! (New Balance: {new_bal})",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"💀 **WRONG!** It was NOT **{author_name}**. The server historian laughs at your ignorance.",
                    ephemeral=True
                )

        return callback

class QuotesCog(commands.Cog, name="Quote Vault"):
    def __init__(self, bot):
        self.bot = bot
        self.daily_flashback_loop.start()

    def cog_unload(self):
        self.daily_flashback_loop.cancel()

    # --- Reaction Listener to Archive Quotes ---
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji.name) not in VAULT_EMOJIS:
            return

        if not payload.guild_id:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except Exception:
                return

        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception as e:
            logger.debug(f"Could not fetch message {payload.message_id}: {e}")
            return

        # Don't archive bots or empty messages
        if message.author.bot or not message.content.strip():
            return

        # Fetch capturer name
        capturer_name = "Unknown Citizen"
        guild = self.bot.get_guild(payload.guild_id)
        if guild:
            member = guild.get_member(payload.user_id)
            if member:
                capturer_name = member.display_name

        quote_id = db.add_quote(
            guild_id=payload.guild_id,
            channel_id=payload.channel_id,
            message_id=payload.message_id,
            author_id=message.author.id,
            author_name=message.author.display_name,
            content=message.clean_content,
            jump_url=message.jump_url,
            captured_by_id=payload.user_id,
            captured_by_name=capturer_name
        )

        if quote_id:
            # Send a subtle confirmation reaction or message
            try:
                await message.add_reaction("🏛️")
            except Exception:
                pass
            logger.info(f"Archived Quote #{quote_id} from {message.author.display_name} in guild {payload.guild_id}")

    # --- Slash Commands ---
    @app_commands.command(
        name="quote",
        description="Pulls a random hilarious or embarrassing out-of-context quote from the server vault."
    )
    async def random_quote(self, interaction: discord.Interaction):
        quote = db.get_random_quote(interaction.guild_id)
        if not quote:
            await interaction.response.send_message(
                "📭 The Quote Vault is empty! React to funny messages with 📸 or 💬 to archive them.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📸 Vault Exhibit #{quote['id']}",
            description=f"> *\"{quote['content']}\"*",
            color=0xF1C40F
        )
        embed.set_author(name=f"— {quote['author_name']}")
        embed.add_field(name="🔗 Source", value=f"[Jump to Message]({quote['jump_url']})", inline=True)
        embed.set_footer(text=f"Preserved by {quote['captured_by_name']} • Out of Context Vault")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="quoteleaderboard",
        description="Displays the members who have the most quoted lines in the vault."
    )
    async def quote_leaderboard(self, interaction: discord.Interaction):
        leaders = db.get_quote_leaderboard(interaction.guild_id, limit=10)
        total = db.get_total_quotes(interaction.guild_id)

        if not leaders:
            await interaction.response.send_message(
                "📭 No quotes have been archived yet! React with 📸 or 💬 to get on the board.",
                ephemeral=True
            )
            return

        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for rank, (name, count) in enumerate(leaders, start=1):
            badge = medals[rank - 1] if rank <= 3 else f"#{rank}"
            lines.append(f"{badge} **{name}** — **{count}** quote{'s' if count != 1 else ''}")

        embed = discord.Embed(
            title="🏆 Hall of Infamy — Most Quoted Legends",
            description="\n".join(lines),
            color=0xF39C12
        )
        embed.set_footer(text=f"Total artifacts preserved in vault: {total}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="whosaidit",
        description="Trivia Game: Guess which server friend uttered this iconic out-of-context quote!"
    )
    async def who_said_it(self, interaction: discord.Interaction):
        quote = db.get_random_quote(interaction.guild_id)
        if not quote:
            await interaction.response.send_message(
                "📭 Not enough quotes in the vault! React to messages with 📸 or 💬 first.",
                ephemeral=True
            )
            return

        authors = db.get_all_quote_authors(interaction.guild_id)
        correct_author = (quote["author_id"], quote["author_name"])

        # Filter out correct author and pick up to 3 random distractors
        distractors = [a for a in authors if a[0] != correct_author[0]]
        random.shuffle(distractors)
        chosen_distractors = distractors[:3]

        options = [correct_author] + chosen_distractors
        random.shuffle(options)

        embed = discord.Embed(
            title="🎯 Who Said It? — Server Trivia",
            description=(
                f"**\" {quote['content']} \"**\n\n"
                f"Who was reckless enough to utter these immortal words?\n"
                f"*(Click the button below to guess! Correct answer wins 100 Coins!)*"
            ),
            color=0x9B59B6
        )
        embed.set_footer(text="Round expires in 45 seconds • First correct guesser wins!")

        view = QuoteTriviaView(correct_author_id=quote["author_id"], options=options)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(
        name="setflashback",
        description="Sets the channel where the Daily Flashback quote will be announced automatically."
    )
    @app_commands.describe(channel="The channel for daily flashback memories")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_flashback(self, interaction: discord.Interaction, channel: discord.TextChannel):
        db.set_flashback_channel(interaction.guild_id, channel.id)
        await interaction.response.send_message(
            f"✅ **Daily Flashback Channel Set!** The Grand Historian will now post historical quotes to {channel.mention} every day.",
            ephemeral=True
        )

    # --- Background Loop for Daily Flashback ---
    @tasks.loop(minutes=30)
    async def daily_flashback_loop(self):
        await self.bot.wait_until_ready()
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        guild_settings = db.get_all_flashback_guilds()
        for setting in guild_settings:
            guild_id = setting["guild_id"]
            channel_id = setting["flashback_channel_id"]
            last_date = setting["last_flashback_date"]

            if last_date == today_str:
                continue # Already posted today

            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue

            quote = db.get_random_quote(guild_id)
            if not quote:
                continue

            embed = discord.Embed(
                title="🌅 Daily Flashback — From the Out of Context Vault",
                description=f"> *\"{quote['content']}\"*\n\n— **{quote['author_name']}**",
                color=0xE67E22
            )
            embed.add_field(name="📍 Context", value=f"[Visit Original Incident]({quote['jump_url']})")
            embed.set_footer(text=f"Archived by {quote['captured_by_name']} • Memory of the Day")

            try:
                await channel.send(content="🔔 **A blast from the server's past has resurfaced!**", embed=embed)
                db.update_flashback_date(guild_id, today_str)
                logger.info(f"Dispatched daily flashback to guild {guild_id}")
            except Exception as e:
                logger.error(f"Failed to send daily flashback in guild {guild_id}: {e}")

async def setup(bot):
    await bot.add_cog(QuotesCog(bot))
