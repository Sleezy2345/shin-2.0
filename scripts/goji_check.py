import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goji.sportsgameodds import SportsGameOddsClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Goji foundation smoke check")
    parser.add_argument("--sgo", action="store_true", help="Query a small SportsGameOdds MLB sample")
    args = parser.parse_args()

    if not args.sgo:
        print("Goji import/configuration smoke check OK")
        return 0

    events = SportsGameOddsClient().events("MLB", odds_available=True, limit=5)
    print(f"SportsGameOdds connection successful. Events received: {len(events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
