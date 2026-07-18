CREATE TABLE banzuke_entry(basho_id VARCHAR, rikishi_id INTEGER, division VARCHAR, side VARCHAR, rank_value INTEGER, rank VARCHAR, wins INTEGER, losses INTEGER, absences INTEGER, PRIMARY KEY(basho_id, rikishi_id));;
CREATE TABLE basho(basho_id VARCHAR PRIMARY KEY, start_date VARCHAR, end_date VARCHAR, "location" VARCHAR);;
CREATE TABLE basho_yusho(basho_id VARCHAR, division VARCHAR, rikishi_id INTEGER, shikona_en VARCHAR, shikona_jp VARCHAR, PRIMARY KEY(basho_id, division));;
CREATE TABLE bout(basho_id VARCHAR, division VARCHAR, "day" INTEGER, match_no INTEGER, east_id INTEGER, east_shikona VARCHAR, east_rank VARCHAR, west_id INTEGER, west_shikona VARCHAR, west_rank VARCHAR, kimarite VARCHAR, winner_id INTEGER, winner_en VARCHAR, winner_jp VARCHAR, PRIMARY KEY(basho_id, division, "day", match_no));;
CREATE TABLE fetch_log(url VARCHAR PRIMARY KEY, status VARCHAR, fetched_at VARCHAR, note VARCHAR);;
CREATE TABLE kimarite(kimarite VARCHAR PRIMARY KEY, count INTEGER, last_usage VARCHAR);;
CREATE TABLE measurement_history(basho_id VARCHAR, rikishi_id INTEGER, height DOUBLE, weight DOUBLE, PRIMARY KEY(basho_id, rikishi_id));;
CREATE TABLE rank_history(basho_id VARCHAR, rikishi_id INTEGER, rank_value INTEGER, rank VARCHAR, PRIMARY KEY(basho_id, rikishi_id));;
CREATE TABLE rikishi(id INTEGER PRIMARY KEY, sumodb_id INTEGER, nsk_id INTEGER, shikona_en VARCHAR, shikona_jp VARCHAR, current_rank VARCHAR, heya VARCHAR, birth_date VARCHAR, shusshin VARCHAR, height DOUBLE, weight DOUBLE, debut VARCHAR, intai VARCHAR, updated_at VARCHAR, created_at VARCHAR);;
CREATE TABLE rikishi_stats(rikishi_id INTEGER PRIMARY KEY, total_matches INTEGER, total_wins INTEGER, total_losses INTEGER, total_absences INTEGER, total_basho INTEGER, yusho INTEGER, sansho INTEGER);;
CREATE TABLE shikona_history(basho_id VARCHAR, rikishi_id INTEGER, shikona_en VARCHAR, shikona_jp VARCHAR, PRIMARY KEY(basho_id, rikishi_id));;
CREATE TABLE special_prize(basho_id VARCHAR, prize_type VARCHAR, rikishi_id INTEGER, shikona_en VARCHAR, shikona_jp VARCHAR, PRIMARY KEY(basho_id, prize_type, rikishi_id));;

