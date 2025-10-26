import os
import math
import logging
from dotenv import load_dotenv
from discord.ext import commands
import discord
from commands.trig import TrigCommands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BOT_NAME = "Axis"

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

user_modes = {}

@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.tree.sync()
    logging.info("Slash commands synced.")

@bot.event
async def setup_hook():
    await bot.add_cog(TrigCommands(bot, user_modes))

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN not set. Copy .env.example to .env and set your token.")
    bot.run(TOKEN)
