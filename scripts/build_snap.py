#!/usr/bin/env python3
"""
Build the SNAP weather snapshot embedded in index.html from CWA open data.

  CWA_API_KEY=... python3 scripts/build_snap.py              # fetch all 22 counties, rewrite index.html
  python3 scripts/build_snap.py --src-dir DIR --partial       # use cached F-D0047-xxx.json files (testing)
  python3 scripts/build_snap.py --dry-run                     # build and validate, do not write

SNAP layout (decoded by expand() in index.html), per town:
  s  epoch hour of the first hourly row (offsets below are hours from it)
  h  hourly   [offset, temp, feels-like, humidity, T[comfort text]]
  p  3-hourly [offset, rain %, weather code, T[weather text]]
  w  3-hourly [offset, T[wind direction], beaufort]
  d  daily    [date, lo, hi, rain % (max of day/night, -1 unknown), code, T[text],
               full day (1 if both day and night periods exist), T[day text] or -1, T[night text] or -1,
               day rain %, night rain %, feels-like lo, feels-like hi, UV]
T is one shared string table, so every text is stored once.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
TZ = dt.timezone(dt.timedelta(hours=8))
API = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/{}?Authorization={}&format=JSON"

# 22 counties: (3-day id, 1-week id); 001/003 Yilan, 005/007 Taoyuan ... 085/087 Kinmen
COUNTY_IDS = [("F-D0047-%03d" % n, "F-D0047-%03d" % (n + 2)) for n in range(1, 87, 4)]
LIVE_URL = "https://weather-tw.pages.dev/"
BATCH = 5          # datasets per request (CWA maximum)
WORKERS = 3        # requests in flight at once; kept low to be gentle with CWA
HOURLY_ROWS = 96  # how many hourly rows to keep per town


def get_json(dataset, key, extra=""):
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    req = urllib.request.Request(API.format(dataset, key), headers={"User-Agent": "WeatherTW/1.0"}) if not extra else urllib.request.Request(API.format(dataset, key) + extra, headers={"User-Agent": "WeatherTW/1.0"})
    last = None
    for attempt in range(3):
        if attempt:
            time.sleep(2 * attempt)
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
                d = json.loads(r.read().decode("utf-8"))
            if d.get("success") not in (True, "true"):
                raise RuntimeError("CWA API error for %s" % dataset)
            return d
        except Exception as e:  # noqa: BLE001 - retry any network hiccup
            last = e
    raise RuntimeError("fetch %s failed: %s" % (dataset, str(last).replace(key, "***")))


def get_batch(ids, key):
    """Several county datasets in one request via F-D0047-093 (CWA allows at most 5, and silently drops the rest)."""
    d = get_json("F-D0047-093", key, "&locationId=" + ",".join(ids))
    out = {"F-" + b["Dataid"]: {"records": {"Locations": [b]}} for b in d["records"]["Locations"]}
    missing = [i for i in ids if i not in out]
    if missing:
        raise RuntimeError("CWA did not return %s" % ", ".join(missing))
    return out


def elements(town):
    return {e["ElementName"]: e["Time"] for e in town["WeatherElement"]}


def val(item, field):
    """First value of an ElementValue entry, None when CWA says '-' (no data)."""
    v = item["ElementValue"][0].get(field)
    return None if v in (None, "", "-") else v


def to_int(v):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def epoch_hour(s):
    return int(dt.datetime.fromisoformat(s).timestamp() // 3600)


class Strings:
    def __init__(self):
        self.items, self.idx = [], {}

    def of(self, s):
        if s not in self.idx:
            self.idx[s] = len(self.items)
            self.items.append(s)
        return self.idx[s]


def build_town(t3, t7, S):
    e3, e7 = elements(t3), elements(t7)
    temp = [(epoch_hour(x["DataTime"]), to_int(val(x, "Temperature"))) for x in e3["溫度"]]
    feel = {epoch_hour(x["DataTime"]): to_int(val(x, "ApparentTemperature")) for x in e3["體感溫度"]}
    rh = {epoch_hour(x["DataTime"]): to_int(val(x, "RelativeHumidity")) for x in e3["相對濕度"]}
    com = {epoch_hour(x["DataTime"]): val(x, "ComfortIndexDescription") for x in e3["舒適度指數"]}
    temp = [(h, v) for h, v in temp if v is not None]
    s = temp[0][0]

    # hourly rows: CWA gives hourly early on and 3-hourly later, so fill the gaps linearly
    known = {h: (v, feel.get(h), rh.get(h), com.get(h)) for h, v in temp}
    hs = sorted(known)
    rows = []
    for a, b in zip(hs, hs[1:] + [None]):
        ta, fa, ra, ca = known[a]
        step = (b - a) if b else 1
        for k in range(step):
            f = k / step
            if b:
                tb, fb, rb, _ = known[b]
                mix = lambda x, y: x if x is None or y is None else int(round(x + (y - x) * f))
            else:
                tb, fb, rb = ta, fa, ra
                mix = lambda x, y: x
            rows.append([a + k - s, mix(ta, tb), mix(fa, fb), mix(ra, rb), ca])
    h = [[o, tv, fv if fv is not None else tv, rv if rv is not None else 0, S.of(c or "")]
         for o, tv, fv, rv, c in rows[:HOURLY_ROWS] if tv is not None]

    wx = [(epoch_hour(x["StartTime"]), x) for x in e3["天氣現象"]]
    pops = {epoch_hour(x["StartTime"]): to_int(val(x, "ProbabilityOfPrecipitation")) for x in e3["3小時降雨機率"]}
    p = []
    for st, x in wx:
        pp = pops.get(st)
        code = to_int(val(x, "WeatherCode"))
        text = val(x, "Weather")
        if pp is None or code is None or text is None:
            continue
        p.append([st - s, pp, code, S.of(text)])

    wd = {epoch_hour(x["DataTime"]): val(x, "WindDirection") for x in e3["風向"]}
    w = []
    for x in e3["風速"]:
        st = epoch_hour(x["DataTime"])
        bf, d_ = to_int(val(x, "BeaufortScale")), wd.get(st)
        if bf is not None and d_ is not None:
            w.append([st - s, S.of(d_), bf])

    # daily rows from the 12-hour week data: day = 06-18, night = 18-06, both belong to the date they start on
    def periods(name, field):
        out = {}
        for x in e7.get(name, []):
            st = dt.datetime.fromisoformat(x["StartTime"]).astimezone(TZ)
            out[(st.date().isoformat(), st.hour < 12)] = x  # (date, is_day)
        return out

    names = {
        "lo": ("最低溫度", "MinTemperature"), "hi": ("最高溫度", "MaxTemperature"),
        "flo": ("最低體感溫度", "MinApparentTemperature"), "fhi": ("最高體感溫度", "MaxApparentTemperature"),
        "pop": ("12小時降雨機率", "ProbabilityOfPrecipitation"), "wx": ("天氣現象", "Weather"),
        "code": ("天氣現象", "WeatherCode"), "uv": ("紫外線指數", "UVIndex"),
    }
    P = {k: periods(n, f) for k, (n, f) in names.items()}
    dates = sorted({d for (d, _) in P["hi"]} | {d for (d, _) in P["lo"]})

    def pv(key, date, is_day, conv=to_int):
        x = P[key].get((date, is_day))
        return None if x is None else conv(val(x, names[key][1]))

    ident = lambda v: v
    d = []
    for date in dates:
        los = [v for v in (pv("lo", date, True), pv("lo", date, False)) if v is not None]
        his = [v for v in (pv("hi", date, True), pv("hi", date, False)) if v is not None]
        flos = [v for v in (pv("flo", date, True), pv("flo", date, False)) if v is not None]
        fhis = [v for v in (pv("fhi", date, True), pv("fhi", date, False)) if v is not None]
        if not los or not his:
            continue
        pd_, pn = pv("pop", date, True), pv("pop", date, False)
        pops_ = [v for v in (pd_, pn) if v is not None]
        txt_d, txt_n = pv("wx", date, True, ident), pv("wx", date, False, ident)
        code_d, code_n = pv("code", date, True), pv("code", date, False)
        txt = txt_d if txt_d is not None else txt_n
        code = code_d if code_d is not None else code_n
        if txt is None or code is None:
            continue
        uv = pv("uv", date, True)
        d.append([date, min(los), max(his), max(pops_) if pops_ else -1, code, S.of(txt),
                  1 if (pv("hi", date, True) is not None and pv("hi", date, False) is not None) else 0,
                  S.of(txt_d) if txt_d is not None else -1, S.of(txt_n) if txt_n is not None else -1,
                  pd_ if pd_ is not None else -1, pn if pn is not None else -1,
                  min(flos) if flos else 99, max(fhis) if fhis else -99, uv if uv is not None else 0])
    return {"s": s, "h": h, "p": p, "w": w, "d": d}


def fingerprint(dataset):
    """Short hash of one dataset's content. CWA gives no publish time, so a changed hash is how we notice a new release."""
    body = json.dumps(dataset["records"], sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:12]


def live_fingerprint(url):
    """The fingerprint inside the deployed page, or None when it has none yet."""
    req = urllib.request.Request("%s?_=%d" % (url, int(dt.datetime.now().timestamp())), headers={"User-Agent": "WeatherTW/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8")
    m = re.search(r'const SNAP = \{"at":"[^"]*","k":"([0-9a-f]+)"', html)
    return m.group(1) if m else None


def check(key):
    """Probe one dataset against the live site. Prints changed=true/false (also to $GITHUB_OUTPUT)."""
    new = fingerprint(get_json(COUNTY_IDS[0][0], key))
    old = live_fingerprint(LIVE_URL)
    changed = new != old
    print("probe %s, live %s -> changed=%s" % (new, old, str(changed).lower()))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("changed=%s\n" % str(changed).lower())


def build(pairs, partial=False):
    S = Strings()
    counties = {}
    for d3, d7 in pairs:
        c3, c7 = d3["records"]["Locations"][0], d7["records"]["Locations"][0]
        towns7 = {l["LocationName"]: l for l in c7["Location"]}
        out = {}
        for t3 in c3["Location"]:
            name = t3["LocationName"]
            if name not in towns7:
                raise RuntimeError("%s %s missing in 1-week data" % (c3["LocationsName"], name))
            out[name] = build_town(t3, towns7[name], S)
        counties[c3["LocationsName"]] = out
    return {"at": dt.datetime.now(TZ).strftime("%m/%d %H:%M"), "k": fingerprint(pairs[0][0]), "t": S.items, "c": counties}


def validate(snap, old, partial):
    problems = []
    for county, towns in snap["c"].items():
        for name, t in towns.items():
            if len(t["h"]) < 24:
                problems.append("%s%s: only %d hourly rows" % (county, name, len(t["h"])))
            if not t["p"] or not t["w"]:
                problems.append("%s%s: empty p/w" % (county, name))
            if len(t["d"]) < 5:
                problems.append("%s%s: only %d daily rows" % (county, name, len(t["d"])))
    n = sum(len(v) for v in snap["c"].values())
    if not partial:
        if len(snap["c"]) != 22:
            problems.append("expected 22 counties, got %d" % len(snap["c"]))
        if old and n < sum(len(v) for v in old["c"].values()):
            problems.append("town count dropped: %d" % n)
    return problems


def read_snap_line(html):
    m = re.search(r"^const SNAP = (\{.*\});[ \t]*$", html, re.M)
    if not m:
        sys.exit("SNAP line not found in index.html")
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-dir", help="use cached F-D0047-xxx.json files instead of the API")
    ap.add_argument("--partial", action="store_true", help="allow fewer than 22 counties (testing)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="only probe whether CWA has new data compared with the live site")
    a = ap.parse_args()
    if a.check:
        if not os.environ.get("CWA_API_KEY"):
            sys.exit("CWA_API_KEY is not set")
        return check(os.environ["CWA_API_KEY"])

    pairs, todo = [], []
    key = os.environ.get("CWA_API_KEY", "")
    for d3, d7 in COUNTY_IDS:
        if a.src_dir:
            f3, f7 = (os.path.join(a.src_dir, "%s.json" % i) for i in (d3, d7))
            if not (os.path.exists(f3) and os.path.exists(f7)):
                continue
            pairs.append((json.load(open(f3, encoding="utf-8")), json.load(open(f7, encoding="utf-8"))))
        else:
            if not key:
                sys.exit("CWA_API_KEY is not set")
            todo.append((d3, d7))
    if todo:
        ids = [i for pair in todo for i in pair]
        batches = [ids[k:k + BATCH] for k in range(0, len(ids), BATCH)]

        def timed(b):
            t0 = time.time()
            d = get_batch(b, key)
            print("fetched %s..%s (%d datasets) in %.1fs" % (b[0], b[-1], len(b), time.time() - t0), flush=True)
            return d
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            got = {}
            for r in ex.map(timed, batches):
                got.update(r)
        pairs = [(got[a], got[b]) for a, b in todo]
        print("fetched %d datasets in %d requests, %.0fs" % (len(ids), len(batches), time.time() - t0), flush=True)
    if not pairs:
        sys.exit("no data")

    html = open(INDEX, encoding="utf-8").read()
    m = read_snap_line(html)
    snap = build(pairs, a.partial)
    problems = validate(snap, json.loads(m.group(1)), a.partial)
    if problems:
        print("\n".join(problems[:20]), file=sys.stderr)
        sys.exit("refusing to write: %d problem(s)" % len(problems))
    line = "const SNAP = " + json.dumps(snap, ensure_ascii=False, separators=(",", ":")) + ";"
    print("towns: %d, strings: %d, at: %s" % (sum(len(v) for v in snap["c"].values()), len(snap["t"]), snap["at"]))
    if a.dry_run:
        return
    if a.partial:
        sys.exit("--partial output is never written to index.html (use --dry-run)")
    open(INDEX, "w", encoding="utf-8").write(html[:m.start()] + line + html[m.end():])


if __name__ == "__main__":
    main()
