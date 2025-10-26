import math

def format_result(val: float) -> str:
    if abs(val) < 1e-12:
        val = 0.0
    return f"{val:.10g}"

def get_context_for_angle(angle: float, mode: str) -> str | None:
    if mode == "deg":
        a = angle % 360
        quad = (int(a // 90) + 1) if a != 0 else 1
        ref = a % 90
        return f"Quadrant: {quad}\nReference angle: {ref}°"
    else:
        a = angle % (2 * math.pi)
        deg = math.degrees(a)
        quad = (int(deg // 90) + 1) if deg != 0 else 1
        ref = deg % 90
        return f"Quadrant: {quad}\nReference angle: {ref:.4g}°"
