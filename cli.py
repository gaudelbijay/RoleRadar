"""
CLI runner — test the multi-agent pipeline without any UI.

Usage:
    python cli.py --country "United States" --city Boston "robotics PhD"
"""

import argparse

from agents.coordinator import Coordinator

DEFAULT_QUERY = "AI PhD robotics research scientist"


def main() -> None:
    parser = argparse.ArgumentParser(description="Strict live job search")
    parser.add_argument("query", nargs="*", help="Job keywords")
    parser.add_argument("--country", required=True, help="Required country filter")
    parser.add_argument("--city", default="", help="Optional city filter")
    parser.add_argument("--max-age", type=int, default=10, choices=range(1, 31),
                        metavar="DAYS", help="Maximum posting age (1-30)")
    args = parser.parse_args()
    query = " ".join(args.query) or DEFAULT_QUERY
    print(f"Query: {query} | Country: {args.country} | City: {args.city or 'Any'}")
    print("=" * 70)
    result = Coordinator(log=print).run(
        query, args.country, args.city, args.max_age
    )
    print("=" * 70)
    print(result["report"])


if __name__ == "__main__":
    main()
