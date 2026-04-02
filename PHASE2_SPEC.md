# BitCaps — Phase 2 Spec: Visual Layer

**Date:** 2026-03-30
**Status:** Planning complete. Ready to build.

---

## Stack Decision

**Framework:** Static HTML / CSS / JavaScript (no framework — vanilla JS or lightweight lib as needed)
**Hosting:** Netlify (free tier, git-linked deploy)
**Data flow:** Python sim engine (unchanged) → JSON export → static site consumes JSON

### Why not Streamlit

Phase 2 requires two custom visual components (trading cards + animated supersim) that need precise layout and animation control. Streamlit's widget-based rendering would constrain both. The HTML/JS path also aligns with the long-term goal of a public tool for any Sleeper user — no Python runtime required for the viewer.

### Architecture

```
[Python sim engine] → [JSON files] → [Static HTML/JS site]
     (Phase 1)          (bridge)          (Phase 2)
```

- Sim engine stays untouched. JSON exports are the data contract.
- Site loads JSON client-side and renders.
- No backend required until Phase 3+ (when public users need on-demand sims).

---

## Two Core Visuals

### 1. Player Trading Cards (Ultimate Team Lineup View)

**Concept:** Each player rendered as a styled card showing their sim profile. A team's starting lineup displayed as a card collection, similar to Madden Ultimate Team or FIFA Ultimate Team lineup screens.

**Per-card data:**
- Player name
- Position
- Average weekly score (across season)
- Score range (floor / ceiling)
- Consistency grade (derived from score variance — low variance = high consistency)
- Games played (weeks with non-zero score)

**Layout:**
- One team's full starting lineup displayed as a grid/row of cards
- Cards sized and arranged by position (QB prominent, flex smaller, etc.)
- Visual treatment: dark background, bold stat numbers, position-colored accents

**Interaction:**
- Select a team from a dropdown/selector
- Cards populate for that team's actual starting lineup
- Hover/tap a card for expanded stats (full weekly score history, comparison to position average)

**Data requirement:** New export function in sim engine — per-player sim profiles. Currently available in `build_player_profiles()` but not exposed in JSON exports.

---

### 2. Matchup Supersim (Animated Playback)

**Concept:** Watch a simulated matchup unfold player by player. Two teams side by side, scores accumulating as each player's sim score resolves. Inspired by Madden's in-game supersim screen.

**Layout:**
- Two columns (Team A vs Team B)
- Each row = one starter slot (QB, RB1, RB2, WR1, etc.)
- Score bars that fill as each player's score resolves
- Running total at top updating as players resolve
- Final outcome highlighted (W/L, margin, whether it flipped from reality)

**Playback modes (user toggle):**
- **Auto-animate:** Hit play, scores tick up player-by-player on a timer (~0.5-1s per player). Running total updates live.
- **Step-through:** Click/tap to advance one player at a time. Same visual, manual pacing.

**Key visual moments:**
- When a matchup **flips** from the real outcome, highlight it (flash, color change, callout)
- Close matchups (< 5 point margin) get a "nail-biter" indicator
- Show real score vs sim score per player (subtle comparison — "would have scored X, sim says Y")

**Data source:** `export_single_sim_json()` already contains per-matchup, per-team real vs sim points. Needs to be extended to include per-player starter scores (currently in `weekly_results` but stripped during export).

---

### 3. Multi-Sim Dashboard (Analytical Layer)

**Concept:** The FiveThirtyEight-ish view. Aggregated results across N simulations. This is the "proof" layer — it answers "how lucky/unlucky was I really?"

**Components:**
- **Standings comparison table** — Real season rank vs sim average rank, with movement arrows
- **Luck delta bar chart** — Horizontal bars showing real wins minus sim average wins per team. Positive = lucky, negative = unlucky. Color-coded.
- **Playoff odds gauge** — Per team: "made playoffs in X% of 500 simulations." Circular gauge or probability bar.
- **Win distribution histogram** — Per team: bell curve of win totals across all sims. Real win total marked with a line. Shows whether reality was an outlier.
- **First/Last probability** — Small badges: "Finished 1st in X% of sims" / "Finished last in X% of sims"

**Data source:** `export_multi_sim_json()` — already contains all needed aggregates. May want to re-include `win_counts` arrays (currently stripped) for the histogram view.

---

## Data Contract Updates Needed (sim_engine.py)

### New: `export_player_profiles_json(sim_result)`
Exposes per-player data for trading cards:
```python
{
    "player_id": {
        "name": "...",          # Requires player name lookup (new)
        "position": "...",      # Requires player metadata (new)
        "avg_score": float,
        "min_score": float,
        "max_score": float,
        "std_dev": float,
        "games_played": int,
        "weekly_scores": [float, ...]
    }
}
```

**Note:** Player names and positions require a Sleeper player metadata lookup. The current engine only uses player IDs. This is new work — either fetch from Sleeper's `/players` endpoint or bundle a static player map.

### Modified: `export_single_sim_json()`
Include per-player starter scores in weekly results (currently stripped). Needed for supersim playback.

### Modified: `export_multi_sim_json()`
Re-include `win_counts` arrays. Needed for histogram view.

---

## Phase 2 Build Order

### 2A — Foundation + Trading Cards
1. Add player name/position lookup to data pipeline
2. Add `export_player_profiles_json()` to sim engine
3. Site skeleton: HTML shell, dark theme, team selector
4. Trading card component: single card, then full lineup grid
5. Wire up: load JSON → render cards for selected team

### 2B — Matchup Supersim
6. Extend `export_single_sim_json()` with per-player scores
7. Matchup selector (pick a week, pick a matchup)
8. Supersim layout: two-column player-by-player view
9. Auto-animate mode (timed playback)
10. Step-through mode (manual advance)
11. Flip detection + visual highlight

### 2C — Multi-Sim Dashboard
12. Re-include `win_counts` in multi-sim export
13. Standings comparison table
14. Luck delta bar chart
15. Win distribution histogram
16. Playoff odds display

### 2D — Polish + Deploy
17. Retro/dark theme refinement (fonts, colors, card styling)
18. Responsive layout (desktop-first, mobile-aware)
19. Deploy to Netlify
20. Test with both league1 and league2 data

---

## Visual Direction

**Aesthetic:** Dark background, retro-tinged but not pixel art. Stadium scoreboard energy — glowing numbers on dark surfaces, monospace or condensed fonts, accent colors for team differentiation. Trading cards bring the collectible/game feel. Supersim brings the broadcast energy.

**Pixel art:** Deferred to Phase 3. Phase 2 establishes the tone without committing to pixel rendering.

**Palette (starting point):**
- Background: near-black (#0a0a0a or similar)
- Primary text: warm white (#f0e6d3)
- Accent 1: amber/gold (#f59e0b) — scores, highlights
- Accent 2: teal (#14b8a6) — positive indicators (lucky, winning)
- Accent 3: red (#ef4444) — negative indicators (unlucky, losing)
- Card backgrounds: dark gray (#1a1a2e) with subtle gradient

---

## Open Questions (to resolve during build)

1. **Player name source:** Sleeper's `/players` endpoint is a ~25MB JSON blob. Cache it locally? Bundle a trimmed version with only players in the league? Or fetch on-demand?
2. **How many sims to pre-bake?** Default 500 is fine for multi-sim. Single sim seeds — offer a few pre-baked or let user generate on the fly (requires Python, so pre-baked for static site)?
3. **Team branding:** Use Sleeper avatars/colors or generate our own per-team identity?
