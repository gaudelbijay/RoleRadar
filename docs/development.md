# Development Guide

[Documentation index](document.md)

Live job functionality is in `core/jobs.py`. Add a source by implementing an
adapter that returns the normalized dictionary produced by `_job()`, then add
it to the source list in `search_jobs()`.

Test adapters with mocked HTTP responses. Test HTML cleanup, deduplication,
exact-token matching, multi-term relevance thresholds, requirement extraction,
malformed feeds, source timeouts, report links, and dashboard escaping.

Respect every feed's attribution, caching, and rate-limit requirements. Never
store user credentials or bypass authenticated job-platform access controls.
