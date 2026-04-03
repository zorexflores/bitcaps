#!/bin/bash
# BitCaps — Data Refresh
# Run this any time rosters change (trades, FA adds, lineup changes).
# Pulls fresh Sleeper data, regenerates site JSON, and deploys to Netlify via git push.

set -e  # stop on any error

cd "$(dirname "$0")"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BitCaps — Data Refresh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Pull fresh data from Sleeper API
echo "① Pulling Sleeper data..."
python3 pull_league_data.py
echo ""

# 2. Regenerate site JSON
echo "② Regenerating site data..."
python3 generate_site_data.py
echo ""

# 3. Commit and push — Netlify auto-deploys on push
echo "③ Deploying..."
git add site/data/
git commit -m "data refresh — $(date '+%Y-%m-%d %H:%M')"
git push

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Done. Netlify will redeploy in ~30s."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
