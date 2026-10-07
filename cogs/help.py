import discord
from discord import app_commands
from discord.ext import commands

HELP_CATEGORIES = {
    "overview": {
        "title": "🎭 The Dramatic Narrator & Historian — Guidebook",
        "description": (
            "Welcome, mortals! I am your server's all-seeing chronicler, roastmaster, and vault keeper.\n\n"
            "Use the select menu below or /help category:[name] to browse each domain:\n\n"
            "🎬 **1. Recaps & Roasts** — AI summaries & punchy comedy burns\n"
            "📜 **2. Server Lore & Chronicles** — Etching history into the archives\n"
            "📸 **3. Out of Context Quote Vault** — Capture quotes, leaderboards & trivia\n"
            "💰 **4. Economy & Black Market Shop** — Earn coins & buy hilarious friend pranks"
        ),
        "color": 0xD4AF37
    },
    "narrator": {
        "title": "🎬 AI Recaps & Roasts",
        "description": "Transform ordinary server chatter into comedy masterpieces.",
        "color": 0xE74C3C,
        "fields": [
            ("/recap [style] [limit]", "Summarizes recent channel chat in hilarious bullet points.\n**Styles:** 🍷 Reality TV, ⚖️ Courtroom Trial, 🚨 Breaking News, 🏰 Medieval Fantasy, 🎙️ Nature Doc."),
            ("/roast @friend [spice]", "Scans a friend's recent chat activity and delivers a short, punchy, hilarious 2–4 sentence burn.\n**Spice:** 🌱 Mild, 🔥 Medium, 💀 Spicy.")
        ]
    },
    "historian": {
        "title": "📜 Server Lore & Chronicles",
        "description": "Preserve the legendary moments and myths of your community.",
        "color": 0x9B59B6,
        "fields": [
            ("/chronicle title:[text] description:[text]", "Immortalizes an unforgettable moment into an official epic saga in the Sacred Archives."),
            ("/lore [entry_number]", "Reads back a random or specific chronicle entry from the archives.")
        ]
    },
    "quotes": {
        "title": "📸 'Out of Context' Quote Vault",
        "description": "Archive your friends' most embarrassing, out-of-context quotes forever.",
        "color": 0xF1C40F,
        "fields": [
            ("React with 📸 or 💬", "Any message reacted with 📸 or 💬 is automatically archived into the database (with author, jump link, and date)."),
            ("/quote", "Pulls a random hilarious out-of-context quote from the vault."),
            ("/quoteleaderboard", "Hall of Infamy: ranks who has the most quoted lines in the server."),
            ("/whosaidit", "Interactive Quote Trivia! Guess who uttered the quote using buttons. First correct guess wins **100 Coins**!"),
            ("/setflashback #channel", "*(Admins)* Sets the channel where the bot posts a daily morning flashback quote automatically.")
        ]
    },
    "economy": {
        "title": "💰 Server Economy & Black Market Shop",
        "description": "Earn coins through activity and spend them on server perks and pranks.",
        "color": 0x2ECC71,
        "fields": [
            ("How to Earn Coins", "• **Chatting:** +5 coins every minute\n• **/daily:** Claim +250 coins every 24 hours\n• **/whosaidit:** Win +100 coins for correct trivia guesses"),
            ("/balance [@user]", "Check your or a friend's coin balance."),
            ("/rich", "View the server's top 10 wealthiest citizens."),
            ("/shop", "Browse all available perks and their costs."),
            ("🏷️ /buy_rename @friend new_name", "Changes a friend's nickname for 24 hours (500 Coins, auto-reverts)."),
            ("🤐 /buy_chatmute @friend [duration]", "Time out a friend in chat: 1m (300c), 2m (500c), 5m (1,000c), 10m (1,800c)."),
            ("🤫 /buy_vcmute @friend [duration]", "Mute a friend in voice chat: 1m (300c), 2m (500c), 5m (1,000c), 10m (1,800c)."),
            ("🕊️ /buy_chatunmute [@friend]", "Post bail to lift chat timeout immediately (scales dynamically with time remaining, starts at 400c)."),
            ("📢 /buy_vcunmute [@friend]", "Rescue a muted friend in voice chat immediately (scales dynamically with time remaining, starts at 400c)."),
            ("📌 /buy_pin message_id", "Pins any funny message to the channel (250 Coins)."),
            ("🎨 /buy_role role_name [hex_color]", "Creates and gives you a custom vanity color role (1000 Coins).")
        ]
    }
}

class HelpDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Overview & Welcome", value="overview", emoji="🎭", description="General guide to the bot"),
            discord.SelectOption(label="AI Recaps & Roasts", value="narrator", emoji="🎬", description="/recap and /roast commands"),
            discord.SelectOption(label="Server Lore & Chronicles", value="historian", emoji="📜", description="/chronicle and /lore commands"),
            discord.SelectOption(label="Quote Vault & Trivia", value="quotes", emoji="📸", description="Archive quotes, leaderboard, /whosaidit"),
            discord.SelectOption(label="Economy & Custom Shop", value="economy", emoji="💰", description="Earn coins, /daily, /shop, prank perks"),
        ]
        super().__init__(placeholder="Choose a feature category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cat_key = self.values[0]
        embed = build_help_embed(cat_key)
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180.0)
        self.add_item(HelpDropdown())

def build_help_embed(category_key: str) -> discord.Embed:
    data = HELP_CATEGORIES.get(category_key, HELP_CATEGORIES["overview"])
    embed = discord.Embed(
        title=data["title"],
        description=data["description"],
        color=data["color"]
    )
    if "fields" in data:
        for name, value in data["fields"]:
            embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text="The Dramatic Narrator • Select a category below to explore more")
    return embed

class HelpCog(commands.Cog, name="Help Guide"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Comprehensive guide on how to use The Dramatic Narrator bot."
    )
    @app_commands.describe(
        category="Jump straight to a specific feature category"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="🎭 Overview & Welcome", value="overview"),
        app_commands.Choice(name="🎬 AI Recaps & Roasts", value="narrator"),
        app_commands.Choice(name="📜 Server Lore & Chronicles", value="historian"),
        app_commands.Choice(name="📸 Quote Vault & Trivia", value="quotes"),
        app_commands.Choice(name="💰 Economy & Custom Shop", value="economy"),
    ])
    async def help(self, interaction: discord.Interaction, category: app_commands.Choice[str] = None):
        cat_key = category.value if category else "overview"
        embed = build_help_embed(cat_key)
        view = HelpView()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(
        name="narrator_help",
        description="Direct help command for The Dramatic Narrator (avoids conflicts with other bots)."
    )
    async def narrator_help(self, interaction: discord.Interaction):
        embed = build_help_embed("overview")
        view = HelpView()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(
        name="guide",
        description="Quick user guide for The Dramatic Narrator bot."
    )
    async def guide(self, interaction: discord.Interaction):
        embed = build_help_embed("overview")
        view = HelpView()
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
