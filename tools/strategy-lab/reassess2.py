"""Reassessment 2026-11-20, after the selloff kept going (SPY -8%, QQQ -12%, chips -22%, BTC -23% in a month).
1) Sector Rotation has no exit between month-ends: test a trend filter on its picks.
2) The trend bots sit in cash (0% in the league) for weeks: test parking idle cash in BIL (T-bills).
Same rules as backtest.py."""
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import backtest as b
from creative import band_state, lev_trend
from reassess import row, hdr, run_w

RECENT = "2026-10-20"
UNI = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "SMH", "QQQ", "GLD", "TLT"]


def sector_rotation(trend_pick=False, daily_exit=False, safe="SHY"):
    """Monthly top 3 of 14 by 126-day return, each only if it beats SHY's (absolute momentum).
    trend_pick: a pick must also be above its 200-day average at month end, else its third goes to `safe`.
    daily_exit: between month-ends, a pick that falls 2% below its 200-day average is swapped into `safe`."""
    px = b.closes(UNI + ["SHY", safe])
    px = px.loc[:, ~px.columns.duplicated()]
    mom = px.pct_change(126)
    s200 = px.rolling(200).mean()
    ends = b.month_ends(px.index)
    w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    picks = []
    for d in px.index:
        if d in ends:
            m = mom.loc[d, UNI].dropna()
            picks = []
            for s, v in m.nlargest(3).items():
                ok = v > mom.loc[d, "SHY"] and (not trend_pick or px.loc[d, s] > s200.loc[d, s])
                picks.append(s if ok else safe)
        if daily_exit:
            picks = [safe if p != safe and px.loc[d, p] < s200.loc[d, p] * 0.98 else p for p in picks]
        for p in picks:
            w.loc[d, p] += 1 / 3
    return w, px, 5


def with_bil(f):
    """Any idle weight (1 - sum of weights) is held in BIL instead of cash."""
    w, px, cost, *_ = f
    bil = b.closes(["BIL"])["BIL"].reindex(px.index).ffill()
    px = px.assign(BIL=bil)
    w = w.reindex(px.index).ffill().fillna(0.0)
    w["BIL"] = (1 - w.drop(columns=["BIL"], errors="ignore").sum(axis=1)).clip(lower=0)
    cb = cost if isinstance(cost, dict) else {c: cost for c in px.columns}
    cb = {**cb, "BIL": 2}
    return w, px, cb


if __name__ == "__main__":
    import reassess
    reassess.RECENT = RECENT
    hdr("1. Sector Rotation")
    row("  now (monthly, vs SHY only)", *run_w(*sector_rotation()))
    row("  + pick must be above its 200d", *run_w(*sector_rotation(True)))
    row("  + daily exit below 200d -2%", *run_w(*sector_rotation(False, True)))
    row("  + both", *run_w(*sector_rotation(True, True)))
    row("  + both, idle in BIL instead of SHY", *run_w(*sector_rotation(True, True, "BIL")))
    hdr("2. Idle cash in BIL instead of cash")
    for name, f in [("Trend Rider QQQ->TQQQ", lev_trend("QQQ", "TQQQ")()), ("Chip trend SMH->SOXL", lev_trend("SMH", "SOXL")()),
                    ("QQQ->QLD", lev_trend("QQQ", "QLD")())]:
        row("  " + name + ", cash", *run_w(*f[:3]))
        row("  " + name + ", BIL", *run_w(*with_bil(f)))
    print("\nBIL alone:")
    w = pd.DataFrame({"BIL": 1.0}, index=b.closes(["BIL"]).index)
    row("  BIL buy & hold", *run_w(w, b.closes(["BIL"]), 2))
