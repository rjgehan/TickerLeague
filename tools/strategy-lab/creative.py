"""A creative batch: leveraged trend variants, rotations between 3x funds, a trend-filtered stock/bond 3x mix, 2x/3x
hybrids and crypto rules. Same rules as backtest.py (trade at the close, slippage, 2016-21 in sample, 2022-26 out of
sample, "+1d" one day late). Run: PYTHONPATH=site:. python creative.py"""
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import backtest as b


def band_state(c, n=200, band=0.02):
    """Trend switch: ON once close > SMA*(1+band), OFF once close < SMA*(1-band); starts ON if above the SMA."""
    sma = c.rolling(n).mean()
    out, on = [], None
    for x, s in zip(c, sma):
        if np.isnan(s):
            out.append(False)
            continue
        if on is None:
            on = x > s
        elif not on and x > s * (1 + band):
            on = True
        elif on and x < s * (1 - band):
            on = False
        out.append(on)
    return pd.Series(out, index=c.index)


def lev_trend(sig, hold, n=200, band=0.02):
    def f():
        px = b.closes(sorted({sig, hold}))
        on = band_state(px[sig], n, band)
        w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
        w.loc[on, hold] = 1.0
        return w, px, 10, 252
    return f


def vix_trend(calm, stressed, vmax=25):
    """QQQ trend ON: the 3x fund while the VIX is calm, the plain fund while it is high; OFF: cash."""
    def f():
        px = b.closes(["QQQ", calm, stressed])
        vix = b.closes(["VIX"])["VIX"]
        on = band_state(px["QQQ"])
        w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
        w.loc[on & (vix < vmax), calm] = 1.0
        w.loc[on & (vix >= vmax), stressed] = 1.0
        return w, px, 10, 252
    return f


LEV = {"QQQ": "TQQQ", "SPY": "UPRO", "SMH": "SOXL", "XLK": "TECL"}


def lev_rotation(daily_exit):
    """Monthly: of QQQ, SPY, SMH and XLK, the one with the best 6-month return among those in their trend; hold its 3x
    fund. None in trend: GLD if GLD is in its trend, else cash. daily_exit: leave at once if the pick's trend breaks."""
    def f():
        sig = list(LEV) + ["GLD"]
        px = b.closes(sig + list(LEV.values()))
        on = {s: band_state(px[s]) for s in sig}
        mom = px[sig].pct_change(126)
        ends = b.month_ends(px.index)
        w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
        pick = None
        for d in px.index:
            if d in ends:
                cands = {s: mom.loc[d, s] for s in LEV if on[s].loc[d] and not np.isnan(mom.loc[d, s])}
                pick = max(cands, key=cands.get) if cands else ("GLD" if on["GLD"].loc[d] else None)
            if daily_exit and pick and not on[pick].loc[d]:
                pick = "GLD" if pick != "GLD" and on["GLD"].loc[d] else None
            if pick:
                w.loc[d, LEV.get(pick, pick)] = 1.0
        return w, px, 10, 252
    return f


def hfea(trend):
    """55% UPRO / 45% TMF, rebalanced monthly; trend: everything to cash while SPY is out of its trend."""
    def f():
        px = b.closes(["UPRO", "TMF", "SPY"])
        on = band_state(px["SPY"])
        ends = b.month_ends(px.index)
        w = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
        for d in px.index:
            if trend and not on.loc[d]:
                w.loc[d] = 0.0
            elif d in ends or (trend and w.index.get_loc(d) > 0 and not on.iloc[w.index.get_loc(d) - 1]):
                w.loc[d] = {"UPRO": 0.55, "TMF": 0.45, "SPY": 0.0}
        return w, px, 10, 252
    return f


def hybrid(idx, normal, boost, n=200):
    """Trend ON: hold `normal` (e.g. 2x); during an RSI(2) < 10 dip switch to `boost` (3x) until close > 5-day average;
    trend OFF: cash."""
    def f():
        px = b.closes(sorted({idx, normal, boost}))
        c = px[idx]
        on = band_state(c, n)
        r2, sma5 = b.rsi(c, 2), c.rolling(5).mean()
        w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
        dip = False
        for i, d in enumerate(px.index):
            if not on.iloc[i]:
                dip = False
                continue
            if dip and c.iloc[i] > sma5.iloc[i]:
                dip = False
            elif not dip and r2.iloc[i] < 10:
                dip = True
            w.loc[d, boost if dip else normal] = 1.0
        return w, px, 10, 252
    return f


def crypto_turtle(entry=20, exit_=10):
    def f():
        px = b.closes(["BTC", "ETH"], crypto=True)
        w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
        for s in px.columns:
            hi, lo = px[s].rolling(entry).max().shift(1), px[s].rolling(exit_).min().shift(1)
            pos, col = 0.0, []
            for x, h, l in zip(px[s], hi, lo):
                if pos == 0 and not np.isnan(h) and x > h:
                    pos = 0.5
                elif pos > 0 and not np.isnan(l) and x < l:
                    pos = 0.0
                col.append(pos)
            w[s] = col
        return w, px, 10, 365
    return f


def crypto_trend_n(n, coins=("BTC", "ETH"), weekly=False):
    def f():
        px = b.closes(list(coins), crypto=True)
        w = pd.DataFrame(np.nan if weekly else 0.0, index=px.index, columns=px.columns)
        days = px.index[px.index.day_of_week == 6] if weekly else px.index
        for s in px.columns:
            above = px[s] > px[s].rolling(n).mean()
            w.loc[days, s] = np.where(above.loc[days], 1 / len(coins), 0.0)
        return w, px, 10, 365
    return f


def crypto_stack():
    """Half size above the 50-day average, full size above both the 50- and 200-day averages."""
    px = b.closes(["BTC", "ETH"], crypto=True)
    w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for s in px.columns:
        a50 = px[s] > px[s].rolling(50).mean()
        a200 = px[s] > px[s].rolling(200).mean()
        w[s] = np.where(a50 & a200, 0.5, np.where(a50, 0.25, 0.0))
    return w, px, 10, 365


STRATS = {
    "ref Trend Rider QQQ->TQQQ (200d)": lev_trend("QQQ", "TQQQ"),
    "  same, 150-day average": lev_trend("QQQ", "TQQQ", 150),
    "  same, 100-day average": lev_trend("QQQ", "TQQQ", 100),
    "QQQ trend -> QLD (2x)": lev_trend("QQQ", "QLD"),
    "SPY trend -> UPRO": lev_trend("SPY", "UPRO"),
    "SMH trend -> SOXL (chips 3x)": lev_trend("SMH", "SOXL"),
    "XLK trend -> TECL (tech 3x)": lev_trend("XLK", "TECL"),
    "VIX filter: TQQQ calm / QQQ stressed": vix_trend("TQQQ", "QQQ"),
    "VIX filter: TQQQ calm / QLD stressed": vix_trend("TQQQ", "QLD"),
    "3x rotation QQQ/SPY/SMH/XLK monthly": lev_rotation(False),
    "3x rotation + daily trend exit": lev_rotation(True),
    "HFEA 55 UPRO / 45 TMF": hfea(False),
    "HFEA + SPY trend filter": hfea(True),
    "Hybrid QQQ: QLD, TQQQ on dips": hybrid("QQQ", "QLD", "TQQQ"),
    "Hybrid QQQ: QQQ, TQQQ on dips": hybrid("QQQ", "QQQ", "TQQQ"),
    "Hybrid SMH: SMH, SOXL on dips": hybrid("SMH", "SMH", "SOXL"),
    "ref Crypto 50d trend BTC/ETH": crypto_trend_n(50),
    "  same, 100-day": crypto_trend_n(100),
    "  same, 30-day": crypto_trend_n(30),
    "  same, checked weekly (Sundays)": crypto_trend_n(50, weekly=True),
    "Crypto 50d trend BTC only": crypto_trend_n(50, ("BTC",)),
    "Crypto turtle 20/10 BTC/ETH": crypto_turtle(),
    "Crypto turtle 55/20 BTC/ETH": crypto_turtle(55, 20),
    "Crypto stacked 50d+200d": crypto_stack,
}

if __name__ == "__main__":
    print(f"{'strategy':40} {'16-21':>7} {'22-26':>7} {'+1d':>7} {'Sharpe':>6} {'MaxDD':>7} {'$500k->10y':>12}")
    for name, f in STRATS.items():
        w, px, cost, per = f()
        r, _ = b.run(w, px, cost)
        late, _ = b.run(w, px, cost, 1)
        i, o, a, l = b.stats(r[:b.SPLIT], per), b.stats(r[b.SPLIT:], per), b.stats(r, per), b.stats(late[b.SPLIT:], per)
        print(f"{name:40} {i['cagr']:7.1%} {o['cagr']:7.1%} {l['cagr']:7.1%} {o['sharpe']:6.2f} {o['maxdd']:7.1%} {500_000 + a['pnl']:>12,.0f}")
