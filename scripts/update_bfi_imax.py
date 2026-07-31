#!/usr/bin/env python3
"""
Generate data/bfi_imax_screenings.json.

BFI IMAX is behind Cloudflare, which blocks GitHub Actions runners but not a
residential connection. So it is not part of the daily Action like the other
venues - this script runs locally (cron/launchd) and commits its own file,
which api/index.py merges into the listings.

Usage:
    python scripts/update_bfi_imax.py            # write the file
    python scripts/update_bfi_imax.py --commit   # also commit and push it

Exit codes:
    0  wrote the file
    1  scrape failed (file left untouched)
"""

import argparse
import asyncio
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.bfi_imax import BFIImaxScraper  # noqa: E402

REPO = Path(__file__).parent.parent
OUTPUT = REPO / 'data' / 'bfi_imax_screenings.json'


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14, help="days ahead to scrape")
    ap.add_argument("--commit", action="store_true", help="commit and push the result")
    args = ap.parse_args()

    print(f"Scraping BFI IMAX ({args.days} days ahead)...")
    try:
        screenings = await BFIImaxScraper().scrape(days_ahead=args.days)
    except Exception as exc:
        # Leave the previous file in place rather than blanking the listings
        # because one run got blocked.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output = []
    for s in screenings:
        d = asdict(s)
        d['start_time'] = s.start_time.isoformat()
        d['scraped_at'] = s.scraped_at.isoformat()
        if s.end_time:
            d['end_time'] = s.end_time.isoformat()
        output.append(d)
    output.sort(key=lambda x: x['start_time'])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "screenings": output,
        "generated_at": datetime.now().isoformat(),
        "total_screenings": len(output),
    }, indent=2))

    print(f"Wrote {len(output)} screenings to {OUTPUT.relative_to(REPO)}")

    if args.commit:
        git("add", str(OUTPUT.relative_to(REPO)))
        if not git("diff", "--staged", "--quiet").returncode:
            print("No changes to commit")
            return 0
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        git("commit", "-m", f"Update BFI IMAX screenings {stamp}")
        # Rebase first: the daily Action commits to the same branch.
        git("fetch", "origin")
        rebase = git("rebase", "origin/main")
        if rebase.returncode:
            git("rebase", "--abort")
            print("ERROR: rebase failed, not pushing", file=sys.stderr)
            return 1
        push = git("push", "origin", "main")
        if push.returncode:
            print(f"ERROR: push failed: {push.stderr}", file=sys.stderr)
            return 1
        print("Committed and pushed")

    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
