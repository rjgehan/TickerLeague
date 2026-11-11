"""50/50 blends of two strategies (each sleeve keeps its own half of the cash; daily returns averaged)."""
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import backtest as b

def series(f, delay=0):
    w, px, cost, per = f()
    r, _ = b.run(w, px, cost, delay)
    return r

def stock_days(r):  # crypto runs 7 days a week: compound onto stock trading days
    idx = b.closes(["SPY"]).index
    return (1 + r).cumprod().reindex(idx, method="ffill").pct_change().fillna(0.0)

S = {
    "trend": series(b.trend_band(True, 0.02)),
    "trendQ": series(b.trend_band(False, 0.02)),
    "dips": series(b.rsi2(True)),
    "sectors": series(b.dual_momentum),
    "crypto": stock_days(series(b.crypto_trend(50))),
}
print("correlations, 2022-26:")
print(pd.DataFrame(S)[b.SPLIT:].corr().round(2).to_string())
for a, c in [("trend", "crypto"), ("dips", "sectors"), ("trendQ", "dips"), ("sectors", "crypto"), ("dips", "crypto")]:
    r = 0.5 * S[a] + 0.5 * S[c]
    o, i, al = b.stats(r[b.SPLIT:], 252), b.stats(r[:b.SPLIT], 252), b.stats(r, 252)
    print(f"{a}+{c:8} CAGR 16-21 {i['cagr']:6.1%}  22-26 {o['cagr']:6.1%}  Sharpe {o['sharpe']:.2f}  MaxDD {o['maxdd']:6.1%}  $10y {al['pnl']:>12,.0f}")
