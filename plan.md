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

- [ ] **G. Unblock `sumo-api.com`** in the environment network policy, restart
  the session if needed, and confirm one live call succeeds. *(User action.)*

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
- [ ] **4a. Write `extract.py` with all gentle-API safeguards (offline-buildable):**
  - [ ] config constants: `BASE_URL`, `REQUEST_DELAY_SECONDS = 1.5`,
    `USER_AGENT`, `MAX_RETRIES = 3`, `CACHE_DIR`, `DB_PATH`
  - [ ] `fetch(url)`: check disk cache → return cached JSON if present;
    otherwise sleep(delay), GET with UA, handle 429/`Retry-After`, retry with
    exponential backoff (2/4/8s), write raw JSON to `cache/`, record in
    `fetch_log`, log progress
  - [ ] small, commented loader functions per entity that upsert into DuckDB
    (`INSERT OR REPLACE`), reading from the cached JSON
  - [ ] CLI flags to scope a run: `--basho <id>`, `--rikishi <id>`,
    `--divisions`, `--test` (tiny run), `--full` (guarded; refuses without an
    explicit confirm flag)
  - [ ] resumable: cache hits + upserts make re-runs continue where they left off
- [ ] **4b. SMALL TEST RUN** *(requires network — G)*: one recent basho
  (e.g. `202305`) across divisions + a handful of rikishi + kimarite list.
  Populate the DB from cache. Keep the request count tiny.
- [ ] **4c. Show test-run output** (log + row counts + a couple of sample rows)
  to user; reconcile any UNVERIFIED fields in `architecture.md` against the real
  JSON now sitting in `cache/`, and fix schema/loaders if needed.
- [ ] **4d. Test run approved by user.**

## Step 5 — Sanity-check queries
- [ ] **5a. Write `queries.sql`** with: row counts per table; one rikishi's full
  bout history; one tournament's full results (banzuke + torikumi + yusho);
  a kimarite frequency summary.
- [ ] **5b. Run against the test DB; show results to user.**
- [ ] **5c. Queries/validation approved by user.**

## Step 6 — Full historical pull (1958 → present)  ⚠️ big, gentle, resumable
- [ ] **6a. Confirm scope with user** (all divisions? all basho back to `195801`?
  estimated request count & wall-clock time at 1.5s/request, stated before
  starting).
- [ ] **6b. Enumerate all basho ids** 1958→present (6/year, odd months).
- [ ] **6c. Crawl in a resumable order**: rikishi list (with embedded history) →
  per basho: summary, banzuke per division, torikumi per division per day →
  kimarite. Cache-first, sequential, 1.5s delay, progress logged.
- [ ] **6d. Load everything into DuckDB from cache; run `queries.sql` for final
  validation; report final row counts.**
- [ ] **6e. Commit final artifacts** (code + schema + queries; NOT the DB/cache —
  gitignored). Report completion.

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
  1.5.4. Awaiting schema review. (Still offline — no API traffic yet.)
