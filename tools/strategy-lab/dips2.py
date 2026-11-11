"""Dip Sniper upgrades. Two halves: SPY -> UPRO and QQQ -> TQQQ, 50% each; trend = index > its 200-day average.

A  close dips: buy at the close when RSI(2) < 10 (the original).
B  resting buy: while flat in an uptrend, leave a buy order k% under the 3x fund's close for the next day; it fills if
   the day's low reaches it (at the limit, or the open if it gaps below). Uses daily highs/lows: an approximation.
C  A and B together.
D  core + boost: hold the plain index fund (SPY / QQQ) whenever it is in its trend (2% band), and swap into the 3x
   fund during an RSI(2) dip until the bounce (close > 5-day average); out of the trend: cash.
E  D, plus B's resting buy for the boost.
All exits at the close when the index closes above its 5-day average (D/E: back to the plain fund).
"""
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import backtest as b

PAIRS = {"SPY": "UPRO", "QQQ": "TQQQ"}


def ohlc(sym):
    d = b.load(sym)
    f = d["adjclose"] / d["close"]
    return pd.DataFrame({k: d[k] * f for k in ("open", "high", "low")}).assign(close=d["adjclose"])


def half(idx_sym, lev_sym, mode, k=0.06, band=0.02):
    """Daily returns of one half (its own capital), mode in A..E."""
    days = b.closes(["SPY"]).index
    ix = ohlc(idx_sym).reindex(days).ffill()
    lv = ohlc(lev_sym).reindex(days).ffill()
    c = ix["close"]
    sma200, sma5, r2 = c.rolling(200).mean(), c.rolling(5).mean(), b.rsi(c, 2)
    core = mode in ("D", "E")
    rest = mode in ("B", "C", "E")
    close_dip = mode in ("A", "C", "D", "E")
    held = "cash"           # what the half holds after today's close: cash, plain, lev
    trend = False
    rets = []
    for i in range(1, len(days)):
        prev = held
        # today's return of what we held overnight
        if prev == "lev":
            r = lv["close"].iloc[i] / lv["close"].iloc[i - 1] - 1
        elif prev == "plain":
            r = c.iloc[i] / c.iloc[i - 1] - 1
        else:
            r = 0.0
        # a resting buy (placed at yesterday's close) fills intraday
        if rest and prev != "lev" and (trend if core else c.iloc[i - 1] > sma200.iloc[i - 1]):
            limit = lv["close"].iloc[i - 1] * (1 - k)
            if lv["low"].iloc[i] <= limit:
                fill = min(lv["open"].iloc[i], limit)
                base = r if prev == "plain" else 0.0
                # from the fill to the close in the 3x fund; before the fill, what we held
                part_before = (c.loc[days[i]] if False else 0)  # noqa (kept simple below)
                if prev == "plain":   # sold the plain fund at the moment of the fill: approximate by the 3x fill path
                    r = lv["close"].iloc[i] / fill - 1 + (fill / lv["close"].iloc[i - 1] - 1) / 3
                else:
                    r = lv["close"].iloc[i] / fill - 1
                r -= 0.001
                held = "lev"
                prev = "lev*"
        rets.append(r)
        # decisions at today's close
        if pd.isna(sma200.iloc[i]):
            continue
        if core:
            if not trend and c.iloc[i] > sma200.iloc[i] * (1 + band):
                trend = True
            elif trend and c.iloc[i] < sma200.iloc[i] * (1 - band):
                trend = False
        new = held
        uptrend = trend if core else c.iloc[i] > sma200.iloc[i]
        if held == "lev":
            if prev != "lev*" and c.iloc[i] > sma5.iloc[i]:
                new = "plain" if core and uptrend else "cash"
            if core and not trend:
                new = "cash"
        else:
            if close_dip and uptrend and r2.iloc[i] < 10:
                new = "lev"
            elif core:
                new = "plain" if trend else "cash"
        if new != held:
            rets[-1] -= 0.001 if "lev" in (new, held) else 0.0005
        held = new
    return pd.Series([0.0] + rets, index=days)


def run(mode, k=0.06):
    r = 0.5 * half("SPY", "UPRO", mode, k) + 0.5 * half("QQQ", "TQQQ", mode, k)
    return r


def show(name, r):
    i, o, a = b.stats(r[:b.SPLIT], 252), b.stats(r[b.SPLIT:], 252), b.stats(r, 252)
    print(f"{name:44} 16-21 {i['cagr']:6.1%}   22-26 {o['cagr']:6.1%}  Sharpe {o['sharpe']:.2f}  MaxDD {o['maxdd']:6.1%}  $10y {a['pnl']:>12,.0f}")


if __name__ == "__main__":
    show("A  close dips (original)", run("A"))
    show("B  resting buy 6% under (3x fund)", run("B", 0.06))
    show("B  resting buy 9% under (3x fund)", run("B", 0.09))
    show("C  close dips + resting buy 6%", run("C", 0.06))
    show("D  core index + 3x boost on dips", run("D"))
    show("E  D + resting buy 6%", run("E", 0.06))
    w, px, cost, per = b.trend_band(True, 0.02)()
    r, _ = b.run(w, px, cost)
    show("ref: Trend Rider (QQQ trend -> TQQQ)", r)
