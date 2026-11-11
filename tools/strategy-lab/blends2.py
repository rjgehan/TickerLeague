import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import backtest as b
import creative as c
import dips2 as d

def ser(f):
    w, px, cost, per = f()
    r, _ = b.run(w, px, cost)
    return r

def stock_days(r):
    idx = b.closes(["SPY"]).index
    return (1 + r).cumprod().reindex(idx, method="ffill").pct_change().fillna(0.0)

S = {
    "trend": ser(c.lev_trend("QQQ", "TQQQ")),
    "qld": ser(c.lev_trend("QQQ", "QLD")),
    "chips": ser(c.hybrid("SMH", "SMH", "SOXL")),
    "rot": ser(c.lev_rotation(True)),
    "dipb": d.run("D"),
    "cstack": stock_days(ser(c.crypto_stack)),
    "c50": stock_days(ser(c.crypto_trend_n(50))),
}
print(pd.DataFrame(S)[b.SPLIT:].corr().round(2).to_string())
for name, mix in {
    "50 trend + 50 crypto stacked": {"trend": .5, "cstack": .5},
    "50 trend + 50 crypto 50d (current)": {"trend": .5, "c50": .5},
    "50 chips + 50 crypto stacked": {"chips": .5, "cstack": .5},
    "70 QLD trend + 30 crypto stacked": {"qld": .7, "cstack": .3},
    "50 dip booster + 50 chips": {"dipb": .5, "chips": .5},
    "50 rotation + 50 crypto stacked": {"rot": .5, "cstack": .5},
    "1/3 chips + 1/3 dip booster + 1/3 crypto": {"chips": 1/3, "dipb": 1/3, "cstack": 1/3},
}.items():
    r = sum(v * S[k] for k, v in mix.items())
    i, o, a = b.stats(r[:b.SPLIT], 252), b.stats(r[b.SPLIT:], 252), b.stats(r, 252)
    print(f"{name:42} 16-21 {i['cagr']:6.1%}  22-26 {o['cagr']:6.1%}  Sharpe {o['sharpe']:.2f}  MaxDD {o['maxdd']:6.1%}  $500k->10y {500_000 + a['pnl']:>13,.0f}")
