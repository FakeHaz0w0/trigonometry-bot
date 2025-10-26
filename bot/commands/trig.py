import math
from discord.ext import commands
import discord
from discord import app_commands
from ..utils import format_result, get_context_for_angle

class TrigCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, user_modes: dict):
        self.bot = bot
        self.user_modes = user_modes

    async def _resolve_angle(self, angle: float, mode: str):
        return math.radians(angle) if mode == "deg" else angle

    @app_commands.command(name="mode", description="Set your preferred angle mode (degrees or radians)")
    @app_commands.choices(mode=[
        app_commands.Choice(name="degrees", value="deg"),
        app_commands.Choice(name="radians", value="rad")
    ])
    async def set_mode(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        self.user_modes[interaction.user.id] = mode.value
        await interaction.response.send_message(f"Saved mode **{mode.name}** for {interaction.user.mention}", ephemeral=True)

    async def _calc_and_respond(self, interaction, func_name, angle, use_mode):
        mode = use_mode or self.user_modes.get(interaction.user.id, "deg")
        rad = await self._resolve_angle(angle, mode)
        funcs = {"sin": math.sin, "cos": math.cos, "tan": math.tan}
        f = funcs[func_name]
        try:
            val = f(rad)
        except ValueError as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            return
        friendly = format_result(val)
        context = get_context_for_angle(angle, mode)
        embed = discord.Embed(title=f"{func_name}({angle} {'°' if mode=='deg' else 'rad'})", description=friendly, color=discord.Color.blue())
        if context:
            embed.add_field(name="Context", value=context)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="sin", description="Sine of an angle")
    async def sin(self, interaction: discord.Interaction, angle: float):
        await self._calc_and_respond(interaction, "sin", angle, None)

    @app_commands.command(name="cos", description="Cosine of an angle")
    async def cos(self, interaction: discord.Interaction, angle: float):
        await self._calc_and_respond(interaction, "cos", angle, None)

    @app_commands.command(name="tan", description="Tangent of an angle")
    async def tan(self, interaction: discord.Interaction, angle: float):
        await self._calc_and_respond(interaction, "tan", angle, None)
