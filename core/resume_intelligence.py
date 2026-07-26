"""Parallel, evidence-based resume and public-link intelligence."""
from __future__ import annotations

import contextlib
import hashlib
import html
import ipaddress
import json
import os
import re
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib import error, parse, request

from core.skill_taxonomy import (
    DOMAIN_ALIASES as BROAD_DOMAIN_ALIASES,
    ROLE_PATTERNS as BROAD_ROLE_PATTERNS,
    SKILL_ALIASES as BROAD_SKILL_ALIASES,
    SKILL_CATEGORY,
)

USER_AGENT = "jobSearch-resume-intelligence/1.0"
MAX_LINKS = 8
MAX_PAGE_BYTES = 500_000
MAX_PAGE_TEXT = 20_000

SKILL_ALIASES = BROAD_SKILL_ALIASES
DOMAIN_ALIASES = BROAD_DOMAIN_ALIASES
ROLE_PATTERNS = BROAD_ROLE_PATTERNS


def _contains(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase.lower())}(?![a-z0-9])", text.lower()))


def _extract_named(text: str, aliases: dict[str, set[str]]) -> list[str]:
    return sorted(name for name, terms in aliases.items() if any(_contains(text, term) for term in terms))


def categorize_skills(skills: list[str]) -> dict[str, list[str]]:
    grouped = {}
    for skill in skills:
        category = SKILL_CATEGORY.get(skill, "Other")
        grouped.setdefault(category, []).append(skill)
    return {category: sorted(values) for category, values in sorted(grouped.items())}


def extract_urls(text: str) -> list[str]:
    found = re.findall(r"https?://[^\s<>\]\[(){}\"]+", text, flags=re.I)
    bare = re.findall(
        r"(?<![@\w/])(?:www\.)?(?:github\.com/[^\s<>\]\[(){}\"]+|linkedin\.com/in/[^\s<>\]\[(){}\"]+)",
        text, flags=re.I)
    found.extend("https://" + value for value in bare)
    urls = []
    for raw in found:
        url = raw.rstrip(".,;:!?\")'")
        parts = parse.urlsplit(url)
        if parts.scheme.lower() in {"http", "https"} and parts.hostname:
            normalized = parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))
            if normalized not in urls:
                urls.append(normalized)
    return urls[:MAX_LINKS]



def _resume_agent(text: str) -> dict:
    education = []
    for label, terms in {
        "PhD": {"phd", "ph.d", "doctorate", "doctoral"},
        "Master's": {"master's", "masters", "m.s.", "msc"},
        "Bachelor's": {"bachelor's", "bachelors", "b.s.", "bsc"},
    }.items():
        if any(_contains(text, term) for term in terms):
            education.append(label)
    years = sorted(set(re.findall(r"\b(?:[1-9]|[1-4][0-9])\+?\s+years?\b", text, flags=re.I)))[:6]
    roles = [role for role in ROLE_PATTERNS if _contains(text, role)]
    return {
        "skills": _extract_named(text, SKILL_ALIASES),
        "domains": _extract_named(f" {text} ", DOMAIN_ALIASES),
        "role_terms": roles,
        "education": education,
        "experience_signals": years,
    }


def _github_target(url: str) -> tuple[str, str | None] | None:
    parts = parse.urlsplit(url)
    if (parts.hostname or "").lower() not in {"github.com", "www.github.com"}:
        return None
    path = [parse.unquote(x) for x in parts.path.split("/") if x]
    if not path or path[0].lower() in {"features", "topics", "collections", "marketplace", "login", "settings", "orgs"}:
        return None
    return path[0], path[1] if len(path) > 1 else None


def _github_json(url: str) -> object:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=8) as response:
        return json.loads(response.read(MAX_PAGE_BYTES).decode("utf-8"))


def _normalize_public_link(value: object) -> str:
    """Normalize a website URL exposed by GitHub without fetching it."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parts = parse.urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return ""
    return parse.urlunsplit((parts.scheme.lower(), parts.netloc, parts.path or "", "", ""))


def _github_agent(url: str) -> dict:
    target = _github_target(url)
    if not target:
        return {"url": url, "kind": "github", "status": "skipped", "text": ""}
    username, repository = target
    try:
        profile = _github_json(f"https://api.github.com/users/{parse.quote(username)}")
        repos = _github_json(f"https://api.github.com/users/{parse.quote(username)}/repos?per_page=30&sort=updated")
        if not isinstance(profile, dict) or not isinstance(repos, list):
            raise ValueError("Unexpected GitHub response")
        selected = [r for r in repos if isinstance(r, dict) and not r.get("fork")]
        if repository:
            selected.sort(key=lambda r: r.get("name", "").lower() != repository.lower())
        selected = selected[:20]
        chunks = [str(profile.get(k) or "") for k in ("name", "bio", "company", "location")]
        languages, topics = [], []
        discovered_urls = []
        profile_website = _normalize_public_link(profile.get("blog"))
        if profile_website:
            discovered_urls.append(profile_website)
        for repo in selected:
            chunks.extend([str(repo.get("name") or ""), str(repo.get("description") or "")])
            if repo.get("language"):
                languages.append(str(repo["language"]))
            topics.extend(str(x) for x in (repo.get("topics") or []))
            homepage = _normalize_public_link(repo.get("homepage"))
            if homepage and homepage not in discovered_urls:
                discovered_urls.append(homepage)
        text = " ".join(chunks + languages + topics)
        return {"url": url, "kind": "github", "status": "analyzed", "text": text[:MAX_PAGE_TEXT],
                "summary": f"GitHub @{username}: {len(selected)} public non-fork repositories analyzed",
                "languages": sorted(set(languages))[:12], "topics": sorted(set(topics))[:20],
                "discovered_urls": discovered_urls[:6]}
    except (error.HTTPError, error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return {"url": url, "kind": "github", "status": "error", "text": "",
                "summary": f"GitHub data unavailable: {type(exc).__name__}"}


def _bare_host(netloc: str) -> str:
    """Strip a trailing :port from a URL netloc while preserving original case.

    Must match exactly what http.client hands to socket.getaddrinfo when it
    actually connects, so the DNS pin below lands on the right key.
    """
    if netloc.startswith("["):
        end = netloc.find("]")
        return netloc[:end + 1] if end != -1 else netloc
    return netloc.rsplit(":", 1)[0] if ":" in netloc else netloc


_real_getaddrinfo = socket.getaddrinfo
_dns_pins = threading.local()


def _pin_stack() -> list[dict]:
    stack = getattr(_dns_pins, "stack", None)
    if stack is None:
        stack = []
        _dns_pins.stack = stack
    return stack


def _pinned_getaddrinfo(host, port, *args, **kwargs):
    for pins in reversed(_pin_stack()):
        resolved_ip = pins.get((host, port))
        if resolved_ip is not None:
            return _real_getaddrinfo(resolved_ip, port, *args, **kwargs)
    return _real_getaddrinfo(host, port, *args, **kwargs)


# Every socket connection in this process resolves through this wrapper so a
# pin set below is actually honored; hosts with no active pin behave exactly
# as before.
socket.getaddrinfo = _pinned_getaddrinfo


@contextlib.contextmanager
def _pinned_dns_scope(host: str, port: int, resolved_ip: str | None):
    """Bind host:port to one already-validated address for this thread only.

    `_validate_public_url` resolves and checks a hostname once; without this,
    the connection made moments later re-resolves the same hostname on its
    own, and a DNS-rebinding attacker could serve a public address for the
    check and a private one for the real connection. Pinning closes that
    window. Scoped to a stack so redirects (see `_SafeRedirect`) can add
    further pins that are all released together when the fetch finishes.
    """
    stack = _pin_stack()
    stack.append({})
    if resolved_ip:
        stack[-1][(host, port)] = resolved_ip
    try:
        yield
    finally:
        stack.pop()


def _validate_public_url(url: str) -> str | None:
    """Validate a public URL and return the single IP it should be pinned to."""
    parts = parse.urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Unsupported URL")
    if parts.port not in {None, 80, 443}:
        raise ValueError("Non-standard ports are blocked")
    hostname = parts.hostname.rstrip(".").lower()
    if hostname in {"localhost"} or hostname.endswith((".local", ".internal", ".localhost")):
        raise ValueError("Private hosts are blocked")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    # Resolve through the real resolver so validation isn't fooled by a pin
    # left over from an unrelated in-flight fetch on this thread.
    addresses = _real_getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    resolved_ip = None
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if not ip.is_global:
            raise ValueError("Private or non-global network addresses are blocked")
        if resolved_ip is None:
            resolved_ip = item[4][0]
    return resolved_ip


class _SafeRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        resolved_ip = _validate_public_url(newurl)
        parts = parse.urlsplit(newurl)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if resolved_ip and _pin_stack():
            _pin_stack()[-1][(_bare_host(parts.netloc), port)] = resolved_ip
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.hidden = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def _portfolio_agent(url: str) -> dict:
    try:
        resolved_ip = _validate_public_url(url)
        parts = parse.urlsplit(url)
        host = _bare_host(parts.netloc)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        with _pinned_dns_scope(host, port, resolved_ip):
            opener = request.build_opener(_SafeRedirect())
            req = request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"})
            with opener.open(req, timeout=8) as response:
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "text/plain"}:
                    raise ValueError("Only public HTML or text pages are analyzed")
                data = response.read(MAX_PAGE_BYTES + 1)
                if len(data) > MAX_PAGE_BYTES:
                    raise ValueError("Page is too large")
                decoded = data.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
        if content_type == "text/html":
            parser = _TextHTMLParser()
            parser.feed(decoded)
            text = " ".join(parser.parts)
        else:
            text = decoded
        return {"url": url, "kind": "portfolio", "status": "analyzed", "text": html.unescape(text)[:MAX_PAGE_TEXT],
                "summary": f"Public portfolio page analyzed: {parse.urlsplit(url).hostname}"}
    except Exception as exc:
        hostname = parse.urlsplit(url).hostname or "portfolio website"
        reason = getattr(exc, "reason", None)
        if isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError) or "timed out" in str(exc).lower():
            summary = f"{hostname} did not respond in time; matching continued without that page."
        elif isinstance(exc, error.HTTPError):
            summary = f"{hostname} declined the request (HTTP {exc.code}); matching continued without that page."
        elif isinstance(exc, ValueError):
            summary = f"{hostname} was skipped by the public-page safety check; matching continued without it."
        else:
            summary = f"{hostname} could not be read; matching continued without that page."
        return {"url": url, "kind": "portfolio", "status": "blocked", "text": "",
                "summary": summary}


def analyze_candidate(cv_text: str, explicit_urls=None, use_github=True,
                      use_portfolios=False, log=print) -> dict:
    """Run bounded resume, GitHub, and public-page agents concurrently."""
    explicit_urls = [x for x in (explicit_urls or []) if x]
    urls = extract_urls(cv_text + "\n" + "\n".join(explicit_urls))
    linkedin = [u for u in urls if (parse.urlsplit(u).hostname or "").lower().endswith("linkedin.com")]
    github = [u for u in urls if _github_target(u)] if use_github else []
    portfolios = [u for u in urls if u not in linkedin and u not in github] if use_portfolios else []
    tasks = [("resume", _resume_agent, cv_text)]
    tasks += [("github", _github_agent, u) for u in github[:3]]
    tasks += [("portfolio", _portfolio_agent, u) for u in portfolios[:3]]
    outputs, activity = [], []
    with ThreadPoolExecutor(max_workers=min(4, len(tasks))) as pool:
        futures = {}
        for kind, fn, value in tasks:
            message = f"[resume agent: {kind}] analyzing supplied evidence..."
            log(message); activity.append(message)
            futures[pool.submit(fn, value)] = kind
        for future in as_completed(futures):
            kind = futures[future]
            try:
                item = future.result()
                outputs.append((kind, item))
                message = f"[resume agent: {kind}] analysis complete"
            except Exception as exc:
                message = f"[resume agent: {kind}] skipped: {type(exc).__name__}"
            log(message); activity.append(message)
    base = next(item for kind, item in outputs if kind == "resume")
    link_results = [item for kind, item in outputs if kind != "resume"]
    if use_portfolios:
        already_seen = set(portfolios)
        github_websites = []
        for item in link_results:
            if item.get("kind") != "github" or item.get("status") != "analyzed":
                continue
            for discovered in item.get("discovered_urls", []):
                if discovered not in already_seen and not _github_target(discovered):
                    already_seen.add(discovered)
                    github_websites.append(discovered)
        if github_websites:
            with ThreadPoolExecutor(max_workers=min(3, len(github_websites[:3]))) as pool:
                futures = {}
                for website in github_websites[:3]:
                    message = "[resume agent: github website] analyzing public page..."
                    log(message); activity.append(message)
                    futures[pool.submit(_portfolio_agent, website)] = website
                for future in as_completed(futures):
                    try:
                        link_results.append(future.result())
                        message = "[resume agent: github website] analysis complete"
                    except Exception as exc:
                        message = f"[resume agent: github website] skipped: {type(exc).__name__}"
                    log(message); activity.append(message)
    enriched_text = " ".join(item.get("text", "") for item in link_results if item.get("status") == "analyzed")
    skills = sorted(set(base["skills"]) | set(_extract_named(enriched_text, SKILL_ALIASES)))
    domains = sorted(set(base["domains"]) | set(_extract_named(f" {enriched_text} ", DOMAIN_ALIASES)))
    role_terms = sorted(set(base["role_terms"]) | {r for r in ROLE_PATTERNS if _contains(enriched_text, r)})
    sources = ([{"url": u, "kind": "linkedin", "status": "recognized-not-fetched",
                 "summary": "LinkedIn URL recognized; profile content was not fetched."} for u in linkedin]
               + [{k: v for k, v in item.items() if k != "text"} for item in link_results])
    warnings = [s["summary"] for s in sources if s.get("status") in {"blocked", "error", "recognized-not-fetched"}]
    return {
        "fingerprint": hashlib.sha256(cv_text.encode("utf-8")).hexdigest()[:16],
        "skills": skills, "skill_categories": categorize_skills(skills),
        "domains": domains, "role_terms": role_terms,
        "education": base["education"], "experience_signals": base["experience_signals"],
        "urls": urls, "sources": sources, "warnings": warnings, "agent_activity": activity,
        "summary": f"Detected {len(skills)} skills, {len(role_terms)} role signals, and {len(urls)} public profile links.",
    }


def score_job_fit(job: dict, candidate: dict | None) -> dict | None:
    if not candidate:
        return None
    text = " ".join([str(job.get("title") or ""), str(job.get("description") or ""),
                     " ".join(job.get("requirements") or []), " ".join(job.get("tags") or [])])
    job_skills = _extract_named(text, SKILL_ALIASES)
    job_domains = _extract_named(f" {text} ", DOMAIN_ALIASES)
    matched_skills = sorted(set(candidate.get("skills", [])) & set(job_skills))
    matched_domains = sorted(set(candidate.get("domains", [])) & set(job_domains))
    role_matches = [role for role in candidate.get("role_terms", []) if _contains(text, role)]
    skill_score = min(55, len(matched_skills) * 9)
    domain_score = min(20, len(matched_domains) * 10)
    role_score = min(15, len(role_matches) * 10)
    education_score = 10 if candidate.get("education") and any(
        _contains(text, level) for level in candidate["education"]) else 0
    score = min(100, skill_score + domain_score + role_score + education_score)
    matched_categories = sorted({SKILL_CATEGORY.get(x, "Other") for x in matched_skills})
    potential_gaps = [x for x in job_skills if x not in candidate.get("skills", [])][:5]
    reasons = []
    if matched_skills:
        reasons.append("CV/public evidence mentions " + ", ".join(matched_skills[:5]))
    if matched_domains:
        reasons.append("Domain overlap: " + ", ".join(matched_domains[:3]))
    if role_matches:
        reasons.append("Role overlap: " + ", ".join(role_matches[:2]))
    return {"score": score, "matched_skills": matched_skills[:10],
            "matched_categories": matched_categories,
            "matched_domains": matched_domains[:6], "matched_roles": role_matches[:4],
            "potential_gaps": potential_gaps,
            "reasons": reasons or ["Limited direct resume evidence was found for this posting"],
            "confidence": round(min(1.0, (len(job_skills) + len(job_domains)) / 8), 2)}
