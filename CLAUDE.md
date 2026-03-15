# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This project is in initial setup. No build system, dependencies, or application code exist yet.

## Branch

Active development branch: `claude/init-project-setup-wLYNa`

## Data Source

**Primary API:** [sumo-api.com](https://www.sumo-api.com/) — free REST API, no authentication required for GET requests.

Base URL: `https://www.sumo-api.com`

Key endpoints:
- `GET /api/rikishis` — all wrestlers (supports pagination)
- `GET /api/rikishi/:id` — wrestler detail (includes rank/shikona/measurement history)
- `GET /api/rikishi/:id/stats` — career stats
- `GET /api/rikishi/:id/matches` — full match history
- `GET /api/rikishi/:id/matches/:opponentId` — head-to-head
- `GET /api/basho/:bashoId` — tournament (bashoId format: `YYYYMM`, e.g. `202501`)
- `GET /api/basho/:bashoId/banzuke/:division` — rankings for a division
- `GET /api/basho/:bashoId/torikumi/:division/:day` — bout schedule/results
- `GET /api/kimarite` — winning techniques with usage counts
- `GET /api/ranks`, `/api/shikonas`, `/api/measurements` — historical tracking

Divisions: `Makuuchi`, `Juryo`, `Makushita`, `Sandanme`, `Jonidan`, `Jonokuchi`

Full docs: https://www.sumo-api.com/api-guide

### Estimated Data Volume

| Entity | Estimate | Basis |
|---|---|---|
| Basho covered | ~405 | 6/year × 68 years (1958–2026), minus ~3 cancellations |
| Unique rikishi | ~4,000–5,000+ | ~600 active at any time, ~10-year avg careers |
| Bouts (top 2 divisions) | ~210,000 | 42 Makuuchi + 28 Juryo rikishi × 15 days × ~405 basho |
| Bouts (all divisions) | ~500,000–800,000 | Lower divisions fight 7 bouts/basho with larger rosters |
| Kimarite techniques | ~70+ | Standardized winning move classifications |

The API covers all six divisions and tracks shikona/rank/measurement changes over time, making the full dataset substantially richer than bout records alone.
