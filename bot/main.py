import os
import sys
import logging
import discord
from discord.ext import commands

# ======================================================
# AXIS BOT — Main Entrypoint
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("axisbot")

# ======================================================
# Token & Intents
# ======================================================
TOKEN = (
    os.getenv("DISCORD_TOKEN")
    or os.getenv("DISCORD_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
)

if not TOKEN:
    logger.error("❌ Discord token not set. Define DISCORD_TOKEN in your environment or GitHub Secrets.")
    sys.exit(1)

# Default intents are fine for slash-command bots
intents = discord.Intents.default()

# ======================================================
# Bot Setup
# ======================================================
bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)


@bot.event
async def on_ready():
    """Log startup info and sync slash commands."""
    logger.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    # Sync slash commands once at startup
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        logger.warning(f"⚠️ Could not sync slash commands: {e}")

    logger.info("🎯 AxisBot is now online and ready!")


async def load_cogs():
    """Dynamically load all Cogs in the bot/cogs directory."""
    for filename in os.listdir(os.path.join(os.path.dirname(__file__), "cogs")):
        if filename.endswith(".py") and not filename.startswith("_"):
            cog_name = f"bot.cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                logger.info(f"🔹 Loaded Cog: {cog_name}")
            except Exception as e:
                logger.error(f"❌ Failed to load Cog {cog_name}: {e}")


# ======================================================
# Entrypoint
# ======================================================
if __name__ == "__main__":
    try:
        bot.loop.run_until_complete(load_cogs())
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        logger.error("❌ Invalid Discord token! Check your GitHub Secret DISCORD_TOKEN.")
        sys.exit(1)
    except Exception:
        logger.exception("💥 Unexpected error running the bot.")
        sys.exit(1)
