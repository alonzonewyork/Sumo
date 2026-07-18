-- Sumo data model — sanity-check queries (Step 5)
-- Run against sumo.duckdb after a test/full load. Research code: clarity over
-- robustness. Example ids below (rikishi 2 = Asanoyama, basho 202305) match
-- what the Step 4 test run (`extract.py --test`) populates.

-- =========================================================================
-- 1. Row counts per table — quick sanity check that a load actually happened
-- =========================================================================
SELECT 'rikishi' AS table_name, COUNT(*) AS rows FROM rikishi
UNION ALL SELECT 'basho', COUNT(*) FROM basho
UNION ALL SELECT 'basho_yusho', COUNT(*) FROM basho_yusho
UNION ALL SELECT 'special_prize', COUNT(*) FROM special_prize
UNION ALL SELECT 'banzuke_entry', COUNT(*) FROM banzuke_entry
UNION ALL SELECT 'bout', COUNT(*) FROM bout
UNION ALL SELECT 'kimarite', COUNT(*) FROM kimarite
UNION ALL SELECT 'rank_history', COUNT(*) FROM rank_history
UNION ALL SELECT 'shikona_history', COUNT(*) FROM shikona_history
UNION ALL SELECT 'measurement_history', COUNT(*) FROM measurement_history
UNION ALL SELECT 'rikishi_stats', COUNT(*) FROM rikishi_stats
UNION ALL SELECT 'fetch_log', COUNT(*) FROM fetch_log
ORDER BY table_name;

-- =========================================================================
-- 2. One rikishi's full bout history (wins/losses, opponent, technique)
-- =========================================================================
SELECT
    b.basho_id, b.division, b.day, b.match_no,
    CASE WHEN b.east_id = 2 THEN b.west_shikona ELSE b.east_shikona END AS opponent,
    CASE WHEN b.winner_id = 2 THEN 'win' ELSE 'loss' END AS result,
    b.kimarite
FROM bout b
WHERE 2 IN (b.east_id, b.west_id)
ORDER BY b.basho_id, b.day, b.match_no;

-- =========================================================================
-- 3. One tournament's full results: banzuke + torikumi + yusho
-- =========================================================================
-- 3a. Tournament summary + champions
SELECT bs.basho_id, bs.start_date, bs.end_date, bs.location,
       y.division, y.shikona_en AS yusho_winner
FROM basho bs
LEFT JOIN basho_yusho y ON y.basho_id = bs.basho_id
WHERE bs.basho_id = '202305'
ORDER BY y.division;

-- 3b. Banzuke (ranking sheet) for one division
SELECT rikishi_id, side, rank, wins, losses, absences
FROM banzuke_entry
WHERE basho_id = '202305' AND division = 'Makuuchi'
ORDER BY rank_value;

-- 3c. Torikumi (day-by-day bouts) for one division/day
SELECT day, match_no, east_shikona, west_shikona, kimarite, winner_en
FROM bout
WHERE basho_id = '202305' AND division = 'Makuuchi' AND day = 1
ORDER BY match_no;

-- =========================================================================
-- 4. Kimarite frequency summary (from the seeded reference table, and from
--    the bouts we've actually loaded, for comparison)
-- =========================================================================
-- 4a. API-reported all-time usage counts (reference table)
SELECT kimarite, count, last_usage
FROM kimarite
ORDER BY count DESC
LIMIT 10;

-- 4b. Usage counts within the bouts currently loaded in this DB
SELECT kimarite, COUNT(*) AS uses
FROM bout
WHERE kimarite IS NOT NULL
GROUP BY kimarite
ORDER BY uses DESC
LIMIT 10;
