#!/usr/bin/env python3
"""CLI procedure to rescrape and update all Merit Badge requirement JSON files in data/merit_badge_requirements/."""

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tools.requirements_scraper import scrape_all_merit_badges_to_directory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rescrape all Merit Badge requirements from scouting.org into data/merit_badge_requirements/<slug>.json"
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore cached HTML in /tmp/scouting_mb_html_cache and re-fetch every page live from scouting.org.",
    )
    args = parser.parse_args()

    print("Starting full Merit Badge requirements scrape from https://www.scouting.org/skills/merit-badges/all/ ...")
    summary = scrape_all_merit_badges_to_directory(use_disk_cache=not args.fresh)
    print(f"Completed! Total Merit Badges written: {summary['total_badges']}")
    print(f"  Eagle-Required Badges: {summary['eagle_required_count']}")
    print(f"  Direct scouting.org requirements extracted: {summary['direct_scouting_org_count']}")
    print(f"  Recovered from scouting.org CDN 'Under maintenance' via ?v=2 cache-bust: {len(summary['cache_bust_recovered_slugs'])}")
    print(f"  Missing on scouting.org (fallback used): {summary['missing_on_scouting_org']}")


if __name__ == "__main__":
    main()
