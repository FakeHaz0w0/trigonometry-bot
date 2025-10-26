# trigonometry-bot/bot/main.py
"""
AxisBot main entrypoint — modern, robust, diagnostic-friendly.

- Loads commands from `commands.trig` (expects `async def setup(bot)` in that module).
- Supports both slash commands (recommended) and prefix commands using '?'.
- Provides explicit warnings when Message Content Intent is not enabled (required for prefix commands).
- Read env vars:
    DISCORD_TOKEN           - required
    DEV_GUILD_ID            - optional (use for fast guild-scoped slash command sync)
    ENABLE_MESSAGE_CONTENT  - optional ("true"/"1"/"yes" to enable message_content intent)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
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
TOKEN = (
    os.getenv("DISCORD_TOKEN")
    or os.getenv("DISCORD_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
)

DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")  # optional: for fast guild-scoped slash sync
ENABLE_MESSAGE_CONTENT = os.getenv("ENABLE_MESSAGE_CONTENT", "false").lower() in ("1", "true", "yes")

# ---------------------------
# Sanity checks
# ---------------------------
if not TOKEN:
    logger.error("❌ DISCORD_TOKEN is not set. Add it to your environment or GitHub Secrets.")
    logger.error("   Example (GitHub Actions): env: DISCORD_TOKEN: ${{ secrets.DISCORD_TOKEN }}")
    sys.exit(2)

# ---------------------------
# PyNaCl check (voice warning)
# ---------------------------
try:
    import nacl  # type: ignore
    PYNACL_AVAILABLE = True
except Exception:
    PYNACL_AVAILABLE = False
    logger.warning("PyNaCl is not installed; voice features will NOT be supported. (pip install PyNaCl)")

# ---------------------------
# Intents
# ---------------------------
intents = discord.Intents.default()
if ENABLE_MESSAGE_CONTENT:
    intents.message_content = True
    logger.info("Message content intent will be enabled (ENABLE_MESSAGE_CONTENT=true).")
else:
    # leave disabled by default for safety; commands will rely on slash commands.
    intents.message_content = False
    logger.info("Message content intent is disabled (default). Prefix commands (e.g. ?sin) require it.")

# ---------------------------
# Bot subclass (modern pattern)
# ---------------------------
class AxisBot(commands.Bot):
    def __init__(self, *, intents: discord.Intents):
        # Accept when mentioned OR '?' as prefix
        super().__init__(command_prefix=commands.when_mentioned_or("?"), intents=intents, help_command=None)
        self.shared: dict = {}
        self.shared.setdefault("user_modes", {})  # per-user mode storage
        self._commands_module = "commands"  # the package where extensions live (commands.trig)

    async def setup_hook(self) -> None:
        """Load extension(s) before connecting and sync slash commands."""
        # 1) Load the commands.trig extension
        module_name = f"{self._commands_module}.trig"
        try:
            await self.load_extension(module_name)
            logger.info(f"🔹 Loaded extension: {module_name}")
        except Exception as exc:
            logger.exception(f"❌ Failed to load extension '{module_name}': {exc}")

        # 2) Sync slash commands
        try:
            if DEV_GUILD_ID:
                try:
                    gid = int(DEV_GUILD_ID)
                    logger.info(f"Syncing slash commands to dev guild {gid} (fast).")
                    await self.tree.sync(guild=discord.Object(id=gid))
                    logger.info("✅ Guild-scoped slash commands synced.")
                except ValueError:
                    logger.warning("DEV_GUILD_ID env var is not an integer; falling back to global sync.")
                    synced = await self.tree.sync()
                    logger.info(f"✅ Globally synced {len(synced)} commands.")
            else:
                synced = await self.tree.sync()
                logger.info(f"✅ Globally synced {len(synced)} commands.")
        except Exception as exc:
            logger.warning(f"⚠️ Could not sync slash commands: {exc}")

    async def on_ready(self) -> None:
        logger.info(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        # Post-startup diagnostic about prefix commands vs message_content intent
        self._diagnose_prefix_intent()

    def _diagnose_prefix_intent(self) -> None:
        """Warn if there are prefix commands loaded but message_content intent is disabled."""
        # Count prefix commands loaded from cogs/commands
        prefix_command_count = sum(1 for _ in self.walk_commands())  # includes app commands? walk_commands yields prefix commands
        # More reliable: check presence of any commands.Command objects in bot.commands
        prefix_present = len(self.commands) > 0
        if prefix_present and not self.intents.message_content:
            logger.warning(
                "⚠️ Privileged message content intent is missing but prefix commands are registered."
                " Prefix commands (e.g. ?sin) will NOT receive message content from the gateway unless "
                "the Message Content Intent is enabled in BOTH your code (ENABLE_MESSAGE_CONTENT) and the "
                "Developer Portal (Applications → Your App → Bot → Privileged Gateway Intents → Message Content)."
            )
            logger.info("If you only want slash commands, you can ignore this. Otherwise enable message content intent.")

# ---------------------------
# Helper: global command error handler
# ---------------------------
def attach_global_error_handler(bot: AxisBot) -> None:
    @bot.event
    async def on_command_error(ctx, error):
        # Keep responses helpful and non-verbose for users
        from discord.ext.commands import CommandNotFound, BadArgument, MissingRequiredArgument
        if isinstance(error, CommandNotFound):
            await ctx.send("❌ Unknown command. Try `/sin` or `?sin 30`.")
        elif isinstance(error, (BadArgument, MissingRequiredArgument)):
            await ctx.send(f"❌ Bad usage: {error}")
        else:
            # Unexpected: log with stack trace and notify channel generically
            logger.exception(f"Unhandled command error: {error}")
            try:
                await ctx.send("❌ An internal error occurred. Check logs.")
            except Exception:
                pass

# ---------------------------
# Entrypoint
# ---------------------------
async def main() -> None:
    bot = AxisBot(intents=intents)
    bot.shared.setdefault("user_modes", {})  # accessible by commands.trig

    # attach helpful on_command_error for prefix commands
    attach_global_error_handler(bot)

    try:
        # Use async context manager for graceful startup/shutdown
        async with bot:
            await bot.start(TOKEN)
    except discord.errors.LoginFailure:
        logger.error("❌ Invalid Discord token (LoginFailure). Verify DISCORD_TOKEN value.")
        sys.exit(3)
    except discord.errors.PrivilegedIntentsRequired as exc:
        logger.error("❌ Privileged intents required but not enabled for this bot.")
        logger.error("   If you need message content, enable the Message Content Intent in the Developer Portal.")
        logger.error(f"   Full error: {exc}")
        sys.exit(4)
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received; shutting down.")
    except Exception as exc:
        logger.exception(f"💥 Unexpected error running bot: {exc}")
        sys.exit(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception(f"Fatal error in main runner: {e}")
        sys.exit(10)
