"""
BitCaps — Run a simulated alternate season.
Usage:
  Single sim:    python3 run_sim.py --seed 42
  Multi-sim:     python3 run_sim.py --multi 500
  JSON export:   python3 run_sim.py --multi 500 --json
  Full detail:   python3 run_sim.py --seed 42 --all-weeks
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict

from sim_engine import (
    load_league_season,
    simulate_season,
    run_multi_sim,
    format_standings_comparison,
    format_multi_sim_report,
    format_weekly_detail,
    export_single_sim_json,
    export_multi_sim_json,
)


def main():
    parser = argparse.ArgumentParser(description="BitCaps Season Simulator")
    parser.add_argument("--league", default="league1",
                        help="League tag (league1 or league2)")
    parser.add_argument("--season", default="2025",
                        help="Season year")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility (single sim mode)")
    parser.add_argument("--dampening", type=float, default=0.2,
                        help="Variance dampening 0.0-1.0 (default: 0.2)")
    parser.add_argument("--multi", type=int, default=None,
                        help="Run N simulations and show aggregate stats")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="Export results as JSON to data/output/")
    parser.add_argument("--detail-week", type=int, default=None,
                        help="Show detailed results for a specific week")
    parser.add_argument("--all-weeks", action="store_true",
                        help="Show detailed results for all weeks")
    args = parser.parse_args()

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "raw")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "output")

    print(f"Loading {args.league} season {args.season}...")
    try:
        data = load_league_season(data_dir, args.league, args.season)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print(f"\nAvailable files in {data_dir}:")
        for f in sorted(os.listdir(data_dir)):
            if f.endswith("_info.json"):
                print(f"  {f}")
        sys.exit(1)

    # --- Multi-sim mode ---
    if args.multi:
        n = args.multi
        base_seed = args.seed if args.seed is not None else int(time.time()) % 100000
        print(f"Running {n} simulations (dampening={args.dampening}, "
              f"base_seed={base_seed})...")

        t0 = time.time()
        result = run_multi_sim(data, n_sims=n, dampening=args.dampening,
                               base_seed=base_seed)
        elapsed = time.time() - t0

        print(format_multi_sim_report(result))
        print(f"\n  Completed in {elapsed:.1f}s "
              f"({elapsed/n*1000:.0f}ms per sim)")

        if args.json_out:
            os.makedirs(out_dir, exist_ok=True)
            fname = f"{args.league}_s{args.season}_multi{n}.json"
            fpath = os.path.join(out_dir, fname)
            with open(fpath, "w") as f:
                json.dump(export_multi_sim_json(result), f, indent=2)
            print(f"\n  JSON exported to {fpath}")
        return

    # --- Single sim mode ---
    seed = args.seed
    if seed is None:
        seed = int(time.time()) % 100000
    print(f"Running simulation (seed={seed}, dampening={args.dampening})...")

    result = simulate_season(data, seed=seed, dampening=args.dampening)

    print(format_standings_comparison(result))

    if args.detail_week:
        print(format_weekly_detail(result, args.detail_week))
    elif args.all_weeks:
        weeks = sorted(result["weekly_results"].keys())
        for w in weeks:
            print(format_weekly_detail(result, w))

    # Summary stats
    total_matchups = 0
    flipped_matchups = 0
    for week, entries in result["weekly_results"].items():
        by_mid = defaultdict(list)
        for e in entries:
            by_mid[e["matchup_id"]].append(e)
        for mid, teams in by_mid.items():
            if len(teams) != 2:
                continue
            total_matchups += 1
            a, b = teams
            real_winner = a["roster_id"] if a["real_points"] > b["real_points"] else b["roster_id"]
            sim_winner = a["roster_id"] if a["sim_points"] > b["sim_points"] else b["roster_id"]
            if real_winner != sim_winner:
                flipped_matchups += 1

    print(f"\n{'='*78}")
    print(f"  SIMULATION SUMMARY")
    print(f"{'='*78}")
    print(f"  Total regular season matchups: {total_matchups}")
    print(f"  Matchups with different winner: {flipped_matchups} "
          f"({flipped_matchups/total_matchups*100:.0f}%)")
    print(f"  Dampening: {args.dampening}")
    print(f"  Seed: {seed} (use --seed {seed} to reproduce this exact sim)")

    if args.json_out:
        os.makedirs(out_dir, exist_ok=True)
        fname = f"{args.league}_s{args.season}_seed{seed}.json"
        fpath = os.path.join(out_dir, fname)
        with open(fpath, "w") as f:
            json.dump(export_single_sim_json(result), f, indent=2)
        print(f"\n  JSON exported to {fpath}")


if __name__ == "__main__":
    main()
