"""Reassessment after the Oct-Nov 2026 tech selloff.
1) Dip cushion: only boost to 3x on an RSI(2) dip when the index is at least `cush` above its 200-day average.
2) Diversifiers: strategies that do not move with leveraged tech.
Same rules as backtest.py: trade at the close, slippage, 2016-21 in sample, 2022-26 out of sample, +1d = a day late."""
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import backtest as b
from creative import band_state, lev_trend

RECENT = "2026-10-06"   # the selloff month


def row(name, r, late=None, per=252):
    i, o, a = b.stats(r[:b.SPLIT], per), b.stats(r[b.SPLIT:], per), b.stats(r, per)
    l = b.stats(late[b.SPLIT:], per)["cagr"] if late is not None else np.nan
    m = (1 + r[RECENT:]).prod() - 1
    print(f"{name:46} {i['cagr']:7.1%} {o['cagr']:7.1%} {l:7.1%} {o['sharpe']:6.2f} {o['maxdd']:7.1%} {m:8.1%}")


def hdr(t):
    print(f"\n{t}\n{'strategy':46} {'16-21':>7} {'22-26':>7} {'+1d':>7} {'Sharpe':>6} {'MaxDD':>7} {'lastmo':>8}")


# ---------------------------------------------------------------- 1. dip cushion
def hybrid_cush(idx, normal, boost, cush=None, sma50=False):
    """Claude Tech: trend ON (2% band) -> `normal`; RSI(2) < 10 dip -> `boost` until close > 5-day average, but only if
    the index is > cush above its 200-day (and above its 50-day if sma50); OFF -> cash."""
    px = b.closes(sorted({idx, normal, boost}))
    c = px[idx]
    on = band_state(c)
    r2, sma5, s200, s50 = b.rsi(c, 2), c.rolling(5).mean(), c.rolling(200).mean(), c.rolling(50).mean()
    w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    dip = False
    for i, d in enumerate(px.index):
        if not on.iloc[i]:
            dip = False
            continue
        ok = (cush is None or c.iloc[i] > s200.iloc[i] * (1 + cush)) and (not sma50 or c.iloc[i] > s50.iloc[i])
        if dip and c.iloc[i] > sma5.iloc[i]:
            dip = False
        elif not dip and r2.iloc[i] < 10 and ok:
            dip = True
        w.loc[d, boost if dip else normal] = 1.0
    return w, px, 10


def dip_booster(cush=None, sma50=False):
    """Dip Sniper: halves SPY/UPRO and QQQ/TQQQ, each the hybrid above."""
    parts = []
    for idx, lev in (("SPY", "UPRO"), ("QQQ", "TQQQ")):
        w, px, cost = hybrid_cush(idx, idx, lev, cush, sma50)
        parts.append((w * 0.5, px))
    px = pd.concat([p for _, p in parts], axis=1)
    px = px.loc[:, ~px.columns.duplicated()]
    w = pd.concat([w for w, _ in parts], axis=1).T.groupby(level=0).sum().T.reindex(columns=px.columns).fillna(0)
    return w, px, 10


def run_w(w, px, cost):
    r, _ = b.run(w, px, cost)
    late, _ = b.run(w, px, cost, 1)
    return r, late


# ---------------------------------------------------------------- 2. diversifiers
def trend_basket(syms, n=200, band=0.02, monthly=False):
    """Equal slots; each asset held while above its n-day average (2% band); unused slots stay cash."""
    px = b.closes(syms)
    w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for s in syms:
        w[s] = band_state(px[s], n, band).astype(float) / len(syms)
    if monthly:
        ends = b.month_ends(px.index)
        w = w.where(pd.Series(w.index.isin(sorted(ends)), index=w.index), np.nan)
    return w, px, 5


def rotation(syms, cash="SHY", top=1, look=126):
    px = b.closes(syms + [cash])
    mom = px.pct_change(look)
    w = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
    for d in sorted(b.month_ends(px.index)):
        m = mom.loc[d, syms].dropna()
        if m.empty:
            continue
        w.loc[d] = 0.0
        for s, v in m.nlargest(top).items():
            w.loc[d, s if v > mom.loc[d, cash] else cash] += 1 / top
    return w, px, 5


def bh(sym):
    px = b.closes([sym])
    return pd.DataFrame({sym: 1.0}, index=px.index), px, 5


def corr_and_crash(name, r, ref):
    x = pd.concat([r, ref], axis=1).loc[b.SPLIT:].dropna()
    x = x[(x.iloc[:, 1] != 0)]
    c = x.corr().iloc[0, 1]
    # months when QQQ fell more than 5%
    q = b.closes(["QQQ"])["QQQ"].pct_change().fillna(0)
    mo = pd.concat({"s": r, "q": q}, axis=1).loc["2016-12-01":].groupby(pd.Grouper(freq="ME")).apply(lambda d: (1 + d).prod() - 1)
    bad = mo[mo["q"] < -0.05]
    print(f"{name:46} corr w/ TQQQ trend {c:5.2f}   avg in {len(bad)} QQQ<-5% months {bad['s'].mean():6.1%}   (QQQ {bad['q'].mean():6.1%})")


if __name__ == "__main__":
    hdr("1. Claude Tech: SMH, SOXL on dips")
    for cush, s50, label in [(None, False, "now (no cushion)"), (0.0, False, "dip only if > 200d"), (0.02, False, "dip only if > 200d +2%"),
                             (0.04, False, "dip only if > 200d +4%"), (0.06, False, "dip only if > 200d +6%"), (None, True, "dip only if > 50d")]:
        row("  " + label, *run_w(*hybrid_cush("SMH", "SMH", "SOXL", cush, s50)))
    hdr("1b. Dip Sniper: SPY/UPRO + QQQ/TQQQ")
    for cush, s50, label in [(None, False, "now (no cushion)"), (0.0, False, "dip only if > 200d"), (0.02, False, "dip only if > 200d +2%"),
                             (0.04, False, "dip only if > 200d +4%"), (0.06, False, "dip only if > 200d +6%"), (None, True, "dip only if > 50d")]:
        row("  " + label, *run_w(*dip_booster(cush, s50)))

    hdr("2. Diversifiers")
    tq, _ = b.run(*lev_trend("QQQ", "TQQQ")()[:3])
    ref = {"ref Trend Rider (QQQ trend -> TQQQ)": lev_trend("QQQ", "TQQQ")()[:3],
           "ref Chip Rocket (SMH trend -> SOXL)": lev_trend("SMH", "SOXL")()[:3]}
    cands = {
        "GTAA5 monthly (SPY EFA IEF VNQ DBC, 210d)": trend_basket(["SPY", "EFA", "IEF", "VNQ", "DBC"], 210, 0.0, True),
        "Trend basket 7 (SPY EFA EEM TLT GLD DBC UUP)": trend_basket(["SPY", "EFA", "EEM", "TLT", "GLD", "DBC", "UUP"]),
        "Defensive trend (TLT GLD DBC UUP IEF)": trend_basket(["TLT", "GLD", "DBC", "UUP", "IEF"]),
        "Gold 200d trend": trend_basket(["GLD"]),
        "Gold+bonds+dollar rotation top1": rotation(["GLD", "TLT", "UUP", "DBC"]),
        "Defensive rotation top2 (GLD TLT UUP DBC XLP XLU XLV)": rotation(["GLD", "TLT", "UUP", "DBC", "XLP", "XLU", "XLV"], top=2),
        "Managed futures DBMF buy&hold (2019+)": bh("DBMF"),
        "Managed futures KMLM buy&hold (2020+)": bh("KMLM"),
        "Sector rotation now (14 ETFs top3)": b.dual_momentum(),
    }
    for name, (w, px, cost, *_) in {**ref, **cands}.items():
        row(name, *run_w(w, px, cost))
    print()
    for name, (w, px, cost, *_) in {**ref, **cands}.items():
        r, _ = b.run(w, px, cost)
        corr_and_crash(name, r, tq)
