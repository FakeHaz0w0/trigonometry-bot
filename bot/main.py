import os
import math
import logging
from dotenv import load_dotenv
from discord.ext import commands
import discord

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BOT_NAME = "Axis"

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

# Per-user mode storage
user_modes = {}

# -------------------------------
# Utility functions
# -------------------------------
def calculate_trig(func, angle, mode):
    """Calculate trig function result based on user mode."""
    if mode == "degrees":
        angle = math.radians(angle)
    value = func(angle)
    return round(value, 6)


# -------------------------------
# Slash commands
# -------------------------------
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
    try:
        result = calculate_trig(math.tan, angle, mode)
        await interaction.response.send_message(f"🧮 tan({angle} {mode}) = **{result}**")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}")


# -------------------------------
# Events
# -------------------------------
@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.tree.sync()
    logging.info("✅ Slash commands synced and ready.")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ DISCORD_TOKEN not set. Copy .env.example to .env and set your token.")
    bot.run(TOKEN)
