# Sumo Data Extraction — Build Plan

> **This is the living checklist.** I tick boxes and append progress notes as I
> go, so this file always reflects the true state. Steps are sequenced so
> **nothing risky (real API traffic, full pull) happens before your approval.**
>
> Legend: `[ ]` todo · `[~]` in progress / awaiting review · `[x]` done

---

## ⛔ Gating blocker — network access

The extractor cannot make a single real call until `www.sumo-api.com` is
allowed by this environment's outbound network policy (currently blocked → 403
at the egress proxy). Everything up to and including **Step 3** can be done
offline. **Steps 4b, 5, and 6 require the API to be reachable.**

- [x] **G. Unblock `sumo-api.com`** in the environment network policy, restart
  the session if needed, and confirm one live call succeeds. *(User action.)*
  — confirmed reachable (HTTP 200) in the new working environment, 2026-07-05.

---

## Step 1 — Explore the API & finalize the data model
- [x] **1a. Enumerate endpoints + fields; summarize raw shape** → `architecture.md` §3
- [x] **1b. Finalize normalized data model** (tables, keys, ER diagram) → `architecture.md` §4
- [x] **1c. Record tech choices + gentle-API strategy** → `architecture.md` §5, §7
- [x] **1d. Switch storage engine to DuckDB** (match other repos)
- [x] **1e. Architecture review approved by user**

## Step 2 — Build plan
- [~] **2a. Write `plan.md`** (this file) — awaiting review
- [ ] **2b. Plan review approved by user**

## Step 3 — Create the DuckDB schema (offline, safe)
- [x] **3a. Write `schema.sql`** — DDL for all tables in `architecture.md` §4
  (rikishi, basho, basho_yusho, special_prize, banzuke_entry, bout, kimarite,
  rank_history, shikona_history, measurement_history, rikishi_stats, fetch_log)
  using `CREATE TABLE IF NOT EXISTS`, DuckDB types, natural PKs.
- [x] **3b. Write `init_db.py`** that creates `sumo.duckdb` from `schema.sql`.
- [x] **3c. Run it; verify all tables exist and are empty** — 12 tables created,
  PKs correct (bout composite of 4, banzuke_entry of 2), re-run idempotent.
- [~] **3d. Show schema result to user for review.**

## Step 4 — Extraction script + SMALL test run
- [x] **4a. Write `extract.py` with all gentle-API safeguards (offline-buildable):**
  - [x] config constants: `BASE_URL`, `REQUEST_DELAY_SECONDS = 1.5`,
    `USER_AGENT`, `MAX_RETRIES = 3`, `CACHE_DIR`, `DB_PATH`
  - [x] `fetch_json(url)`: cache-first; else sleep(delay), GET with UA, handle
    429/`Retry-After`, retry with exponential backoff (2/4/8s), write raw JSON
    to `cache/`, record in `fetch_log`, log progress
  - [x] small, commented loader functions per entity that upsert into DuckDB
    (`INSERT OR REPLACE`), reading from cached JSON; `pick()` tolerates
    field-name variants while fields are UNVERIFIED
  - [x] CLI flags: `--test`, `--basho <id>`, `--rikishi <id>`, `--full`
    (guarded — refuses without `--yes-full`)
  - [x] resumable: cache hits + upserts make re-runs continue where they left off
  - [x] **offline plumbing test** (synthetic cache → run_test): every table
    populated, composite PKs hold, idempotent on re-run, field-name variant
    (`rikishiID`) handled. Guards verified.
- [x] **4b. SMALL TEST RUN** *(requires network — G)*: one recent basho
  (e.g. `202305`) across divisions + a handful of rikishi + kimarite list.
  Populate the DB from cache. Keep the request count tiny. — Done: 22 live
  requests, all cache-first/idempotent on re-run (verified: 2nd run made 0
  live fetches), gentle 1.5s+ delay honored throughout, no errors.
- [x] **4c. Show test-run output** (log + row counts + a couple of sample rows)
  to user; reconcile any UNVERIFIED fields in `architecture.md` against the real
  JSON now sitting in `cache/`, and fix schema/loaders if needed. — Reconciled;
  found and fixed 3 real bugs (see progress log below) before/while running.
- [x] **4d. Test run approved by user.**

## Step 5 — Sanity-check queries
- [x] **5a. Write `queries.sql`** with: row counts per table; one rikishi's full
  bout history; one tournament's full results (banzuke + torikumi + yusho);
  a kimarite frequency summary.
- [x] **5b. Run against the test DB; show results to user.** — All 7 queries
  ran clean: row counts, Asanoyama's 15-bout 202305 history (incl. the fusen
  walkover bout), all 6 divisions' yusho winners, Makuuchi banzuke (incl. a
  realistic 0-0-15 kyujo/absence row), day-1 torikumi, and kimarite frequency
  (`oshidashi`/`yorikiri` dominate, as expected).
- [x] **5c. Queries/validation approved by user.**

## Step 6 — Full historical pull (1958 → present)  ⚠️ big, gentle, resumable
- [x] **6a. Confirm scope with user.** Approved 2026-07-05:
  - **Divisions:** Makuuchi + Juryo only (the 2 salaried divisions), not all 6.
    Added `FULL_PULL_DIVISIONS = ["Makuuchi", "Juryo"]` in `extract.py`;
    `run_full()` now uses it instead of the full `DIVISIONS` list. Lower
    divisions can be backfilled later by widening this constant.
  - **Per-wrestler `/stats` calls:** deferred to **Step 7**, not skipped —
    `rikishi_stats` stays empty during Step 6 (everything in it is derivable
    from `bout` anyway); saves ~9,724 requests / ~4 hours off the main pull.
    Backfilled once Step 6 is fully done (2026-07-18 decision).
  - **Basho range:** 1958 → present, all of it (nonexistent basho like
    `195801` cost only 1 request each now, thanks to the 2026-07-05
    stub-detection fix, so there's no reason to hand-trim the range).
  - **Est. scope:** ~413 basho × 33 requests/basho (1 summary + 2 divisions ×
    16) + ~11 rikishi-list pages (599 active + 9,125 retired, paged 1000/req,
    both `intai` buckets) + 1 kimarite ≈ **~13,650 requests, ~5–6 hours**
    at 1.5s/request.
  - **Also fixed before this estimate was possible:** `run_full()`'s rikishi
    crawl wasn't passing `intai` at all, which defaults to active-only
    (599) — it would have silently skipped all 9,125 retired historical
    wrestlers. `load_rikishi_list()` now takes an `intai` param and
    `run_full()` crawls both buckets. Verified live (a retired wrestler,
    Takakeisho, loaded correctly with a real `intai` timestamp).
- [~] **6b. Enumerate all basho ids** 1958→present (6/year, odd months) —
  `enumerate_basho_ids()` already does this; not yet run end-to-end.
- [~] **6c. Crawl in a resumable order**: basho **newest → oldest** (recent
  data is the most-used, so it lands first if the ~5-6hr crawl gets
  interrupted — `run_full()` now reverses `enumerate_basho_ids()`), then
  rikishi list (with embedded history, both `intai` buckets) → kimarite.
  Cache-first, sequential, 1.5s delay, progress logged.
  - [x] Live-tested the pipeline against the most recent **complete** basho,
    **202605**, before committing to the full crawl (2026-07-18) — avoids
    caching a permanently-incomplete result from the in-progress 202607
    (Nagoya) tournament, whose later days haven't been fought yet.
- [ ] **6d. Load everything into DuckDB from cache; run `queries.sql` for final
  validation; report final row counts.**
- [ ] **6e. Commit final artifacts** (code + schema + queries; NOT the DB/cache —
  gitignored). Report completion.

## Step 7 — Per-wrestler stats backfill (only after Step 6 is fully done)
- [ ] **7a. Confirm Step 6 finished cleanly** (final row counts reviewed, 6e
  committed) before starting — this step is intentionally last so it never
  competes with the main historical pull.
- [ ] **7b. Crawl `/rikishi/{id}/stats`** for every `rikishi_id` already in the
  DB (from Step 6's rikishi crawl) via `load_rikishi_stats()` — cache-first,
  1.5s delay, same guardrails. ~9,724 requests / ~4 hours estimated (2026-07
  sizing from 6a).
- [ ] **7c. Reconcile a sample of `rikishi_stats` rows against `bout` counts**
  (spot-check a few wrestlers' win/loss totals) since this table is otherwise
  fully derivable and never exercised live before.
- [ ] **7d. Commit.**

> ### ⏸️ PAUSED HERE 2026-07-05 — resume checklist
> Nothing in Step 6 has run yet. All gating approvals are done; the single
> next action is:
> 1. Run `python3 extract.py --full --yes-full` (this executes 6b–6d in one
>    go: enumerates basho ids, crawls rikishi + every basho, loads DuckDB).
>    No further approval needed — scope is locked in from 6a above.
> 2. It's long (~5–6 hrs) and resumable — cache + `fetch_log` mean it's safe
>    to Ctrl-C and re-run; already-fetched URLs won't be re-hit.
> 3. When it finishes (or if resuming after an interruption), do 6d's
>    validation: `duckdb sumo.duckdb` and run `queries.sql`, report row
>    counts to the user.
> 4. Then 6e: ask the user before committing (code/schema/queries only, DB
>    and cache stay gitignored).
> 5. Only after 6e is done, move to Step 7 (per-wrestler stats backfill).

---

## Guardrails carried through every step
- Strictly sequential requests; `REQUEST_DELAY_SECONDS = 1.5` between calls.
- Descriptive `User-Agent` identifying this as personal research.
- Cache every raw response to `cache/`; always check cache before calling.
- Retry ×3 with exponential backoff; honor `429` / `Retry-After`.
- Idempotent + resumable (URL cache + `fetch_log` + upserts).
- Log every fetch (cache hit vs live).
- Pause for user review after each step (3d, 4c/4d, 5b/5c, 6a).

---

## Progress log
- **2026-07-04** — Step 1 complete. `architecture.md` drafted (13 endpoints, 12
  tables, ER diagram, gentle-API strategy). Response field lists flagged
  UNVERIFIED because `sumo-api.com` is blocked by the environment network policy
  — to be reconciled against real JSON during the Step 4 test run. Switched
  storage from SQLite to DuckDB at user request (match other repos). Architecture
  approved.
- **2026-07-04** — Step 2: `plan.md` written (this file). Approved.
- **2026-07-04** — Step 3: `schema.sql` + `init_db.py` written; `.gitignore`
  added (DB + cache not committed). Ran init: 12 tables created in
  `sumo.duckdb`, all empty, PKs verified, re-run idempotent. Installed `duckdb`
  1.5.4. Schema approved.
- **2026-07-04** — Step 4a: `extract.py` written with all gentle-API safeguards
  (cache-first fetch, 1.5s delay, backoff, 429 handling, fetch_log, per-entity
  loaders, CLI + `--full` guard). Validated the full pipeline OFFLINE with a
  synthetic cache: all 12 tables populate, PKs/idempotency hold. No real API
  traffic yet. **Step 4b (live test run) is blocked on item G** — `sumo-api.com`
  must be unblocked in the environment network policy.
- **2026-07-05** — New working environment; `sumo-api.com` confirmed reachable
  (item G unblocked). Reconciled UNVERIFIED fields against real JSON and found
  3 real bugs before/during the live test, all fixed in `extract.py`:
  1. `rikishi_stats.sansho` — API returns a per-prize-type object
     (`{"Gino-sho":1,...}`), not a scalar; `load_rikishi_stats` now sums it.
  2. `GET /kimarite` requires a `sortField` param or the API returns an error
     object with no `records` key, which `load_kimarite` was silently treating
     as zero rows; added `sortField=count&sortOrder=desc`.
  3. Nonexistent basho (e.g. `195801` — the 6/year format's first Hatsu Basho
     hadn't started that January) return **HTTP 200 with a blank stub**
     (`"date": ""`, `0001-01-01` dates), not a 404. `load_basho` now detects
     this and returns `False`; `load_basho_full` skips banzuke/torikumi calls
     for that basho instead of inserting a garbage row or wasting requests.
  Also fixed an unrelated CLI bug: `--rikishi 0` was treated as "not provided"
  because `elif args.rikishi:` is falsy on `0` (`is not None` now).
  Everything else in `architecture.md` §3 matched the real API exactly
  (rikishi fields, rank/measurement/shikona history, basho summary,
  yusho/specialPrizes, banzuke incl. the `rikishiID` capitalization, torikumi
  bout shape, including `kimarite: "fusen"` for fusen wins with a real
  `winnerId` set — confirms open question 3).
  Ran `python3 extract.py --test`: 22 live requests (kimarite + basho 202305
  summary + Makuuchi banzuke/torikumi all 15 days + Juryo banzuke + 10 rikishi
  w/ history + 2 stats), all 12 tables populated (294 bouts, 507 rank_history,
  90 kimarite, etc.), re-run made 0 live fetches (pure cache hits), row counts
  unchanged after re-run (idempotent). **Awaiting user approval (4d) to
  proceed to Step 5.**
- **2026-07-05** — Step 4d approved. Step 5: wrote `queries.sql` (row counts,
  one rikishi's full bout history, one tournament's full results, kimarite
  frequency); ran all 7 queries against the test DB — all clean and sane
  (Asanoyama's 15-bout 202305 history incl. the fusen bout, all 6 divisions'
  yusho winners, a realistic 0-0-15 kyujo banzuke row, kimarite frequency
  matching real-world sumo expectations). Approved (5c).
  Step 6a scope confirmed with user: Makuuchi + Juryo only (not all 6
  divisions), skip per-wrestler `/stats` calls, full 1958→present basho range
  — **~13,650 requests, ~5–6 hours** estimated. While sizing this, found and
  fixed one more real bug: `run_full()`'s rikishi crawl wasn't passing
  `intai`, which defaults to active-only (599) and would have silently
  skipped all 9,125 retired historical wrestlers — `load_rikishi_list()` now
  takes an `intai` param and `run_full()` crawls both buckets (verified live
  with a retired wrestler, Takakeisho). Added `FULL_PULL_DIVISIONS =
  ["Makuuchi", "Juryo"]` constant, used by `run_full()` instead of the full
  `DIVISIONS` list.
  **Paused here at user's request (session break) before starting Step 6 —
  see the "resume checklist" under Step 6 above.**
