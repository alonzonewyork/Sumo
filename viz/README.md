# Visual — "A Basho in Circles"

A self-contained web visual over one basho's Makuuchi/Juryo results: plain
HTML + vanilla JS, no build step (same convention as the nflProject visuals
this was modeled on).

| File | What it shows |
|------|---------------|
| `wrestler_in_circles.html` | Every bout as a circle, one wrestler per row, sorted by final win record — toggle between Makuuchi and Juryo. |

## Viewing

The page fetches `bouts.json`, so it must be served over HTTP (`file://` is
blocked by the browser's fetch). From the repo root:

```sh
cd viz
python3 -m http.server 8000
# then open http://localhost:8000/wrestler_in_circles.html
```

## Regenerating the data

`bouts.json` is a static snapshot of one basho's `banzuke_entry` + `bout` rows
from `sumo.duckdb`, for the Makuuchi and Juryo divisions.

```sh
pip install duckdb        # once
python3 viz/export_viz.py 202605   # or any other basho_id already loaded
```

## Data contract

```json
{
  "basho_id": "202605",
  "start_date": "2026-05-10",
  "divisions": {
    "Makuuchi": [
      {"id": 7, "name": "Kirishima", "rank": "Ozeki 2 East", "rank_value": 202,
       "wins": 12, "losses": 3, "absences": 0, "yusho": false,
       "days": {"1": {"opp": "Takanosho", "opp_rank": "Maegashira 1 West",
                       "win": true, "kimarite": "hatakikomi", "side": "E"}, ...}}
    ],
    "Juryo": [...]
  }
}
```

A wrestler with no entry for a given day was absent (kyujo) that day. `side`
is which edge of the banzuke sheet they fought from that day (East/West) —
rendered as a filled-vs-open dot, mirroring nflProject's home/away cue.
