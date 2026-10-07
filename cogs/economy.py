import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import logging
import time
import db

logger = logging.getLogger("DramaticNarrator.Economy")

SHOP_ITEMS = {
    "rename": {
        "name": "🏷️ Rename a Friend (24 Hours)",
        "cost": 500,
        "description": "Change any friend's nickname in the server for 24 hours.",
        "usage": "Use /buy_rename @friend new_nickname"
    },
    "chatmute": {
        "name": "🤐 Chat Timeout Curse",
        "cost": 300,
        "description": "Timeout a friend in chat. Choose duration: 1m (300c), 2m (500c), 5m (1000c), 10m (1800c).",
        "usage": "Use /buy_chatmute @friend [minutes]"
    },
    "chatunmute": {
        "name": "🕊️ Chat Bailout / Unmute",
        "cost": 400,
        "description": "Bail a friend out from chat timeout immediately. Cost scales with remaining time.",
        "usage": "Use /buy_chatunmute [@friend]"
    },
    "vcmute": {
        "name": "🤫 Voice Mute Curse",
        "cost": 300,
        "description": "Mute a friend in voice chat. Choose duration: 1m (300c), 2m (500c), 5m (1000c), 10m (1800c).",
        "usage": "Use /buy_vcmute @friend [minutes]"
    },
    "vcunmute": {
        "name": "📢 Voice Chat Bailout / Unmute",
        "cost": 400,
        "description": "Lift a friend's voice mute curse immediately. Cost scales with remaining time.",
        "usage": "Use /buy_vcunmute [@friend]"
    },
    "pin": {
        "name": "📌 Sacred Pin",
        "cost": 250,
        "description": "Pin any funny message of your choice to the channel.",
        "usage": "Use /buy_pin message_id"
    },
    "customrole": {
        "name": "🎨 Custom Vanity Role",
        "cost": 1000,
        "description": "Create a unique custom vanity role with your chosen name and color (HEX).",
        "usage": "Use /buy_role role_name hex_color"
    }
}

class EconomyCog(commands.Cog, name="Server Economy & Shop"):
    def __init__(self, bot):
        self.bot = bot
        self.perk_cleanup_loop.start()

    def cog_unload(self):
        self.perk_cleanup_loop.cancel()

    # --- Chat Activity Reward Listener ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Give 5 coins for chatting (1 minute cooldown per user)
        db.award_chat_activity(
            user_id=message.author.id,
            guild_id=message.guild.id,
            points=5,
            cooldown_sec=60
        )

    # --- Commands ---
    @app_commands.command(
        name="balance",
        description="Check your current wallet of server coins."
    )
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        points = db.get_balance(target.id, interaction.guild_id)
        embed = discord.Embed(
            title=f"💰 Vault Treasury — {target.display_name}",
            description=f"Current Wealth: **{points:,} Gold Coins**",
            color=0xF1C40F
        )
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Earn coins by chatting, /daily claims, and /whosaidit trivia!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="daily",
        description="Claim your daily server allowance (250 Gold Coins)."
    )
    async def daily(self, interaction: discord.Interaction):
        success, balance, remaining = db.claim_daily(
            user_id=interaction.user.id,
            guild_id=interaction.guild_id,
            reward=250,
            cooldown_sec=86400
        )

        if success:
            embed = discord.Embed(
                title="🎁 Daily Tribute Collected!",
                description=(
                    f"The Grand Historian rewards your loyalty with **+250 Gold Coins**!\n\n"
                    f"💳 **New Balance:** {balance:,} Coins"
                ),
                color=0x2ECC71
            )
            embed.set_footer(text="Return tomorrow for another daily tribute.")
            await interaction.response.send_message(embed=embed)
        else:
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await interaction.response.send_message(
                f"⏳ **Greedy mortal!** You have already collected your tribute today.\n"
                f"Come back in **{hours}h {minutes}m**.",
                ephemeral=True
            )

    @app_commands.command(
        name="rich",
        description="View the server's wealthiest oligarchs."
    )
    async def rich(self, interaction: discord.Interaction):
        leaders = db.get_rich_leaderboard(interaction.guild_id, limit=10)
        if not leaders:
            await interaction.response.send_message("💸 The server is bankrupt! Start chatting or claim /daily.", ephemeral=True)
            return

        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for rank, (uid, pts) in enumerate(leaders, start=1):
            badge = medals[rank - 1] if rank <= 3 else f"#{rank}"
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            lines.append(f"{badge} **{name}** — **{pts:,}** Coins")

        embed = discord.Embed(
            title="💎 The Forbes Server 10 — Wealthiest Citizens",
            description="\n".join(lines),
            color=0xD4AF37
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="shop",
        description="Browse exclusive server perks you can buy with your coins."
    )
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏪 The Black Market & Bazaar of Perks",
            description="Spend your hard-earned gold coins to prank friends or claim glory!\n",
            color=0x3498DB
        )

        for key, item in SHOP_ITEMS.items():
            embed.add_field(
                name=f"{item['name']} — 💰 {item['cost']} Coins",
                value=f"{item['description']}\n*Command:* {item['usage']}",
                inline=False
            )

        user_balance = db.get_balance(interaction.user.id, interaction.guild_id)
        embed.set_footer(text=f"Your Balance: {user_balance:,} Coins • Spend wisely!")
        await interaction.response.send_message(embed=embed)

    # --- Shop Purchase Commands ---

    @app_commands.command(
        name="buy_rename",
        description="Shop Perk: Change a friend's nickname for 24 hours (Cost: 500 Coins)."
    )
    @app_commands.describe(
        target="The friend you want to rename",
        new_nickname="The temporary nickname to bestow upon them"
    )
    async def buy_rename(self, interaction: discord.Interaction, target: discord.Member, new_nickname: str):
        cost = SHOP_ITEMS["rename"]["cost"]
        if not db.remove_points(interaction.user.id, interaction.guild_id, cost):
            await interaction.response.send_message(
                f"❌ Insufficient funds! You need **{cost} Coins** for this purchase.",
                ephemeral=True
            )
        # Prevent targeting bots or the bot itself
        if target.bot:
            await interaction.response.send_message("🛡️ Mechanical beings and the Grand Historian are immune to mortal curses!", ephemeral=True)
            return

        # Check permissions
        if target.id == interaction.guild.owner_id:
            db.add_points(interaction.user.id, interaction.guild_id, cost)
            await interaction.response.send_message("❌ The server owner is protected by royal divine right!", ephemeral=True)
            return

        bot_member = interaction.guild.me
        if target.top_role >= bot_member.top_role:
            db.add_points(interaction.user.id, interaction.guild_id, cost)
            await interaction.response.send_message("❌ The bot's role is too low in the role hierarchy to rename that member!", ephemeral=True)
            return

        original_nick = target.nick or target.name
        clean_nick = new_nickname[:32] # Discord limit

        try:
            await target.edit(nick=clean_nick, reason=f"Shop perk purchased by {interaction.user.name}")
            # Record expiration (24 hours = 86400s)
            db.add_active_perk(
                guild_id=interaction.guild_id,
                user_id=target.id,
                perk_type="rename",
                original_value=original_nick,
                duration_sec=86400
            )

            embed = discord.Embed(
                title="🏷️ Nickname Decree Enacted!",
                description=(
                    f"{interaction.user.mention} paid **{cost} Coins** to rebrand {target.mention} as:\n\n"
                    f"✨ **{clean_nick}** ✨\n\n"
                    f"*(This curse shall remain for 24 hours)*"
                ),
                color=0xE67E22
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            db.add_points(interaction.user.id, interaction.guild_id, cost)
            logger.error(f"Failed to edit nickname: {e}")
            await interaction.response.send_message(f"❌ Failed to rename target: {e}. Your coins were refunded.", ephemeral=True)

    @app_commands.command(
        name="buy_vcmute",
        description="Shop Perk: Mute a friend in voice chat with selectable duration."
    )
    @app_commands.describe(
        target="The friend in voice chat to temporarily silence",
        duration="Duration of the VC silence"
    )
    @app_commands.choices(duration=[
        app_commands.Choice(name="1 Minute (Cost: 300 Coins)", value=1),
        app_commands.Choice(name="2 Minutes (Cost: 500 Coins)", value=2),
        app_commands.Choice(name="5 Minutes (Cost: 1,000 Coins)", value=5),
        app_commands.Choice(name="10 Minutes (Cost: 1,800 Coins)", value=10),
    ])
    async def buy_vcmute(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        duration: app_commands.Choice[int] = None
    ):
        if target.bot:
            await interaction.response.send_message("🛡️ Mechanical beings and the Grand Historian are immune to VC curses!", ephemeral=True)
            return

        minutes = duration.value if duration else 2
        costs = {1: 300, 2: 500, 5: 1000, 10: 1800}
        cost = costs.get(minutes, 500)

        if not target.voice or not target.voice.channel:
            await interaction.response.send_message(f"❌ {target.display_name} is not currently in a voice channel!", ephemeral=True)
            return

        if not db.remove_points(interaction.user.id, interaction.guild_id, cost):
            await interaction.response.send_message(f"❌ Insufficient funds! You need **{cost} Coins** for a {minutes}-minute VC mute.", ephemeral=True)
            return

        duration_sec = minutes * 60
        try:
            await target.edit(mute=True, reason=f"VC Mute curse bought by {interaction.user.name} for {minutes}m")
            db.add_active_perk(
                guild_id=interaction.guild_id,
                user_id=target.id,
                perk_type="vcmute",
                original_value="true",
                duration_sec=duration_sec
            )

            embed = discord.Embed(
                title="🤫 The Cone of Silence Has Fallen!",
                description=(
                    f"{target.mention} has been silenced in VC for **{minutes} minute{'s' if minutes > 1 else ''}** "
                    f"by {interaction.user.mention}!\n\n"
                    f"💰 *Fee paid: {cost:,} Coins*"
                ),
                color=0x95A5A6
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            db.add_points(interaction.user.id, interaction.guild_id, cost)
            logger.error(f"VC mute error: {e}")
            await interaction.response.send_message(f"❌ Failed to mute: {e}. Coins refunded.", ephemeral=True)

    @app_commands.command(
        name="buy_chatmute",
        description="Shop Perk: Put a friend in chat timeout with selectable duration."
    )
    @app_commands.describe(
        target="The friend to temporarily silence in chat",
        duration="Duration of the timeout"
    )
    @app_commands.choices(duration=[
        app_commands.Choice(name="1 Minute (Cost: 300 Coins)", value=1),
        app_commands.Choice(name="2 Minutes (Cost: 500 Coins)", value=2),
        app_commands.Choice(name="5 Minutes (Cost: 1,000 Coins)", value=5),
        app_commands.Choice(name="10 Minutes (Cost: 1,800 Coins)", value=10),
    ])
    async def buy_chatmute(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        duration: app_commands.Choice[int] = None
    ):
        if target.bot:
            await interaction.response.send_message("🛡️ Mechanical beings and the Grand Historian cannot be silenced!", ephemeral=True)
            return

        minutes = duration.value if duration else 2
        costs = {1: 300, 2: 500, 5: 1000, 10: 1800}
        cost = costs.get(minutes, 500)

        if target.id == interaction.guild.owner_id:
            await interaction.response.send_message("❌ You cannot silence the server owner!", ephemeral=True)
            return

        bot_member = interaction.guild.me
        if target.top_role >= bot_member.top_role:
            await interaction.response.send_message("❌ The bot's role is too low in the role hierarchy to timeout that member!", ephemeral=True)
            return

        if not db.remove_points(interaction.user.id, interaction.guild_id, cost):
            await interaction.response.send_message(f"❌ Insufficient funds! You need **{cost} Coins** for a {minutes}-minute timeout.", ephemeral=True)
            return

        from datetime import datetime, timezone, timedelta
        duration_sec = minutes * 60
        until = datetime.now(timezone.utc) + timedelta(seconds=duration_sec)

        try:
            await target.timeout(until, reason=f"Chat timeout perk bought by {interaction.user.name} for {minutes}m")
            db.add_active_perk(
                guild_id=interaction.guild_id,
                user_id=target.id,
                perk_type="chatmute",
                original_value="true",
                duration_sec=duration_sec
            )

            embed = discord.Embed(
                title="🤐 The Vow of Chat Silence Has Commenced!",
                description=(
                    f"{target.mention} has been timed out for **{minutes} minute{'s' if minutes > 1 else ''}** "
                    f"by {interaction.user.mention}!\n\n"
                    f"💰 *Fee paid: {cost:,} Coins*\n"
                    f"*Their keyboard has been confiscated by the Grand Historian.*"
                ),
                color=0xE74C3C
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            db.add_points(interaction.user.id, interaction.guild_id, cost)
            logger.error(f"Chat mute error: {e}")
            await interaction.response.send_message(f"❌ Failed to timeout member: `{e}`. Coins refunded.", ephemeral=True)

    @app_commands.command(
        name="buy_chatunmute",
        description="Shop Perk: Bail out and unmute a friend (or yourself!) from chat timeout (Scales with time)."
    )
    @app_commands.describe(target="The timed-out friend to rescue (or yourself)")
    async def buy_chatunmute(self, interaction: discord.Interaction, target: discord.Member = None):
        target = target or interaction.user

        if not target.is_timed_out():
            await interaction.response.send_message(f"🧐 {target.display_name} is not currently timed out!", ephemeral=True)
            return

        # Calculate remaining time from Discord's timed_out_until
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        remaining_seconds = (target.timed_out_until - now).total_seconds()
        remaining_minutes = max(1, int(round(remaining_seconds / 60.0)))

        # Dynamic Bailout Pricing: 200 base fee + 200 per minute remaining (Min: 400c)
        cost = max(400, 200 + (remaining_minutes * 200))

        if not db.remove_points(interaction.user.id, interaction.guild_id, cost):
            await interaction.response.send_message(
                f"❌ Insufficient funds!\n"
                f"There are **~{remaining_minutes} min** left on {target.display_name}'s sentence.\n"
                f"Bailout costs **{cost:,} Coins**.",
                ephemeral=True
            )
            return

        try:
            await target.timeout(None, reason=f"Chat bailout purchased by {interaction.user.name}")
            db.remove_user_active_perk(interaction.guild_id, target.id, "chatmute")

            embed = discord.Embed(
                title="🕊️ Chat Freedom Granted!",
                description=(
                    f"{interaction.user.mention} paid **{cost:,} Coins** to post bail for {target.mention}!\n\n"
                    f"⏱️ *Sentence cancelled with {remaining_minutes} min remaining!*\n"
                    f"✨ *Their chat privileges have been fully restored!*"
                ),
                color=0x2ECC71
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            db.add_points(interaction.user.id, interaction.guild_id, cost)
            logger.error(f"Chat unmute error: {e}")
            await interaction.response.send_message(f"❌ Failed to lift timeout: `{e}`. Coins refunded.", ephemeral=True)

    @app_commands.command(
        name="buy_vcunmute",
        description="Shop Perk: Rescue and unmute a friend (or yourself!) in voice chat (Scales with time)."
    )
    @app_commands.describe(target="The muted friend in voice chat to rescue (or yourself)")
    async def buy_vcunmute(self, interaction: discord.Interaction, target: discord.Member = None):
        target = target or interaction.user

        if not target.voice or not target.voice.channel:
            await interaction.response.send_message(f"❌ {target.display_name} is not currently in a voice channel!", ephemeral=True)
            return

        if not target.voice.mute:
            await interaction.response.send_message(f"🧐 {target.display_name} is not currently server-muted in voice chat!", ephemeral=True)
            return

        # Calculate remaining time from active_perks database
        active_perk = db.get_user_active_perk(interaction.guild_id, target.id, "vcmute")
        if active_perk:
            remaining_seconds = max(0, active_perk["expires_at"] - time.time())
            remaining_minutes = max(1, int(round(remaining_seconds / 60.0)))
        else:
            remaining_minutes = 2

        # Dynamic Bailout Pricing: 200 base fee + 200 per minute remaining (Min: 400c)
        cost = max(400, 200 + (remaining_minutes * 200))

        if not db.remove_points(interaction.user.id, interaction.guild_id, cost):
            await interaction.response.send_message(
                f"❌ Insufficient funds!\n"
                f"There are **~{remaining_minutes} min** left on {target.display_name}'s VC mute.\n"
                f"Bailout costs **{cost:,} Coins**.",
                ephemeral=True
            )
            return

        try:
            await target.edit(mute=False, reason=f"VC bailout purchased by {interaction.user.name}")
            db.remove_user_active_perk(interaction.guild_id, target.id, "vcmute")

            embed = discord.Embed(
                title="📢 Voice Chat Curse Broken!",
                description=(
                    f"{interaction.user.mention} paid **{cost:,} Coins** to break the silence on {target.mention}!\n\n"
                    f"⏱️ *Sentence cancelled with {remaining_minutes} min remaining!*\n"
                    f"🎙️ *Speak freely once more in the halls of voice!*"
                ),
                color=0x2ECC71
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            db.add_points(interaction.user.id, interaction.guild_id, cost)
            logger.error(f"VC unmute error: {e}")
            await interaction.response.send_message(f"❌ Failed to unmute in VC: `{e}`. Coins refunded.", ephemeral=True)

    @app_commands.command(
        name="buy_pin",
        description="Shop Perk: Pin an iconic message to the channel (Cost: 250 Coins)."
    )
    @app_commands.describe(message_id="The ID of the message you want to pin")
    async def buy_pin(self, interaction: discord.Interaction, message_id: str):
        cost = SHOP_ITEMS["pin"]["cost"]

        try:
            mid = int(message_id.strip())
            msg = await interaction.channel.fetch_message(mid)
        except Exception:
            await interaction.response.send_message("❌ Could not find a message with that ID in this channel!", ephemeral=True)
            return

        if msg.pinned:
            await interaction.response.send_message("📌 That message is already pinned!", ephemeral=True)
            return

        if not db.remove_points(interaction.user.id, interaction.guild_id, cost):
            await interaction.response.send_message(f"❌ Insufficient funds! You need **{cost} Coins**.", ephemeral=True)
            return

        try:
            await msg.pin(reason=f"Sacred Pin purchased by {interaction.user.name}")
            await interaction.response.send_message(
                f"📌 {interaction.user.mention} paid **{cost} Coins** to immortalize [this message]({msg.jump_url}) to the channel pins!"
            )
        except Exception as e:
            db.add_points(interaction.user.id, interaction.guild_id, cost)
            logger.error(f"Failed to pin message: {e}")
            await interaction.response.send_message(f"❌ Failed to pin: {e}. Coins refunded.", ephemeral=True)

    @app_commands.command(
        name="buy_role",
        description="Shop Perk: Create a custom vanity text/color role for yourself (Cost: 1000 Coins)."
    )
    @app_commands.describe(
        role_name="Name of your custom role",
        hex_color="Color hex code, e.g. #FF5733 or FF5733 (Default: random)"
    )
    async def buy_role(self, interaction: discord.Interaction, role_name: str, hex_color: str = None):
        cost = SHOP_ITEMS["customrole"]["cost"]

        if not db.remove_points(interaction.user.id, interaction.guild_id, cost):
            await interaction.response.send_message(f"❌ Insufficient funds! You need **{cost} Coins**.", ephemeral=True)
            return

        # Parse color
        color_val = discord.Color.random()
        if hex_color:
            cleaned = hex_color.replace("#", "").strip()
            try:
                color_val = discord.Color(int(cleaned, 16))
            except ValueError:
                pass

        try:
            # Create role below the bot's highest role
            guild = interaction.guild
            new_role = await guild.create_role(
                name=role_name[:50],
                color=color_val,
                reason=f"Custom vanity role bought by {interaction.user.name}"
            )
            # Assign to user
            await interaction.user.add_roles(new_role)

            embed = discord.Embed(
                title="🎨 Custom Royalty Crowned!",
                description=(
                    f"Congratulations {interaction.user.mention}! Your custom role {new_role.mention} has been crafted and assigned!"
                ),
                color=color_val
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            db.add_points(interaction.user.id, interaction.guild_id, cost)
            logger.error(f"Role creation error: {e}")
            await interaction.response.send_message(f"❌ Could not create role: {e}. Coins refunded.", ephemeral=True)

    # --- Background Cleanup Loop for Expired Perks (Nicknames & Mutes) ---
    @tasks.loop(seconds=45)
    async def perk_cleanup_loop(self):
        await self.bot.wait_until_ready()
        expired = db.get_expired_perks()

        for perk in expired:
            perk_id = perk["id"]
            guild = self.bot.get_guild(perk["guild_id"])
            if not guild:
                db.remove_active_perk(perk_id)
                continue

            member = guild.get_member(perk["user_id"])
            if not member:
                db.remove_active_perk(perk_id)
                continue

            if perk["perk_type"] == "rename":
                try:
                    orig_nick = perk["original_value"]
                    await member.edit(nick=orig_nick if orig_nick != member.name else None, reason="Temporary rename perk expired")
                    logger.info(f"Restored original nickname for {member.name}")
                except Exception as e:
                    logger.debug(f"Could not restore nickname: {e}")

            elif perk["perk_type"] == "vcmute":
                try:
                    if member.voice:
                        await member.edit(mute=False, reason="Temporary VC mute expired")
                        logger.info(f"Unmuted {member.name} in VC")
                except Exception as e:
                    logger.debug(f"Could not unmute: {e}")

            db.remove_active_perk(perk_id)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
