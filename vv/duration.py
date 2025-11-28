from __future__ import annotations

FADE_MAX = 0.7
FADE_K = 0.3  # fade = min(sec_per * 0.3, 0.7)
FADE_SWITCH = FADE_MAX / FADE_K  # 2.333333...

def fade_for(sec_per: float) -> float:
    if sec_per <= 0:
        return 0.0
    return min(sec_per * FADE_K, FADE_MAX)

def total_for(n: int, sec_per: float, *, transitions: bool) -> float:
    if n <= 0:
        raise ValueError("n must be > 0")
    if sec_per <= 0:
        raise ValueError("sec_per must be > 0")
    if not transitions or n == 1:
        return n * sec_per
    f = fade_for(sec_per)
    return n * sec_per - (n - 1) * f

def sec_per_for_total(n: int, total: float, *, transitions: bool) -> float:
    if n <= 0:
        raise ValueError("n must be > 0")
    if total <= 0:
        raise ValueError("total must be > 0")
    if not transitions or n == 1:
        return total / n if n > 1 else total

    # Case A: sec_per <= FADE_SWITCH  => fade = FADE_K * sec_per
    # total = n*sec_per - (n-1)*FADE_K*sec_per = sec_per*(n - (n-1)*FADE_K)
    denom = n - (n - 1) * FADE_K
    sec_a = total / denom
    if sec_a <= FADE_SWITCH:
        return sec_a

    # Case B: sec_per > FADE_SWITCH => fade = FADE_MAX
    # total = n*sec_per - (n-1)*FADE_MAX
    return (total + (n - 1) * FADE_MAX) / n