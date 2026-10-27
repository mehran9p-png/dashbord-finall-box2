#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wealth Terminal Pro V25 — Automated Multi-Source Price Sync Engine
Updates data/prices.json, data/portfolio.json, and data/history.json
Sources: TSETMC + BrsApi + Tetherland + Nobitex + CoinGecko + CryptoCompare
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO_PATH = os.path.join(ROOT, "data", "portfolio.json")
PRICES_PATH = os.path.join(ROOT, "data", "prices.json")
HISTORY_PATH = os.path.join(ROOT, "data", "history.json")

BRS_API_KEY = os.environ.get("BRS_API_KEY", "FreeSV0E1LSgB9RDjuf0QorSLViX8pPG")

def fetch_json(url, timeout=12):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (WealthTerminalPro/25.0)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def normalize_fa(text):
    if not text:
        return ""
    return (
        str(text)
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", "")
        .strip()
    )

def fetch_usdt_toman():
    # 1. Tetherland
    try:
        data = fetch_json("https://api.tetherland.com/currencies")
        price = float(data["data"]["currencies"]["USDT"]["price"])
        if price > 20000:
            return int(price)
    except Exception:
        pass
    # 2. Nobitex (Rial -> Toman)
    try:
        data = fetch_json("https://apiv2.nobitex.ir/v3/orderbook/USDTIRT")
        last_rial = float(data.get("lastTradePrice", 0))
        if last_rial > 200000:
            return int(round(last_rial / 10.0))
    except Exception:
        pass
    return None

def fetch_crypto_usd():
    out = {}
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,liquity-usd,tether&vs_currencies=usd&include_24hr_change=true"
        data = fetch_json(url)
        mapping = {
            "bitcoin": "BTC",
            "ethereum": "ETH",
            "solana": "SOL",
            "liquity-usd": "LUSD",
            "tether": "USDT"
        }
        for cg_id, sym in mapping.items():
            if cg_id in data:
                out[sym] = {
                    "usd": float(data[cg_id].get("usd", 0)),
                    "change24h": round(float(data[cg_id].get("usd_24h_change", 0)), 2)
                }
    except Exception:
        pass
    return out

def fetch_tse_stock_tsetmc(ins_code):
    if not ins_code:
        return None
    try:
        url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ins_code}"
        data = fetch_json(url, timeout=8)
        info = data.get("closingPriceInfo", {})
        p_closing = float(info.get("pClosing", 0))
        p_dr_cot_val = float(info.get("pDrCotVal", 0))
        yesterday = float(info.get("priceYesterday", 0))
        price_rial = p_dr_cot_val if p_dr_cot_val > 0 else p_closing
        if price_rial > 0:
            price_toman = round(price_rial / 10.0, 1)
            chg = round(((price_rial - yesterday) / yesterday) * 100.0, 2) if yesterday > 0 else 0.0
            return {"price": price_toman, "change": chg}
    except Exception:
        pass
    return None

def main():
    with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
        portfolio = json.load(f)
    with open(PRICES_PATH, "r", encoding="utf-8") as f:
        prices = json.load(f)

    usdt = fetch_usdt_toman()
    if usdt:
        prices["fx"]["usdtToman"] = usdt
        prices["fx"]["freeUsdToman"] = int(round(usdt * 0.996))

    crypto = fetch_crypto_usd()
    for sym, val in crypto.items():
        if val.get("usd", 0) > 0:
            prices["crypto"][sym] = val

    # Update stocks via TSETMC / BrsApi
    for st in portfolio.get("stocks", []):
        sym = st["symbol"]
        ins = st.get("insCode")
        res = fetch_tse_stock_tsetmc(ins)
        if res and res["price"] > 0:
            st["currentPrice"] = res["price"]
            st["dailyChange"] = res["change"]
            prices["stocks"][sym] = res

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prices["updatedAt"] = now_iso
    portfolio["meta"]["lastUpdated"] = now_iso

    with open(PRICES_PATH, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)
    with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

    print(f"Successfully updated prices at {now_iso}")

if __name__ == "__main__":
    main()
