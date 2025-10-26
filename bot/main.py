# bot/main.py
import os
import logging
import sys
import asyncio
import discord
from discord.ext import commands

# ==============================
# AXIS BOT — Trigonometry Helper
# ==============================

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Retrieve Discord token from environment (for GitHub Actions or local env)
TOKEN = (
    os.getenv("DISCORD_TOKEN")
    or os.getenv("DISCORD_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
)

if not TOKEN:
    logger.error("❌ Missing DISCORD_TOKEN environment variable.")
    logger.error("In GitHub Actions, add it under 'secrets' as DISCORD_TOKEN.")
    sys.exit(1)

# ------------------------------
# Discord Bot Setup
# ------------------------------
intents = discord.Intents.default()
intents.message_content = True  # Required for prefix commands like ?sin

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("?"),  # Support ? + mentions
    intents=intents,
    help_command=None,
)

bot.shared = {"user_modes": {}}

# ------------------------------
# Async Cog Loader
# ------------------------------
async def load_cogs():
    """Load all bot cogs."""
    try:
        await bot.load_extension("bot.cogs.trig_commands")
        logger.info("✅ Loaded cog: trig_commands")
    except Exception as e:
        logger.exception(f"❌ Failed to load cog: {e}")

# ------------------------------
# Events
# ------------------------------
@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        await bot.tree.sync()
        logger.info("✅ Slash commands synced successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Could not sync slash commands: {e}")
    print(f"🤖 {bot.user} is now online and ready!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Unknown command. Try `/sin` or `?sin 30`.")
    else:
        logger.exception(f"Command error: {error}")

# ------------------------------
# Entrypoint
# ------------------------------
async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped manually.")
    except discord.errors.LoginFailure:
        logger.error("❌ Invalid Discord token.")
        sys.exit(1)
    except discord.errors.PrivilegedIntentsRequired:
        logger.error("❌ Privileged intents required — enable Message Content in Discord Dev Portal.")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"💥 Unexpected error: {e}")
        sys.exit(1)
