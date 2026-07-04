-- Sumo data model — DuckDB DDL (Step 3)
-- Mirrors architecture.md §4. Research code: clarity over robustness.
-- Idempotent: every statement uses CREATE TABLE IF NOT EXISTS, so re-running
-- init is safe. Natural primary keys make loads idempotent (INSERT OR REPLACE).

-- =========================================================================
-- Core entities
-- =========================================================================

-- One row per wrestler. `id` is the Sumo-API's own rikishi id.
CREATE TABLE IF NOT EXISTS rikishi (
    id            INTEGER PRIMARY KEY,
    sumodb_id     INTEGER,        -- id on SumoDB
    nsk_id        INTEGER,        -- id on the official NSK site
    shikona_en    VARCHAR,        -- current ring name (romaji)
    shikona_jp    VARCHAR,        -- current ring name (kanji)
    current_rank  VARCHAR,        -- e.g. "Maegashira 1 East"
    heya          VARCHAR,        -- stable
    birth_date    VARCHAR,        -- ISO datetime
    shusshin      VARCHAR,        -- hometown / origin
    height        DOUBLE,         -- cm (current)
    weight        DOUBLE,         -- kg (current)
    debut         VARCHAR,        -- debut basho YYYYMM
    intai         VARCHAR,        -- retirement datetime, NULL if active
    updated_at    VARCHAR,        -- source timestamp
    created_at    VARCHAR         -- source timestamp
);

-- One row per tournament. basho_id is YYYYMM (e.g. '202305').
CREATE TABLE IF NOT EXISTS basho (
    basho_id    VARCHAR PRIMARY KEY,
    start_date  VARCHAR,
    end_date    VARCHAR,
    location    VARCHAR
);

-- Winning-technique reference table (seeded from /kimarite).
CREATE TABLE IF NOT EXISTS kimarite (
    kimarite    VARCHAR PRIMARY KEY,  -- technique name (romaji)
    count       INTEGER,              -- usage count reported by API
    last_usage  VARCHAR               -- last-used marker from API
);

-- =========================================================================
-- Per-basho, per-rikishi facts
-- =========================================================================

-- Championship winners: one row per (basho, division).
CREATE TABLE IF NOT EXISTS basho_yusho (
    basho_id    VARCHAR,
    division    VARCHAR,
    rikishi_id  INTEGER,
    shikona_en  VARCHAR,   -- denormalized snapshot at win time
    shikona_jp  VARCHAR,
    PRIMARY KEY (basho_id, division)
);

-- Sansho (special prizes): Shukun-sho / Kanto-sho / Gino-sho.
-- A prize can be shared, so rikishi_id is part of the key.
CREATE TABLE IF NOT EXISTS special_prize (
    basho_id    VARCHAR,
    prize_type  VARCHAR,
    rikishi_id  INTEGER,
    shikona_en  VARCHAR,
    shikona_jp  VARCHAR,
    PRIMARY KEY (basho_id, prize_type, rikishi_id)
);

-- A rikishi's ranking and W/L/absence record in one basho/division.
CREATE TABLE IF NOT EXISTS banzuke_entry (
    basho_id    VARCHAR,
    rikishi_id  INTEGER,
    division    VARCHAR,
    side        VARCHAR,     -- East / West
    rank_value  INTEGER,     -- numeric rank for sorting
    rank        VARCHAR,     -- e.g. "Ozeki", "Maegashira 3"
    wins        INTEGER,
    losses      INTEGER,
    absences    INTEGER,
    PRIMARY KEY (basho_id, rikishi_id)
);

-- =========================================================================
-- Fact table: one row per match (from the torikumi endpoint)
-- =========================================================================
CREATE TABLE IF NOT EXISTS bout (
    basho_id      VARCHAR,
    division      VARCHAR,
    day           INTEGER,     -- 1..15
    match_no      INTEGER,     -- order within the day/division
    east_id       INTEGER,
    east_shikona  VARCHAR,     -- snapshot
    east_rank     VARCHAR,     -- snapshot
    west_id       INTEGER,
    west_shikona  VARCHAR,     -- snapshot
    west_rank     VARCHAR,     -- snapshot
    kimarite      VARCHAR,     -- NULL for fusen / no-contest
    winner_id     INTEGER,     -- NULL if none
    winner_en     VARCHAR,     -- snapshot
    winner_jp     VARCHAR,     -- snapshot
    PRIMARY KEY (basho_id, division, day, match_no)
);

-- =========================================================================
-- Time-series history tables (state changes at tournament granularity)
-- =========================================================================

CREATE TABLE IF NOT EXISTS rank_history (
    basho_id    VARCHAR,
    rikishi_id  INTEGER,
    rank_value  INTEGER,
    rank        VARCHAR,
    PRIMARY KEY (basho_id, rikishi_id)
);

CREATE TABLE IF NOT EXISTS shikona_history (
    basho_id    VARCHAR,
    rikishi_id  INTEGER,
    shikona_en  VARCHAR,
    shikona_jp  VARCHAR,
    PRIMARY KEY (basho_id, rikishi_id)
);

CREATE TABLE IF NOT EXISTS measurement_history (
    basho_id    VARCHAR,
    rikishi_id  INTEGER,
    height      DOUBLE,   -- cm
    weight      DOUBLE,   -- kg
    PRIMARY KEY (basho_id, rikishi_id)
);

-- =========================================================================
-- Conveniences / housekeeping
-- =========================================================================

-- Flattened career totals (by-division breakdowns stay in the raw cache).
CREATE TABLE IF NOT EXISTS rikishi_stats (
    rikishi_id      INTEGER PRIMARY KEY,
    total_matches   INTEGER,
    total_wins      INTEGER,
    total_losses    INTEGER,
    total_absences  INTEGER,
    total_basho     INTEGER,
    yusho           INTEGER,   -- championships
    sansho          INTEGER    -- special prizes
);

-- Resumability ledger: one row per fetched URL (also the cache key).
CREATE TABLE IF NOT EXISTS fetch_log (
    url         VARCHAR PRIMARY KEY,
    status      VARCHAR,     -- ok / error
    fetched_at  VARCHAR,     -- timestamp
    note        VARCHAR      -- e.g. HTTP code, record count
);
