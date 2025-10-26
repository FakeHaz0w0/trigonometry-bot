import math
import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, Optional

from ..utils import format_result, get_context_for_angle


class TrigCommands(commands.Cog):
    """Cog providing trigonometric calculation commands with per-user mode."""

    def __init__(self, bot: commands.Bot, user_modes: Dict[int, str]):
        self.bot = bot
        self.user_modes = user_modes

    # ======================================================
    # Internal helpers
    # ======================================================
    async def _resolve_angle(self, angle: float, mode: str) -> float:
        """Convert angle from degrees to radians if needed."""
        return math.radians(angle) if mode == "deg" else angle

    async def _calc_and_respond(
        self,
        interaction: discord.Interaction,
        func_name: str,
        angle: float,
        use_mode: Optional[str] = None,
    ) -> None:
        """Compute trig function and send embed response."""
        mode = use_mode or self.user_modes.get(interaction.user.id, "deg")
        radians = await self._resolve_angle(angle, mode)

        funcs = {"sin": math.sin, "cos": math.cos, "tan": math.tan}
        func = funcs.get(func_name)

        try:
            result = func(radians)
        except ValueError as e:
            await interaction.response.send_message(
                f"⚠️ Math domain error: {e}", ephemeral=True
            )
            return
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Unexpected error: {e}", ephemeral=True
            )
            return

        result_str = format_result(result)
        context_str = get_context_for_angle(angle, mode)

        embed = discord.Embed(
            title=f"{func_name}({angle}{'°' if mode == 'deg' else ' rad'})",
            description=f"**Result:** {result_str}",
            color=discord.Color.blurple(),
        )
        if context_str:
            embed.add_field(name="Context", value=context_str, inline=False)

        await interaction.response.send_message(embed=embed)

    # ======================================================
    # Commands
    # ======================================================
    @app_commands.command(
        name="mode",
        description="Set your preferred angle mode (degrees or radians).",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="degrees", value="deg"),
            app_commands.Choice(name="radians", value="rad"),
        ]
    )
    async def set_mode(
        self, interaction: discord.Interaction, mode: app_commands.Choice[str]
    ):
        """Set user’s preferred angle mode."""
        self.user_modes[interaction.user.id] = mode.value
        await interaction.response.send_message(
            f"✅ Mode set to **{mode.name}** for {interaction.user.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="sin", description="Calculate sine of an angle.")
    async def sin(self, interaction: discord.Interaction, angle: float):
        await self._calc_and_respond(interaction, "sin", angle)

    @app_commands.command(name="cos", description="Calculate cosine of an angle.")
    async def cos(self, interaction: discord.Interaction, angle: float):
        await self._calc_and_respond(interaction, "cos", angle)

    @app_commands.command(name="tan", description="Calculate tangent of an angle.")
    async def tan(self, interaction: discord.Interaction, angle: float):
        # Pre-check: prevent tan(90°), tan(270°), etc.
        mode = self.user_modes.get(interaction.user.id, "deg")
        if mode == "deg" and (angle % 180) == 90:
            await interaction.response.send_message(
                "⚠️ Tangent is undefined at this angle.", ephemeral=True
            )
            return
        await self._calc_and_respond(interaction, "tan", angle)


async def setup(bot: commands.Bot):
    """Asynchronous cog setup entrypoint (for discord.py ≥2.0)."""
    user_modes: Dict[int, str] = {}
    await bot.add_cog(TrigCommands(bot, user_modes))
