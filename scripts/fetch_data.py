#!/usr/bin/env python3
"""
Refresh the economic data behind the D-Advisory Markets & Economy dashboard.

Sources (all free, no API key needed):
  * FRED (Federal Reserve Bank of St. Louis): U.S. Treasury, Federal Reserve,
    BLS, BEA, Freddie Mac and EIA series, plus OECD series for Canada.
  * Bank of Canada Valet API: policy rate, Government of Canada bond yields,
    CPI and core CPI measures, USD/CAD exchange rate.

Market prices (stocks, indexes, crypto, commodities) are NOT fetched here.
They come from TradingView's embedded widgets, which update on their own.

Output: data/data.js  (window.MD = {...})
The file is only rewritten when a number actually changes, so the scheduled
job does not create empty commits.

Run locally with:  python scripts/fetch_data.py
Uses only the Python standard library.
"""
import csv
import datetime as dt
import io
import json
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "data.js"
UA = {"User-Agent": "D-Advisory-dashboard/1.0 (+https://dinian.ca)"}

# Weekly series (last value of each week, about 10 years) ---------------------
FRED_WEEKLY = ["DGS2", "DGS5", "DGS10", "DGS30", "T10Y2Y", "DFF", "MORTGAGE30US",
               "DTWEXBGS", "DCOILWTICO", "DCOILBRENTEU"]
BOC_WEEKLY = ["V39079", "BD.CDN.2YR.DQ.YLD", "BD.CDN.5YR.DQ.YLD",
              "BD.CDN.10YR.DQ.YLD", "BD.CDN.LONG.DQ.YLD", "FXUSDCAD"]

# Monthly series (long history) ------------------------------------------------
FRED_MONTHLY = {  # output key -> FRED id
    "UNRATE": "UNRATE", "DFF": "DFF", "DGS2": "DGS2", "DGS10": "DGS10", "DGS30": "DGS30",
    "T10Y2Y": "T10Y2Y", "MORTGAGE30US": "MORTGAGE30US", "DTWEXBGS": "DTWEXBGS",
    "DCOILWTICO": "DCOILWTICO", "DCOILBRENTEU": "DCOILBRENTEU",
    "IRLTLT01CAM156N": "IRLTLT01CAM156N", "LRUNTTTTCAM156S": "LRUNTTTTCAM156S",
    "IR3TIB01CAM156N": "IR3TIB01CAM156N",
}
FRED_YOY = {"CPI": "CPIAUCSL", "CORECPI": "CPILFESL", "PCE": "PCEPI", "COREPCE": "PCEPILFE"}
BOC_MONTHLY = {"CACPI": "STATIC_TOTALCPICHANGE", "CATRIM": "CPI_TRIM",
               "CAMEDIAN": "CPI_MEDIAN", "BOC": "V39079"}


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8")
        except Exception as e:  # network hiccup: wait and retry
            if i == tries - 1:
                raise
            print(f"  retry {url[:70]}... ({e})", file=sys.stderr)
            time.sleep(4 * (i + 1))


def fred_csv(series_id, monthly=False, start="1940-01-01"):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    if monthly:
        url += "&fq=Monthly&fam=avg"
    rows = list(csv.reader(io.StringIO(get(url))))[1:]
    out = []
    for r in rows:
        if len(r) < 2 or r[1] in (".", ""):
            continue
        try:
            out.append((r[0], float(r[1])))
        except ValueError:
            pass
    return out


def boc_obs(series_id, start):
    j = json.loads(get(f"https://www.bankofcanada.ca/valet/observations/{series_id}/json?start_date={start}"))
    out = []
    for o in j.get("observations", []):
        cell = o.get(series_id)
        if cell and cell.get("v") not in (None, ""):
            out.append((o["d"], float(cell["v"])))
    return out


def week_grid(today):
    """Fridays covering the last 10 years, ending at the most recent Friday."""
    last_fri = today - dt.timedelta(days=(today.weekday() - 4) % 7)
    first = last_fri - dt.timedelta(weeks=520)
    return [(first + dt.timedelta(weeks=i)).isoformat() for i in range(521)]


def to_weekly(rows, weeks, dp):
    out, i, last = [], 0, None
    for w in weeks:
        while i < len(rows) and rows[i][0] <= w:
            last = rows[i][1]
            i += 1
        out.append(None if last is None else round(last, dp))
    return out


def latest(rows, dp):
    return [rows[-1][0], round(rows[-1][1], dp), round(rows[-2][1], dp)]


def month_key(d):
    return d[:7]


def pack_monthly(rows, end_month):
    """Contiguous monthly array from the first observation; missing months are null."""
    m = {}
    for d, v in rows:
        if month_key(d) <= end_month:
            m[month_key(d)] = v  # last value in the month wins (BoC daily data)
    if not m:
        return None
    keys = sorted(m)
    y, mo = map(int, keys[0].split("-"))
    ey, emo = map(int, keys[-1].split("-"))
    vals = []
    while (y, mo) <= (ey, emo):
        k = f"{y:04d}-{mo:02d}"
        vals.append(round(m[k], 2) if k in m else None)
        mo += 1
        if mo > 12:
            y, mo = y + 1, 1
    return {"start": keys[0], "v": vals}


def monthly_avg(rows):
    """Average daily observations by month (used for the BoC policy rate)."""
    acc = {}
    for d, v in rows:
        acc.setdefault(month_key(d), []).append(v)
    return [(k + "-01", sum(v) / len(v)) for k, v in sorted(acc.items())]


def yoy(rows):
    by = {month_key(d): v for d, v in rows}
    out = []
    for d, v in rows:
        k = month_key(d)
        prev = by.get(f"{int(k[:4]) - 1}{k[4:]}")
        if prev:
            out.append((d, (v / prev - 1) * 100))
    return out


def build():
    today = dt.date.today()
    end_month = today.strftime("%Y-%m")
    if today.day < 28:  # skip the current, incomplete month for averaged daily series
        first = today.replace(day=1) - dt.timedelta(days=1)
        end_month_avg = first.strftime("%Y-%m")
    else:
        end_month_avg = end_month
    weeks = week_grid(today)
    W, L, M = {}, {}, {}

    for sid in FRED_WEEKLY:
        rows = fred_csv(sid, start=(today - dt.timedelta(days=3700)).isoformat())
        W[sid] = to_weekly(rows, weeks, 2)
        L[sid] = latest(rows, 2)
        print(f"FRED weekly {sid}: {rows[-1]}")

    for sid in BOC_WEEKLY:
        rows = boc_obs(sid, (today - dt.timedelta(days=3700)).isoformat())
        dp = 4 if sid == "FXUSDCAD" else 2
        W[sid] = to_weekly(rows, weeks, dp)
        L[sid] = latest(rows, dp)
        print(f"BoC weekly {sid}: {rows[-1]}")

    for key, sid in FRED_MONTHLY.items():
        M[key] = pack_monthly(fred_csv(sid, monthly=True), end_month_avg)
    for key, sid in FRED_YOY.items():
        M[key] = pack_monthly(yoy(fred_csv(sid, monthly=True)), end_month)
    for key, sid in BOC_MONTHLY.items():
        rows = boc_obs(sid, "1950-01-01")
        if key == "BOC":
            rows = monthly_avg(rows)
            M[key] = pack_monthly(rows, end_month_avg)
        else:
            M[key] = pack_monthly(rows, end_month)
    for k, v in M.items():
        print(f"monthly {k}: from {v['start']}, {len(v['v'])} months")

    return {"weekStart": weeks[0], "W": W, "L": L, "M": M}


def main():
    try:
        data = build()
    except Exception as e:
        # Keep the last good file; the dashboard keeps showing it.
        print(f"Fetch failed, keeping existing data: {e}", file=sys.stderr)
        sys.exit(0)

    body = json.dumps(data, separators=(",", ":"), sort_keys=True)
    if OUT.exists():
        old = OUT.read_text(encoding="utf-8")
        start = old.find("/*DATA*/")
        end = old.find("/*END*/")
        if start != -1 and end != -1 and old[start + 8:end] == body:
            print("No change in the data; nothing to write.")
            return
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "// Generated by scripts/fetch_data.py. Do not edit by hand.\n"
        f"window.MD=Object.assign({{asOf:\"{stamp}\"}},/*DATA*/{body}/*END*/);\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT} ({len(body):,} bytes) at {stamp}")


if __name__ == "__main__":
    main()
