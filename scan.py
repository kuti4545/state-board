#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests

import config
from engine import pick_side
from render import render_html

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "state-board/1.0"})
TR = timezone(timedelta(hours=3))


def get_tickers():
    r = SESSION.get(
        f"{config.BITGET_BASE}/api/v2/mix/market/tickers",
        params={"productType": config.PRODUCT_TYPE},
        timeout=20,
    )
    r.raise_for_status()
    rows = r.json().get("data") or []
    out = []
    skip = {"SPYUSDT", "TSLAUSDT", "NVDAUSDT", "SOXLUSDT", "SOXSUSDT"}
    for row in rows:
        try:
            vol = float(row.get("usdtVolume") or 0)
        except (TypeError, ValueError):
            vol = 0.0
        if vol < config.MIN_VOLUME or row.get("symbol") in skip:
            continue
        out.append(row)
    out.sort(key=lambda x: float(x.get("usdtVolume") or 0), reverse=True)
    return out[: config.MAX_SYMBOLS]


def candles(symbol, gran, limit=80):
    try:
        r = SESSION.get(
            f"{config.BITGET_BASE}/api/v2/mix/market/candles",
            params={
                "symbol": symbol,
                "granularity": gran,
                "limit": str(limit),
                "productType": config.PRODUCT_TYPE,
            },
            timeout=15,
        )
        body = r.json()
        raw = body.get("data") or []
        if len(raw) < 40:
            return None
        df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "base_vol", "quote_vol"])
        for col in ["open", "high", "low", "close", "base_vol", "quote_vol"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna().sort_values("ts").reset_index(drop=True)
        df["volume"] = df["base_vol"]
        if gran == "15m" and len(df) >= 2:
            last_open = int(df["ts"].iloc[-1])
            if int(time.time() * 1000) < last_open + 15 * 60 * 1000 - 8000:
                df = df.iloc[:-1].reset_index(drop=True)
        return df if len(df) >= 40 else None
    except Exception:
        return None


def scan_one(row):
    symbol = row.get("symbol")
    d15 = candles(symbol, "15m", 80)
    if d15 is None:
        return None
    d4 = candles(symbol, "4H", 80)
    side, mods, state, pop, weight, combo = pick_side(d15, d4)
    try:
        price = float(row.get("lastPr") or d15["close"].iloc[-1])
        chg = float(row.get("change24h") or 0) * 100
        vol = float(row.get("usdtVolume") or 0)
    except (TypeError, ValueError):
        price = float(d15["close"].iloc[-1])
        chg, vol = 0.0, 0.0
    signal = ""
    if pop >= config.MIN_POPCOUNT and combo >= config.MIN_COMBO:
        signal = side
    return {
        "symbol": symbol,
        "price": float(price),
        "change24h": round(float(chg), 2),
        "volume": float(vol),
        "side": side,
        "state": int(state),
        "pop": int(pop),
        "weight": float(weight),
        "combo": float(combo),
        "mods": {k: bool(v) for k, v in mods.items()},
        "signal": signal,
    }


def send_tg(text):
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        print(text)
        return False
    try:
        r = SESSION.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        return r.status_code == 200
    except requests.RequestException:
        return False


def main():
    started = datetime.now(TR)
    tickers = get_tickers()
    rows = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(scan_one, t) for t in tickers]
        for fut in as_completed(futs):
            try:
                item = fut.result()
            except Exception as exc:
                print("hata", exc)
                continue
            if item:
                rows.append(item)
            time.sleep(0.01)
    rows.sort(key=lambda x: (x["pop"], x["combo"]), reverse=True)
    bulls = [x for x in rows if x["signal"] == "BULL"]
    bears = [x for x in rows if x["signal"] == "BEAR"]
    payload = {
        "updated_at": started.strftime("%Y-%m-%d %H:%M:%S TR"),
        "scanned": len(rows),
        "total": len(tickers),
        "bull": len(bulls),
        "bear": len(bears),
        "signals": len(bulls) + len(bears),
        "min_pop": config.MIN_POPCOUNT,
        "min_combo": config.MIN_COMBO,
        "rows": rows,
    }
    Path("docs").mkdir(parents=True, exist_ok=True)
    Path(config.DATA_PATH).write_text(
        json.dumps(payload, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    Path(config.HTML_PATH).write_text(render_html(payload), encoding="utf-8")

    prev = {}
    sp = Path(config.STATE_PATH)
    if sp.exists():
        try:
            prev = json.loads(sp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    last_keys = set(prev.get("sent") or [])
    sent = []
    for item in bulls + bears:
        key = f"{item['symbol']}:{item['signal']}"
        if key in last_keys:
            sent.append(key)
            continue
        arrow = "🟢 BULL" if item["signal"] == "BULL" else "🔴 BEAR"
        ok = send_tg(
            f"{arrow}  <b>{item['symbol']}</b>  [STATE]\n"
            f"Pop {item['pop']}/10  combo {item['combo']}  state {item['state']}\n"
            f"Fiyat {item['price']}  24s {item['change24h']:+.2f}%\n"
            f"<i>Panel skorudur, emir değildir.</i>"
        )
        if ok:
            sent.append(key)
    Path(config.STATE_PATH).write_text(
        json.dumps({"sent": sent[-80:], "updated": payload["updated_at"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"taranan {len(rows)} sinyal {payload['signals']} bull {len(bulls)} bear {len(bears)}")


if __name__ == "__main__":
    main()
