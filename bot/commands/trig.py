# bot/cogs/trig_commands.py
"""
TrigCommands Cog with dynamic unit-circle image generation (matplotlib).

Features:
- /sin, /cos, /tan (slash) and ?sin, ?cos, ?tan (prefix)
- /mode and ?mode to set per-user 'deg' or 'rad' mode (stored in bot.shared["user_modes"])
- /circle and ?circle generate a fresh unit-circle PNG and send it
- Symbolic results for special angles (√2/2, 1/2, etc.) + numeric fallback
- Safe input parsing for '30', 'pi/6', 'π/4', '45/1', '-pi/2', simple expressions
"""
from __future__ import annotations

import io
import math
import re
from typing import Optional, Tuple, Dict

import discord
from discord.ext import commands
from discord import app_commands

# Attempt to import matplotlib; if missing we'll handle it at runtime
try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - runtime fallback
    plt = None  # type: ignore

# --------------------------
# Symbolic mapping for unit circle (degrees)
# --------------------------
MAPPING_DEG = {
    0: ("0", "1", "0"),
    30: ("1/2", "√3/2", "1/√3"),
    45: ("√2/2", "√2/2", "1"),
    60: ("√3/2", "1/2", "√3"),
    90: ("1", "0", "undefined"),
    120: ("√3/2", "-1/2", "-√3"),
    135: ("√2/2", "-√2/2", "-1"),
    150: ("1/2", "-√3/2", "-1/√3"),
    180: ("0", "-1", "0"),
    210: ("-1/2", "-√3/2", "1/√3"),
    225: ("-√2/2", "-√2/2", "1"),
    240: ("-√3/2", "-1/2", "-√3"),
    270: ("-1", "0", "undefined"),
    300: ("-√3/2", "1/2", "-√3"),
    315: ("-√2/2", "√2/2", "-1"),
    330: ("-1/2", "√3/2", "-1/√3"),
}

# --------------------------
# Parsing helpers
# --------------------------
PI_RE = re.compile(r"^(?P<num>-?\d*\.?\d*)\s*(?:pi|π)(?:\s*/\s*(?P<den>\d+(\.\d+)?))?$", re.IGNORECASE)
FRACTION_RE = re.compile(r"^(?P<num>-?\d+(\.\d+)?)/(?P<den>\d+(\.\d+)?)$")

def safe_float_convert(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None

def parse_angle_input(text: str) -> Tuple[Optional[float], str, str]:
    """
    Parse a user-provided angle string and return (value, detected_mode, canonical_str)
    - value: numeric value. If detected_mode == 'rad' or caller decides 'deg', value is interpreted accordingly.
    - detected_mode: 'rad' | 'auto' (auto means numeric but undecided)
    - canonical_str: cleaned input for display
    Accepts: 30, -45.5, pi/6, -pi, 3pi/4, 1/2, 45/1, simple expressions using pi and numbers (very limited)
    """
    t = text.strip().replace(" ", "")
    if t == "":
        return None, "auto", text

    # pure float numeric
    f = safe_float_convert(t)
    if f is not None:
        return f, "auto", t

    # match pi patterns
    m = PI_RE.match(t)
    if m:
        num = m.group("num")
        den = m.group("den")
        # interpret num (could be '', '-', '2', '-3.5', etc.)
        if num in ("", "+"):
            num_val = 1.0
        elif num == "-":
            num_val = -1.0
        else:
            try:
                num_val = float(num)
            except Exception:
                num_val = 1.0
        if den:
            try:
                den_val = float(den)
                rad = num_val * math.pi / den_val
                return rad, "rad", t
            except Exception:
                return None, "rad", t
        else:
            rad = num_val * math.pi
            return rad, "rad", t

    # fraction like "1/2"
    m2 = FRACTION_RE.match(t)
    if m2:
        try:
            numerator = float(m2.group("num"))
            denominator = float(m2.group("den"))
            return numerator / denominator, "auto", t
        except Exception:
            return None, "auto", t

    # very limited safe eval for simple arithmetic with pi
    # only allow digits, pi/π, .,+,-,*,/, parentheses and spaces
    if re.fullmatch(r"[0-9\.\+\-\*\/\(\)piπ ]+", text, flags=re.IGNORECASE):
        safe = text.replace("π", "pi")
        safe = re.sub(r"(?i)pi", "math.pi", safe)
        try:
            val = eval(safe, {"__builtins__": None, "math": math}, {})
            if isinstance(val, (int, float)):
                # if expression contained math.pi -> treat as radians
                return float(val), ("rad" if "math.pi" in safe else "auto"), t
        except Exception:
            pass

    return None, "auto", t

# --------------------------
# Formatting helpers
# --------------------------
def fmt_num(x: float) -> str:
    return f"{x:.6f}"

def normalize_degrees(angle: float) -> float:
    return angle % 360

def deg_from_rad(rad: float) -> float:
    return math.degrees(rad)

def attempt_symbolic_deg(deg: float) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    If deg is one of the special angles, return (sin_sym, cos_sym, tan_sym).
    Otherwise, (None, None, None).
    """
    nd = round(normalize_degrees(deg))
    if nd in MAPPING_DEG:
        sin_s, cos_s, tan_s = MAPPING_DEG[nd]
        return sin_s, cos_s, tan_s
    return None, None, None

# --------------------------
# Unit circle generator (matplotlib)
# --------------------------
class UnitCirclePlotter:
    """
    Generates a unit-circle PNG in-memory using matplotlib.
    Labels degrees (green) and radians (purple) plus coordinates for key angles.
    """

    # key degrees to label around the circle (common special angles)
    KEY_DEGREES = [0, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330]

    @staticmethod
    def generate_png(highlight_rad: Optional[float] = None) -> Optional[io.BytesIO]:
        """
        Returns BytesIO containing PNG data, or None if matplotlib not available.
        highlight_rad: if provided, draw the radius and point for that angle (in red).
        """
        if plt is None:
            return None

        fig, ax = plt.subplots(figsize=(7, 7), dpi=150)
        ax.set_aspect("equal")
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-1.3, 1.3)
        ax.axis("off")

        # draw unit circle and axes
        circle = plt.Circle((0, 0), 1.0, fill=False, linewidth=1.5)
        ax.add_artist(circle)
        ax.axhline(0, linewidth=0.8)
        ax.axvline(0, linewidth=0.8)

        # Plot and label key points
        for deg in UnitCirclePlotter.KEY_DEGREES:
            rad = math.radians(deg)
            x, y = math.cos(rad), math.sin(rad)
            ax.plot(x, y, marker="o", markersize=4, color="orange", zorder=3)

            # degree label (green) just outside the circle
            ax.text(x * 1.12, y * 1.12, f"{deg}°", color="green", ha="center", va="center", fontsize=8)

            # radian label (purple). Attempt friendly pi/ form
            # Prefer display like 0, π/6, π/4, π/3, π/2, 2π/3, etc.
            frac = deg / 180
            rad_label = UnitCirclePlotter._friendly_radian_label(frac)
            ax.text(x * 1.30, y * 1.30, rad_label, color="purple", ha="center", va="center", fontsize=8)

            # numeric coordinate (cos, sin) small label inside
            coord_label = UnitCirclePlotter._coord_label(deg)
            ax.text(x * 0.72, y * 0.72, coord_label, color="black", ha="center", va="center", fontsize=7)

        # Optionally highlight a particular angle
        if highlight_rad is not None:
            hx, hy = math.cos(highlight_rad), math.sin(highlight_rad)
            # draw radius line
            ax.plot([0, hx], [0, hy], linewidth=2.0, linestyle="-", color="red")
            ax.scatter([hx], [hy], color="red", s=40, zorder=5)
            ax.text(hx * 1.05, hy * 1.05, "target", color="red", ha="center", va="center", fontsize=8)

        # Save to buffer
        buf = io.BytesIO()
        plt.tight_layout()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    @staticmethod
    def _friendly_radian_label(frac: float) -> str:
        # frac = deg/180. Want to express as multiples of π.
        # common fractions: 0, 1/6, 1/4, 1/3, 1/2, 2/3, 3/2, 2
        eps = 1e-9
        if abs(frac) < eps:
            return "0"
        if abs(frac - 1) < eps:
            return "π"
        if abs(frac - 2) < eps:
            return "2π"
        # check common denominators
        for den in (6, 4, 3, 2):
            num = frac * den
            if abs(round(num) - num) < 1e-6:
                numi = int(round(num))
                if numi == 1:
                    return f"π/{den}"
                else:
                    return f"{numi}π/{den}"
        # fallback decimal times pi
        return f"{frac:.2f}π".rstrip("0").rstrip(".")

    @staticmethod
    def _coord_label(deg: int) -> str:
        # Provide common symbolic coordinate pairs for key angles where useful
        if deg in MAPPING_DEG:
            sin_s, cos_s, _ = MAPPING_DEG[deg]
            # note mapping is (sin, cos, tan) so swap for coordinates (cos, sin)
            return f"({cos_s}, {sin_s})"
        # else numeric fallback
        rad = math.radians(deg)
        return f"({math.cos(rad):.2f}, {math.sin(rad):.2f})"

# --------------------------
# Cog
# --------------------------
class TrigCommands(commands.Cog):
    """Trigonometry Cog with dynamic unit circle generator."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ensure shared store exists
        self.bot.shared = getattr(self.bot, "shared", {})
        self.bot.shared.setdefault("user_modes", {})
        self.user_modes = self.bot.shared["user_modes"]

    # ---- Mode commands ----
    @app_commands.command(name="mode", description="Set your preferred angle mode (degrees or radians).")
    @app_commands.choices(mode=[
        app_commands.Choice(name="degrees", value="deg"),
        app_commands.Choice(name="radians", value="rad"),
    ])
    async def mode_slash(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        self.user_modes[interaction.user.id] = mode.value
        await interaction.response.send_message(f"✅ Mode set to **{mode.name}**.", ephemeral=True)

    @commands.command(name="mode")
    async def mode_prefix(self, ctx: commands.Context, mode: str):
        m = mode.lower()
        if m not in ("deg", "rad", "degrees", "radians"):
            await ctx.send("Usage: `?mode degrees` or `?mode radians`")
            return
        val = "deg" if m.startswith("d") else "rad"
        self.user_modes[ctx.author.id] = val
        await ctx.send(f"✅ Mode set to **{'degrees' if val == 'deg' else 'radians'}**.", mention_author=False)

    # ---- Core helper to resolve angle ----
    async def _resolve_to_radians(self, raw: str, user_id: int) -> Tuple[Optional[float], str, str]:
        parsed, detected, canon = parse_angle_input(raw)
        user_mode = self.user_modes.get(user_id, "deg")
        if detected == "rad":
            # parsed is radians numeric (or None)
            return parsed, "rad", canon
        if detected == "auto":
            if parsed is None:
                return None, user_mode, canon
            # if user-mode is degrees, treat number as degrees
            if user_mode == "deg":
                return math.radians(parsed), "deg", canon
            else:
                return parsed, "rad", canon
        return None, user_mode, canon

    # ---- Unified response builder ----
    async def _respond_trig(self, target, *, user_id: int, func: str, raw_angle: str, is_interaction: bool):
        rad, used_mode, canon = await self._resolve_to_radians(raw_angle, user_id)
        if rad is None:
            msg = f"Could not parse `{raw_angle}`. Try examples: `30`, `π/6`, `pi/4`, `45`."
            if is_interaction:
                await target.response.send_message(msg, ephemeral=True)
            else:
                await target.send(msg)
            return

        deg = deg_from_rad(rad)
        s_sin, s_cos, s_tan = attempt_symbolic_deg(deg)

        numeric = None
        undefined = False
        try:
            if func == "sin":
                numeric = math.sin(rad)
            elif func == "cos":
                numeric = math.cos(rad)
            elif func == "tan":
                cosv = math.cos(rad)
                if abs(cosv) < 1e-12:
                    undefined = True
                    numeric = None
                else:
                    numeric = math.tan(rad)
        except Exception:
            numeric = None

        # choose symbolic when available
        symbol = None
        if func == "sin" and s_sin:
            symbol = s_sin
        elif func == "cos" and s_cos:
            symbol = s_cos
        elif func == "tan" and s_tan:
            symbol = s_tan

        # build embed
        angle_label = canon
        if used_mode == "deg":
            angle_label = f"{round(deg,6)}°"
        else:
            angle_label = canon

        title = f"{func}({angle_label})"
        embed = discord.Embed(title=title, color=discord.Color.blurple())
        if symbol:
            embed.add_field(name="Exact (unit circle)", value=f"`{symbol}`", inline=False)

        if undefined:
            embed.add_field(name="Numeric", value="`undefined`", inline=False)
        elif numeric is not None:
            embed.add_field(name="Numeric", value=f"`{fmt_num(numeric)}`", inline=False)
        else:
            embed.add_field(name="Numeric", value="`error`", inline=False)

        embed.add_field(name="Degrees", value=f"`{round(deg,6)}°`", inline=True)
        ndeg = normalize_degrees(deg)
        quadrant = 1 + int(ndeg // 90)
        if quadrant == 5:
            quadrant = 1
        embed.add_field(name="Quadrant", value=f"`Q{quadrant}`", inline=True)

        if is_interaction:
            await target.response.send_message(embed=embed)
        else:
            await target.send(embed=embed)

    # ---- Slash commands ----
    @app_commands.command(name="sin", description="Sine of an angle (e.g. 30 or pi/6).")
    async def sin_slash(self, interaction: discord.Interaction, angle: str):
        await self._respond_trig(interaction, user_id=interaction.user.id, func="sin", raw_angle=angle, is_interaction=True)

    @app_commands.command(name="cos", description="Cosine of an angle (e.g. 45 or pi/4).")
    async def cos_slash(self, interaction: discord.Interaction, angle: str):
        await self._respond_trig(interaction, user_id=interaction.user.id, func="cos", raw_angle=angle, is_interaction=True)

    @app_commands.command(name="tan", description="Tangent of an angle (e.g. 60 or pi/3).")
    async def tan_slash(self, interaction: discord.Interaction, angle: str):
        await self._respond_trig(interaction, user_id=interaction.user.id, func="tan", raw_angle=angle, is_interaction=True)

    @app_commands.command(name="circle", description="Generate a fresh unit-circle image.")
    async def circle_slash(self, interaction: discord.Interaction, highlight: Optional[str] = None):
        # optional highlight argument: allow user to pass angle to highlight the point
        highlight_rad = None
        if highlight:
            parsed, detected, _ = parse_angle_input(highlight)
            if parsed is not None:
                highlight_rad = parsed if detected == "rad" else math.radians(parsed)

        if plt is None:
            await interaction.response.send_message("Unit circle generator requires matplotlib (pip install matplotlib).", ephemeral=True)
            return

        buf = UnitCirclePlotter.generate_png(highlight_rad)
        if buf is None:
            await interaction.response.send_message("Failed to generate unit circle image.", ephemeral=True)
            return

        file = discord.File(fp=buf, filename="unit_circle.png")
        embed = discord.Embed(title="Unit Circle (degrees in green, radians in purple)", color=discord.Color.green())
        embed.set_image(url="attachment://unit_circle.png")
        await interaction.response.send_message(embed=embed, file=file)

    # ---- Prefix commands ----
    @commands.command(name="sin")
    async def sin_prefix(self, ctx: commands.Context, *, angle: str):
        await self._respond_trig(ctx, user_id=ctx.author.id, func="sin", raw_angle=angle, is_interaction=False)

    @commands.command(name="cos")
    async def cos_prefix(self, ctx: commands.Context, *, angle: str):
        await self._respond_trig(ctx, user_id=ctx.author.id, func="cos", raw_angle=angle, is_interaction=False)

    @commands.command(name="tan")
    async def tan_prefix(self, ctx: commands.Context, *, angle: str):
        await self._respond_trig(ctx, user_id=ctx.author.id, func="tan", raw_angle=angle, is_interaction=False)

    @commands.command(name="circle")
    async def circle_prefix(self, ctx: commands.Context, *, highlight: Optional[str] = None):
        highlight_rad = None
        if highlight:
            parsed, detected, _ = parse_angle_input(highlight)
            if parsed is not None:
                highlight_rad = parsed if detected == "rad" else math.radians(parsed)

        if plt is None:
            await ctx.send("Unit circle generator requires matplotlib (pip install matplotlib).")
            return

        buf = UnitCirclePlotter.generate_png(highlight_rad)
        if buf is None:
            await ctx.send("Failed to generate unit circle image.")
            return

        file = discord.File(fp=buf, filename="unit_circle.png")
        embed = discord.Embed(title="Unit Circle (degrees in green, radians in purple)", color=discord.Color.green())
        embed.set_image(url="attachment://unit_circle.png")
        await ctx.send(embed=embed, file=file)

# --------------------------
# Cog setup
# --------------------------
async def setup(bot: commands.Bot):
    bot.shared = getattr(bot, "shared", {})
    bot.shared.setdefault("user_modes", {})
    await bot.add_cog(TrigCommands(bot))
