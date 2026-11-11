# Strategy lab

Backtests behind `tools/claude-trader/agents.recommended.toml`: textbook trading rules on ten years of daily bars
(Nov 2016 - Oct 2026), the same kind of data the league trades on (checked against its Alpaca bars).

- Signals use closes up to the trading day only; trades happen at that day's close (the bots' 15:50 ET check-in) and
  pay slippage (5 bps stocks and ETFs, 10 bps leveraged ETFs and crypto). Cash earns nothing, as in the league.
- Parameters are the published defaults, never tuned. 2016-21 is in sample, 2022-26 out of sample; "+1d" runs the
  same signals a day late to see how fragile they are.
- The options test prices calls with Black-Scholes at the VIX (there is no free history of real option prices), so
  it is an approximation.
- Past results do not predict future ones. This is for a paper-trading game, not investment advice.

```bash
python -m pip install --target site numpy pandas
python fetch.py                       # data/*.csv from Yahoo's chart API (daily, adjusted)
PYTHONPATH=site python backtest.py    # every strategy
PYTHONPATH=site:. python blends.py    # 50/50 blends and correlations
PYTHONPATH=site:. python creative.py  # leveraged trend variants, 3x rotation, hybrids, crypto rules
PYTHONPATH=site:. python dips2.py     # dip-buying upgrades (resting orders, core + boost)
PYTHONPATH=site:. python blends2.py   # the blends behind the six bots
PYTHONPATH=site:. python reassess.py   # 2026-11-05: dip cushion, non-tech diversifiers
PYTHONPATH=site:. python safehaven.py  # Safe Haven sensitivity and blend
```

## Results (run of 2026-10-27)

```
strategy                         CAGR 16-21 CAGR 22-26 Sharpe oos MaxDD oos    $ P&L 10y +1d CAGR oos in mkt trades/y
SPY buy & hold (benchmark)            19.2%      12.0%       0.75    -24.5%    1,634,443        12.0%   100%        0
QQQ buy & hold                        27.9%      13.9%       0.68    -34.8%    2,820,312        13.9%   100%        0
QQQ 200d trend -> QQQ                 16.3%      13.4%       0.87    -20.8%    1,490,668        12.0%    76%        4
QQQ 200d trend -> TQQQ                40.2%      24.5%       0.70    -52.2%    7,702,734        19.9%    76%        4
Dual momentum, sectors top 3           8.9%      14.1%       0.78    -19.4%      961,469        13.2%    94%        8
Mega-cap momentum top 3               45.9%       9.2%       0.45    -44.5%    4,861,331         8.4%    70%        8
RSI(2) dips SPY/QQQ                    2.4%       5.7%       0.99     -6.3%      237,937         4.8%    14%       23
RSI(2) dips via UPRO/TQQQ              5.5%      15.9%       0.94    -18.0%      835,554        13.4%    14%       23
Turn of month SPY                      4.7%       0.4%       0.09    -14.0%      146,315        -2.3%    14%       24
Turn of month UPRO                    13.5%      -0.1%       0.09    -38.8%      460,046        -8.4%    14%       24
Vol-target 20% UPRO + trend           17.3%       5.9%       0.40    -25.0%      998,838         5.4%    76%       41
Crypto buy & hold BTC/ETH            101.2%       2.8%       0.33    -68.4%   20,183,126         2.8%   100%        0
Crypto 50d trend BTC/ETH             107.1%      24.8%       0.81    -40.1%   62,329,001        15.1%    61%       32
Crypto 20d trend BTC/ETH             125.0%       7.6%       0.38    -36.3%   46,814,182         5.3%    61%       59
Crypto rotation BTC/ETH/SOL          347.2%      49.6%       0.95    -59.4% 8,088,785,332        49.4%    66%       16
Crypto rotation, 12 league coins top1     128.4%     -20.3%       0.15    -88.1%   11,041,112       -17.8%    81%       23
Crypto rotation, 12 league coins top3     256.6%       3.8%       0.38    -64.8%  417,722,782         6.9%    81%       36
QQQ trend +/-2% band -> TQQQ          30.5%      26.8%       0.74    -43.4%    5,674,087        21.5%    75%        2
QQQ trend +/-2% band -> QQQ           13.8%      14.1%       0.92    -16.1%    1,335,038        12.5%    75%        2
RSI(2) dips as SPY calls, 10%         -6.9%      -3.3%      -0.41    -18.8%     -205,299         nan%   nan%      nan
RSI(2) dips as SPY calls, 20%        -13.8%      -7.1%      -0.41    -36.2%     -336,671         nan%   nan%      nan
correlations, 2022-26:
         trend  trendQ  dips  sectors  crypto
trend     1.00    1.00  0.47     0.67    0.18
trendQ    1.00    1.00  0.47     0.67    0.18
dips      0.47    0.47  1.00     0.38    0.07
sectors   0.67    0.67  0.38     1.00    0.13
crypto    0.18    0.18  0.07     0.13    1.00
trend+crypto   CAGR 16-21  74.8%  22-26  30.4%  Sharpe 1.00  MaxDD -35.7%  $10y   31,456,557
dips+sectors  CAGR 16-21   7.9%  22-26  15.6%  Sharpe 1.03  MaxDD -16.1%  $10y      982,241
trendQ+dips     CAGR 16-21  10.1%  22-26  15.4%  Sharpe 1.09  MaxDD -14.9%  $10y    1,135,542
sectors+crypto   CAGR 16-21  55.8%  22-26  21.5%  Sharpe 1.03  MaxDD -28.0%  $10y   12,059,071
dips+crypto   CAGR 16-21  53.6%  22-26  22.5%  Sharpe 1.10  MaxDD -25.7%  $10y   11,659,515
```
