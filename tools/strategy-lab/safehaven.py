import warnings; warnings.filterwarnings("ignore")
import pandas as pd, backtest as b
from creative import lev_trend
from reassess import rotation, row, hdr
H = ["GLD", "TLT", "UUP", "DBC"]
def r_of(t):
    w, px, cost, *_ = t; return b.run(w, px, cost)[0], b.run(w, px, cost, 1)[0]
hdr("Safe Haven rotation: sensitivity")
for look in (63, 126, 252):
    row(f"  top1 of GLD TLT UUP DBC, {look}d lookback", *r_of(rotation(H, look=look)))
row("  without gold (TLT UUP DBC)", *r_of(rotation(["TLT", "UUP", "DBC"])))
row("  top2", *r_of(rotation(H, top=2)))
hdr("Blends (daily rebalanced halves)")
tq, tql = r_of(lev_trend("QQQ", "TQQQ")()); hv, hvl = r_of(rotation(H))
row("  50% TQQQ trend + 50% Safe Haven", 0.5*tq+0.5*hv, 0.5*tql+0.5*hvl)
row("  TQQQ trend alone", tq, tql)
