"""10 modullu state tarayici — Bitget USDT-M. Orijinal skor, video kopyasi degil."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

import config

TR = timezone(timedelta(hours=3))


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    au = up.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    ad = dn.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = au / ad.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def hour_tr() -> int:
    return datetime.now(TR).hour


def modules(df15: pd.DataFrame, df4h: pd.DataFrame | None, side: str) -> dict[str, bool]:
    """side: BULL veya BEAR. Her kutu o yon icin True/False."""
    c = df15["close"]
    h = df15["high"]
    l = df15["low"]
    o = df15["open"]
    v = df15["volume"]
    last_c = float(c.iloc[-1])
    last_h = float(h.iloc[-1])
    last_l = float(l.iloc[-1])
    last_o = float(o.iloc[-1])
    bull_bar = last_c > last_o
    bear_bar = last_c < last_o
    e20 = float(ema(c, 20).iloc[-1])
    r = float(rsi(c).iloc[-1])
    a = atr(df15)
    vol_sma = float(v.rolling(20).mean().iloc[-1] or 1)
    vol_x = float(v.iloc[-1] / vol_sma) if vol_sma else 1.0
    atr_now = float(a.iloc[-1])
    atr_avg = float(a.rolling(20).mean().iloc[-1] or atr_now)
    macd = ema(c, 12) - ema(c, 26)
    hist = macd - ema(macd, 9)
    hist_v = float(hist.iloc[-1])
    hist_p = float(hist.iloc[-2])

    # TIME: Londra-NY (15-23 TR) biraz daha acik, gece zayif
    hr = hour_tr()
    time_ok = 8 <= hr <= 23

    # VOL
    vol_bull = vol_x >= 1.4 and bull_bar
    vol_bear = vol_x >= 1.4 and bear_bar

    # PRC fiyat EMA
    prc_bull = last_c > e20
    prc_bear = last_c < e20

    # MOM
    mom_bull = hist_v > 0 and hist_v >= hist_p and r < 72
    mom_bear = hist_v < 0 and hist_v <= hist_p and r > 28

    # VLT genisleme
    vlt = atr_now > atr_avg * 1.05

    # OB: son 16 barda genis govde, fiyat o bolgeye donmus
    body = (c - o).abs()
    rng = (h - l).replace(0, np.nan)
    imb = body / rng
    ob_bull = ob_bear = False
    if len(df15) >= 16:
        sl = imb.iloc[-16:-1]
        if sl.max() == sl.max():
            i = int(sl.idxmax())
            if c.iloc[i] > o.iloc[i]:
                ob_lo, ob_hi = float(min(o.iloc[i], c.iloc[i])), float(max(o.iloc[i], c.iloc[i]))
                ob_bull = last_l <= ob_hi * 1.002 and last_c >= ob_lo
            else:
                ob_lo, ob_hi = float(min(o.iloc[i], c.iloc[i])), float(max(o.iloc[i], c.iloc[i]))
                ob_bear = last_h >= ob_lo * 0.998 and last_c <= ob_hi

    # FVG 3 mum boslugu son 8 barda
    fvg_bull = fvg_bear = False
    for i in range(-8, -2):
        if l.iloc[i] > h.iloc[i - 2]:
            fvg_bull = last_c >= h.iloc[i - 2]
        if h.iloc[i] < l.iloc[i - 2]:
            fvg_bear = last_c <= l.iloc[i - 2]

    # FHS likidite supurme
    prior_lo = float(l.iloc[-16:-1].min())
    prior_hi = float(h.iloc[-16:-1].max())
    fhs_bull = last_l < prior_lo and last_c > prior_lo and bull_bar
    fhs_bear = last_h > prior_hi and last_c < prior_hi and bear_bar

    # SCR yapi: son 8 kapanis egimi
    slp = float(c.iloc[-1] / c.iloc[-8] - 1) if len(c) >= 8 else 0
    scr_bull = slp > 0
    scr_bear = slp < 0

    # REG 4H
    reg_bull = reg_bear = False
    if df4h is not None and len(df4h) >= 55:
        e20h = float(ema(df4h["close"], 20).iloc[-1])
        e50h = float(ema(df4h["close"], 50).iloc[-1])
        c4 = float(df4h["close"].iloc[-1])
        if c4 > e20h > e50h:
            reg_bull = True
        elif c4 < e20h < e50h:
            reg_bear = True
        elif c4 > e20h:
            reg_bull = True
        elif c4 < e20h:
            reg_bear = True

    if side == "BULL":
        return {
            "VOL": vol_bull,
            "PRC": prc_bull,
            "MOM": mom_bull,
            "VLT": vlt and bull_bar,
            "TIME": time_ok,
            "OB": ob_bull,
            "FVG": fvg_bull,
            "FHS": fhs_bull,
            "SCR": scr_bull,
            "REG": reg_bull,
        }
    return {
        "VOL": vol_bear,
        "PRC": prc_bear,
        "MOM": mom_bear,
        "VLT": vlt and bear_bar,
        "TIME": time_ok,
        "OB": ob_bear,
        "FVG": fvg_bear,
        "FHS": fhs_bear,
        "SCR": scr_bear,
        "REG": reg_bear,
    }


def pack(mods: dict[str, bool]) -> tuple[int, int, float, float]:
    bits = 0
    for i, name in enumerate(config.MODULES):
        if mods.get(name):
            bits |= 1 << i
    pop = bin(bits).count("1")
    w = pop / len(config.MODULES)
    combo = round(w * w, 3)
    return bits, pop, round(w, 3), combo


def pick_side(df15, df4h) -> tuple[str, dict, int, int, float, float]:
    bull_m = modules(df15, df4h, "BULL")
    bear_m = modules(df15, df4h, "BEAR")
    bs, bp, bw, bc = pack(bull_m)
    rs, rp, rw, rc = pack(bear_m)
    if bp > rp or (bp == rp and bc >= rc):
        return "BULL", bull_m, bs, bp, bw, bc
    return "BEAR", bear_m, rs, rp, rw, rc
