import math
from bot.utils import format_result

def test_format_result_zero():
    assert format_result(0.0) == "0"

def test_format_result_precision():
    s = format_result(math.sqrt(2) / 2)
    assert s.startswith("0.707106")
