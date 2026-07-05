#!/usr/bin/env python3
"""Sumo-API extractor + DuckDB loader (Step 4).

Design principles (see architecture.md §7 — "gentle API"):
  * strictly sequential requests, no concurrency
  * a deliberate delay between every live request
  * descriptive User-Agent identifying this as personal research
  * cache every raw JSON response to disk, keyed by URL; check cache first
  * retry with exponential backoff; honor HTTP 429 / Retry-After
  * resumable & idempotent: cache hits + fetch_log + INSERT OR REPLACE upserts

Usage:
  python3 extract.py --test              # tiny run: 1 basho + a few rikishi
  python3 extract.py --basho 202305      # one tournament (all divisions/days)
  python3 extract.py --rikishi 45        # one wrestler (profile+history+stats)
  python3 extract.py --full --yes-full   # full historical pull 1958->present
"""
import argparse
import datetime as dt
import json
import logging
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

import duckdb

# ------------------------------------------------------------------ config
BASE_URL = "https://www.sumo-api.com/api"
REQUEST_DELAY_SECONDS = 1.5          # deliberate pause between live requests
USER_AGENT = "Sumo-Research/1.0 (personal research project; cohare1986@gmail.com)"
MAX_RETRIES = 3                      # retries on transient failure
BACKOFF_BASE_SECONDS = 2            # 2s, 4s, 8s ...
DEFAULT_RETRY_AFTER = 30           # fallback wait on 429 with no Retry-After
HERE = pathlib.Path(__file__).parent
CACHE_DIR = HERE / "cache"
DB_PATH = HERE / "sumo.duckdb"

DIVISIONS = ["Makuuchi", "Juryo", "Makushita", "Sandanme", "Jonidan", "Jonokuchi"]
BASHO_DAYS = range(1, 16)            # a tournament runs 15 days
FIRST_BASHO_YEAR = 1958             # historical data starts here
BASHO_MONTHS = [1, 3, 5, 7, 9, 11]   # 6 tournaments/year, odd months

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("sumo")


# ------------------------------------------------------------ small helpers
def pick(d, *keys, default=None):
    """Return the first present key from a dict — tolerates API field-name
    variants (e.g. rikishiID vs rikishiId) while fields stay UNVERIFIED."""
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default


def upsert(con, table, row):
    """Idempotent insert against the table's primary key."""
    cols = list(row.keys())
    collist = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)
    con.execute(f"INSERT OR REPLACE INTO {table} ({collist}) VALUES ({placeholders})",
                [row[c] for c in cols])


# ---------------------------------------------------------------- HTTP + cache
def cache_path(url):
    """Map a URL to a stable cache filename (slug of the full URL)."""
    slug = urllib.parse.quote(url.replace(BASE_URL + "/", ""), safe="")
    return CACHE_DIR / f"{slug}.json"


def fetch_json(con, url):
    """Return parsed JSON for url. Cache-first; on a miss make one gentle live
    request with delay, retries/backoff, and 429 handling, then cache it."""
    path = cache_path(url)
    if path.exists():                                # cache hit -> no API call
        log.info("cache  %s", url)
        return json.loads(path.read_text())

    CACHE_DIR.mkdir(exist_ok=True)
    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(REQUEST_DELAY_SECONDS)            # be gentle before every call
        try:
            log.info("fetch  %s", url)
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            path.write_text(json.dumps(data))        # cache raw response
            _log_fetch(con, url, "ok", f"attempt {attempt}")
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:                        # rate limited -> back off
                wait = int(e.headers.get("Retry-After", DEFAULT_RETRY_AFTER))
                log.warning("429 rate limited; sleeping %ss", wait)
                time.sleep(wait)
                continue
            wait = BACKOFF_BASE_SECONDS ** attempt
            log.warning("HTTP %s on %s; retry in %ss", e.code, url, wait)
            time.sleep(wait)
        except Exception as e:                       # network/timeout -> backoff
            wait = BACKOFF_BASE_SECONDS ** attempt
            log.warning("error %s on %s; retry in %ss", e, url, wait)
            time.sleep(wait)

    _log_fetch(con, url, "error", f"failed after {MAX_RETRIES} retries")
    raise RuntimeError(f"failed to fetch {url}")


def _log_fetch(con, url, status, note):
    upsert(con, "fetch_log", {
        "url": url, "status": status,
        "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
        "note": note,
    })


# --------------------------------------------------------------------- loaders
# Each loader fetches one endpoint (via the cache) and upserts normalized rows.
# Field access uses pick()/.get() so a missing/renamed field never crashes the
# run — we reconcile against real JSON in Step 4c.

def load_rikishi_record(con, r):
    """Upsert one rikishi profile plus any embedded history arrays."""
    rid = pick(r, "id", "rikishiId")
    if rid is None:
        return
    upsert(con, "rikishi", {
        "id": rid,
        "sumodb_id": pick(r, "sumodbId"),
        "nsk_id": pick(r, "nskId"),
        "shikona_en": pick(r, "shikonaEn"),
        "shikona_jp": pick(r, "shikonaJp"),
        "current_rank": pick(r, "currentRank"),
        "heya": pick(r, "heya"),
        "birth_date": pick(r, "birthDate"),
        "shusshin": pick(r, "shusshin"),
        "height": pick(r, "height"),
        "weight": pick(r, "weight"),
        "debut": pick(r, "debut"),
        "intai": pick(r, "intai"),
        "updated_at": pick(r, "updatedAt"),
        "created_at": pick(r, "createdAt"),
    })
    # embedded time-series (present when measurements/ranks/shikonas requested)
    for h in pick(r, "rankHistory", default=[]) or []:
        upsert(con, "rank_history", {
            "basho_id": pick(h, "bashoId"), "rikishi_id": rid,
            "rank_value": pick(h, "rankValue"), "rank": pick(h, "rank")})
    for h in pick(r, "measurementHistory", default=[]) or []:
        upsert(con, "measurement_history", {
            "basho_id": pick(h, "bashoId"), "rikishi_id": rid,
            "height": pick(h, "height"), "weight": pick(h, "weight")})
    for h in pick(r, "shikonaHistory", default=[]) or []:
        upsert(con, "shikona_history", {
            "basho_id": pick(h, "bashoId"), "rikishi_id": rid,
            "shikona_en": pick(h, "shikonaEn"), "shikona_jp": pick(h, "shikonaJp")})


def load_rikishi_by_id(con, rikishi_id):
    """Fetch one wrestler with all embedded history, plus career stats."""
    url = (f"{BASE_URL}/rikishi/{rikishi_id}"
           "?measurements=true&ranks=true&shikonas=true")
    load_rikishi_record(con, fetch_json(con, url))
    load_rikishi_stats(con, rikishi_id)


def load_rikishi_list(con, limit=10, skip=0):
    """Fetch a page of rikishi (with embedded history) and load each."""
    url = (f"{BASE_URL}/rikishis?limit={limit}&skip={skip}"
           "&measurements=true&ranks=true&shikonas=true")
    data = fetch_json(con, url)
    records = data.get("records", []) if isinstance(data, dict) else data
    for r in records:
        load_rikishi_record(con, r)
    return data.get("total") if isinstance(data, dict) else len(records)


def load_rikishi_stats(con, rikishi_id):
    """Fetch and flatten career totals for one wrestler."""
    s = fetch_json(con, f"{BASE_URL}/rikishi/{rikishi_id}/stats")
    if not isinstance(s, dict):
        return
    upsert(con, "rikishi_stats", {
        "rikishi_id": rikishi_id,
        "total_matches": pick(s, "totalMatches"),
        "total_wins": pick(s, "totalWins"),
        "total_losses": pick(s, "totalLosses"),
        "total_absences": pick(s, "totalAbsences"),
        "total_basho": pick(s, "totalBasho", "basho"),
        "yusho": pick(s, "yusho"),
        "sansho": pick(s, "sansho"),
    })


def load_basho(con, basho_id):
    """Fetch a tournament summary; upsert basho, yusho winners, special prizes."""
    b = fetch_json(con, f"{BASE_URL}/basho/{basho_id}")
    if not isinstance(b, dict):
        return
    upsert(con, "basho", {
        "basho_id": basho_id,
        "start_date": pick(b, "startDate"),
        "end_date": pick(b, "endDate"),
        "location": pick(b, "location"),
    })
    for y in pick(b, "yusho", default=[]) or []:
        upsert(con, "basho_yusho", {
            "basho_id": basho_id, "division": pick(y, "type", "division"),
            "rikishi_id": pick(y, "rikishiId"),
            "shikona_en": pick(y, "shikonaEn"), "shikona_jp": pick(y, "shikonaJp")})
    for p in pick(b, "specialPrizes", "sansho", default=[]) or []:
        upsert(con, "special_prize", {
            "basho_id": basho_id, "prize_type": pick(p, "type"),
            "rikishi_id": pick(p, "rikishiId"),
            "shikona_en": pick(p, "shikonaEn"), "shikona_jp": pick(p, "shikonaJp")})


def load_banzuke(con, basho_id, division):
    """Fetch a division's ranking sheet; upsert one banzuke_entry per rikishi."""
    data = fetch_json(con, f"{BASE_URL}/basho/{basho_id}/banzuke/{division}")
    if not isinstance(data, dict):
        return
    for side in ("east", "west"):
        for e in pick(data, side, default=[]) or []:
            rid = pick(e, "rikishiID", "rikishiId")
            if rid is None:
                continue
            upsert(con, "banzuke_entry", {
                "basho_id": basho_id, "rikishi_id": rid, "division": division,
                "side": pick(e, "side", default=side.capitalize()),
                "rank_value": pick(e, "rankValue"), "rank": pick(e, "rank"),
                "wins": pick(e, "wins"), "losses": pick(e, "losses"),
                "absences": pick(e, "absences")})


def load_torikumi(con, basho_id, division, day):
    """Fetch one division-day's bouts; upsert into the bout fact table."""
    data = fetch_json(con,
                      f"{BASE_URL}/basho/{basho_id}/torikumi/{division}/{day}")
    bouts = pick(data, "torikumi", default=[]) if isinstance(data, dict) else data
    for m in bouts or []:
        upsert(con, "bout", {
            "basho_id": basho_id, "division": division, "day": day,
            "match_no": pick(m, "matchNo"),
            "east_id": pick(m, "eastId"), "east_shikona": pick(m, "eastShikona"),
            "east_rank": pick(m, "eastRank"),
            "west_id": pick(m, "westId"), "west_shikona": pick(m, "westShikona"),
            "west_rank": pick(m, "westRank"),
            "kimarite": pick(m, "kimarite"),
            "winner_id": pick(m, "winnerId"),
            "winner_en": pick(m, "winnerEn"), "winner_jp": pick(m, "winnerJp")})


def load_kimarite(con, limit=1000):
    """Fetch kimarite usage stats and seed the reference table."""
    data = fetch_json(con, f"{BASE_URL}/kimarite?limit={limit}")
    records = data.get("records", []) if isinstance(data, dict) else data
    for k in records or []:
        name = pick(k, "kimarite")
        if name is None:
            continue
        upsert(con, "kimarite", {
            "kimarite": name, "count": pick(k, "count"),
            "last_usage": pick(k, "lastUsage")})


def load_basho_full(con, basho_id, divisions=DIVISIONS):
    """Everything for one tournament: summary + banzuke + torikumi (all days)."""
    load_basho(con, basho_id)
    for div in divisions:
        load_banzuke(con, basho_id, div)
        for day in BASHO_DAYS:
            load_torikumi(con, basho_id, div, day)


# ------------------------------------------------------------------ run modes
def enumerate_basho_ids():
    """All bashoIds from 1958 to today, in order (6/year, odd months)."""
    today = dt.date.today()
    ids = []
    for year in range(FIRST_BASHO_YEAR, today.year + 1):
        for month in BASHO_MONTHS:
            if (year, month) <= (today.year, today.month):
                ids.append(f"{year}{month:02d}")
    return ids


def run_test(con):
    """Tiny, representative run to validate the model (Step 4b)."""
    log.info("== TEST RUN: kimarite + 1 basho (Makuuchi/Juryo) + 10 rikishi ==")
    load_kimarite(con)
    load_basho(con, "202305")
    load_banzuke(con, "202305", "Makuuchi")
    for day in BASHO_DAYS:                      # Makuuchi torikumi, all 15 days
        load_torikumi(con, "202305", "Makuuchi", day)
    load_banzuke(con, "202305", "Juryo")       # a 2nd division's banzuke
    load_rikishi_list(con, limit=10)           # 10 wrestlers w/ embedded history
    # exercise the stats loader on the first couple of wrestlers we just loaded
    for (rid,) in con.execute("SELECT id FROM rikishi ORDER BY id LIMIT 2").fetchall():
        load_rikishi_stats(con, rid)
    log.info("== TEST RUN complete ==")


def run_full(con):
    """Full historical pull — sequential, cache-first, resumable (Step 6)."""
    basho_ids = enumerate_basho_ids()
    log.info("== FULL PULL: %d basho, %d divisions ==", len(basho_ids), len(DIVISIONS))
    load_kimarite(con)
    for i, bid in enumerate(basho_ids, 1):
        log.info("[%d/%d] basho %s", i, len(basho_ids), bid)
        load_basho_full(con, bid)
    # rikishi crawl (paged) with embedded history
    skip, page = 0, 1000
    while True:
        total = load_rikishi_list(con, limit=page, skip=skip)
        skip += page
        if not total or skip >= total:
            break
    log.info("== FULL PULL complete ==")


def main():
    ap = argparse.ArgumentParser(description="Sumo-API extractor -> DuckDB")
    ap.add_argument("--test", action="store_true", help="tiny validation run")
    ap.add_argument("--basho", help="load one tournament by id (YYYYMM)")
    ap.add_argument("--rikishi", type=int, help="load one wrestler by id")
    ap.add_argument("--full", action="store_true", help="full historical pull")
    ap.add_argument("--yes-full", action="store_true",
                    help="required confirmation for --full (large API traffic)")
    args = ap.parse_args()

    con = duckdb.connect(str(DB_PATH))
    try:
        if args.test:
            run_test(con)
        elif args.basho:
            load_basho_full(con, args.basho)
        elif args.rikishi:
            load_rikishi_by_id(con, args.rikishi)
        elif args.full:
            if not args.yes_full:
                ap.error("--full needs --yes-full (it makes thousands of API calls)")
            run_full(con)
        else:
            ap.error("choose one of --test / --basho / --rikishi / --full")
    finally:
        con.close()


if __name__ == "__main__":
    main()
