# BitCaps — Phase 2 Handoff

**Date:** 2026-04-01
**Status:** Phase 2A (Cards), 2B (Supersim), 2C (Dashboard) complete. Ready for 2D (Polish + Deploy).

---

## What's Built

### Site structure
```
~/projects/BitCaps/
├── sim_engine.py            # Core engine — Phase 1, unchanged
├── pull_league_data.py      # Fetches Sleeper data + builds players_cache.json
├── generate_site_data.py    # Generates all JSON the site needs → site/data/
├── generate_site_data.py    # Run this to refresh site data
├── PHASE2_SPEC.md           # Full Phase 2 spec
├── HANDOFF.md               # Phase 1 handoff (still valid)
├── data/
│   ├── raw/                 # Cached Sleeper API data + players_cache.json
│   └── output/              # Legacy CLI exports (not used by site)
└── site/
    ├── index.html           # The entire site — single file
    └── data/
        ├── index.json                    # League index
        ├── league1_2025/
        │   ├── manifest.json             # League metadata + file list
        │   ├── player_profiles.json      # Trading card data
        │   ├── multi_sim.json            # 500-sim aggregate (with win_counts)
        │   └── sim_seed{1,42,100,500,999}.json  # Single sim exports
        └── league2_2025/
            └── (same structure)
```

### Three working tabs

**Lineup Cards (2A)**
- Portrait trading cards, MUT-style tiers (Elite/Gold/Silver/Bronze)
- OVR rating scaled to league's best scorer
- Position color coding, foil shine on hover, scanline art area
- Per-team scoreboard strip: avg wins, playoff odds, sim rank, luck delta, win range
- Cards sorted stars-first

**Supersim (2B)**
- Animated matchup playback — player by player, alternating teams
- Auto-animate mode (900ms/player) and step-through mode (manual)
- Running score scoreboard with live winner coloring (teal/dim)
- Flip alert pulses red when sim outcome differs from reality
- 5 pre-baked alternate seasons selectable; week + matchup pickers
- Matchups with flipped outcomes marked ⚡ in the dropdown

**Dashboard (2C)**
- Sim standings vs reality table (gold badges for playoff teams)
- Luck delta bar chart — teal = unlucky, red = lucky, centered on zero
- Win distribution histograms per team (SVG, gold bar = real result)
- Auto-generated key insights: luckiest, most robbed, playoff outliers
- Meta strip: sim count, dampening, flip rate, playoff spots

### About modal
- ? button in header
- Explains the shadow league concept
- Currently plain monospace text — flagged for redesign in 2D

---

## To run locally

```bash
cd ~/projects/BitCaps

# Refresh player cache (one-time or after roster changes)
python3 pull_league_data.py

# Regenerate site data
python3 generate_site_data.py

# Serve
cd site && python3 -m http.server 8000
# open http://localhost:8000
```

---

## Phase 2D — What's Left

### Polish
- [ ] **About modal redesign** — currently a wall of monospace text. Should be punchy, visual, use actual sim data (e.g. "38% of matchups flip outcomes"), reflect the retro aesthetic
- [ ] **D/ST name truncation fix** — "T. Bay Bucca..." should render as "TB Buccaneers D/ST"
- [ ] **Sleeper avatars** on team chips (currently initials only) — URL pattern: `https://sleepercdn.com/avatars/thumbs/{avatar_id}`; avatar IDs are in users JSON
- [ ] **Supersim speed control** — slider or fast/normal/slow toggle
- [ ] **Mobile layout pass** — cards and dashboard need responsive review

### Netlify deploy
- [ ] Push `site/` folder to a GitHub repo
- [ ] Connect repo to Netlify (or drag-and-drop `site/` to Netlify dashboard)
- [ ] Set base directory to `site/` — no build command needed, it's static
- [ ] Custom domain (optional)

### Known issues
- `players_cache.json` is required for player names on cards/supersim. If missing, falls back to "Player #ID". Run `pull_league_data.py` once to generate it.
- OVR is relative to league's highest scorer — highest player always ~98. Intentional design.
- Dashboard luck delta uses `real_wins - avg_sim_wins`. Positive = lucky (real > expected).

---

## Recommended next chat prompt

> "Read ~/projects/BitCaps/PHASE2_HANDOFF.md. We're in Phase 2D — polish and Netlify deploy. Start with: (1) fix D/ST name truncation, (2) redesign the about modal to be visual and punchy, (3) add Sleeper avatars to team chips, then walk me through the Netlify deploy."
