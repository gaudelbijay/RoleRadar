"""
CLI runner — test the multi-agent pipeline without any UI.

Usage:
    python cli.py "your research query"
    python cli.py            # uses a default example query
"""

import sys

from agents.coordinator import Coordinator

DEFAULT_QUERY = ("Research silicon-based semiconductor companies: 5-year "
                 "performance, key collaborations, risks, and how they compare")


def main() -> None:
    query = " ".join(sys.argv[1:]) or DEFAULT_QUERY
    print(f"Query: {query}\n" + "=" * 70)
    result = Coordinator(log=print).run(query)
    print("=" * 70)
    print(result["report"])


if __name__ == "__main__":
    main()
