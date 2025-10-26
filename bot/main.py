# trigonometry-bot/bot/main.py
"""
Main entrypoint for AxisBot (Trigonometry / Unit Circle)

- Loads commands from `commands/trig.py` (expects an async `setup(bot)` in that module)
- Supports prefix "?" (e.g. ?sin 30) AND slash commands (/sin 30)
- Dynamic cog loading, DEV_GUILD_ID for fast command sync
- Minimal privileged intents by default; message_content is optional via env
- Uses modern discord.py setup_hook pattern
"""

from __future__ import annotations

import os
import sys
import logging
import asyncio
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
# Configuration (via env)
# ---------------------------
# Primary token environment variable (map your GitHub secret to this)
TOKEN = (
    os.getenv("DISCORD_TOKEN")
    or os.getenv("DISCORD_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
)

# Optional development guild ID to speed up slash command registration
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")  # example: "123456789012345678"

# Allow enabling message_content intent (use only if you actually need prefix/message reading)
ENABLE_MESSAGE_CONTENT = os.getenv("ENABLE_MESSAGE_CONTENT", "false").lower() in ("1", "true", "yes")

# Folder where commands live (module path will be 'commands.<name>')
COMMANDS_MODULE = "commands"  # we will load commands.trig as commands.trig

# ---------------------------
# Sanity checks
# ---------------------------
if not TOKEN:
    logger.error("❌ DISCORD_TOKEN is not set. Add it to your environment or GitHub Secrets.")
    logger.error("   In GitHub Actions workflow example: env: DISCORD_TOKEN: ${{ secrets.DISCORD_TOKEN }}")
    sys.exit(2)

# ---------------------------
# Intents
# ---------------------------
intents = discord.Intents.default()
# For prefix commands that rely on reading messages, message_content must be True.
# Keep disabled by default for safety; enable only via env var when necessary.
if ENABLE_MESSAGE_CONTENT:
    logger.warning("⚠️ ENABLE_MESSAGE_CONTENT is true; enabling message_content intent.")
    intents.message_content = True

# ---------------------------
# Bot subclass
# ---------------------------
class AxisBot(commands.Bot):
    def __init__(self, *, intents: discord.Intents, command_prefix: Optional[str] = "?"):
        # Accept commands when mentioned OR `?` prefix (so both @Bot sin and ?sin work)
        prefix_resolver = commands.when_mentioned_or("?")
        super().__init__(command_prefix=prefix_resolver, intents=intents, help_command=None)
        # shared store accessible to cogs (per-user mode, etc.)
        self.shared: dict = {}
        self.shared.setdefault("user_modes", {})
        # location of commands module (for dynamic loading)
        self.commands_module = COMMANDS_MODULE

    async def setup_hook(self) -> None:
        """Run before login - load commands module(s) and sync slash commands."""
        # Load the main commands module (commands.trig)
        # If you add more modules in `commands/`, expand this loader.
        try:
            module_name = f"{self.commands_module}.trig"
            await self.load_extension(module_name)
            logger.info(f"🔹 Loaded commands module: {module_name}")
        except Exception as exc:
            logger.exception(f"❌ Failed loading commands module '{module_name}': {exc}")

        # Sync slash commands. Use DEV_GUILD_ID if present to speed up propagation during dev.
        try:
            if DEV_GUILD_ID:
                try:
                    gid = int(DEV_GUILD_ID)
                    logger.info(f"Registering slash commands to development guild {gid} (fast sync).")
                    await self.tree.sync(guild=discord.Object(id=gid))
                    logger.info("✅ Guild-scoped slash commands synced.")
                except ValueError:
                    logger.warning("DEV_GUILD_ID is not a valid integer; performing global sync instead.")
                    synced = await self.tree.sync()
                    logger.info(f"✅ Globally synced {len(synced)} commands.")
            else:
                synced = await self.tree.sync()
                logger.info(f"✅ Globally synced {len(synced)} commands.")
        except Exception as exc:
            logger.warning(f"⚠️ Could not sync slash commands: {exc}")

    async def on_ready(self) -> None:
        logger.info(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        logger.info("🎯 AxisBot ready — commands available via slash and prefix '?'")

# ---------------------------
# Entrypoint
# ---------------------------
async def main() -> None:
    bot = AxisBot(intents=intents)

    # expose shared store for cogs
    bot.shared.setdefault("user_modes", {})

    # attach basic global error handler for commands (prefix)
    @bot.event
    async def on_command_error(ctx, error):
        # keep user messages helpful and short
        from discord.ext.commands import CommandNotFound, BadArgument, MissingRequiredArgument
        if isinstance(error, CommandNotFound):
            await ctx.send("❌ Unknown command. Try `/sin` or `?sin 30`.")
        elif isinstance(error, (BadArgument, MissingRequiredArgument)):
            await ctx.send(f"❌ Bad command usage: {error}")
        else:
            logger.exception(f"Unhandled command error: {error}")
            try:
                await ctx.send("❌ An unexpected error occurred. Check logs.")
            except Exception:
                pass

    # start
    try:
        # `async with bot` ensures graceful cleanup (cog unloads, shutdown)
        async with bot:
            await bot.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received. Shutting down.")
    except discord.errors.LoginFailure:
        logger.error("❌ Invalid Discord token. Verify DISCORD_TOKEN value.")
        sys.exit(3)
    except discord.errors.PrivilegedIntentsRequired as exc:
        logger.error("❌ Privileged intents required but not enabled for this bot.")
        logger.error("   If you need message content, enable it in the Developer Portal or disable message usage in code.")
        logger.error(f"   Full error: {exc}")
        sys.exit(4)
    except Exception as exc:
        logger.exception(f"💥 Unexpected error starting bot: {exc}")
        sys.exit(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception(f"Fatal error in main runner: {e}")
        sys.exit(10)
