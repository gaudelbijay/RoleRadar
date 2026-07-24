"""Bounded extraction of public technical staff from official company pages."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from urllib import error, parse, request

from bs4 import BeautifulSoup

from core.resume_intelligence import MAX_PAGE_BYTES, USER_AGENT, _SafeRedirect, _validate_public_url

MAX_PAGES_PER_COMPANY = 5
MAX_PEOPLE_PER_COMPANY = 40
RELEVANT_PATH = re.compile(r"(?:team|people|leadership|about|engineering|research|staff)", re.I)
CONTACT_PATH = re.compile(r"(?:careers?|jobs?|contact|join[- ]?us|work[- ]?with[- ]?us)", re.I)
GENERIC_CONTACT_LOCAL = re.compile(
    r"^(?:careers?|jobs?|recruit(?:ing|ment)?|talent|hiring|people|hr|info|hello)$", re.I,
)
TECHNICAL_TITLE = re.compile(
    r"\b(?:cto|chief technology|chief technical|engineering|engineer|software|hardware|"
    r"research|scientist|robotics|machine learning|artificial intelligence|\bai\b|data|"
    r"product development|technical|technology|developer|security|infrastructure|platform|"
    r"architecture|architect|devops|cloud|systems|controls|perception|autonomy)\b",
    re.I,
)
HIRING_MANAGER = re.compile(r"\b(?:hiring manager|recruiting manager|talent hiring manager)\b", re.I)
BLOCKED_HOST_PARTS = {
    "linkedin.com", "indeed.com", "glassdoor.com", "google.com", "remotive.com",
    "jobicy.com", "arbeitnow.com", "remoteok.com", "greenhouse.io", "lever.co",
    "myworkdayjobs.com", "workdayjobs.com", "ashbyhq.com", "jobvite.com",
    "smartrecruiters.com",
}


def _valid_public_http(value: object) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    parts = parse.urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return ""
    host = parts.hostname.lower().removeprefix("www.")
    if any(host == blocked or host.endswith("." + blocked) for blocked in BLOCKED_HOST_PARTS):
        return ""
    return parse.urlunsplit((parts.scheme.lower(), parts.netloc, parts.path or "/", "", ""))


def official_company_url(job: dict) -> str:
    """Return an explicit official URL, or a non-aggregator application origin."""
    explicit = _valid_public_http(job.get("company_url"))
    if explicit:
        return explicit
    apply_url = _valid_public_http(job.get("apply_url"))
    if not apply_url:
        return ""
    parts = parse.urlsplit(apply_url)
    return parse.urlunsplit((parts.scheme, parts.netloc, "/", "", ""))


def _same_host(url: str, root: str) -> bool:
    first = (parse.urlsplit(url).hostname or "").lower().removeprefix("www.")
    second = (parse.urlsplit(root).hostname or "").lower().removeprefix("www.")
    return bool(first and first == second)


def _fetch_html(url: str) -> str:
    _validate_public_url(url)
    opener = request.build_opener(_SafeRedirect())
    req = request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with opener.open(req, timeout=8) as response:
        if response.headers.get_content_type() != "text/html":
            raise ValueError("Official page is not HTML")
        data = response.read(MAX_PAGE_BYTES + 1)
        if len(data) > MAX_PAGE_BYTES:
            raise ValueError("Official page is too large")
        return data.decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()



def _json_public_links(value: object) -> list[dict]:
    values = value if isinstance(value, list) else [value]
    links = []
    for item in values:
        target = _valid_public_http(item)
        host = (parse.urlsplit(target).hostname or "").lower().removeprefix("www.")
        if target and (host == "github.com" or host.endswith(".github.com")):
            link = {"label": "GitHub", "url": target}
            if link not in links:
                links.append(link)
    return links[:4]
def _person_from_json(value: object, source_url: str) -> list[dict]:
    found = []
    if isinstance(value, list):
        for item in value:
            found.extend(_person_from_json(item, source_url))
    elif isinstance(value, dict):
        types = value.get("@type", [])
        types = [types] if isinstance(types, str) else types
        if "Person" in types:
            name = _clean(value.get("name"))
            occupation = value.get("hasOccupation") if isinstance(value.get("hasOccupation"), dict) else {}
            title = _clean(value.get("jobTitle") or occupation.get("name"))
            bio = _clean(value.get("description"))
            if name and title and TECHNICAL_TITLE.search(title):
                profile = _valid_public_http(value.get("url"))
                found.append(_person(
                    name, title, profile, source_url, title,
                    bio, _json_public_links(value.get("sameAs", [])),
                ))
        for child in value.values():
            if isinstance(child, (dict, list)):
                found.extend(_person_from_json(child, source_url))
    return found


def _public_links(container, source_url: str) -> list[dict]:
    links = []
    for anchor in container.find_all("a", href=True):
        target = _valid_public_http(parse.urljoin(source_url, anchor["href"]))
        if not target:
            continue
        host = (parse.urlsplit(target).hostname or "").lower().removeprefix("www.")
        label = _clean(anchor.get_text(" ", strip=True))
        if host == "github.com" or host.endswith(".github.com"):
            kind = "GitHub"
        elif not _same_host(target, source_url) and re.search(r"(?:portfolio|website|homepage|personal site)", label, re.I):
            kind = "Portfolio"
        else:
            continue
        item = {"label": kind, "url": target}
        if item not in links:
            links.append(item)
    return links[:4]


def _person(name: str, title: str, profile_url: str, source_url: str, context: str,
            bio: str = "", public_links: list[dict] | None = None) -> dict:
    return {
        "name": name,
        "title": title,
        "technical_area": _technical_area(title),
        "official_profile_url": profile_url if profile_url and _same_host(profile_url, source_url) else "",
        "source_url": source_url,
        "bio": _clean(bio)[:500],
        "public_links": public_links or [],
        "hiring_manager": bool(HIRING_MANAGER.search(context)),
    }


def _technical_area(title: str) -> str:
    lowered = title.lower()
    for label, terms in (
        ("AI / Machine Learning", ("machine learning", "artificial intelligence", " ai ", "data science")),
        ("Robotics / Autonomy", ("robot", "autonomy", "perception", "controls")),
        ("Research", ("research", "scientist")),
        ("Engineering leadership", ("cto", "chief technology", "vp engineering", "head of engineering", "director")),
        ("Software / Platform", ("software", "platform", "cloud", "devops", "infrastructure", "security")),
        ("Hardware / Systems", ("hardware", "systems", "electrical", "mechanical")),
    ):
        if any(term in f" {lowered} " for term in terms):
            return label


def extract_people(html_text: str, source_url: str) -> list[dict]:
    """Conservatively extract public technical people from one official page."""
    soup = BeautifulSoup(html_text, "html.parser")
    people = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            people.extend(_person_from_json(json.loads(script.string or ""), source_url))
        except (json.JSONDecodeError, TypeError):
            continue
    selectors = "[class*='team'],[class*='member'],[class*='person'],[class*='leader'],[class*='staff'],article"
    for card in soup.select(selectors):
        context = _clean(card.get_text(" ", strip=True))
        if not context or len(context) > 900 or not TECHNICAL_TITLE.search(context):
            continue
        heading = card.find(["h2", "h3", "h4", "strong"])
        name = _clean(heading.get_text(" ", strip=True) if heading else "")
        if not re.fullmatch(r"[A-Z][\w.'’-]+(?:\s+[A-Z][\w.'’-]+){1,4}", name):
            continue
        title = ""
        for candidate in card.find_all(["p", "span", "div"], limit=12):
            text = _clean(candidate.get_text(" ", strip=True))
            if text != name and len(text) <= 180 and TECHNICAL_TITLE.search(text):
                title = text
                break
        if not title:
            continue
        link = heading.find("a", href=True) if heading else None
        profile = parse.urljoin(source_url, link["href"]) if link else ""
        bio_parts = []
        for candidate in card.find_all("p", limit=10):
            text = _clean(candidate.get_text(" ", strip=True))
            if text not in {name, title} and 35 <= len(text) <= 500:
                bio_parts.append(text)
        people.append(_person(
            name, title, profile, source_url, context,
            " ".join(bio_parts)[:500], _public_links(card, source_url),
        ))
    unique = {}
    for item in people:
        key = (item["name"].lower(), item["title"].lower())
        unique.setdefault(key, item)
    return list(unique.values())[:MAX_PEOPLE_PER_COMPANY]


def _discover_pages(home_html: str, root_url: str) -> list[str]:
    soup = BeautifulSoup(home_html, "html.parser")
    pages = [root_url]
    for link in soup.find_all("a", href=True):
        label = _clean(link.get_text(" ", strip=True))
        target = parse.urljoin(root_url, link["href"])
        if (RELEVANT_PATH.search(label + " " + parse.urlsplit(target).path)
                and _same_host(target, root_url)):
            target = parse.urlunsplit((*parse.urlsplit(target)[:3], "", ""))
            if target not in pages:
                pages.append(target)
        if len(pages) >= MAX_PAGES_PER_COMPANY:
            break
    return pages



def extract_company_contacts(html_text: str, source_url: str) -> dict:
    """Extract only generic recruiting contacts and public careers/contact pages."""
    soup = BeautifulSoup(html_text, "html.parser")
    emails, links = [], []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        label = _clean(anchor.get_text(" ", strip=True))
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?", 1)[0].strip().lower()
            local, separator, domain = email.partition("@")
            source_host = (parse.urlsplit(source_url).hostname or "").lower().removeprefix("www.")
            company_domain = bool(separator and (
                source_host == domain or source_host.endswith("." + domain)
                or domain.endswith("." + source_host)
            ))
            if GENERIC_CONTACT_LOCAL.fullmatch(local) and company_domain:
                emails.append(email)
            continue
        target = _valid_public_http(parse.urljoin(source_url, href))
        if (target and _same_host(target, source_url)
                and CONTACT_PATH.search(label + " " + parse.urlsplit(target).path)):
            links.append(target)
    return {
        "generic_emails": list(dict.fromkeys(emails))[:5],
        "contact_urls": list(dict.fromkeys(links))[:5],
    }
def explicit_job_hiring_managers(job: dict) -> list[dict]:
    """Extract only hiring managers explicitly named in the public posting."""
    description = str(job.get("description") or "")
    source_url = _valid_public_http(job.get("apply_url")) or str(job.get("apply_url") or "")
    pattern = re.compile(
        r"(?i)\bhiring manager\s*(?:is|:|-)\s*"
        r"([A-Z][A-Za-z.\x27’-]+(?:\s+[A-Z][A-Za-z.\x27’-]+){1,3})"
        r"(?:\s*[,|-]\s*([^\n.]{3,120}))?"
    )
    found = []
    for match in pattern.finditer(description):
        name = _clean(match.group(1))
        title = _clean(match.group(2)) or "Hiring Manager"
        found.append({
            "name": name, "title": title,
            "technical_area": _technical_area(title),
            "official_profile_url": "", "source_url": source_url,
            "bio": "", "public_links": [],
            "hiring_manager": True,
        })
    return found


def research_company(job: dict, log=lambda _message: None) -> dict:
    company = str(job.get("company") or "Company not specified")
    root = official_company_url(job)
    posting_managers = explicit_job_hiring_managers(job)
    if not root:
        return {"company": company, "status": "analyzed" if posting_managers else "unavailable",
                "official_url": "", "people": posting_managers, "pages_scanned": 0,
                "note": ("Hiring manager was explicitly named in the public job posting."
                         if posting_managers else
                         "No verified official company URL was supplied by the listing.")}
    try:
        log(f"[company people] {company}: reading official public pages...")
        home = _fetch_html(root)
        pages = _discover_pages(home, root)
        contacts = extract_company_contacts(home, root)
        people = posting_managers + extract_people(home, root)
        scanned = 1
        for page in pages[1:]:
            try:
                people.extend(extract_people(_fetch_html(page), page))
                scanned += 1
            except Exception:
                continue
        unique = {}
        for person in people:
            unique.setdefault((person["name"].lower(), person["title"].lower()), person)
        final = list(unique.values())[:MAX_PEOPLE_PER_COMPANY]
        final.sort(key=lambda item: (not item["hiring_manager"], item["technical_area"], item["name"]))
        return {"company": company, "status": "analyzed", "official_url": root,
                "people": final, "pages_scanned": scanned,
                "generic_emails": contacts["generic_emails"],
                "contact_urls": contacts["contact_urls"],
                "note": "Hiring manager is highlighted only when explicitly identified by a public source."}
    except (error.HTTPError, error.URLError, TimeoutError, ValueError, OSError) as exc:
        return {"company": company, "status": "unavailable", "official_url": root, "people": [],
                "pages_scanned": 0, "note": f"Official pages could not be analyzed: {type(exc).__name__}."}


def research_all_companies(jobs: list[dict], log=lambda _message: None) -> list[dict]:
    unique = {}
    for job in jobs:
        unique.setdefault((str(job.get("company") or "").lower(), official_company_url(job)), job)
    results = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(unique)))) as pool:
        futures = [pool.submit(research_company, job, log) for job in unique.values()]
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda item: item["company"].lower())
