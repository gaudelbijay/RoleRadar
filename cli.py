"""
CLI runner — test the multi-agent pipeline without any UI.

Usage:
    python cli.py --country "United States" --city Boston "robotics PhD"
"""

import argparse

from agents.coordinator import Coordinator
from core.jobs import EDUCATION_LEVELS

DEFAULT_QUERY = "AI robotics research scientist"


def main() -> None:
    parser = argparse.ArgumentParser(description="Strict live job search")
    parser.add_argument("query", nargs="*", help="Job keywords")
    parser.add_argument("--country", required=True, help="Required country filter")
    parser.add_argument("--city", default="", help="Optional city filter")
    parser.add_argument("--max-age", type=int, default=10, choices=range(1, 31),
                        metavar="DAYS", help="Maximum posting age (1-30)")
    parser.add_argument("--education", choices=EDUCATION_LEVELS, default="PhD",
                        help="Required education evidence (default: PhD)")
    parser.add_argument("--minimum-salary", type=int, default=100_000,
                        help="Minimum disclosed annualized salary (default: 100000; 0 disables)")
    args = parser.parse_args()
    query = " ".join(args.query) or DEFAULT_QUERY
    print(f"Query: {query} | Country: {args.country} | City: {args.city or 'Any'}")
    print("=" * 70)
    result = Coordinator(log=print).run(
        query, args.country, args.city, args.max_age, args.education, args.minimum_salary
    )
    print("=" * 70)
    print(result["report"])


if __name__ == "__main__":
    main()
