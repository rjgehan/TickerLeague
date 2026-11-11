"""Daily bars (10 years, split/dividend adjusted) from Yahoo's chart API into data/<SYM>.csv: date,open,high,low,close,adjclose,volume."""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).parent / "data"
SYMBOLS = [
    "SPY", "QQQ", "IWM", "DIA", "TLT", "IEF", "SHY", "GLD", "SLV", "USO",
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "XLC", "SMH",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "NFLX", "JPM", "LLY", "COST",
    "TQQQ", "SOXL", "UPRO", "^VIX", "BTC-USD", "ETH-USD", "SOL-USD",
    "TECL", "QLD", "TMF", "EFA", "EEM", "VNQ", "DBC", "AGG", "UUP", "DBMF", "KMLM",
]


def fetch(sym: str) -> int:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=10y&interval=1d&events=div,splits"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.load(r)
    res = j["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
    lines = ["date,open,high,low,close,adjclose,volume"]
    for i, t in enumerate(ts):
        o, h, l, c, v, a = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i], adj[i]
        if None in (o, h, l, c, a):
            continue
        d = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
        lines.append(f"{d},{o},{h},{l},{c},{a},{v or 0}")
    name = sym.replace("^", "").replace("-USD", "")
    (OUT / f"{name}.csv").write_text("\n".join(lines) + "\n")
    return len(lines) - 1


if __name__ == "__main__":
    import urllib.parse  # noqa: F401
    OUT.mkdir(exist_ok=True)
    for s in sys.argv[1:] or SYMBOLS:
        try:
            print(s, fetch(s))
        except Exception as e:  # keep going; report
            print(s, "FAILED", e)
        time.sleep(0.4)
