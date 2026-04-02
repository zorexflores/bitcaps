"""
Pull raw Sleeper API data for both test leagues.
Run locally: python3 pull_league_data.py
Requires: pip install requests
Outputs: JSON files in ./data/raw/
"""

import json
import os
import requests

BASE = "https://api.sleeper.app/v1"

LEAGUES = {
    "league1": "1313587973614223360",
    "league2": "1181854504482328576",
}

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")
os.makedirs(OUT_DIR, exist_ok=True)


def fetch(url):
    """Fetch JSON from URL, return None on error."""
    try:
        r = requests.get(url)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        print(f"  ⚠️  {e}")
        return None


def pull_league(tag, lid, depth=0):
    """Pull all data for a league. Follows previous_league_id chain."""
    prefix = "  " * depth
    print(f"\n{prefix}--- {tag} ({lid}) ---")

    info = fetch(f"{BASE}/league/{lid}")
    if not info:
        print(f"{prefix}  ❌ Could not fetch league info")
        return

    season = info.get("season", "?")
    status = info.get("status", "?")
    name = info.get("name", "N/A")
    safe_tag = f"{tag}_s{season}"

    print(f"{prefix}  League: {name} | Teams: {info.get('total_rosters', '?')} | "
          f"Season: {season} | Status: {status}")

    # Save league info
    with open(os.path.join(OUT_DIR, f"{safe_tag}_info.json"), "w") as f:
        json.dump(info, f, indent=2)

    # Users
    users = fetch(f"{BASE}/league/{lid}/users")
    if users:
        with open(os.path.join(OUT_DIR, f"{safe_tag}_users.json"), "w") as f:
            json.dump(users, f, indent=2)
        print(f"{prefix}  Users: {len(users)}")

    # Rosters
    rosters = fetch(f"{BASE}/league/{lid}/rosters")
    if rosters:
        with open(os.path.join(OUT_DIR, f"{safe_tag}_rosters.json"), "w") as f:
            json.dump(rosters, f, indent=2)
        print(f"{prefix}  Rosters: {len(rosters)}")

    # Matchups — try weeks 1-18
    all_matchups = {}
    for week in range(1, 19):
        m = fetch(f"{BASE}/league/{lid}/matchups/{week}")
        if m:
            # Only count weeks that have actual point data
            has_points = any(entry.get("points", 0) > 0 for entry in m)
            if has_points:
                all_matchups[week] = m
    if all_matchups:
        with open(os.path.join(OUT_DIR, f"{safe_tag}_matchups.json"), "w") as f:
            json.dump(all_matchups, f, indent=2)
    print(f"{prefix}  Matchup weeks with scores: {len(all_matchups)}")

    # Drafts — use league's draft_id if available, else try the drafts-by-league endpoint
    draft_id = info.get("draft_id")
    if draft_id:
        draft_data = fetch(f"{BASE}/draft/{draft_id}")
        if draft_data:
            with open(os.path.join(OUT_DIR, f"{safe_tag}_draft.json"), "w") as f:
                json.dump(draft_data, f, indent=2)
            print(f"{prefix}  Draft: {draft_data.get('status', '?')}")

            # Draft picks
            picks = fetch(f"{BASE}/draft/{draft_id}/picks")
            if picks:
                with open(os.path.join(OUT_DIR, f"{safe_tag}_draft_picks.json"), "w") as f:
                    json.dump(picks, f, indent=2)
                print(f"{prefix}  Draft picks: {len(picks)}")
    else:
        print(f"{prefix}  No draft_id found")

    # Follow the chain to previous season
    prev_id = info.get("previous_league_id")
    if prev_id:
        print(f"{prefix}  ↳ Has previous league: {prev_id}")
        pull_league(tag, prev_id, depth + 1)
    else:
        print(f"{prefix}  (No previous league — end of chain)")


# Pull both leagues and follow history chains
for tag, lid in LEAGUES.items():
    pull_league(tag, lid)

# Pull 2024 season-level player stats
print("\n--- Pulling 2024 season stats ---")
stats = fetch(f"{BASE}/stats/nfl/regular/2024")
if stats:
    with open(os.path.join(OUT_DIR, "nfl_stats_2024.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print(f"  Players with stats: {len(stats)}")

# Pull week 1 stats as a sample
print("\n--- Pulling 2024 week 1 stats (sample) ---")
w1_stats = fetch(f"{BASE}/stats/nfl/regular/2024/1")
if w1_stats:
    with open(os.path.join(OUT_DIR, "nfl_stats_2024_week1.json"), "w") as f:
        json.dump(w1_stats, f, indent=2)
    print(f"  Players with week 1 stats: {len(w1_stats)}")

# ---------------------------------------------------------------------------
# Player name/position cache — needed for Phase 2 trading cards
# ---------------------------------------------------------------------------

print("\n--- Building player name cache ---")

# Collect all player IDs used in matchup starters across all cached leagues
all_player_ids = set()
for fname in os.listdir(OUT_DIR):
    if fname.endswith("_matchups.json"):
        with open(os.path.join(OUT_DIR, fname)) as f:
            matchups = json.load(f)
        for week, entries in matchups.items():
            for entry in entries:
                for pid in entry.get("starters", []):
                    if pid and pid != "0":
                        all_player_ids.add(pid)

print(f"  Unique player IDs across all leagues: {len(all_player_ids)}")

# Step 1: Seed from draft picks (already cached, no API call)
player_cache = {}
for fname in os.listdir(OUT_DIR):
    if fname.endswith("_draft_picks.json"):
        with open(os.path.join(OUT_DIR, fname)) as f:
            picks = json.load(f)
        for p in picks:
            pid = p.get("player_id")
            meta = p.get("metadata", {})
            if pid and meta.get("first_name") and pid not in player_cache:
                player_cache[pid] = {
                    "player_id": pid,
                    "first_name": meta.get("first_name", ""),
                    "last_name": meta.get("last_name", ""),
                    "position": meta.get("position", ""),
                    "team": meta.get("team", ""),
                }

print(f"  From draft picks: {len(player_cache)} players")

# Step 2: Fetch full Sleeper players endpoint and fill gaps
NFL_TEAMS = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys", "DEN": "Denver Broncos",
    "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs",
    "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings", "NE": "New England Patriots",
    "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers", "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}

# Handle defense/ST IDs (team abbreviations)
for pid in all_player_ids:
    if pid.isalpha() and pid.upper() in NFL_TEAMS:
        player_cache[pid] = {
            "player_id": pid,
            "first_name": NFL_TEAMS[pid.upper()],
            "last_name": "D/ST",
            "position": "DEF",
            "team": pid.upper(),
        }

missing_ids = all_player_ids - set(player_cache.keys())
print(f"  After drafts + D/ST: {len(missing_ids)} players still missing")

if missing_ids:
    print("  Fetching Sleeper /players/nfl endpoint (this is ~25MB, one-time)...")
    all_players = fetch(f"{BASE}/players/nfl")
    if all_players:
        filled = 0
        for pid in missing_ids:
            p = all_players.get(pid)
            if p:
                player_cache[pid] = {
                    "player_id": pid,
                    "first_name": p.get("first_name", ""),
                    "last_name": p.get("last_name", ""),
                    "position": p.get("position", ""),
                    "team": p.get("team", ""),
                }
                filled += 1
        print(f"  Filled from API: {filled} players")
    else:
        print("  ⚠️  Could not fetch players endpoint — some names will be missing")

# Save only the players we need (not the full 25MB blob)
still_missing = all_player_ids - set(player_cache.keys())
if still_missing:
    print(f"  ⚠️  Still missing {len(still_missing)} players: {list(still_missing)[:5]}...")
    for pid in still_missing:
        player_cache[pid] = {
            "player_id": pid,
            "first_name": "Unknown",
            "last_name": f"#{pid}",
            "position": "?",
            "team": "?",
        }

with open(os.path.join(OUT_DIR, "players_cache.json"), "w") as f:
    json.dump(player_cache, f, indent=2)
print(f"  ✅ Saved {len(player_cache)} players to players_cache.json")

# Summary
print(f"\n✅ All data saved to {OUT_DIR}/")
print("Files:")
for f_name in sorted(os.listdir(OUT_DIR)):
    size = os.path.getsize(os.path.join(OUT_DIR, f_name))
    print(f"  {f_name} ({size:,} bytes)")
