#!/usr/bin/env python3
"""Macro Desk data updater (D-Advisory / dinian.ca).

On the D-Advisory/markets repository it runs with --stocks-only and writes data/stocks.json
(prices for the Sectors and Tech map pages). Economic data there is handled by fetch_data.py.

Builds data.json for the Macro Desk page from free public sources:
  * Yahoo Finance chart endpoint  - index, ETF, futures, FX, crypto and stock prices
  * FRED (St. Louis Fed)          - U.S. rates, inflation, jobs, oil, dollar (and Canada OECD series)
  * Bank of Canada Valet          - policy rate, GoC bond yields, CPI, CPI-trim, CPI-median

Usage:
  python update.py --mode quick   # prices only (runs every 15 minutes in market hours)
  python update.py --mode full    # prices + 1-year stats + all economic data

It starts from the last published data.json (or the copy in this repo), refreshes what
it can, and never throws away good data: if a source fails, the previous values stay.
Only the Python standard library is used. Set FRED_API_KEY to use the official FRED API
(recommended); without it the public FRED CSV download is used.
"""
import argparse, csv, datetime as dt, io, json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "application/json,text/csv,*/*"}
FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()
WEEK0 = dt.date(2016, 10, 7)          # first Friday of the weekly arrays (F.W, CA.W)
M0 = (2017, 1)                        # first month of F.M / CA.M
ERRORS = []


# ---------------------------------------------------------------- helpers
def http(url, tries=3, timeout=25):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url[:90]} -> {last}")


def rnd_px(v):
    if v is None:
        return None
    a = abs(v)
    return round(v) if a >= 1000 else round(v, 2) if a >= 10 else round(v, 4)


def d(s):
    return dt.date.fromisoformat(s[:10])


def mkey(day):
    return (day.year, day.month)


def month_index(start, ym):
    y, m = map(int, start.split("-"))
    return (ym[0] - y) * 12 + (ym[1] - m)


def weekly(obs, upto):
    """obs: sorted list of (date, value). Returns Friday-sampled list from WEEK0, forward filled."""
    out, j, last = [], 0, None
    fri = WEEK0
    while fri <= upto:
        while j < len(obs) and obs[j][0] <= fri:
            last = obs[j][1]
            j += 1
        out.append(last)
        fri += dt.timedelta(days=7)
    return out


def last_friday_needed(obs_dates):
    """Weekly arrays run to the Friday on/after the latest observation."""
    if not obs_dates:
        return None
    m = max(obs_dates)
    return m + dt.timedelta(days=(4 - m.weekday()) % 7)


def monthly_avg(obs):
    acc = {}
    for day, v in obs:
        acc.setdefault(mkey(day), []).append(v)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def patch_long(series, values, nd=2, first=None):
    """Write {(y,m): value} into a LONG-style {start, v} dict, extending as needed."""
    if not values:
        return
    for ym, val in sorted(values.items()):
        if first and ym < first:
            continue
        i = month_index(series["start"], ym)
        if i < 0:
            continue
        while len(series["v"]) <= i:
            series["v"].append(None)
        series["v"][i] = None if val is None else round(val, nd)


def long_last_month(series):
    v = series["v"]
    for i in range(len(v) - 1, -1, -1):
        if v[i] is not None:
            y, m = map(int, series["start"].split("-"))
            k = y * 12 + m - 1 + i
            return f"{k // 12}-{k % 12 + 1:02d}"
    return None


def since_2017(series):
    i0 = month_index(series["start"], M0)
    return [x for x in series["v"][max(i0, 0):] if x is not None]


# ---------------------------------------------------------------- sources
def fred(sid, start):
    if FRED_KEY:
        q = urllib.parse.urlencode({"series_id": sid, "api_key": FRED_KEY, "file_type": "json",
                                    "observation_start": start})
        js = json.loads(http("https://api.stlouisfed.org/fred/series/observations?" + q))
        rows = [(o["date"], o["value"]) for o in js["observations"]]
    else:
        txt = http(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}")
        rd = csv.reader(io.StringIO(txt))
        next(rd)
        rows = [(r[0], r[1]) for r in rd if len(r) >= 2]
    out = []
    for day, v in rows:
        try:
            out.append((d(day), float(v)))
        except ValueError:
            pass
    if not out:
        raise RuntimeError(f"FRED {sid}: no data")
    return out


def boc(series, start):
    js = json.loads(http("https://www.bankofcanada.ca/valet/observations/" + ",".join(series) +
                         f"/json?start_date={start}"))
    out = {s: [] for s in series}
    for o in js.get("observations", []):
        for s in series:
            try:
                out[s].append((d(o["d"]), float(o[s]["v"])))
            except (KeyError, TypeError, ValueError):
                pass
    return out


def yahoo(sym, rng, interval="1d"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
           f"?range={rng}&interval={interval}&includePrePost=false")
    js = json.loads(http(url))
    res = js["chart"]["result"][0]
    meta = res.get("meta", {})
    ts = res.get("timestamp") or []
    cl = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    tz = ZoneInfo(meta.get("exchangeTimezoneName") or "America/New_York")
    pts = [(dt.datetime.fromtimestamp(t, tz).date(), c) for t, c in zip(ts, cl) if c is not None]
    rmp, rmt = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
    if rmp is not None and pts and interval == "1d":
        day = dt.datetime.fromtimestamp(rmt, tz).date() if rmt else pts[-1][0]
        if day > pts[-1][0]:
            pts.append((day, rmp))
        elif day == pts[-1][0]:
            pts[-1] = (day, rmp)
    if len(pts) < 2:
        raise RuntimeError(f"Yahoo {sym}: too few points")
    return pts, rmt


def pmap(fn, items, workers=6):
    res = {}

    def run(x):
        try:
            return x, fn(x)
        except Exception as e:  # noqa
            ERRORS.append(f"{x}: {e}")
            return x, None
    with ThreadPoolExecutor(workers) as ex:
        for k, v in ex.map(run, items):
            if v is not None:
                res[k] = v
    return res


def close_on_or_before(pts, day):
    best = None
    for p in pts:
        if p[0] <= day:
            best = p[1]
        else:
            break
    return best


# ---------------------------------------------------------------- updaters
def update_prices(D, mode):
    Y, Q, REF = D["Y"], D["STK"]["Q"], D.setdefault("_ref", {})
    syms = sorted(set(Y) | set(Q))
    rng = "1y" if mode == "full" else "1mo"
    data = pmap(lambda s: yahoo(s, rng), syms)
    today = dt.datetime.now(ET).date()
    latest_t = 0
    for s, (pts, rmt) in data.items():
        p = pts[-1][1]
        prev = pts[-2][1]
        dchg = (p / prev - 1) * 100 if prev else 0
        if rmt and s in ("^GSPC", "^IXIC"):
            latest_t = max(latest_t, rmt)
        if s in Y:
            Y[s]["p"] = rnd_px(p)
            Y[s]["d"] = round(dchg, 2)
            if "s" in Y[s]:
                cut = pts[-1][0] - dt.timedelta(days=31)
                Y[s]["s"] = [rnd_px(c) for day, c in pts if day >= cut]
        if s in Q:
            q = Q[s]
            ref = REF.setdefault(s, {})
            wk = close_on_or_before(pts, today - dt.timedelta(days=7))
            mo = close_on_or_before(pts, today - dt.timedelta(days=30))
            q[1] = round(p, 2)
            q[2] = round(dchg, 2)
            if wk:
                q[3] = round((p / wk - 1) * 100, 1)
            if mo:
                q[4] = round((p / mo - 1) * 100, 1)
            if mode == "full":
                yr = close_on_or_before(pts, today - dt.timedelta(days=365)) or pts[0][1]
                closes = [c for _, c in pts]
                ref.update(y=round(yr, 4), hi=round(max(closes), 4), lo=round(min(closes), 4))
            if ref.get("y"):
                q[5] = round((p / ref["y"] - 1) * 100, 1)
            if ref.get("hi") is not None:
                hi, lo = max(ref["hi"], p), min(ref["lo"], p)
                ref["hi"], ref["lo"] = round(hi, 4), round(lo, 4)
                q[7] = round((p - lo) / (hi - lo) * 100) if hi > lo else 50
            if ref.get("sh"):
                q[6] = round(ref["sh"] * p, 1)
    if mode == "full":
        update_groups(D, data)
    return latest_t, len(data), len(syms)


def update_groups(D, data):
    """STK.G: per group [1-month daily, 1-year weekly] equal-weight indexes (start = 1)."""
    STK = D["STK"]
    groups = []
    for name, slug, etf, gl in STK["SEC"]:
        for gname, tks in gl:
            groups.append((f"{slug}|{gname}", tks))
    for gname, tks in STK["TECHG"]:
        groups.append((f"tech|{gname}", tks))
    for key, tks in groups:
        series = {t: dict(data[t][0]) for t in tks if t in data}
        if not series:
            continue
        cal = sorted(set().union(*[set(s) for s in series.values()]))
        if len(cal) < 30:
            continue

        def idx(days):
            rows = []
            for t, s in series.items():
                last, vals = None, []
                for day in cal:
                    if day in s:
                        last = s[day]
                    if day in days:
                        vals.append(last)
                if vals and vals[0]:
                    rows.append([v / vals[0] if v else None for v in vals])
            if not rows:
                return None
            n = len(rows[0])
            return [round(sum(r[i] for r in rows if r[i]) / max(1, sum(1 for r in rows if r[i])), 3) for i in range(n)]
        m_days = set(cal[-22:])
        y_days = set(cal[::-5][:50])
        a, b = idx(m_days), idx(y_days)
        if a and b:
            STK["G"][key] = [a, b]


def update_history(D):
    """STK.H: monthly closes for the long-run market charts."""
    H = D["STK"]["H"]

    def fetch(s):
        return yahoo(s, "5y", "1mo")[0]
    for s, pts in pmap(fetch, list(H)).items():
        vals = {}
        for day, c in pts:
            vals[mkey(day)] = c
        ser = H[s]
        for ym, c in sorted(vals.items()):
            i = month_index(ser["start"], ym)
            if i < 0:
                continue
            while len(ser["v"]) <= i:
                ser["v"].append(None)
            ser["v"][i] = rnd_px(c)


FRED_WEEKLY = ["DGS2", "DGS5", "DGS10", "DGS30", "T10Y2Y", "DFF", "SP500", "NASDAQCOM", "VIXCLS",
               "DTWEXBGS", "DCOILWTICO", "DCOILBRENTEU", "MORTGAGE30US"]
FRED_LONG_DAILY = ["DGS2", "DGS10", "DGS30", "DFF", "MORTGAGE30US", "VIXCLS", "DCOILWTICO",
                   "DCOILBRENTEU", "DTWEXBGS", "T10Y2Y"]
FRED_LATEST = ["DGS2", "DGS5", "DGS10", "DGS30", "T10Y2Y", "DFF", "MORTGAGE30US"]
FRED_LONG_MONTHLY = {"UNRATE": 1, "IRLTLT01CAM156N": 2, "LRUNTTTTCAM156S": 1, "IR3TIB01CAM156N": 2}
FRED_YOY = {"CPI": "CPIAUCSL", "CORECPI": "CPILFESL", "PCE": "PCEPI", "COREPCE": "PCEPILFE"}
BOC_DAILY = ["V39079", "BD.CDN.2YR.DQ.YLD", "BD.CDN.5YR.DQ.YLD", "BD.CDN.10YR.DQ.YLD", "BD.CDN.LONG.DQ.YLD"]


def nd_for(sid):
    return 0 if sid in ("SP500", "NASDAQCOM") else 2


def update_econ(D):
    F, CA, LONG = D["F"], D["CA"], D["LONG"]
    start_w = "2016-10-01"
    # --- U.S. daily / weekly series
    daily = pmap(lambda s: fred(s, start_w), sorted(set(FRED_WEEKLY) | set(FRED_LONG_DAILY)), workers=4)
    upto = last_friday_needed([o[-1][0] for o in daily.values()])
    for sid in FRED_WEEKLY:
        if sid in daily and upto:
            nd = nd_for(sid)
            F["W"][sid] = [None if v is None else (round(v) if nd == 0 else round(v, nd))
                           for v in weekly(daily[sid], upto)]
    for sid in FRED_LONG_DAILY:
        if sid in daily and sid in LONG:
            patch_long(LONG[sid], monthly_avg(daily[sid]), 2, first=M0)
    for sid in FRED_LATEST:
        if sid in daily and len(daily[sid]) >= 2:
            o = daily[sid]
            F["latest"][sid] = [o[-1][0].isoformat(), round(o[-1][1], 2), round(o[-2][1], 2)]
    # --- U.S. / OECD monthly series
    start_m = "2014-01-01"
    mon = pmap(lambda s: fred(s, start_m), list(FRED_LONG_MONTHLY) + list(FRED_YOY.values()), workers=4)
    for sid, nd in FRED_LONG_MONTHLY.items():
        if sid in mon and sid in LONG:
            patch_long(LONG[sid], {mkey(a): b for a, b in mon[sid]}, nd, first=M0)
    if "UNRATE" in mon and len(mon["UNRATE"]) >= 2:
        o = mon["UNRATE"]
        F["latest"]["UNRATE"] = [o[-1][0].isoformat(), o[-1][1], o[-2][1]]
    for key, sid in FRED_YOY.items():
        if sid not in mon or key not in LONG:
            continue
        lvl = {mkey(a): b for a, b in mon[sid]}
        # fill an unpublished month (e.g. Oct 2025) for the YoY base only, by geometric interpolation
        ks = sorted(lvl)
        filled = dict(lvl)
        for i in range(1, len(ks)):
            a, b = ks[i - 1], ks[i]
            gap = (b[0] - a[0]) * 12 + b[1] - a[1]
            if gap == 2:
                mid = (a[0] + (a[1]) // 12, a[1] % 12 + 1)
                filled[mid] = (lvl[a] * lvl[b]) ** 0.5
        yoy = {}
        for ym, v in lvl.items():
            base = filled.get((ym[0] - 1, ym[1]))
            if base:
                yoy[ym] = (v / base - 1) * 100
        patch_long(LONG[key], yoy, 2, first=M0)
    for k in ("CPI", "CORECPI", "PCE", "COREPCE", "UNRATE"):
        if k in LONG:
            F["M"][k] = since_2017(LONG[k])
    # --- Canada (Bank of Canada Valet)
    try:
        b = boc(BOC_DAILY, start_w)
        upto_c = last_friday_needed([o[-1][0] for o in b.values() if o])
        for s in BOC_DAILY:
            o = b.get(s) or []
            if o and upto_c:
                CA["W"][s] = [None if v is None else round(v, 2) for v in weekly(o, upto_c)]
            if len(o) >= 2:
                CA["latest"][s] = [o[-1][0].isoformat(), round(o[-1][1], 2), round(o[-2][1], 2)]
        if b.get("V39079") and "BOC" in LONG:
            patch_long(LONG["BOC"], monthly_avg(b["V39079"]), 2, first=M0)
    except Exception as e:  # noqa
        ERRORS.append(f"BoC daily: {e}")
    try:
        cpi = boc(["STATIC_TOTALCPICHANGE", "CPI_TRIM", "CPI_MEDIAN"], "2016-12-01")
        for src, key, lk in (("STATIC_TOTALCPICHANGE", "CACPI", "CACPI"), ("CPI_TRIM", "CATRIM", "CATRIM"),
                             ("CPI_MEDIAN", "CAMEDIAN", None)):
            o = cpi.get(src) or []
            if not o:
                continue
            vals = {mkey(a): v for a, v in o}
            if lk and lk in LONG:
                patch_long(LONG[lk], vals, 1, first=M0)
                CA["M"][key] = since_2017(LONG[lk])
            else:
                CA["M"][key] = [round(v, 1) for ym, v in sorted(vals.items()) if ym >= M0]
    except Exception as e:  # noqa
        ERRORS.append(f"BoC CPI: {e}")
    if "LRUNTTTTCAM156S" in LONG:
        CA["M"]["CAUR"] = since_2017(LONG["LRUNTTTTCAM156S"])
    if "IR3TIB01CAM156N" in LONG:
        CA["M"]["CA3M"] = since_2017(LONG["IR3TIB01CAM156N"])
        o = mon.get("IR3TIB01CAM156N")
        if o and len(o) >= 2:
            CA["latest"]["CA3M"] = [o[-1][0].isoformat(), round(o[-1][1], 2), round(o[-2][1], 2)]
    # keep the weekly arrays the same length
    n = max(len(v) for v in list(F["W"].values()) + list(CA["W"].values()))
    for W in (F["W"], CA["W"]):
        for k, v in W.items():
            if len(v) < n:
                v.extend([v[-1] if v else None] * (n - len(v)))


def set_meta(D, mode, latest_t):
    now = dt.datetime.now(dt.timezone.utc)
    meta = D.setdefault("meta", {})
    t = dt.datetime.fromtimestamp(latest_t, dt.timezone.utc) if latest_t else now
    et = t.astimezone(ET)
    open_ = et.weekday() < 5 and (dt.time(9, 30) <= et.time() < dt.time(16, 0))
    if open_:
        meta["label"] = f"{et:%a %b} {et.day}, {et.year} · {et:%I:%M %p} ET".replace(" 0", " ") + " (delayed)"
        meta["short"] = f"{et:%I:%M %p} ET".lstrip("0") + " (delayed)"
    else:
        meta["label"] = f"{et:%a %b} {et.day}, {et.year} close"
        meta["short"] = f"{et:%a %b} {et.day} close"
    meta["asof"] = t.strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["built"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["mode"] = mode
    L = D.get("LONG")
    if L is None:
        meta["errors"] = len(ERRORS)
        return
    meta["months"] = {k: long_last_month(L[v]) for k, v in
                      {"CPI": "CPI", "COREPCE": "COREPCE", "UNRATE": "UNRATE", "CACPI": "CACPI",
                       "CATRIM": "CATRIM", "CAUR": "LRUNTTTTCAM156S", "CA3M": "IR3TIB01CAM156N"}.items() if v in L}
    meta["errors"] = len(ERRORS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["quick", "full"], default="quick")
    ap.add_argument("--base", default="", help="URL of the currently published data.json")
    ap.add_argument("--seed", default="data.json")
    ap.add_argument("--out", default="public/data.json")
    ap.add_argument("--stocks-only", action="store_true", help="prices, stock groups and sectors only (no economic data)")
    a = ap.parse_args()
    D = None
    if a.base:
        try:
            D = json.loads(http(a.base + ("&" if "?" in a.base else "?") + f"t={int(time.time())}"))
            print("base: published data.json, built", D.get("meta", {}).get("built"))
        except Exception as e:  # noqa
            print("base: could not read published copy:", e)
    if D is None:
        D = json.load(open(a.seed, encoding="utf-8"))
        print("base: seed", a.seed)
    latest_t, ok, total = update_prices(D, a.mode)
    print(f"prices: {ok}/{total} symbols refreshed")
    if a.mode == "full" and not a.stocks_only:
        update_history(D)
        update_econ(D)
        print("economic data refreshed")
    if ok < total * 0.5 and a.mode == "quick":
        print("too many price failures; keeping the published file unchanged")
        for e in ERRORS[:20]:
            print("  ", e)
        sys.exit(1)
    set_meta(D, a.mode, latest_t)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(D, f, separators=(",", ":"))
    print("wrote", a.out, os.path.getsize(a.out), "bytes;", len(ERRORS), "source errors")
    for e in ERRORS[:30]:
        print("  ", e)


if __name__ == "__main__":
    main()
