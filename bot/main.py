# bot/main.py
"""
AxisBot main entrypoint
- Uses a Bot subclass to override setup_hook (modern discord.py pattern)
- Dynamically loads cogs from bot/cogs/
- Supports optional DEV_GUILD_ID for fast guild-scoped slash command registration
- Minimal default intents (no message_content unless explicitly enabled)
- Helpful logging and clear exit codes for CI
"""
from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("axisbot")

# ---------------------------
# Environment / Configuration
# ---------------------------
# Primary token env var (set in GitHub Secrets or environment)
TOKEN = (
    os.getenv("DISCORD_TOKEN")
    or os.getenv("DISCORD_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
)

# Optional development guild id to register slash commands quickly (string)
# e.g. DEV_GUILD_ID="123456789012345678"
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")

# If true, allow enabling message content intent via env var (use cautiously)
ENABLE_MESSAGE_CONTENT = os.getenv("ENABLE_MESSAGE_CONTENT", "false").lower() in ("1", "true", "yes")

# Directory for cogs (relative to this file)
COGS_DIR = Path(__file__).resolve().parent / "cogs"

# ---------------------------
# Token validation
# ---------------------------
if not TOKEN:
    if os.getenv("GITHUB_ACTIONS") == "true":
        logger.error("❌ DISCORD_TOKEN not set in GitHub Actions environment. Map secrets correctly.")
        logger.error("   Example (workflow): env: DISCORD_TOKEN: ${{ secrets.DISCORD_TOKEN }}")
    else:
        logger.error("❌ DISCORD_TOKEN environment variable is not set.")
    sys.exit(2)

# ---------------------------
# Intents
# ---------------------------
intents = discord.Intents.default()
# avoid privileged intents by default — slash commands do not need message_content.
if ENABLE_MESSAGE_CONTENT:
    logger.warning("⚠️ ENABLE_MESSAGE_CONTENT is true; enabling message_content intent.")
    intents.message_content = True

# ---------------------------
# Bot subclass
# ---------------------------
class AxisBot(commands.Bot):
    def __init__(self, *, intents: discord.Intents, command_prefix: str = "/", **kwargs):
        super().__init__(command_prefix=command_prefix, intents=intents, help_command=None, **kwargs)
        # (optionally) keep a shared store for user-mode etc.
        self.shared = {}
        self.cogs_path = COGS_DIR

    async def setup_hook(self) -> None:
        """
        Runs before connecting. Load cogs and sync commands.
        Overriding setup_hook is the recommended modern approach.
        """
        # Load cogs dynamically
        if not self.cogs_path.exists():
            logger.warning(f"Cog directory not found: {self.cogs_path}")
        else:
            for file in sorted(self.cogs_path.iterdir()):
                if file.is_file() and file.suffix == ".py" and not file.name.startswith("_"):
                    module = f"bot.cogs.{file.stem}"
                    try:
                        await self.load_extension(module)
                        logger.info(f"🔹 Loaded cog: {module}")
                    except Exception as exc:
                        logger.exception(f"❌ Failed to load cog {module}: {exc}")

        # Register/sync slash commands. Use DEV_GUILD_ID if present for fast dev registration.
        try:
            if DEV_GUILD_ID:
                try:
                    gid = int(DEV_GUILD_ID)
                    logger.info(f"Registering slash commands to development guild {gid} (fast sync).")
                    guild = discord.Object(id=gid)
                    await self.tree.sync(guild=guild)
                    logger.info("✅ Guild-scoped slash commands synced.")
                except ValueError:
                    logger.warning("DEV_GUILD_ID is not an integer; falling back to global sync.")
                    synced = await self.tree.sync()
                    logger.info(f"✅ Globally synced {len(synced)} commands.")
            else:
                synced = await self.tree.sync()
                logger.info(f"✅ Globally synced {len(synced)} commands.")
        except Exception as exc:
            logger.warning(f"⚠️ Could not sync slash commands: {exc}")

    async def on_ready(self) -> None:
        logger.info(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        # Optionally expose basic runtime info
        logger.info("🎯 Bot ready.")


# ---------------------------
# Entrypoint
# ---------------------------
def main() -> None:
    bot = AxisBot(intents=intents)

    # Provide a convenient shared store for cogs (user modes etc.)
    # Cogs can access via: self.bot.shared (or use injection when adding)
    bot.shared["user_modes"] = {}

    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        logger.error("❌ Invalid Discord token. Check DISCORD_TOKEN and GitHub Secret value.")
        sys.exit(3)
    except discord.errors.PrivilegedIntentsRequired as exc:
        logger.error("❌ Privileged intents required but not enabled for this bot.")
        logger.error(
            "   If you need message content or members/presence, enable them in the "
            "Discord Developer Portal -> Applications -> Your App -> Bot -> Privileged Gateway Intents."
        )
        logger.error(f"   Full error: {exc}")
        sys.exit(4)
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received; shutting down.")
        # bot.run handles graceful shutdown, but we still exit.
        sys.exit(0)
    except Exception as exc:
        logger.exception("💥 Unexpected error running the bot.")
        sys.exit(5)


if __name__ == "__main__":
    main()
