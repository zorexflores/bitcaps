"""
BitCaps Simulation Engine — Phase 1
Imports a Sleeper league season and runs a simulated alternate season
using the resample variance method (shuffles when big/small games happen).

Design decisions:
- Uses actual weekly lineups (who they really started)
- Keeps the real matchup schedule (same opponents)
- Variance comes from resampling each player's weekly scores
"""

import json
import os
import random
from collections import defaultdict


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def load_json(filepath):
    """Load a JSON file, return None if missing."""
    if not os.path.exists(filepath):
        return None
    with open(filepath) as f:
        return json.load(f)


def load_league_season(data_dir, league_tag, season):
    """
    Load all data for a league season from raw JSON files.
    Returns a dict with keys: info, users, rosters, matchups.
    """
    prefix = f"{league_tag}_s{season}"
    data = {
        "info": load_json(os.path.join(data_dir, f"{prefix}_info.json")),
        "users": load_json(os.path.join(data_dir, f"{prefix}_users.json")),
        "rosters": load_json(os.path.join(data_dir, f"{prefix}_rosters.json")),
        "matchups": load_json(os.path.join(data_dir, f"{prefix}_matchups.json")),
    }
    if not data["info"]:
        raise FileNotFoundError(f"No league info found for {prefix}")
    if not data["matchups"]:
        raise FileNotFoundError(f"No matchup data found for {prefix}")
    return data


def get_team_names(users, rosters):
    """
    Build a mapping of roster_id -> team display name.
    Falls back to display_name if no team_name set.
    """
    # Map owner_id -> user info
    owner_map = {}
    for u in (users or []):
        uid = u.get("user_id")
        team = u.get("metadata", {}).get("team_name")
        display = u.get("display_name", uid)
        owner_map[uid] = team or display

    # Map roster_id -> owner_id
    roster_names = {}
    for r in (rosters or []):
        rid = r["roster_id"]
        oid = r.get("owner_id")
        roster_names[rid] = owner_map.get(oid, f"Team {rid}")

    return roster_names


# ---------------------------------------------------------------------------
# Player Score Profiles
# ---------------------------------------------------------------------------

def build_player_profiles(matchups, all_weeks):
    """
    Build a score profile for every player who appeared in the matchup data.
    Profile = list of non-zero weekly scores across the season.

    Args:
        matchups: dict of week_str -> list of matchup entries
        all_weeks: list of week numbers to include (e.g. [1..18])

    Returns:
        dict of player_id -> list of float scores (0.0 excluded)
    """
    profiles = defaultdict(list)

    for week in all_weeks:
        week_str = str(week)
        if week_str not in matchups:
            continue
        for entry in matchups[week_str]:
            pp = entry.get("players_points", {})
            for pid, pts in pp.items():
                if pts > 0:
                    profiles[pid].append(pts)

    return dict(profiles)


# ---------------------------------------------------------------------------
# Simulation Core
# ---------------------------------------------------------------------------

def resample_score(player_id, profiles, rng, dampening=0.0):
    """
    Draw a random score from a player's profile.

    Args:
        player_id: Sleeper player ID string
        profiles: dict of player_id -> list of scores
        rng: random.Random instance
        dampening: float 0.0-1.0. At 0.0, pure resample. At 1.0, always
                   returns the player's mean. Values between blend the draw
                   toward the mean, reducing extreme outcomes.

    Returns:
        float score
    """
    # Empty roster slot (Sleeper uses "0" as placeholder)
    if player_id == "0":
        return 0.0

    profile = profiles.get(player_id)
    if not profile:
        return 0.0

    draw = rng.choice(profile)

    if dampening > 0 and len(profile) > 1:
        mean = sum(profile) / len(profile)
        draw = draw * (1 - dampening) + mean * dampening

    return round(draw, 2)


def simulate_week(week_entries, profiles, rng, dampening=0.0):
    """
    Simulate one week of matchups using resample variance.

    Args:
        week_entries: list of matchup entries for this week
        profiles: player score profiles
        rng: random.Random instance
        dampening: variance dampening factor (0.0 = full variance)

    Returns:
        list of dicts with: roster_id, matchup_id, real_points, sim_points,
        real_starters_points, sim_starters_points
    """
    results = []

    for entry in week_entries:
        roster_id = entry["roster_id"]
        matchup_id = entry["matchup_id"]
        starters = entry.get("starters", [])
        real_starter_pts = entry.get("starters_points", [])
        real_total = entry.get("points", 0)

        # Resample each starter's score
        sim_starter_pts = []
        for pid in starters:
            sim_pts = resample_score(pid, profiles, rng, dampening)
            sim_starter_pts.append(sim_pts)

        sim_total = round(sum(sim_starter_pts), 2)

        results.append({
            "roster_id": roster_id,
            "matchup_id": matchup_id,
            "real_points": real_total,
            "sim_points": sim_total,
            "starters": starters,
            "real_starters_points": real_starter_pts,
            "sim_starters_points": sim_starter_pts,
        })

    return results


def determine_outcomes(week_results):
    """
    Pair teams by matchup_id and determine W/L.
    Returns list of (winner_roster_id, loser_roster_id, winner_pts, loser_pts).
    """
    # Group by matchup_id
    by_matchup = defaultdict(list)
    for r in week_results:
        by_matchup[r["matchup_id"]].append(r)

    outcomes = []
    for mid, teams in by_matchup.items():
        if len(teams) != 2:
            continue  # Skip if not a proper 2-team matchup
        a, b = teams
        if a["sim_points"] > b["sim_points"]:
            outcomes.append((a["roster_id"], b["roster_id"],
                             a["sim_points"], b["sim_points"]))
        elif b["sim_points"] > a["sim_points"]:
            outcomes.append((b["roster_id"], a["roster_id"],
                             b["sim_points"], a["sim_points"]))
        else:
            # Tie — both get a tie
            outcomes.append((None, None, a["sim_points"], b["sim_points"],
                             a["roster_id"], b["roster_id"]))

    return outcomes


def simulate_season(data, reg_season_weeks=None, seed=None, dampening=0.0):
    """
    Run a full simulated season.

    Args:
        data: dict from load_league_season()
        reg_season_weeks: list of week numbers for regular season
                          (auto-detected from league settings if None)
        seed: random seed for reproducibility
        dampening: variance dampening 0.0-1.0 (0.0 = full resample variance,
                   higher values pull scores toward player means)

    Returns:
        dict with:
            standings: list of team records sorted by wins then points
            weekly_results: dict of week -> simulate_week output
            real_standings: the actual season standings for comparison
    """
    info = data["info"]
    matchups = data["matchups"]
    rosters = data["rosters"]
    users = data["users"]

    rng = random.Random(seed)

    # Determine regular season weeks
    if reg_season_weeks is None:
        playoff_start = info["settings"].get("playoff_week_start", 15)
        reg_season_weeks = list(range(1, playoff_start))

    # Build profiles from ALL available weeks (including playoffs for more data)
    all_available_weeks = [int(w) for w in matchups.keys()]
    profiles = build_player_profiles(matchups, all_available_weeks)

    # Track standings
    team_names = get_team_names(users, rosters)
    standings = {}
    for r in rosters:
        rid = r["roster_id"]
        standings[rid] = {
            "roster_id": rid,
            "name": team_names.get(rid, f"Team {rid}"),
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "points_for": 0.0,
            "points_against": 0.0,
        }

    # Build real standings from matchup data (not roster settings).
    # Roster settings store total-season wins including playoff rounds and
    # league_average_match virtual games, which inflates win counts for
    # some leagues. Deriving from matchups gives clean head-to-head records
    # for the regular season only.
    real_standings = {}
    for r in rosters:
        rid = r["roster_id"]
        real_standings[rid] = {
            "roster_id": rid,
            "name": team_names.get(rid, f"Team {rid}"),
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "points_for": 0.0,
            "points_against": 0.0,
        }

    for week in reg_season_weeks:
        week_str = str(week)
        if week_str not in matchups:
            continue
        by_mid = defaultdict(list)
        for entry in matchups[week_str]:
            by_mid[entry["matchup_id"]].append(entry)
        for mid, teams in by_mid.items():
            if len(teams) != 2:
                continue
            a, b = teams
            ra, rb = a["roster_id"], b["roster_id"]
            pa, pb = a.get("points", 0), b.get("points", 0)
            real_standings[ra]["points_for"] += pa
            real_standings[ra]["points_against"] += pb
            real_standings[rb]["points_for"] += pb
            real_standings[rb]["points_against"] += pa
            if pa > pb:
                real_standings[ra]["wins"] += 1
                real_standings[rb]["losses"] += 1
            elif pb > pa:
                real_standings[rb]["wins"] += 1
                real_standings[ra]["losses"] += 1
            else:
                real_standings[ra]["ties"] += 1
                real_standings[rb]["ties"] += 1

    # Simulate each regular season week
    weekly_results = {}
    for week in reg_season_weeks:
        week_str = str(week)
        if week_str not in matchups:
            continue

        week_entries = matchups[week_str]
        week_sim = simulate_week(week_entries, profiles, rng, dampening)
        weekly_results[week] = week_sim

        # Determine W/L
        outcomes = determine_outcomes(week_sim)
        for outcome in outcomes:
            if len(outcome) == 4:
                winner_id, loser_id, w_pts, l_pts = outcome
                standings[winner_id]["wins"] += 1
                standings[winner_id]["points_for"] += w_pts
                standings[winner_id]["points_against"] += l_pts
                standings[loser_id]["losses"] += 1
                standings[loser_id]["points_for"] += l_pts
                standings[loser_id]["points_against"] += w_pts
            else:
                # Tie
                _, _, pts_a, pts_b, rid_a, rid_b = outcome
                standings[rid_a]["ties"] += 1
                standings[rid_a]["points_for"] += pts_a
                standings[rid_a]["points_against"] += pts_b
                standings[rid_b]["ties"] += 1
                standings[rid_b]["points_for"] += pts_b
                standings[rid_b]["points_against"] += pts_a

    # Sort standings: wins desc, then points_for desc
    sorted_standings = sorted(
        standings.values(),
        key=lambda x: (x["wins"], x["points_for"]),
        reverse=True
    )

    sorted_real = sorted(
        real_standings.values(),
        key=lambda x: (x["wins"], x["points_for"]),
        reverse=True
    )

    return {
        "standings": sorted_standings,
        "real_standings": sorted_real,
        "weekly_results": weekly_results,
        "profiles": profiles,
        "team_names": team_names,
        "league_info": info,
    }


# ---------------------------------------------------------------------------
# Output Formatting
# ---------------------------------------------------------------------------

def format_standings_comparison(sim_result):
    """Format a side-by-side comparison of real vs simulated standings."""
    real = sim_result["real_standings"]
    sim = sim_result["standings"]
    info = sim_result["league_info"]
    playoff_teams = info["settings"].get("playoff_teams", 6)

    lines = []
    lines.append(f"{'='*78}")
    lines.append(f"  {info['name']} — {info['season']} Season Simulation")
    lines.append(f"{'='*78}")

    # Real standings
    lines.append(f"\n{'REAL SEASON':^38}  {'SIMULATED SEASON':^38}")
    lines.append(f"{'-'*38}  {'-'*38}")
    header = f"{'#':>2} {'Team':<20} {'W-L':>5} {'PF':>7}"
    lines.append(f"{header}  {header}")
    lines.append(f"{'-'*38}  {'-'*38}")

    for i in range(max(len(real), len(sim))):
        real_line = ""
        sim_line = ""

        if i < len(real):
            r = real[i]
            playoff_mark = "★" if i < playoff_teams else " "
            real_line = (f"{i+1:>2} {r['name']:<20} "
                        f"{r['wins']:>2}-{r['losses']:<2} {r['points_for']:>7.1f}")
            real_line = playoff_mark + real_line

        if i < len(sim):
            s = sim[i]
            playoff_mark = "★" if i < playoff_teams else " "
            sim_line = (f"{i+1:>2} {s['name']:<20} "
                       f"{s['wins']:>2}-{s['losses']:<2} {s['points_for']:>7.1f}")
            sim_line = playoff_mark + sim_line

        lines.append(f"{real_line:<39} {sim_line}")

    lines.append(f"\n★ = Playoff team (top {playoff_teams})")

    # Movement summary
    lines.append(f"\n{'STANDINGS MOVEMENT':^78}")
    lines.append(f"{'-'*78}")

    real_ranks = {r["roster_id"]: i + 1 for i, r in enumerate(real)}
    sim_ranks = {s["roster_id"]: i + 1 for i, s in enumerate(sim)}

    movements = []
    for rid in real_ranks:
        real_rank = real_ranks[rid]
        sim_rank = sim_ranks.get(rid, "?")
        name = sim_result["team_names"].get(rid, f"Team {rid}")
        diff = real_rank - sim_rank  # positive = moved up
        movements.append((rid, name, real_rank, sim_rank, diff))

    movements.sort(key=lambda x: -x[4])  # biggest movers first
    for rid, name, rr, sr, diff in movements:
        if diff > 0:
            arrow = f"▲ {diff}"
        elif diff < 0:
            arrow = f"▼ {abs(diff)}"
        else:
            arrow = "  —"
        lines.append(f"  {name:<25} Real: #{rr:<3} Sim: #{sr:<3} {arrow}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Multi-Sim Aggregation
# ---------------------------------------------------------------------------

def run_multi_sim(data, n_sims=100, dampening=0.2, base_seed=None):
    """
    Run N simulations and aggregate results.

    Returns a dict with:
        team_stats: per-team aggregated stats (avg wins, playoff %, etc.)
        real_standings: the actual season standings for comparison
        league_info: league metadata
        n_sims: number of simulations run
        flip_rates: list of flip percentages per sim
    """
    import time

    info = data["info"]
    rosters = data["rosters"]
    users = data["users"]
    team_names = get_team_names(users, rosters)
    playoff_teams = info["settings"].get("playoff_teams", 6)

    if base_seed is None:
        base_seed = int(time.time()) % 100000

    # Accumulators per roster_id
    accum = {}
    for r in rosters:
        rid = r["roster_id"]
        accum[rid] = {
            "roster_id": rid,
            "name": team_names.get(rid, f"Team {rid}"),
            "total_wins": 0,
            "total_losses": 0,
            "total_pf": 0.0,
            "playoff_count": 0,
            "first_place_count": 0,
            "last_place_count": 0,
            "win_counts": [],     # list of wins per sim
            "pf_totals": [],      # list of total PF per sim
            "rank_counts": [],    # list of final rank per sim
        }

    flip_rates = []

    for i in range(n_sims):
        seed = base_seed + i
        result = simulate_season(data, seed=seed, dampening=dampening)

        # Count flipped matchups for this sim
        total_matchups = 0
        flipped = 0
        for week, entries in result["weekly_results"].items():
            by_mid = defaultdict(list)
            for e in entries:
                by_mid[e["matchup_id"]].append(e)
            for mid, teams in by_mid.items():
                if len(teams) != 2:
                    continue
                total_matchups += 1
                a, b = teams
                real_w = a["roster_id"] if a["real_points"] > b["real_points"] else b["roster_id"]
                sim_w = a["roster_id"] if a["sim_points"] > b["sim_points"] else b["roster_id"]
                if real_w != sim_w:
                    flipped += 1
        if total_matchups > 0:
            flip_rates.append(flipped / total_matchups * 100)

        # Accumulate standings
        for rank, team in enumerate(result["standings"]):
            rid = team["roster_id"]
            wins = team["wins"]
            pf = team["points_for"]

            accum[rid]["total_wins"] += wins
            accum[rid]["total_losses"] += team["losses"]
            accum[rid]["total_pf"] += pf
            accum[rid]["win_counts"].append(wins)
            accum[rid]["pf_totals"].append(pf)
            accum[rid]["rank_counts"].append(rank + 1)

            if rank < playoff_teams:
                accum[rid]["playoff_count"] += 1
            if rank == 0:
                accum[rid]["first_place_count"] += 1
            if rank == len(result["standings"]) - 1:
                accum[rid]["last_place_count"] += 1

    # Compute final stats
    team_stats = []
    for rid, a in accum.items():
        avg_wins = a["total_wins"] / n_sims
        avg_pf = a["total_pf"] / n_sims
        playoff_pct = a["playoff_count"] / n_sims * 100
        first_pct = a["first_place_count"] / n_sims * 100
        last_pct = a["last_place_count"] / n_sims * 100
        avg_rank = sum(a["rank_counts"]) / n_sims
        win_min = min(a["win_counts"])
        win_max = max(a["win_counts"])

        team_stats.append({
            "roster_id": rid,
            "name": a["name"],
            "avg_wins": round(avg_wins, 1),
            "avg_losses": round(a["total_losses"] / n_sims, 1),
            "avg_pf": round(avg_pf, 1),
            "playoff_pct": round(playoff_pct, 1),
            "first_pct": round(first_pct, 1),
            "last_pct": round(last_pct, 1),
            "avg_rank": round(avg_rank, 1),
            "win_range": f"{win_min}-{win_max}",
            "win_counts": a["win_counts"],
        })

    # Sort by avg_wins desc, then avg_pf desc
    team_stats.sort(key=lambda x: (x["avg_wins"], x["avg_pf"]), reverse=True)

    # Build real standings from matchup data (same fix as simulate_season —
    # roster settings inflate wins for leagues with league_average_match)
    matchups = data["matchups"]
    playoff_start = info["settings"].get("playoff_week_start", 15)
    reg_season_weeks_multi = list(range(1, playoff_start))

    real_acc = {r["roster_id"]: {"wins": 0, "losses": 0, "ties": 0,
                                  "points_for": 0.0}
                for r in rosters}
    for week in reg_season_weeks_multi:
        week_str = str(week)
        if week_str not in matchups:
            continue
        by_mid = defaultdict(list)
        for entry in matchups[week_str]:
            by_mid[entry["matchup_id"]].append(entry)
        for mid, teams in by_mid.items():
            if len(teams) != 2:
                continue
            a, b = teams
            ra, rb = a["roster_id"], b["roster_id"]
            pa, pb = a.get("points", 0), b.get("points", 0)
            real_acc[ra]["points_for"] += pa
            real_acc[rb]["points_for"] += pb
            if pa > pb:
                real_acc[ra]["wins"] += 1
                real_acc[rb]["losses"] += 1
            elif pb > pa:
                real_acc[rb]["wins"] += 1
                real_acc[ra]["losses"] += 1
            else:
                real_acc[ra]["ties"] += 1
                real_acc[rb]["ties"] += 1

    real_standings = []
    for r in rosters:
        rid = r["roster_id"]
        real_standings.append({
            "roster_id": rid,
            "name": team_names.get(rid, f"Team {rid}"),
            "wins": real_acc[rid]["wins"],
            "losses": real_acc[rid]["losses"],
            "points_for": round(real_acc[rid]["points_for"], 2),
        })
    real_standings.sort(key=lambda x: (x["wins"], x["points_for"]), reverse=True)

    return {
        "team_stats": team_stats,
        "real_standings": real_standings,
        "league_info": info,
        "n_sims": n_sims,
        "flip_rates": flip_rates,
        "base_seed": base_seed,
        "dampening": dampening,
    }


def format_multi_sim_report(multi_result):
    """Format the multi-sim aggregation as a readable report."""
    info = multi_result["league_info"]
    stats = multi_result["team_stats"]
    real = multi_result["real_standings"]
    n = multi_result["n_sims"]
    playoff_count = info["settings"].get("playoff_teams", 6)
    flip_rates = multi_result["flip_rates"]

    lines = []
    lines.append(f"{'='*85}")
    lines.append(f"  {info['name']} — {info['season']} Multi-Sim Report ({n} simulations)")
    lines.append(f"{'='*85}")
    lines.append(f"  Dampening: {multi_result['dampening']}  |  "
                 f"Base seed: {multi_result['base_seed']}  |  "
                 f"Avg flip rate: {sum(flip_rates)/len(flip_rates):.1f}%")

    # Main table
    lines.append(f"\n{'SIMULATED AVERAGES':^85}")
    lines.append(f"{'-'*85}")
    lines.append(f"  {'Team':<25} {'Avg W-L':>8} {'Win Range':>10} {'Avg PF':>8} "
                 f"{'Playoff%':>9} {'#1%':>6} {'Last%':>6} {'Avg Rank':>9}")
    lines.append(f"{'-'*85}")

    for t in stats:
        lines.append(f"  {t['name']:<25} "
                     f"{t['avg_wins']:>4.1f}-{t['avg_losses']:<4.1f}"
                     f"{t['win_range']:>10} "
                     f"{t['avg_pf']:>8.1f} "
                     f"{t['playoff_pct']:>8.1f}% "
                     f"{t['first_pct']:>5.1f}% "
                     f"{t['last_pct']:>5.1f}% "
                     f"{t['avg_rank']:>8.1f}")

    # Comparison to reality
    lines.append(f"\n{'REALITY vs SIMULATION':^85}")
    lines.append(f"{'-'*85}")
    lines.append(f"  {'Team':<25} {'Real W':>7} {'Sim Avg W':>10} {'Diff':>6}  "
                 f"{'Real Rank':>10} {'Sim Avg Rank':>13}")
    lines.append(f"{'-'*85}")

    # Map real standings
    real_map = {r["roster_id"]: r for r in real}
    real_ranks = {r["roster_id"]: i + 1 for i, r in enumerate(real)}

    for t in stats:
        rid = t["roster_id"]
        r = real_map.get(rid, {})
        real_wins = r.get("wins", 0)
        diff = t["avg_wins"] - real_wins
        sign = "+" if diff > 0 else ""
        rr = real_ranks.get(rid, "?")
        lines.append(f"  {t['name']:<25} {real_wins:>7} {t['avg_wins']:>10.1f} "
                     f"{sign}{diff:>5.1f}  {rr:>10} {t['avg_rank']:>13.1f}")

    # Insights
    lines.append(f"\n{'KEY INSIGHTS':^85}")
    lines.append(f"{'-'*85}")

    # Who's most "lucky" (real wins >> sim avg) and "unlucky" (real wins << sim avg)
    luck = []
    for t in stats:
        r = real_map.get(t["roster_id"], {})
        real_wins = r.get("wins", 0)
        luck.append((t["name"], real_wins - t["avg_wins"], t["roster_id"]))
    luck.sort(key=lambda x: x[1], reverse=True)

    luckiest = luck[0]
    unluckiest = luck[-1]
    lines.append(f"  Luckiest team:   {luckiest[0]} "
                 f"(+{luckiest[1]:.1f} wins above sim average)")
    lines.append(f"  Unluckiest team: {unluckiest[0]} "
                 f"({unluckiest[1]:.1f} wins vs sim average)")

    # Biggest playoff swing
    for t in stats:
        r = real_map.get(t["roster_id"], {})
        rr = real_ranks.get(t["roster_id"], 99)
        if rr > playoff_count and t["playoff_pct"] > 50:
            lines.append(f"  Missed out:      {t['name']} made playoffs "
                         f"{t['playoff_pct']:.0f}% of sims but missed in reality")
        elif rr <= playoff_count and t["playoff_pct"] < 50:
            lines.append(f"  Got lucky:       {t['name']} made real playoffs "
                         f"but only qualifies {t['playoff_pct']:.0f}% of sims")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON Export
# ---------------------------------------------------------------------------

def export_player_profiles_json(sim_result, player_cache=None):
    """
    Export per-player sim profiles for the Phase 2 trading card view.

    Args:
        sim_result: result from simulate_season()
        player_cache: dict of player_id -> {first_name, last_name, position, team}
                      loaded from data/raw/players_cache.json. If None, names
                      will fall back to player IDs.

    Returns:
        dict of player_id -> profile dict with name, position, sim stats,
        keyed by roster_id for easy lineup rendering.
    """
    profiles = sim_result["profiles"]          # player_id -> [weekly scores]
    team_names = sim_result["team_names"]
    info = sim_result["league_info"]

    # Build per-roster starter sets from weekly results
    # (which players appeared as starters for each team across the season)
    roster_starters = defaultdict(set)
    roster_starter_order = defaultdict(list)  # preserves slot order for layout
    for week, entries in sim_result["weekly_results"].items():
        for entry in entries:
            rid = entry["roster_id"]
            starters = entry.get("starters", [])
            for pid in starters:
                if pid and pid != "0":
                    roster_starters[rid].add(pid)
                    if pid not in roster_starter_order[rid]:
                        roster_starter_order[rid].append(pid)

    # Build player stats
    def player_stats(pid):
        scores = profiles.get(pid, [])
        if not scores:
            return {"avg": 0, "min": 0, "max": 0, "std": 0, "games": 0}
        avg = sum(scores) / len(scores)
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)
        std = variance ** 0.5
        return {
            "avg": round(avg, 1),
            "min": round(min(scores), 1),
            "max": round(max(scores), 1),
            "std": round(std, 1),
            "games": len(scores),
        }

    def consistency_grade(std, avg):
        """Return A-F grade based on coefficient of variation."""
        if avg == 0:
            return "N/A"
        cv = std / avg  # coefficient of variation — lower = more consistent
        if cv < 0.25:
            return "A"
        elif cv < 0.40:
            return "B"
        elif cv < 0.55:
            return "C"
        elif cv < 0.70:
            return "D"
        return "F"

    def lookup_player(pid):
        if player_cache and pid in player_cache:
            p = player_cache[pid]
            return {
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "position": p.get("position", "?"),
                "team": p.get("team", "?"),
            }
        # Fallback: defense check
        if pid.isalpha():
            return {"name": f"{pid} D/ST", "position": "DEF", "team": pid}
        return {"name": f"Player #{pid}", "position": "?", "team": "?"}

    # Assemble per-roster card data
    rosters_out = {}
    for rid, pid_order in roster_starter_order.items():
        cards = []
        for pid in pid_order:
            stats = player_stats(pid)
            info_p = lookup_player(pid)
            cards.append({
                "player_id": pid,
                "name": info_p["name"],
                "position": info_p["position"],
                "team": info_p["team"],
                "avg_score": stats["avg"],
                "min_score": stats["min"],
                "max_score": stats["max"],
                "std_dev": stats["std"],
                "games_played": stats["games"],
                "consistency_grade": consistency_grade(stats["std"], stats["avg"]),
            })
        rosters_out[rid] = {
            "roster_id": rid,
            "team_name": team_names.get(rid, f"Team {rid}"),
            "players": cards,
        }

    return {
        "type": "player_profiles",
        "league": {"name": info["name"], "season": info["season"],
                   "league_id": info["league_id"]},
        "rosters": rosters_out,
    }


def export_single_sim_json(sim_result):
    """
    Export a single sim result as a JSON-serializable dict.
    Includes per-player starter scores for the supersim playback view.
    """
    info = sim_result["league_info"]

    # Clean weekly results — include per-player scores for supersim
    clean_weekly = {}
    for week, entries in sim_result["weekly_results"].items():
        week_matchups = []
        by_mid = defaultdict(list)
        for e in entries:
            by_mid[e["matchup_id"]].append(e)
        for mid in sorted(by_mid):
            teams = by_mid[mid]
            if len(teams) != 2:
                continue
            a, b = teams
            na = sim_result["team_names"].get(a["roster_id"], f"Team {a['roster_id']}")
            nb = sim_result["team_names"].get(b["roster_id"], f"Team {b['roster_id']}")
            real_winner = a["roster_id"] if a["real_points"] > b["real_points"] else b["roster_id"]
            sim_winner = a["roster_id"] if a["sim_points"] > b["sim_points"] else b["roster_id"]
            week_matchups.append({
                "matchup_id": mid,
                "teams": [
                    {
                        "roster_id": a["roster_id"],
                        "name": na,
                        "real_points": a["real_points"],
                        "sim_points": a["sim_points"],
                        "starters": a.get("starters", []),
                        "real_starters_points": a.get("real_starters_points", []),
                        "sim_starters_points": a.get("sim_starters_points", []),
                    },
                    {
                        "roster_id": b["roster_id"],
                        "name": nb,
                        "real_points": b["real_points"],
                        "sim_points": b["sim_points"],
                        "starters": b.get("starters", []),
                        "real_starters_points": b.get("real_starters_points", []),
                        "sim_starters_points": b.get("sim_starters_points", []),
                    },
                ],
                "real_winner": real_winner,
                "sim_winner": sim_winner,
                "flipped": real_winner != sim_winner,
            })
        clean_weekly[week] = week_matchups

    return {
        "type": "single_sim",
        "league": {"name": info["name"], "season": info["season"],
                    "league_id": info["league_id"], "teams": info["total_rosters"]},
        "seed": sim_result.get("seed"),
        "standings": sim_result["standings"],
        "real_standings": sim_result["real_standings"],
        "weekly_results": clean_weekly,
    }


def export_multi_sim_json(multi_result):
    """
    Export multi-sim results as a JSON-serializable dict.
    Includes win_counts arrays for histogram visualization in Phase 2 dashboard.
    """
    info = multi_result["league_info"]

    return {
        "type": "multi_sim",
        "league": {"name": info["name"], "season": info["season"],
                    "league_id": info["league_id"], "teams": info["total_rosters"]},
        "config": {
            "n_sims": multi_result["n_sims"],
            "dampening": multi_result["dampening"],
            "base_seed": multi_result["base_seed"],
            "avg_flip_rate": round(sum(multi_result["flip_rates"]) /
                                   len(multi_result["flip_rates"]), 1),
        },
        "team_stats": multi_result["team_stats"],   # includes win_counts for histogram
        "real_standings": multi_result["real_standings"],
    }


def format_weekly_detail(sim_result, week):
    """Format detailed results for a specific week."""
    info = sim_result["league_info"]
    team_names = sim_result["team_names"]
    weekly = sim_result["weekly_results"].get(week, [])

    if not weekly:
        return f"No data for week {week}"

    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  Week {week} — Matchup Results")
    lines.append(f"{'='*60}")

    # Group by matchup_id
    by_matchup = defaultdict(list)
    for r in weekly:
        by_matchup[r["matchup_id"]].append(r)

    for mid in sorted(by_matchup):
        teams = by_matchup[mid]
        if len(teams) != 2:
            continue
        a, b = teams
        na = team_names.get(a["roster_id"], f"Team {a['roster_id']}")
        nb = team_names.get(b["roster_id"], f"Team {b['roster_id']}")

        # Determine sim winner
        if a["sim_points"] > b["sim_points"]:
            wa, wb = "W", "L"
        elif b["sim_points"] > a["sim_points"]:
            wa, wb = "L", "W"
        else:
            wa, wb = "T", "T"

        # Also show real outcome
        if a["real_points"] > b["real_points"]:
            rwa, rwb = "W", "L"
        elif b["real_points"] > a["real_points"]:
            rwa, rwb = "L", "W"
        else:
            rwa, rwb = "T", "T"

        flipped = (wa != rwa)
        flip_mark = " ← FLIPPED" if flipped else ""

        lines.append(f"\n  Matchup {mid}:{flip_mark}")
        lines.append(f"    {na:<25} Real: {a['real_points']:>7.2f} ({rwa})  "
                     f"Sim: {a['sim_points']:>7.2f} ({wa})")
        lines.append(f"    {nb:<25} Real: {b['real_points']:>7.2f} ({rwb})  "
                     f"Sim: {b['sim_points']:>7.2f} ({wb})")

    return "\n".join(lines)
