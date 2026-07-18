#!/usr/bin/env python3
"""Export one basho's Makuuchi/Juryo results to viz/bouts.json for the
"A Basho in Circles" visual (viz/wrestler_in_circles.html).

Usage:
  python3 viz/export_viz.py [basho_id]   # defaults to 202605

Regenerate after loading a new basho into sumo.duckdb.
"""
import json
import pathlib
import sys

import duckdb

HERE = pathlib.Path(__file__).parent
DB_PATH = HERE.parent / "sumo.duckdb"
DIVISIONS = ["Makuuchi", "Juryo"]


def export(basho_id):
    con = duckdb.connect(str(DB_PATH), read_only=True)

    start_date = con.execute(
        "SELECT start_date FROM basho WHERE basho_id = ?", [basho_id]
    ).fetchone()[0]

    yusho = {
        row[0]: {"rikishi_id": row[1], "shikona_en": row[2]}
        for row in con.execute(
            "SELECT division, rikishi_id, shikona_en FROM basho_yusho WHERE basho_id = ?",
            [basho_id],
        ).fetchall()
    }

    out = {"basho_id": basho_id, "start_date": str(start_date), "divisions": {}}

    for division in DIVISIONS:
        wrestlers = con.execute(
            """
            SELECT be.rikishi_id, r.shikona_en, be.rank,
                   be.rank_value, be.wins, be.losses, be.absences
            FROM banzuke_entry be
            LEFT JOIN rikishi r ON r.id = be.rikishi_id
            WHERE be.basho_id = ? AND be.division = ?
            """,
            [basho_id, division],
        ).fetchall()

        bouts = con.execute(
            """
            SELECT day, match_no, east_id, east_shikona, east_rank,
                   west_id, west_shikona, west_rank, kimarite, winner_id
            FROM bout WHERE basho_id = ? AND division = ? ORDER BY day, match_no
            """,
            [basho_id, division],
        ).fetchall()

        # bout rows carry each wrestler's shikona as fought that day -- a more
        # reliable name source than the rikishi table, which only has profiles
        # for wrestlers whose full record was crawled (not every basho's field)
        names_from_bouts = {}
        by_wrestler_day = {}
        for (day, _match_no, eid, esh, erank, wid, wsh, wrank, kimarite, winner_id) in bouts:
            for me_id, me_sh, opp_id, opp_sh, opp_rank, side in (
                (eid, esh, wid, wsh, wrank, "E"),
                (wid, wsh, eid, esh, erank, "W"),
            ):
                if me_sh:
                    names_from_bouts[me_id] = me_sh
                by_wrestler_day.setdefault(me_id, {})[day] = {
                    "opp": opp_sh,
                    "opp_rank": opp_rank,
                    "win": winner_id == me_id,
                    "kimarite": kimarite,
                    "side": side,
                }

        rows = []
        for (rid, shikona_en, rank, rank_value, wins, losses, absences) in wrestlers:
            name = names_from_bouts.get(rid) or shikona_en or ("Rikishi " + str(rid))
            rows.append({
                "id": rid,
                "name": name,
                "rank": rank,
                "rank_value": rank_value,
                "wins": wins or 0,
                "losses": losses or 0,
                "absences": absences or 0,
                "yusho": division in yusho and yusho[division]["rikishi_id"] == rid,
                "days": by_wrestler_day.get(rid, {}),
            })
        # descending win record: most wins first, fewest losses breaks ties,
        # rank as the final tiebreak (lower rank_value = higher rank)
        rows.sort(key=lambda r: (-r["wins"], r["losses"], r["rank_value"] if r["rank_value"] is not None else 999))
        out["divisions"][division] = rows

    con.close()
    return out


if __name__ == "__main__":
    basho_id = sys.argv[1] if len(sys.argv) > 1 else "202605"
    data = export(basho_id)
    dest = HERE / "bouts.json"
    dest.write_text(json.dumps(data, separators=(",", ":"), default=str))
    m = sum(len(v) for v in data["divisions"].values())
    print(f"wrote {dest} — basho {basho_id}, {m} wrestlers across {len(data['divisions'])} divisions")
