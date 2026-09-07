"""투구 지표. 이닝은 내부적으로 아웃 수(outs) 또는 진짜 소수 이닝(1/3 단위)으로 다룬다.

야구 표기 '180.1' 은 180과 1/3 이닝이다. 이 값을 그대로 float 로 쓰면 틀린다. parse_ip 를 거칠 것.
"""

from __future__ import annotations

from stats.constants import LeagueConstants


def parse_ip(ip_str: str | float) -> float:
    """'180.1' -> 180.3333, '180.2' -> 180.6667, '180' -> 180.0"""
    s = str(ip_str)
    if "." not in s:
        return float(s)
    whole, frac = s.split(".", 1)
    if frac not in ("0", "1", "2"):
        raise ValueError(f"invalid baseball IP notation: {ip_str}")
    return int(whole) + int(frac) / 3


def outs_from_ip(ip_str: str | float) -> int:
    return round(parse_ip(ip_str) * 3)


def ip_from_outs(outs: int) -> float:
    """아웃 수 -> 진짜 소수 이닝"""
    return outs / 3


def ip_display(outs: int) -> str:
    """아웃 수 -> 야구 표기 문자열 ('180.1')"""
    return f"{outs // 3}.{outs % 3}"


def fip(c: LeagueConstants, *, hr: int, bb: int, hbp: int, so: int, ip: float) -> float:
    """FIP = (13*HR + 3*(BB+HBP) - 2*K) / IP + cFIP   (ip 는 진짜 소수 이닝)"""
    if ip <= 0:
        raise ValueError("ip must be positive")
    return (13 * hr + 3 * (bb + hbp) - 2 * so) / ip + c.c_fip


def era(er: int, ip: float) -> float:
    if ip <= 0:
        raise ValueError("ip must be positive")
    return er * 9 / ip


def whip(bb: int, h: int, ip: float) -> float:
    if ip <= 0:
        raise ValueError("ip must be positive")
    return (bb + h) / ip


def k_per_9(so: int, ip: float) -> float:
    return so * 9 / ip


def bb_per_9(bb: int, ip: float) -> float:
    return bb * 9 / ip


def k_pct(so: int, bf: int) -> float:
    return so / bf


def bb_pct(bb: int, bf: int) -> float:
    return bb / bf
