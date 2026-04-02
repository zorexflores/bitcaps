"""
BitCaps — Generate Site Data for Phase 2 Visual Layer
Run this locally after pull_league_data.py to produce all JSON files the site needs.

Usage:
    python3 generate_site_data.py
    python3 generate_site_data.py --league league1 --season 2025
    python3 generate_site_data.py --sims 500 --seeds 5 10 42 99 777

Outputs to: site/data/
"""

import argparse
import json
import os
import sys

from sim_engine import (
    load_league_season,
    simulate_season,
    run_multi_sim,
    export_single_sim_json,
    export_multi_sim_json,
    export_player_profiles_json,
)

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")
SITE_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site", "data")

# Leagues to generate data for
LEAGUES = [
    ("league1", "2025"),
    ("league2", "2025"),
]

# Default seeds for pre-baked single sims (supersim view)
DEFAULT_SEEDS = [1, 42, 100, 500, 999]

# Default multi-sim count
DEFAULT_N_SIMS = 500


def load_player_cache():
    path = os.path.join(RAW_DIR, "players_cache.json")
    if not os.path.exists(path):
        print("⚠️  players_cache.json not found — run pull_league_data.py first")
        print("   Player names will fall back to IDs on cards")
        return None
    with open(path) as f:
        return json.load(f)


def save(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    size_kb = os.path.getsize(path) / 1024
    print(f"  ✅ {os.path.relpath(path)} ({size_kb:.0f} KB)")


def generate_league(tag, season, seeds, n_sims, player_cache):
    print(f"\n{'='*60}")
    print(f"  {tag} — {season} season")
    print(f"{'='*60}")

    data = load_league_season(RAW_DIR, tag, season)
    league_dir = os.path.join(SITE_DATA_DIR, f"{tag}_{season}")

    # --- Player profiles (trading cards) ---
    # Run one sim to build profiles, then export card data
    print("\n  Building player profiles...")
    base_sim = simulate_season(data, seed=42, dampening=0.2)
    profiles_out = export_player_profiles_json(base_sim, player_cache)

    # Inject Sleeper avatar IDs so the site can show owner profile pictures
    owner_avatar = {
        u["user_id"]: u.get("avatar")
        for u in (data.get("users") or [])
        if u.get("user_id")
    }
    roster_owner = {
        r["roster_id"]: r.get("owner_id")
        for r in (data.get("rosters") or [])
    }
    for roster in profiles_out["rosters"].values():
        oid = roster_owner.get(roster["roster_id"])
        roster["avatar_id"] = owner_avatar.get(oid)  # None if no avatar set

    save(profiles_out, os.path.join(league_dir, "player_profiles.json"))

    # --- Single sims (supersim playback) ---
    print(f"\n  Running {len(seeds)} single sims...")
    single_sims = []
    for seed in seeds:
        result = simulate_season(data, seed=seed, dampening=0.2)
        result["seed"] = seed  # attach for export
        exported = export_single_sim_json(result)
        save(exported, os.path.join(league_dir, f"sim_seed{seed}.json"))
        single_sims.append({
            "seed": seed,
            "file": f"sim_seed{seed}.json",
            "label": f"Alternate Season #{seeds.index(seed) + 1} (seed {seed})",
        })

    # --- Multi-sim (dashboard) ---
    print(f"\n  Running {n_sims}-sim aggregate...")
    multi = run_multi_sim(data, n_sims=n_sims, dampening=0.2, base_seed=42)
    multi_out = export_multi_sim_json(multi)
    save(multi_out, os.path.join(league_dir, "multi_sim.json"))

    # --- League manifest (index for the site) ---
    manifest = {
        "tag": tag,
        "season": season,
        "league_name": data["info"]["name"],
        "teams": data["info"]["total_rosters"],
        "playoff_teams": data["info"]["settings"].get("playoff_teams", 6),
        "single_sims": single_sims,
        "multi_sim_file": "multi_sim.json",
        "player_profiles_file": "player_profiles.json",
    }
    save(manifest, os.path.join(league_dir, "manifest.json"))

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Generate BitCaps site data")
    parser.add_argument("--league", default=None, help="Single league tag to generate")
    parser.add_argument("--season", default="2025", help="Season year")
    parser.add_argument("--sims", type=int, default=DEFAULT_N_SIMS,
                        help=f"Number of sims for multi-sim (default: {DEFAULT_N_SIMS})")
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS,
                        help=f"Seeds for single-sim exports (default: {DEFAULT_SEEDS})")
    args = parser.parse_args()

    print("BitCaps — Site Data Generator")
    print(f"Output directory: {SITE_DATA_DIR}")

    player_cache = load_player_cache()

    leagues_to_run = LEAGUES
    if args.league:
        leagues_to_run = [(args.league, args.season)]

    all_manifests = []
    for tag, season in leagues_to_run:
        try:
            manifest = generate_league(tag, season, args.seeds, args.sims, player_cache)
            all_manifests.append(manifest)
        except FileNotFoundError as e:
            print(f"\n  ❌ Skipping {tag}/{season}: {e}")

    # Write top-level index for site to discover available leagues
    index = {"leagues": all_manifests}
    save(index, os.path.join(SITE_DATA_DIR, "index.json"))

    print(f"\n✅ Done. Site data ready in site/data/")
    print("Next: open site/index.html in a browser, or deploy site/ to Netlify.")


if __name__ == "__main__":
    main()
