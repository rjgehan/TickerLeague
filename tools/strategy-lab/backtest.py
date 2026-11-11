"""Backtests of textbook strategies on 10 years of daily bars (data/*.csv, adjusted closes).

Honesty rules: a signal on day t uses closes up to t only; the trade happens at t's close (the bots' 15:50 ET check-in)
and earns from t's close on; every change of weight pays slippage (5 bps stocks/ETFs, 10 bps leveraged ETFs and
crypto). Parameters are the published defaults, never tuned. Results are split into 2016-21 (in sample, where these
rules come from) and 2022-26 (out of sample). A "+1 day" column runs the same signals one day late (fragility check).
Cash earns 0 (the league pays no interest). Starting equity $500,000, like the league.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).parent / "data"
START, SPLIT = "2016-11-01", "2022-01-01"
CAPITAL = 500_000


def load(sym):
    df = pd.read_csv(D / f"{sym}.csv", parse_dates=["date"]).set_index("date")
    return df


def closes(syms, crypto=False):
    px = pd.concat({s: load(s)["adjclose"] for s in syms}, axis=1)
    if not crypto:
        px = px.reindex(load("SPY").index)
    return px.ffill().loc[START:]


def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def month_ends(idx):
    s = pd.Series(idx, index=idx)
    return set(s.groupby([idx.year, idx.month]).max())


def run(weights, px, cost_bps, delay=0):
    """weights: DataFrame of target weights decided at each close (rows sum <= 1). Returns daily portfolio returns."""
    w = weights.reindex(px.index).ffill().fillna(0.0)
    if delay:
        w = w.shift(delay).fillna(0.0)
    rets = px.pct_change().fillna(0.0)
    gross = (w.shift(1).fillna(0.0) * rets).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(w.abs().sum(axis=1))
    cost = turnover * (cost_bps if np.isscalar(cost_bps) else 0) / 1e4
    if not np.isscalar(cost_bps):
        cost = (w.diff().abs().fillna(w.abs()) * pd.Series(cost_bps)).sum(axis=1) / 1e4
    return gross - cost, w


def stats(r, periods):
    if len(r) < 20:
        return {}
    eq = (1 + r).cumprod()
    years = len(r) / periods
    cagr = eq.iloc[-1] ** (1 / years) - 1
    vol = r.std() * math.sqrt(periods)
    sharpe = r.mean() / r.std() * math.sqrt(periods) if r.std() > 0 else 0
    dd = (eq / eq.cummax() - 1).min()
    return {"cagr": cagr, "sharpe": sharpe, "maxdd": dd, "pnl": CAPITAL * (eq.iloc[-1] - 1)}


# ------------------------------------------------------------------------------------------- strategies
# each returns (weights, prices, cost_bps, periods_per_year)

def buy_hold(sym):
    def f():
        px = closes([sym])
        return pd.DataFrame({sym: 1.0}, index=px.index), px, 5, 252
    return f


def trend_qqq(lev):
    def f():
        px = closes(["QQQ", "TQQQ"])
        on = px["QQQ"] > px["QQQ"].rolling(200).mean()
        w = pd.DataFrame({"QQQ": 0.0, "TQQQ": 0.0}, index=px.index)
        w.loc[on, "TQQQ" if lev else "QQQ"] = 1.0
        return w, px, {"QQQ": 5, "TQQQ": 10}, 252
    return f


def dual_momentum():
    uni = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "SMH", "QQQ", "GLD", "TLT"]
    px = closes(uni + ["SHY"])
    mom = px.pct_change(126)
    w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for d in sorted(month_ends(px.index)):
        m = mom.loc[d, uni].dropna()
        if m.empty:
            continue
        top = m.nlargest(3)
        for s, v in top.items():
            w.loc[d, s if v > mom.loc[d, "SHY"] else "SHY"] += 1 / 3
    keep = w.index.isin(sorted(month_ends(px.index)))
    w = w.where(pd.Series(keep, index=w.index), np.nan)
    return w, px, 5, 252


def megacap_momentum():
    uni = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "NFLX", "JPM", "LLY", "COST"]
    px = closes(uni + ["SPY"])
    mom = px[uni].shift(5).pct_change(121)   # 6 months, skipping the last week
    trend = px["SPY"] > px["SPY"].rolling(200).mean()
    w = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
    for d in sorted(month_ends(px.index)):
        w.loc[d] = 0.0
        if not trend.loc[d]:
            continue
        top = mom.loc[d].dropna().nlargest(3)
        for s in top.index:
            w.loc[d, s] = 1 / 3
    # daily exit when SPY loses its 200-day trend mid-month
    w.loc[~trend & w.isna().all(axis=1)] = 0.0
    return w, px, 5, 252


def rsi2(lev):
    def f():
        sig = closes(["SPY", "QQQ"])
        trade = {"SPY": "UPRO", "QQQ": "TQQQ"} if lev else {"SPY": "SPY", "QQQ": "QQQ"}
        px = closes(list(trade.values()))
        w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
        for s, t in trade.items():
            c = sig[s]
            r2, sma200, sma5 = rsi(c, 2), c.rolling(200).mean(), c.rolling(5).mean()
            pos = 0.0
            col = []
            for i in range(len(c)):
                if pos == 0 and c.iloc[i] > sma200.iloc[i] and r2.iloc[i] < 10:
                    pos = 0.5
                elif pos > 0 and c.iloc[i] > sma5.iloc[i]:
                    pos = 0.0
                col.append(pos)
            w[t] = col
        return w, px, 10 if lev else 5, 252
    return f


def turn_of_month(sym):
    def f():
        px = closes([sym])
        idx = px.index
        ends = sorted(month_ends(idx))
        pos = pd.Series(0.0, index=idx)
        loc = {d: i for i, d in enumerate(idx)}
        for d in ends:
            i = loc[d]
            pos.iloc[i:i + 3] = 1.0   # buy at the last day's close, hold through the 3rd trading day's close
        return pd.DataFrame({sym: pos}), px, 10 if sym in ("UPRO", "TQQQ") else 5, 252
    return f


def vol_target(sym, target):
    def f():
        px = closes([sym, "SPY"])
        rv = px["SPY"].pct_change().rolling(20).std() * math.sqrt(252) * (3 if sym in ("UPRO", "TQQQ") else 1)
        trend = px["SPY"] > px["SPY"].rolling(200).mean()
        wt = (target / rv).clip(upper=1.0).where(trend, 0.0)
        wt = wt.round(1)   # rebalance only on 10%-steps of change
        return pd.DataFrame({sym: wt, "SPY": 0.0}), px, 10, 252
    return f


def crypto_trend(n):
    def f():
        px = closes(["BTC", "ETH"], crypto=True)
        w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
        for s in px.columns:
            w[s] = np.where(px[s] > px[s].rolling(n).mean(), 0.5, 0.0)
        return w, px, 10, 365
    return f


def crypto_bh():
    px = closes(["BTC", "ETH"], crypto=True)
    return pd.DataFrame(0.5, index=px.index, columns=px.columns), px, 10, 365


def crypto_rotation():
    """Weekly: the strongest of BTC/ETH/SOL by 4-week return, if positive; else cash."""
    px = closes(["BTC", "ETH", "SOL"], crypto=True)
    mom = px.pct_change(28)
    w = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
    for d in px.index[px.index.day_of_week == 6]:   # Sundays
        w.loc[d] = 0.0
        m = mom.loc[d].dropna()
        if not m.empty and m.max() > 0:
            w.loc[d, m.idxmax()] = 1.0
    return w, px, 10, 365


LEAGUE_COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "BCH", "LINK", "AVAX", "DOT", "UNI", "AAVE"]


def crypto_rotation_all(top):
    """Weekly (Sunday): the `top` strongest of the league's 12 pairs by 4-week return, equal weight, only those with a
    positive return (else cash). Coins join once they have 4 weeks of history: no hindsight in the universe."""
    def f():
        px = closes(LEAGUE_COINS, crypto=True)
        mom = px.pct_change(28, fill_method=None)
        w = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
        for d in px.index[px.index.day_of_week == 6]:
            w.loc[d] = 0.0
            m = mom.loc[d].dropna()
            m = m[m > 0].nlargest(top)
            for s in m.index:
                w.loc[d, s] = 1 / top
        return w, px, 10, 365
    return f


def trend_band(lev, band):
    """QQQ vs its 200-day average with a buffer: in above SMA*(1+band), out below SMA*(1-band) (fewer whipsaws)."""
    def f():
        px = closes(["QQQ", "TQQQ"])
        c, sma = px["QQQ"], px["QQQ"].rolling(200).mean()
        pos, col = 0.0, []
        for i in range(len(c)):
            if pd.isna(sma.iloc[i]):
                col.append(0.0)
                continue
            if pos == 0 and c.iloc[i] > sma.iloc[i] * (1 + band):
                pos = 1.0
            elif pos == 1 and c.iloc[i] < sma.iloc[i] * (1 - band):
                pos = 0.0
            col.append(pos)
        w = pd.DataFrame({"QQQ": 0.0, "TQQQ": 0.0}, index=px.index)
        w["TQQQ" if lev else "QQQ"] = col
        return w, px, {"QQQ": 5, "TQQQ": 10}, 252
    return f


def _bs_call(s, k, t, vol):
    if t <= 0:
        return max(s - k, 0.0)
    d1 = (math.log(s / k) + 0.5 * vol * vol * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    n = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    return s * n(d1) - k * n(d2)


def rsi2_calls(alloc):
    """APPROXIMATE: the RSI(2) dip signal on SPY bought as a ~30-day at-the-money SPY call with `alloc` of equity,
    sold when the signal exits (or at expiry). Prices from Black-Scholes with VIX as the volatility, paying 3% of the
    premium each way for the spread (the league fills options at the ask/bid). No real option prices go in."""
    def f():
        spy = closes(["SPY"])["SPY"]
        raw = load("SPY")["close"].reindex(spy.index).ffill()   # options strike on the unadjusted price
        vix = closes(["VIX"])["VIX"] / 100
        r2, sma200, sma5 = rsi(spy, 2), spy.rolling(200).mean(), spy.rolling(5).mean()
        eq, held, curve = 1.0, None, []
        for i, d in enumerate(spy.index):
            if held:
                k, t0, n0, units = held
                days = (d - t0).days
                val = _bs_call(raw.iloc[i], k, max(0, 30 - days) / 365, vix.iloc[i])
                if spy.iloc[i] > sma5.iloc[i] or days >= 30:
                    eq += units * val * 0.97 - n0
                    held = None
                    curve.append(eq)
                    continue
                curve.append(eq + units * val * 0.97 - n0)
                continue
            if spy.iloc[i] > sma200.iloc[i] and r2.iloc[i] < 10 and not pd.isna(vix.iloc[i]):
                prem = _bs_call(raw.iloc[i], raw.iloc[i], 30 / 365, vix.iloc[i]) * 1.03
                spend = eq * alloc
                held = (raw.iloc[i], d, spend, spend / prem)
            curve.append(eq)
        r = pd.Series(curve, index=spy.index).pct_change().fillna(0.0)
        return r
    return f


STRATS = {
    "SPY buy & hold (benchmark)": buy_hold("SPY"),
    "QQQ buy & hold": buy_hold("QQQ"),
    "QQQ 200d trend -> QQQ": trend_qqq(False),
    "QQQ 200d trend -> TQQQ": trend_qqq(True),
    "Dual momentum, sectors top 3": dual_momentum,
    "Mega-cap momentum top 3": megacap_momentum,
    "RSI(2) dips SPY/QQQ": rsi2(False),
    "RSI(2) dips via UPRO/TQQQ": rsi2(True),
    "Turn of month SPY": turn_of_month("SPY"),
    "Turn of month UPRO": turn_of_month("UPRO"),
    "Vol-target 20% UPRO + trend": vol_target("UPRO", 0.20),
    "Crypto buy & hold BTC/ETH": crypto_bh,
    "Crypto 50d trend BTC/ETH": crypto_trend(50),
    "Crypto 20d trend BTC/ETH": crypto_trend(20),
    "Crypto rotation BTC/ETH/SOL": crypto_rotation,
    "Crypto rotation, 12 league coins top1": crypto_rotation_all(1),
    "Crypto rotation, 12 league coins top3": crypto_rotation_all(3),
    "QQQ trend +/-2% band -> TQQQ": trend_band(True, 0.02),
    "QQQ trend +/-2% band -> QQQ": trend_band(False, 0.02),
}

OPTION_STRATS = {
    "RSI(2) dips as SPY calls, 10%": rsi2_calls(0.10),
    "RSI(2) dips as SPY calls, 20%": rsi2_calls(0.20),
}


def main(only=None):
    rows = []
    for name, f in STRATS.items():
        if only and only not in name:
            continue
        w, px, cost, per = f()
        out = {}
        for tag, delay in (("", 0), ("late", 1)):
            r, wd = run(w, px, cost, delay)
            out[tag + "is"] = stats(r[:SPLIT], per)
            out[tag + "oos"] = stats(r[SPLIT:], per)
            out[tag + "all"] = stats(r, per)
            if not tag:
                out["invested"] = (wd.sum(axis=1) > 0).mean()
                out["trades"] = (wd.diff().abs().sum(axis=1) > 0.01).sum() / (len(wd) / per)
        rows.append((name, out))
    for name, f in OPTION_STRATS.items():
        if only and only not in name:
            continue
        r = f()
        rows.append((name, {"is": stats(r[:SPLIT], 252), "oos": stats(r[SPLIT:], 252), "all": stats(r, 252),
                            "lateoos": {"cagr": float("nan")}, "invested": float("nan"), "trades": float("nan")}))
    print(f"{'strategy':32} {'CAGR 16-21':>10} {'CAGR 22-26':>10} {'Sharpe oos':>10} {'MaxDD oos':>9} {'$ P&L 10y':>12} {'+1d CAGR oos':>12} {'in mkt':>6} {'trades/y':>8}")
    for name, o in rows:
        print(f"{name:32} {o['is']['cagr']:10.1%} {o['oos']['cagr']:10.1%} {o['oos']['sharpe']:10.2f} {o['oos']['maxdd']:9.1%} "
              f"{o['all']['pnl']:12,.0f} {o['lateoos']['cagr']:12.1%} {o['invested']:6.0%} {o['trades']:8.0f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
