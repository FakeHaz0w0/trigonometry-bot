# trigonometry-bot/commands/trig.py
"""
Trig commands Cog (slash + prefix) with dynamic unit-circle image generation
and LaTeX-style math labels using matplotlib's mathtext.

Drop into: trigonometry-bot/commands/trig.py
Requires: matplotlib (for /circle and ?circle image generation)
"""

from __future__ import annotations

import io
import math
import re
from typing import Optional, Tuple

import discord
from discord.ext import commands
from discord import app_commands

# matplotlib (optional). If not installed, image commands will explain how to add it.
try:
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    # tweak mathtext to look crisp
    rcParams["mathtext.fontset"] = "dejavusans"
    rcParams["font.family"] = "DejaVu Sans"
except Exception:
    plt = None  # type: ignore

# ---------------------------
# Symbolic (LaTeX) mapping for common angles (degrees)
# mapping: deg -> (sin_latex, cos_latex, tan_latex)
# ---------------------------
MAPPING_LATEX = {
    0:  (r"$0$", r"$1$", r"$0$"),
    30: (r"$\frac{1}{2}$", r"$\frac{\sqrt{3}}{2}$", r"$\frac{1}{\sqrt{3}}$"),
    45: (r"$\frac{\sqrt{2}}{2}$", r"$\frac{\sqrt{2}}{2}$", r"$1$"),
    60: (r"$\frac{\sqrt{3}}{2}$", r"$\frac{1}{2}$", r"$\sqrt{3}$"),
    90: (r"$1$", r"$0$", r"$\text{undefined}$"),
    120: (r"$\frac{\sqrt{3}}{2}$", r"$-\frac{1}{2}$", r"$-\sqrt{3}$"),
    135: (r"$\frac{\sqrt{2}}{2}$", r"$-\frac{\sqrt{2}}{2}$", r"$-1$"),
    150: (r"$\frac{1}{2}$", r"$-\frac{\sqrt{3}}{2}$", r"$-\frac{1}{\sqrt{3}}$"),
    180: (r"$0$", r"$-1$", r"$0$"),
    210: (r"$-\frac{1}{2}$", r"$-\frac{\sqrt{3}}{2}$", r"$\frac{1}{\sqrt{3}}$"),
    225: (r"$-\frac{\sqrt{2}}{2}$", r"$-\frac{\sqrt{2}}{2}$", r"$1$"),
    240: (r"$-\frac{\sqrt{3}}{2}$", r"$-\frac{1}{2}$", r"$-\sqrt{3}$"),
    270: (r"$-1$", r"$0$", r"$\text{undefined}$"),
    300: (r"$-\frac{\sqrt{3}}{2}$", r"$\frac{1}{2}$", r"$-\sqrt{3}$"),
    315: (r"$-\frac{\sqrt{2}}{2}$", r"$\frac{\sqrt{2}}{2}$", r"$-1$"),
    330: (r"$-\frac{1}{2}$", r"$\frac{\sqrt{3}}{2}$", r"$-\frac{1}{\sqrt{3}}$"),
}

# ---------------------------
# Parsing utilities
# ---------------------------
PI_RE = re.compile(r"^(?P<num>-?\d*\.?\d*)\s*(?:pi|π)(?:\s*/\s*(?P<den>-?\d+(\.\d+)?))?$", re.IGNORECASE)
FRACTION_RE = re.compile(r"^(?P<num>-?\d+(\.\d+)?)/(?P<den>-?\d+(\.\d+)?)$")

def safe_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None

def parse_angle_input(text: str) -> Tuple[Optional[float], str, str]:
    """
    Parse angle text.
    Returns (value, detected_mode, canonical_input)
      - value: numeric value (if detected_mode == 'rad' then value is in radians;
               if detected_mode == 'auto' the caller will decide based on user-mode)
      - detected_mode: 'rad' if text explicitly used pi; 'auto' for plain numbers/fractions/expr
      - canonical_input: cleaned text for display
    Accepts examples: 30, -45.5, pi/6, -pi, 3pi/4, 1/2, (3/2)pi, pi
    """
    if not text or not text.strip():
        return None, "auto", text

    t = text.strip().replace(" ", "")
    # plain numeric literal
    f = safe_float(t)
    if f is not None:
        return f, "auto", t

    # pi-based patterns
    m = PI_RE.match(t)
    if m:
        num = m.group("num")
        den = m.group("den")
        # interpret num
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
                return num_val * math.pi / den_val, "rad", t
            except Exception:
                return None, "rad", t
        return num_val * math.pi, "rad", t

    # simple fraction like 1/2
    m2 = FRACTION_RE.match(t)
    if m2:
        try:
            return float(m2.group("num")) / float(m2.group("den")), "auto", t
        except Exception:
            return None, "auto", t

    # limited safe eval: only allow numbers, whitespace, + - * / ( ) and pi
    if re.fullmatch(r"[0-9\.\+\-\*\/\(\)piπ ]+", text, flags=re.IGNORECASE):
        safe = text.replace("π", "pi")
        # replace 'pi' -> 'math.pi' prior to eval
        safe_for_eval = re.sub(r"(?i)pi", "math.pi", safe)
        try:
            # evaluate with math only
            val = eval(safe_for_eval, {"__builtins__": None, "math": math}, {})
            if isinstance(val, (int, float)):
                # treat as radians if math.pi present else auto
                return float(val), ("rad" if "math.pi" in safe_for_eval else "auto"), t
        except Exception:
            pass

    return None, "auto", text

# ---------------------------
# Formatting helpers
# ---------------------------
def fmt_num(x: float) -> str:
    return f"{x:.6f}"

def deg_from_rad(rad: float) -> float:
    return math.degrees(rad)

def normalize_deg(deg: float) -> float:
    return deg % 360

def symbolic_for_deg(deg: float) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    If deg lands exactly on a special mapping (rounded to nearest integer),
    return latex strings for (sin, cos, tan). Otherwise (None, None, None).
    """
    nd = int(round(normalize_deg(deg)))
    return MAPPING_LATEX.get(nd, (None, None, None))

# ---------------------------
# Unit circle drawing (LaTeX labels)
# ---------------------------
class UnitCirclePlotter:
    KEY_DEGREES = [0, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330]

    @staticmethod
    def _radian_label_for_deg(deg: int) -> str:
        # return LaTeX friendly radian label like r"$\pi/6$"
        if deg == 0:
            return r"$0$"
        if deg == 180:
            return r"$\pi$"
        if deg == 360:
            return r"$2\pi$"
        mapping = {
            30: r"$\frac{\pi}{6}$",
            45: r"$\frac{\pi}{4}$",
            60: r"$\frac{\pi}{3}$",
            90: r"$\frac{\pi}{2}$",
            120: r"$\frac{2\pi}{3}$",
            135: r"$\frac{3\pi}{4}$",
            150: r"$\frac{5\pi}{6}$",
            210: r"$\frac{7\pi}{6}$",
            225: r"$\frac{5\pi}{4}$",
            240: r"$\frac{4\pi}{3}$",
            270: r"$\frac{3\pi}{2}$",
            300: r"$\frac{5\pi}{3}$",
            315: r"$\frac{7\pi}{4}$",
            330: r"$\frac{11\pi}{6}$",
        }
        return mapping.get(deg, rf"${deg/180:.2f}\pi$")

    @staticmethod
    def _coord_latex_for_deg(deg: int) -> str:
        # return latex coordinate pair string "\left(\frac{\sqrt{3}}{2}, \frac{1}{2}\right)" where possible
        if deg in MAPPING_LATEX:
            sin_l, cos_l, _ = MAPPING_LATEX[deg]
            # mapping stored as (sin, cos, tan) so coordinate is (cos, sin)
            cos_l = MAPPING_LATEX[deg][1]
            sin_l = MAPPING_LATEX[deg][0]
            return rf"$\left({cos_l},\ {sin_l}\right)$"
        # numeric fallback
        rad = math.radians(deg)
        return rf"$\left({math.cos(rad):.2f},\ {math.sin(rad):.2f}\right)$"

    @staticmethod
    def generate_png(highlight_rad: Optional[float] = None, size: int = 800) -> Optional[io.BytesIO]:
        """
        Return BytesIO containing PNG image of the unit circle with LaTeX labels.
        If matplotlib is not installed, returns None.
        """
        if plt is None:
            return None

        fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
        ax.set_aspect("equal")
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-1.3, 1.3)
        ax.axis("off")

        # circle and axes
        circle = plt.Circle((0, 0), 1.0, fill=False, linewidth=1.7, color="black", zorder=0)
        ax.add_artist(circle)
        ax.axhline(0, color="gray", linewidth=0.8, zorder=0)
        ax.axvline(0, color="gray", linewidth=0.8, zorder=0)

        # plot and annotate key angles
        for deg in UnitCirclePlotter.KEY_DEGREES:
            rad = math.radians(deg)
            x, y = math.cos(rad), math.sin(rad)
            # point
            ax.scatter([x], [y], s=24, color="#1f77b4", zorder=3)
            # degree label (green) slightly outside the circle
            ax.text(x * 1.12, y * 1.12, f"{deg}°", color="green", ha="center", va="center", fontsize=10, zorder=4)
            # radian label (purple), LaTeX
            rad_label = UnitCirclePlotter._radian_label_for_deg(deg)
            ax.text(x * 1.32, y * 1.32, rad_label, color="purple", ha="center", va="center", fontsize=10, zorder=4)
            # coordinate label (inside the circle) as LaTeX
            coord = UnitCirclePlotter._coord_latex_for_deg(deg)
            ax.text(x * 0.72, y * 0.72, coord, color="black", ha="center", va="center", fontsize=9, zorder=4)

        # highlight optional angle
        if highlight_rad is not None:
            hx, hy = math.cos(highlight_rad), math.sin(highlight_rad)
            ax.plot([0, hx], [0, hy], color="red", linewidth=2.2, zorder=5)
            ax.scatter([hx], [hy], s=80, color="red", zorder=6)
            # annotate coordinates numerically
            ax.text(hx * 1.05, hy * 1.05, rf"$({math.cos(highlight_rad):.3f},\ {math.sin(highlight_rad):.3f})$",
                    color="red", ha="center", va="center", fontsize=9, zorder=7)

        buf = io.BytesIO()
        plt.tight_layout()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

# ---------------------------
# Cog Implementation
# ---------------------------
class TrigCog(commands.Cog):
    """Trigonometry Cog providing slash & prefix trig functions and circle plotting."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ensure shared user_modes map exists (main.py must set bot.shared beforehand)
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
        if m not in ("degrees", "radians", "deg", "rad"):
            await ctx.send("Usage: `?mode degrees` or `?mode radians`")
            return
        val = "deg" if m.startswith("d") else "rad"
        self.user_modes[ctx.author.id] = val
        await ctx.send(f"✅ Mode set to **{'degrees' if val == 'deg' else 'radians'}**.", mention_author=False)

    # ---- Core: resolve input -> radians ----
    async def _resolve_to_radians(self, raw: str, user_id: int) -> Tuple[Optional[float], str, str]:
        parsed, detected, canon = parse_angle_input(raw)
        user_mode = self.user_users_mode(user_id)
        # if explicit rad (pi present) -> parsed is radians
        if detected == "rad":
            return parsed, "rad", canon
        if detected == "auto":
            if parsed is None:
                return None, user_mode, canon
            # if user's mode is degrees, treat numeric as degrees
            if user_mode == "deg":
                return math.radians(parsed), "deg", canon
            else:
                return parsed, "rad", canon
        return None, user_mode, canon

    def user_users_mode(self, user_id: int) -> str:
        """Get user mode (deg|rad) defaulting to degrees."""
        return self.user_modes.get(user_id, "deg")

    # ---- Helper to build and send trig response ----
    async def _respond_trig(self, target, *, user_id: int, func_name: str, raw_angle: str, is_interaction: bool):
        rad, used_mode, canon = await self._resolve_to_radians(raw_angle, user_id)
        if rad is None:
            msg = f"❌ Could not parse `{raw_angle}` — try `30`, `π/6`, `pi/4`, or `45`."
            if is_interaction:
                await target.response.send_message(msg, ephemeral=True)
            else:
                await target.send(msg)
            return

        deg = deg_from_rad(rad)
        sin_sym, cos_sym, tan_sym = symbolic_for_deg(deg)

        # compute numeric and handle undefined tangent
        numeric = None
        undefined = False
        try:
            if func_name == "sin":
                numeric = math.sin(rad)
            elif func_name == "cos":
                numeric = math.cos(rad)
            elif func_name == "tan":
                cosv = math.cos(rad)
                if abs(cosv) < 1e-12:
                    undefined = True
                    numeric = None
                else:
                    numeric = math.tan(rad)
        except Exception:
            numeric = None

        # choose symbolic if available
        symbol = None
        if func_name == "sin" and sin_sym:
            symbol = sin_sym
        elif func_name == "cos" and cos_sym:
            symbol = cos_sym
        elif func_name == "tan" and tan_sym:
            symbol = tan_sym

        # Build embed with LaTeX in code blocks for Exact (Discord doesn't render LaTeX in embeds;
        # we include LaTeX for human readability and the image shows LaTeX rendering)
        angle_label = canon if used_mode == "rad" else f"{round(deg, 6)}°"
        embed = discord.Embed(title=f"{func_name}({angle_label})", color=discord.Color.blurple())

        if symbol:
            embed.add_field(name="Exact (unit circle)", value=f"`{symbol}`", inline=False)

        if undefined:
            embed.add_field(name="Numeric", value="`undefined`", inline=False)
        elif numeric is not None:
            embed.add_field(name="Numeric", value=f"`{fmt_num(numeric)}`", inline=False)
        else:
            embed.add_field(name="Numeric", value="`error`", inline=False)

        embed.add_field(name="Degrees", value=f"`{round(deg,6)}°`", inline=True)
        q = 1 + int(normalize_deg(deg) // 90)
        if q == 5:
            q = 1
        embed.add_field(name="Quadrant", value=f"`Q{q}`", inline=True)

        if is_interaction:
            await target.response.send_message(embed=embed)
        else:
            await target.send(embed=embed)

    # ---- Slash commands: sin/cos/tan ----
    @app_commands.command(name="sin", description="Sine of an angle — accepts 30, π/6, pi/4, etc.")
    async def sin_slash(self, interaction: discord.Interaction, angle: str):
        await self._respond_trig(interaction, user_id=interaction.user.id, func_name="sin", raw_angle=angle, is_interaction=True)

    @app_commands.command(name="cos", description="Cosine of an angle — accepts 45, π/4, etc.")
    async def cos_slash(self, interaction: discord.Interaction, angle: str):
        await self._respond_trig(interaction, user_id=interaction.user.id, func_name="cos", raw_angle=angle, is_interaction=True)

    @app_commands.command(name="tan", description="Tangent of an angle — accepts 60, π/3, etc.")
    async def tan_slash(self, interaction: discord.Interaction, angle: str):
        await self._respond_trig(interaction, user_id=interaction.user.id, func_name="tan", raw_angle=angle, is_interaction=True)

    @app_commands.command(name="circle", description="Generate a unit circle image (optional highlight).")
    async def circle_slash(self, interaction: discord.Interaction, highlight: Optional[str] = None):
        # parse optional highlight angle
        highlight_rad = None
        if highlight:
            parsed, detected, _ = parse_angle_input(highlight)
            if parsed is not None:
                highlight_rad = parsed if detected == "rad" else math.radians(parsed)

        if plt is None:
            await interaction.response.send_message("❌ `matplotlib` not installed. Install with `pip install matplotlib` to use /circle.", ephemeral=True)
            return

        buf = UnitCirclePlotter.generate_png(highlight_rad)
        if buf is None:
            await interaction.response.send_message("❌ Failed to generate image.", ephemeral=True)
            return

        file = discord.File(buf, filename="unit_circle.png")
        embed = discord.Embed(title="📘 Unit Circle (degrees in green, radians in purple)", color=discord.Color.green())
        embed.set_image(url="attachment://unit_circle.png")
        await interaction.response.send_message(embed=embed, file=file)

    # ---- Prefix commands: ?sin ?cos ?tan ?circle ----
    @commands.command(name="sin")
    async def sin_prefix(self, ctx: commands.Context, *, angle: str):
        await self._respond_trig(ctx, user_id=ctx.author.id, func_name="sin", raw_angle=angle, is_interaction=False)

    @commands.command(name="cos")
    async def cos_prefix(self, ctx: commands.Context, *, angle: str):
        await self._respond_trig(ctx, user_id=ctx.author.id, func_name="cos", raw_angle=angle, is_interaction=False)

    @commands.command(name="tan")
    async def tan_prefix(self, ctx: commands.Context, *, angle: str):
        await self._respond_trig(ctx, user_id=ctx.author.id, func_name="tan", raw_angle=angle, is_interaction=False)

    @commands.command(name="circle")
    async def circle_prefix(self, ctx: commands.Context, *, highlight: Optional[str] = None):
        highlight_rad = None
        if highlight:
            parsed, detected, _ = parse_angle_input(highlight)
            if parsed is not None:
                highlight_rad = parsed if detected == "rad" else math.radians(parsed)

        if plt is None:
            await ctx.send("❌ `matplotlib` not installed. Install with `pip install matplotlib` to use ?circle.")
            return

        buf = UnitCirclePlotter.generate_png(highlight_rad)
        if buf is None:
            await ctx.send("❌ Failed to generate image.")
            return

        file = discord.File(buf, filename="unit_circle.png")
        embed = discord.Embed(title="📘 Unit Circle (degrees in green, radians in purple)", color=discord.Color.green())
        embed.set_image(url="attachment://unit_circle.png")
        await ctx.send(embed=embed, file=file)

# ---------------------------
# async setup for extension loading
# ---------------------------
async def setup(bot: commands.Bot):
    """Called by main.py when loading the extension: await bot.load_extension('commands.trig')"""
    await bot.add_cog(TrigCog(bot))
