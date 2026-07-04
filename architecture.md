# Sumo Data Extraction — Architecture

> **Status:** DRAFT for review (Step 1 of the build plan).
> **Scope:** research code — clarity and simplicity favored over robustness.

---

## ⚠️ Verification caveat (read first)

The Sumo-API host (`www.sumo-api.com`) is currently **blocked by this
environment's outbound network policy**, so I could not read the live
`/api-guide` page or make a single real call while drafting this document.

Everything below marked **(UNVERIFIED)** is reconstructed from prior knowledge
of the Sumo-API plus web-search corroboration of the *endpoint list*. The
**endpoint paths and the general data model are trustworthy**; the **exact
response field names and JSON nesting are not yet confirmed**. The extraction
script (Step 4) is deliberately designed to **dump raw JSON to disk first**, so
that once the API is reachable we can diff real responses against the field
lists here and correct the schema before loading anything.

**Action item before Step 3 (schema creation):** unblock `sumo-api.com` in the
environment network policy, fetch one sample response per endpoint, and
reconcile the "Raw shape" sections below with reality.

---

## 1. Goal

Pull as much sumo data as the Sumo-API exposes into a local SQLite database,
then expose a clean, normalized relational model to build analytical use cases
on (win/loss trends, head-to-head records, rank progression, kimarite usage,
physical-attribute trends over time, etc.). Historical match data goes back to
**1958**.

---

## 2. Data sources

### Primary: Sumo-API

- **Base URL:** `https://www.sumo-api.com/api`
- **Format:** JSON over REST, `GET` (one `POST` batch endpoint, not needed here)
- **Auth:** none
- **Coverage:** all current active rikishi + historical results back to 1958
- **Cost:** free, donation-supported → we treat it gently (see §7)

Key identifiers used throughout:

| Concept   | Form                       | Example      | Notes |
|-----------|----------------------------|--------------|-------|
| `bashoId` | `YYYYMM`                   | `202305`     | 6 tournaments/year, odd months (Jan, Mar, May, Jul, Sep, Nov) |
| `rikishiId` | integer (Sumo-API's own id) | `45`     | distinct from `sumodbId` / `nskId` |
| division  | string enum                | `Makuuchi`   | see §4.1 |
| `day`     | integer 1–15               | `11`         | a basho runs 15 days |

Divisions (top → bottom): **Makuuchi, Juryo, Makushita, Sandanme, Jonidan,
Jonokuchi**.

---

## 3. Endpoints (UNVERIFIED field lists)

Each endpoint below lists path params, query params, and the response shape as
best reconstructed. The extractor caches every raw response so we can confirm
these later.

### 3.1 `GET /rikishis` — list wrestlers
- **Query params:** `shikonaEn`, `heya`, `sumodbId`, `nskId`, `intai`,
  `measurements` (bool), `ranks` (bool), `shikonas` (bool), `limit` (≤ ~1000),
  `skip` (paging offset).
- **Raw shape:** `{ limit, skip, total, records: [ Rikishi, ... ] }`
- **Rikishi object fields:** `id`, `sumodbId`, `nskId`, `shikonaEn`,
  `shikonaJp`, `currentRank`, `heya`, `birthDate`, `shusshin` (hometown),
  `height` (cm), `weight` (kg), `debut` (basho `YYYYMM`), `intai` (retirement
  datetime, absent if active), `updatedAt`, `createdAt`. When the boolean flags
  are set, also embeds `rankHistory[]`, `measurementHistory[]`,
  `shikonaHistory[]`.
- **Use:** primary crawl to enumerate every rikishi id.

### 3.2 `GET /rikishi/{rikishiId}` — one wrestler
- Same fields as a record in 3.1. Query params `measurements`/`ranks`/`shikonas`
  embed the history arrays.

### 3.3 `GET /rikishi/{rikishiId}/stats` — career stats
- **Raw shape (object):** `totalMatches`, `totalWins`, `totalLosses`,
  `totalAbsences`, `totalBasho`, `yusho` (championships), `sansho` (special
  prizes total), plus `*ByDivision` breakdowns (`winsByDivision`,
  `lossByDivision`, `totalByDivision`, `yushoByDivision`, `absenceByDivision`,
  `bashoByDivision`).
- **Use:** convenience/cross-check; most of it is derivable from bouts, so we
  store it in a lightweight `rikishi_stats` table but treat bouts as truth.

### 3.4 `GET /rikishi/{rikishiId}/matches` — a wrestler's bouts
- **Query params:** `bashoId`, `opponentId` (both optional filters).
- **Raw shape:** `{ total, records: [ Bout, ... ] }` (may also carry summary
  counts).
- **Bout object fields:** `bashoId`, `division`, `day`, `matchNo`, `eastId`,
  `eastShikona`, `eastRank`, `westId`, `westShikona`, `westRank`, `kimarite`,
  `winnerId`, `winnerEn`, `winnerJp`.

### 3.5 `GET /rikishi/{rikishiId}/matches/{opponentId}` — head-to-head
- **Raw shape:** `{ total, ... win/loss + kimarite tallies ..., matches: [ Bout ] }`.
- **Use:** redundant with 3.4/torikumi for storage; useful as a validation
  cross-check. **Not** part of the core load — head-to-heads are a query on
  `bout`.

### 3.6 `GET /basho/{bashoId}` — tournament summary
- **Raw shape (object):** `date`/`bashoId`, `startDate`, `endDate`, `location`,
  `yusho: [ { type (division), rikishiId, shikonaEn, shikonaJp } ]`,
  `specialPrizes: [ { type (Shukun-sho | Kanto-sho | Gino-sho), rikishiId,
  shikonaEn, shikonaJp } ]`.

### 3.7 `GET /basho/{bashoId}/banzuke/{division}` — ranking sheet
- **Raw shape (object):** `bashoId`, `division`, `east: [ BanzukeEntry ]`,
  `west: [ BanzukeEntry ]`.
- **BanzukeEntry fields:** `side`, `rikishiID`, `shikonaEn`, `rankValue`,
  `rank`, `wins`, `losses`, `absences`, and a per-day `record: [ { result,
  opponentID, opponentShikonaEn, kimarite } ]`.
- **Use:** authoritative per-basho ranking + W/L/absence totals per rikishi.

### 3.8 `GET /basho/{bashoId}/torikumi/{division}/{day}` — bouts of a day
- **Raw shape (object):** `date`, `location`, `startDate`, `endDate`,
  `torikumi: [ Bout ]` (Bout shape as in 3.4).
- **Use:** the canonical, complete source for the `bout` table (every division,
  every day, every basho).

### 3.9 `GET /kimarite` — technique usage stats
- **Query params:** `sortField`, `sortOrder`, `limit`, `skip`.
- **Raw shape:** `{ limit, skip, total, sortField, sortOrder,
  records: [ { kimarite, count, lastUsage } ] }`.
- **Use:** seed the `kimarite` reference table.

### 3.10 `GET /kimarite/{kimarite}` — bouts decided by a technique
- **Query params:** `sortOrder`, `limit`, `skip`.
- **Raw shape:** `{ limit, skip, total, records: [ Bout ] }`.
- **Use:** validation cross-check only (bouts already captured via torikumi).

### 3.11 `GET /measurements` — measurement changes (time series)
- **Query params:** `bashoId`, `rikishiId`, `sortOrder`.
- **Raw shape:** array of `{ id (`"bashoId-rikishiId"`), bashoId, rikishiId,
  height, weight }`.

### 3.12 `GET /ranks` — rank changes (time series)
- **Query params:** `bashoId`, `rikishiId`, `rankValue`, `sortOrder`.
- **Raw shape:** array of `{ id, bashoId, rikishiId, rankValue, rank }`.

### 3.13 `GET /shikonas` — ring-name changes (time series)
- **Query params:** `bashoId`, `rikishiId`, `sortOrder`.
- **Raw shape:** array of `{ id, bashoId, rikishiId, shikonaEn, shikonaJp }`.

> The three time-series endpoints (3.11–3.13) return the same data that the
> `rikishi` endpoints embed when you pass `measurements=true` etc. We will get
> them "for free" during the rikishi crawl (embed the history arrays) and treat
> the standalone endpoints as a fallback / backfill path.

---

## 4. Proposed normalized data model

Design principle: **bouts and banzuke sheets are the source of truth**; stats
endpoints are conveniences we can recompute. History tables are keyed by
`(basho_id, rikishi_id)` because sumo state only changes at tournament
granularity.

### 4.1 Enumerations (stored as TEXT, not lookup tables — research simplicity)
- `division` ∈ {Makuuchi, Juryo, Makushita, Sandanme, Jonidan, Jonokuchi}
- `side` ∈ {East, West}
- `prize_type` ∈ {Shukun-sho, Kanto-sho, Gino-sho}

### 4.2 Tables

**`rikishi`** — one row per wrestler
| column        | type    | key | notes |
|---------------|---------|-----|-------|
| id            | INTEGER | PK  | Sumo-API rikishi id |
| sumodb_id     | INTEGER |     | id in SumoDB |
| nsk_id        | INTEGER |     | id in the official NSK site |
| shikona_en    | TEXT    |     | current ring name (romaji) |
| shikona_jp    | TEXT    |     | current ring name (kanji) |
| current_rank  | TEXT    |     | e.g. "Maegashira 1 East" |
| heya          | TEXT    |     | stable |
| birth_date    | TEXT    |     | ISO datetime |
| shusshin      | TEXT    |     | hometown / origin |
| height        | REAL    |     | cm (current) |
| weight        | REAL    |     | kg (current) |
| debut         | TEXT    |     | debut basho `YYYYMM` |
| intai         | TEXT    |     | retirement datetime, NULL if active |
| updated_at    | TEXT    |     | source timestamp |
| created_at    | TEXT    |     | source timestamp |

**`basho`** — one row per tournament
| column     | type | key | notes |
|------------|------|-----|-------|
| basho_id   | TEXT | PK  | `YYYYMM` |
| start_date | TEXT |     | ISO date |
| end_date   | TEXT |     | ISO date |
| location   | TEXT |     | e.g. "Tokyo, Ryogoku Kokugikan" |

**`basho_yusho`** — championship winners (per basho, per division)
| column     | type    | key | notes |
|------------|---------|-----|-------|
| basho_id   | TEXT    | PK, FK→basho | |
| division   | TEXT    | PK  | |
| rikishi_id | INTEGER | FK→rikishi | |
| shikona_en | TEXT    |     | denormalized snapshot at win time |
| shikona_jp | TEXT    |     | |

**`special_prize`** — sansho awards (per basho, per prize, per rikishi)
| column     | type    | key | notes |
|------------|---------|-----|-------|
| basho_id   | TEXT    | PK, FK→basho | |
| prize_type | TEXT    | PK  | Shukun-sho/Kanto-sho/Gino-sho |
| rikishi_id | INTEGER | PK, FK→rikishi | can be shared → rikishi in PK |
| shikona_en | TEXT    |     | |
| shikona_jp | TEXT    |     | |

**`banzuke_entry`** — a rikishi's ranking & record in one basho/division
| column     | type    | key | notes |
|------------|---------|-----|-------|
| basho_id   | TEXT    | PK, FK→basho   | |
| rikishi_id | INTEGER | PK, FK→rikishi | |
| division   | TEXT    |     | |
| side       | TEXT    |     | East/West |
| rank_value | INTEGER |     | numeric rank for sorting |
| rank       | TEXT    |     | e.g. "Ozeki", "Maegashira 3" |
| wins       | INTEGER |     | tournament W |
| losses     | INTEGER |     | tournament L |
| absences   | INTEGER |     | tournament absences |

**`bout`** — one row per match (the fact table)
| column       | type    | key | notes |
|--------------|---------|-----|-------|
| basho_id     | VARCHAR | PK, FK→basho | |
| division     | VARCHAR | PK  | |
| day          | INTEGER | PK  | 1–15 |
| match_no     | INTEGER | PK  | order within the day/division |
| east_id      | INTEGER | FK→rikishi | |
| east_shikona | VARCHAR |     | snapshot |
| east_rank    | VARCHAR |     | snapshot |
| west_id      | INTEGER | FK→rikishi | |
| west_shikona | VARCHAR |     | snapshot |
| west_rank    | VARCHAR |     | snapshot |
| kimarite     | VARCHAR | FK→kimarite | NULL for fusen/no-contest |
| winner_id    | INTEGER | FK→rikishi | NULL if none |
| winner_en    | VARCHAR |     | snapshot |
| winner_jp    | VARCHAR |     | snapshot |

Primary key is the natural composite `(basho_id, division, day, match_no)` —
this is stable and makes re-loading idempotent (`INSERT OR REPLACE`), so no
surrogate id / sequence is needed.

**`kimarite`** — winning-technique reference
| column     | type    | key | notes |
|------------|---------|-----|-------|
| kimarite   | TEXT    | PK  | technique name (romaji) |
| count      | INTEGER |     | usage count reported by API (denormalized) |
| last_usage | TEXT    |     | last-used marker from API |

**`rank_history`** — rank per rikishi per basho (from `/ranks` / embedded)
| column     | type    | key | notes |
|------------|---------|-----|-------|
| basho_id   | TEXT    | PK, FK→basho   | |
| rikishi_id | INTEGER | PK, FK→rikishi | |
| rank_value | INTEGER |     | |
| rank       | TEXT    |     | |

**`shikona_history`** — ring name per rikishi per basho
| column     | type    | key | notes |
|------------|---------|-----|-------|
| basho_id   | TEXT    | PK, FK→basho   | |
| rikishi_id | INTEGER | PK, FK→rikishi | |
| shikona_en | TEXT    |     | |
| shikona_jp | TEXT    |     | |

**`measurement_history`** — height/weight per rikishi per basho
| column     | type    | key | notes |
|------------|---------|-----|-------|
| basho_id   | TEXT    | PK, FK→basho   | |
| rikishi_id | INTEGER | PK, FK→rikishi | |
| height     | REAL    |     | cm |
| weight     | REAL    |     | kg |

**`rikishi_stats`** (optional convenience) — flattened career totals
| column | type | key | notes |
| rikishi_id | INTEGER | PK, FK→rikishi | |
| total_matches, total_wins, total_losses, total_absences, total_basho, yusho, sansho | INTEGER | | scalar totals; by-division breakdowns left in raw cache |

**`fetch_log`** (housekeeping) — resumability ledger
| column | type | key | notes |
|--------|------|-----|-------|
| url    | TEXT | PK  | request URL (also the cache key) |
| status | TEXT |     | ok / error |
| fetched_at | TEXT | | timestamp |
| note   | TEXT |     | e.g. HTTP code, record count |

> On the `banzuke_entry` vs `rank_history` overlap: both hold a per-basho rank.
> They come from **different endpoints** — `banzuke_entry` (from the banzuke
> sheet) additionally carries side + W/L/absences and only exists for basho we
> crawled division-by-division; `rank_history` (from `/ranks` or the embedded
> rikishi history) is a lighter, wrestler-centric series. Keeping both is
> intentional and cheap; analytics can prefer `banzuke_entry` where present.

### 4.3 Text ER diagram

```
                         ┌───────────────┐
                         │    basho      │  (PK basho_id, YYYYMM)
                         └──────┬────────┘
                                │ 1
            ┌───────────┬───────┼───────────┬───────────────┬──────────────┐
            │ N         │ N     │ N         │ N             │ N            │ N
   ┌────────▼──────┐ ┌──▼─────┐ ┌▼────────────┐ ┌──────────▼───┐ ┌────────▼─────┐
   │ basho_yusho   │ │special │ │banzuke_entry│ │ rank_history │ │shikona_hist. │
   └───────┬───────┘ │_prize  │ └──────┬──────┘ └──────┬───────┘ └──────┬───────┘
           │         └───┬────┘        │               │                │
           │             │             │  ┌────────────┴───┐            │
           │ N           │ N           │ N│  measurement_  │N           │ N
           │             │             │  │  history       │            │
   ┌───────▼─────────────▼─────────────▼──┴────────────────▼────────────▼──┐
   │                         rikishi   (PK id)                              │
   └───────▲──────────────────────────────────────────────────▲───────────┘
           │ east_id / west_id / winner_id (N:1, three FKs)    │ rikishi_id (1:1)
   ┌───────┴────────┐                                  ┌───────┴───────────┐
   │      bout      │───────────► kimarite (PK)        │  rikishi_stats    │
   │ (fact table)   │  kimarite FK                     └───────────────────┘
   └───────┬────────┘
           │ N:1 basho_id
           └────────────► basho
```

**How they relate, in words:**
- A **basho** is the hub. Every history/ranking/prize row is scoped to one
  `(basho_id, rikishi_id)` pair.
- A **rikishi** participates in many basho; per basho they have one
  `banzuke_entry`, one `rank_history`, one `shikona_history`, and one
  `measurement_history` row (state only changes tournament-to-tournament).
- A **bout** belongs to one basho and links to two rikishi (east/west), one
  winner, and one kimarite. This is the analytical fact table; head-to-head and
  win-rate queries run off it.
- **kimarite** is a small reference table the bout fact table points into.

---

## 5. Tech choices

| Choice | What | Why |
|--------|------|-----|
| Language | **Python 3** (`duckdb` package, `urllib`/`requests`, `json`, `time`) | ubiquitous, readable, first-class DuckDB Python API, no heavy deps for research code |
| Store | **DuckDB** (single `sumo.duckdb` file) | file-based like SQLite but columnar and analytics-oriented (fast aggregations/joins over the bout fact table); **matches the storage engine used by my other sumo repos** so datasets and queries are interchangeable |
| Cache | **on-disk JSON cache** under `cache/`, keyed by a slug of the request URL | makes re-runs free and offline; the raw record of truth before normalization |
| Migrations | a single `schema.sql` run with `CREATE TABLE IF NOT EXISTS` | research code — no migration framework needed |
| Deps | `duckdb`; `requests` optional, else stdlib `urllib` | fewer moving parts |

**Type conventions in the tables above:** written in shorthand — in the DuckDB
DDL, `TEXT` maps to `VARCHAR` (DuckDB accepts `TEXT` as an alias), `REAL` maps
to `DOUBLE`, and `INTEGER` stays `INTEGER`. Idempotent loads use DuckDB's
`INSERT OR REPLACE INTO` (or `INSERT ... ON CONFLICT DO UPDATE`) against the
primary keys defined per table — no sequences/autoincrement needed since every
table has a natural key.

Layout:
```
Sumo/
├── architecture.md          ← this file
├── plan.md                  ← living build checklist / progress log
├── schema.sql               ← DDL (Step 3)
├── extract.py               ← gentle extractor + loader (Step 4)
├── queries.sql              ← sanity-check queries (Step 5)
├── cache/                   ← raw JSON responses, URL-keyed (gitignored)
└── sumo.duckdb              ← DuckDB output (gitignored)
```

---

## 6. Analytical use cases this model supports
- Win/loss & win-rate over time per rikishi (from `bout`).
- Head-to-head records between any two rikishi (from `bout`).
- Rank progression / promotions & demotions (from `banzuke_entry` +
  `rank_history`).
- Physique trends (height/weight over a career, or across the sport) from
  `measurement_history`.
- Kimarite frequency and how a wrestler wins/loses (from `bout` + `kimarite`).
- Tournament results, yusho counts, sansho counts (from `basho_yusho`,
  `special_prize`, `banzuke_entry`).

---

## 7. Gentle-API strategy (explicit design principle)

The Sumo-API is free and donation-supported. The extractor is built around
being a considerate client — this is a **first-class design constraint, not an
afterthought**:

1. **Strictly sequential.** No threads, no concurrency, no async fan-out — one
   request at a time.
2. **Deliberate delay between every request.** Config constant
   `REQUEST_DELAY_SECONDS = 1.5` (default), sleep after each call.
3. **Descriptive User-Agent** identifying this as a personal research project
   (e.g. `Sumo-Research/1.0 (personal research; <contact email>)`).
4. **Disk cache first.** Every raw JSON response is written to `cache/`, keyed
   by the request URL. Before any call we check the cache and short-circuit on a
   hit → re-runs never re-hit the API.
5. **Retry with exponential backoff** (3 retries, e.g. 2s → 4s → 8s) on
   transient failures.
6. **Respect HTTP 429 / `Retry-After`.** On a 429 we back off for the header's
   duration (or a long default) rather than hammering.
7. **Resumable / idempotent.** The URL-keyed cache + `fetch_log` + upserts
   (`INSERT OR REPLACE` on natural keys) mean a re-run continues where it left
   off; nothing is duplicated.
8. **Progress logging.** Each fetch logs what it's pulling (endpoint, basho,
   division, day) and whether it was a cache hit or a live call.

---

## 8. Open questions to resolve once the API is reachable
1. Confirm exact response envelopes and field names for every endpoint in §3
   (the UNVERIFIED items) against real JSON; fix schema accordingly.
2. Confirm the `limit`/`skip` paging cap on `/rikishis` and `/kimarite`.
3. Confirm how absences / fusen (default) wins appear in a bout (`kimarite`
   value? `winnerId` = 0/null?).
4. Confirm the earliest available `bashoId` (expected `195801`) and whether
   lower divisions have complete torikumi that far back.
5. Confirm `basho` summary field name for the id (`date` vs `bashoId`).
```
