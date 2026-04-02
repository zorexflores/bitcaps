# BitCaps — Phase 1 Complete / Phase 2 Handoff

**Date:** 2026-03-30
**Status:** Phase 1 simulation engine complete and validated. Ready for Phase 2 (visual layer).

---

## What BitCaps Is

A fantasy football simulation tool — a "shadow league" companion to Sleeper. You import a real Sleeper league, run N simulated alternate seasons using real player score variance, and see how standings could have looked. Long-term vision: pixel-art animated highlights (Retro Bowl-style).

**Three phases:**
- **Phase 1** ✅ — Simulation engine (Python, CLI)
- **Phase 2** 🔜 — Visual layer / UI (stack TBD, likely Streamlit)
- **Phase 3** — Pixel-art highlight clips

---

## File Structure

```
~/projects/BitCaps/
├── pull_league_data.py      # Fetches Sleeper API data locally (must run locally, not in sandbox)
├── sim_engine.py            # Core simulation engine — all logic lives here
├── run_sim.py               # CLI runner
├── data/
│   ├── raw/                 # Cached API JSON (named {tag}_s{season}_{type}.json)
│   │   ├── league1_s2025_league.json
│   │   ├── league1_s2025_rosters.json
│   │   ├── league1_s2025_users.json
│   │   ├── league1_s2025_matchups.json
│   │   ├── league2_s2025_league.json
│   │   ├── league2_s2025_rosters.json
│   │   ├── league2_s2025_users.json
│   │   ├── league2_s2025_matchups.json
│   │   └── league2_s2024_*  (prior season for league2)
│   └── output/              # JSON exports from multi-sim runs
│       └── league2_s2025_multi500.json
└── HANDOFF.md               # This file
```

---

## Key Design Decisions (do not change without discussion)

| Decision | Choice | Why |
|---|---|---|
| Variance method | Resample from player's actual weekly score pool | Fast to build, preserves player identity. Monte Carlo from raw stats is future upgrade. |
| Lineup mode | Actual lineups owners started | Preserves human decisions |
| Schedule | Real matchup pairings | Only scores randomized, not opponents |
| Dampening default | 0.2 | Blends draw 20% toward player mean. Reduces extreme stacking. ~34% of matchups flip at 0.2. |
| Real standings derivation | From matchup data directly (not roster settings) | Roster `settings.wins` is inflated in leagues with `league_average_match=1` (doubles wins) |

---

## sim_engine.py — Key Functions

```python
def build_player_profiles(matchups, all_weeks) -> dict
    # Returns: {player_id: [float, float, ...]} — all non-zero weekly scores

def resample_score(player_id, profiles, rng, dampening=0.0) -> float
    # player_id "0" (empty slot) always returns 0.0
    # draw = rng.choice(profile)
    # if dampening > 0: draw = draw*(1-dampening) + mean*dampening

def simulate_season(data, reg_season_weeks=None, seed=None, dampening=0.0) -> dict
    # Returns single sim result with final standings and per-week matchup outcomes
    # Standings derived from matchup data head-to-head only (not roster settings)

def run_multi_sim(data, n_sims=100, dampening=0.2, base_seed=None) -> dict
    # Returns aggregated results across N sims:
    # - avg_wins, playoff_pct, first_pct, last_pct, avg_rank, win_range
    # - real_standings (actual season for comparison)
    # - luck_delta = real_wins - sim_avg_wins

def export_single_sim_json(sim_result) -> dict
def export_multi_sim_json(multi_result) -> dict
    # Both return dicts ready for JSON serialization — Phase 2 consumes these
```

---

## run_sim.py — CLI Usage

```bash
# Single sim with seed
python3 run_sim.py --league league1 --season 2025 --seed 42

# Multi-sim (500 runs)
python3 run_sim.py --multi 500

# Multi-sim with JSON export
python3 run_sim.py --multi 500 --json

# Single sim with all weeks detailed
python3 run_sim.py --seed 42 --all-weeks

# Specific week detail
python3 run_sim.py --seed 42 --detail-week 5
```

**Flags:** `--league`, `--season`, `--seed`, `--dampening` (default 0.2), `--multi N`, `--json`, `--detail-week N`, `--all-weeks`

---

## Test Leagues

| Tag | Name | Teams | Scoring | Notes |
|---|---|---|---|---|
| `league1` | Gridiron & Grace | 10 | Full PPR | Clean. No special settings. |
| `league2` | League League | 12 | Half PPR | `league_average_match=1` (each team plays real opponent + virtual league median). Bug was found and fixed — standings now derived from matchup data, not roster settings. |

---

## Known Issues / Deferred Items

- **Player-level stats in multi-sim output** — Deferred. Currently outputs team-level. Adding player breakdowns is ~30 lines when ready.
- **Injury counterfactuals** — Not modeled. Injured players simply have smaller score pools (only weeks they played), which is correct behavior for "how would the season have gone." Explicit injury modeling (e.g., "what if this player stayed healthy") is a future feature.
- **Bye week 0.0 scores** — Already filtered from player profiles. Player ID "0" (empty slot) always returns 0.0 explicitly.

---

## Phase 2 — Visual Layer (Decided 2026-03-30)

**Stack:** Static HTML/CSS/JS → Netlify
**Spec:** See `PHASE2_SPEC.md` for full details.

**Key decisions:**
- Streamlit rejected — too constrained for custom visuals (trading cards, animated supersim)
- Pixel art deferred to Phase 3. Phase 2 uses dark/retro scoreboard aesthetic.
- Two core visuals: Player Trading Cards (MUT-style lineup) + Matchup Supersim (animated playback)
- Third view: Multi-sim analytics dashboard (luck delta, playoff odds, win distributions)
- Data flow: Python sim engine → JSON export → static site reads JSON client-side

**Sim engine changes needed for Phase 2:**
- New: `export_player_profiles_json()` with player names/positions (requires Sleeper /players lookup)
- Modified: `export_single_sim_json()` — include per-player starter scores (currently stripped)
- Modified: `export_multi_sim_json()` — re-include win_counts arrays for histograms

**Build order:** 2A (cards) → 2B (supersim) → 2C (dashboard) → 2D (polish + deploy)
