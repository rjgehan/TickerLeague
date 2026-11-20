"""Options bots for a long-only league (buy calls and puts, sell to close). APPROXIMATE: there is no free history of
real option prices, so contracts are priced with Black-Scholes at the index's own implied volatility (VXN for QQQ,
VIX for SPY), plus a put skew, the T-bill rate (BIL's trailing year) and the fund's dividend yield; every buy pays 2.5%
over that value and every sell gets 2.5% under (the league fills at the ask and the bid). Idle money sits in BIL.
Signals: the 200-day trend with a 2% band (creative.band_state) on the adjusted close; strikes on the raw close.
Same split as the other backtests: 2016-21 in sample, 2022-26 out of sample, +1d = the same signals a day late."""
import math
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import backtest as b
from creative import band_state, lev_trend
from reassess import row, hdr, run_w
import reassess

reassess.RECENT = "2026-10-20"
N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(right, s, k, t, vol, r, q):
    if t <= 1 / 365:
        return max(s - k, 0.0) if right == "C" else max(k - s, 0.0)
    v = vol * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * vol * vol) * t) / v
    d2 = d1 - v
    if right == "C":
        return s * math.exp(-q * t) * N(d1) - k * math.exp(-r * t) * N(d2)
    return k * math.exp(-r * t) * N(-d2) - s * math.exp(-q * t) * N(-d1)


def sim(und="QQQ", vix="VXN", alloc=0.15, call_m=0.0, put_m=0.0, dte=90, hold=30, mode="both", cost=0.025,
        delay=0, q=0.006):
    """mode: both (calls in an uptrend, puts in a downtrend), calls, puts. call_m/put_m: strike vs price
    (+0.05 = 5% above). Re-buys after `hold` days, at a trend switch, or with under 20 days left."""
    adj = b.closes([und])[und]
    raw = b.load(und)["close"].reindex(adj.index).ffill()
    iv = (b.closes([vix])[vix] / 100).reindex(adj.index).ffill()
    bil = b.closes(["BIL"])["BIL"].reindex(adj.index).ffill()
    bil_r = bil.pct_change().fillna(0.0)
    rate = (bil / bil.shift(252) - 1).clip(lower=0).fillna(0.01)
    on = band_state(adj)
    if delay:
        on = on.shift(delay).fillna(False)
    cash, pos, curve = 1.0, None, []          # pos: (right, strike, expiry index-date, units, opened)
    days = adj.index
    for i, d in enumerate(days):
        cash *= 1 + bil_r.iloc[i]
        s, vol, r = raw.iloc[i], iv.iloc[i], rate.iloc[i]

        def value(p):
            right, k, exp, units, _ = p
            t = max(0, (exp - d).days) / 365
            skew = max(0.0, 1 - k / s) * 0.8 if right == "P" else 0.0
            return units * bs(right, s, k, t, vol + skew, r, q)

        val = value(pos) if pos else 0.0
        if i < 200 or np.isnan(vol):
            curve.append(cash + val)
            continue
        want = "C" if on.iloc[i] else "P"
        if mode == "calls" and want == "P" or mode == "puts" and want == "C":
            want = None
        stale = pos and ((d - pos[4]).days >= hold or (pos[2] - d).days < 20 or pos[0] != want)
        if pos and (stale or want is None):
            cash += val * (1 - cost)
            pos, val = None, 0.0
        if pos is None and want:
            eq = cash
            k = round(s * (1 + (call_m if want == "C" else put_m)))
            exp = d + pd.Timedelta(days=dte)
            skew = max(0.0, 1 - k / s) * 0.8 if want == "P" else 0.0
            px = bs(want, s, k, dte / 365, vol + skew, r, q) * (1 + cost)
            budget = alloc * eq
            if px > 0:
                pos = (want, k, exp, budget / px, d)
                cash -= budget
                val = value(pos)
        curve.append(cash + val)
    return pd.Series(curve, index=days).pct_change().fillna(0.0)


def run(name, **kw):
    row(name, sim(**kw), sim(delay=1, **kw))


if __name__ == "__main__":
    hdr("References")
    row("QQQ buy & hold", *run_w(*b.buy_hold("QQQ")()[:3]))
    row("Trend Rider QQQ->TQQQ", *run_w(*lev_trend("QQQ", "TQQQ")()[:3]))
    bilw = pd.DataFrame({"BIL": 1.0}, index=b.closes(["BIL"]).index)
    row("BIL (T-bills)", *run_w(bilw, b.closes(["BIL"]), 2))

    hdr("A. Trend options on QQQ: ATM calls in an uptrend, ATM puts in a downtrend, 90-day, re-bought monthly")
    for a in (0.10, 0.15, 0.20, 0.30):
        run(f"  {a:.0%} of equity in options", alloc=a)
    hdr("B. Calls only (uptrend), the rest in BIL")
    for a in (0.15, 0.20, 0.30):
        run(f"  {a:.0%} ATM calls", alloc=a, mode="calls")
    run("  25% calls 10% in the money", alloc=0.25, call_m=-0.10, mode="calls")
    hdr("C. Crash hunter: puts only in a downtrend")
    for a in (0.05, 0.10, 0.15):
        run(f"  {a:.0%} in 5% OTM puts, 60-day", alloc=a, put_m=-0.05, dte=60, mode="puts")
    run("  10% ATM puts, 90-day", alloc=0.10, mode="puts")
    hdr("D. The same on SPY (VIX)")
    run("  SPY trend options 15%", und="SPY", vix="VIX", alloc=0.15, q=0.013)
    run("  SPY trend options 20%", und="SPY", vix="VIX", alloc=0.20, q=0.013)
    run("  SPY crash hunter 10% 5% OTM puts", und="SPY", vix="VIX", alloc=0.10, put_m=-0.05, dte=60, mode="puts",
        q=0.013)
