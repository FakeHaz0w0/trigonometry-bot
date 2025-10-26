# bot/main.py
import os
import math
import logging
import sys
from discord.ext import commands
import discord

# ======================================================
# AXIS BOT — Trigonometry Calculator (GitHub Secrets version)
# ======================================================

# Logging setup
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Retrieve bot token from environment (set by GitHub Actions secret or otherwise)
# - In GitHub Actions workflow we will set env: DISCORD_TOKEN: ${{ secrets.DISCORD_TOKEN }}
TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN") or os.getenv("BOT_TOKEN")

# Verify token presence (fail early with helpful message)
if not TOKEN:
    # If running in CI, provide additional hint
    running_in_actions = os.getenv("GITHUB_ACTIONS") == "true"
    if running_in_actions:
        logger.error("❌ DISCORD_TOKEN is not set! In GitHub Actions, make sure to map the secret to env:")
        logger.error("   env: DISCORD_TOKEN: ${{ secrets.DISCORD_TOKEN }}")
    else:
        logger.error("❌ DISCORD_TOKEN environment variable is not set. Set it in your environment or CI secrets.")
    raise SystemExit("Missing DISCORD_TOKEN environment variable.")

# Create Discord intents
intents = discord.Intents.default()
# your bot needs message content to handle slash commands input or older prefix commands
# Only enable what you actually need:
intents.message_content = True

# Create bot instance
bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

# Store per-user mode (degrees or radians)
user_modes = {}

# ======================================================
# Utility Functions
# ======================================================
def calculate_trig(func, angle, mode):
    """Calculate trig function result based on user mode."""
    if mode == "degrees":
        angle = math.radians(angle)
    value = func(angle)
    # handle floating point near-zero
    if abs(value) < 1e-12:
        value = 0.0
    return round(value, 6)

# ======================================================
# Slash Commands
# ======================================================
@bot.tree.command(name="mode", description="Switch between degrees and radians.")
async def mode(interaction: discord.Interaction, type: str):
    type = type.lower()
    if type not in ["degrees", "radians"]:
        await interaction.response.send_message("❌ Mode must be 'degrees' or 'radians'.", ephemeral=True)
        return

    user_modes[interaction.user.id] = type
    await interaction.response.send_message(f"✅ Mode set to **{type}** for you.")

@bot.tree.command(name="sin", description="Calculate sine of an angle.")
async def sin_cmd(interaction: discord.Interaction, angle: float):
    mode = user_modes.get(interaction.user.id, "degrees")
    result = calculate_trig(math.sin, angle, mode)
    await interaction.response.send_message(f"🧮 sin({angle} {mode}) = **{result}**")

@bot.tree.command(name="cos", description="Calculate cosine of an angle.")
async def cos_cmd(interaction: discord.Interaction, angle: float):
    mode = user_modes.get(interaction.user.id, "degrees")
    result = calculate_trig(math.cos, angle, mode)
    await interaction.response.send_message(f"🧮 cos({angle} {mode}) = **{result}**")

@bot.tree.command(name="tan", description="Calculate tangent of an angle.")
async def tan_cmd(interaction: discord.Interaction, angle: float):
    mode = user_modes.get(interaction.user.id, "degrees")
    # check for angles where tangent is problematic for degrees-mode
    if mode == "degrees" and (angle % 180) == 90:
        await interaction.response.send_message("❌ tan is undefined at this angle.")
        return
    result = calculate_trig(math.tan, angle, mode)
    await interaction.response.send_message(f"🧮 tan({angle} {mode}) = **{result}**")

# ======================================================
# Events
# ======================================================
@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        await bot.tree.sync()
        logger.info("✅ Slash commands synced and ready.")
    except Exception as e:
        logger.warning(f"Could not sync command tree: {e}")
    print(f"✅ {bot.user} is now online and ready!")

# ======================================================
# Run the Bot
# ======================================================
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        logger.error("❌ Invalid Discord token! Check your GitHub Secret DISCORD_TOKEN.")
        sys.exit(1)
    except discord.errors.PrivilegedIntentsRequired as e:
        logger.error("❌ Privileged intents required but not enabled for this bot.")
        logger.error("   Enable the required intents (Message Content / Server Members / Presence) in the")
        logger.error("   Discord Developer Portal -> Applications -> Your App -> Bot -> Privileged Gateway Intents.")
        logger.error("   Alternatively, disable these intents in your code if you do not need them.")
        logger.error(f"   Full error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("Bot terminated with an unexpected exception.")
        sys.exit(1)
