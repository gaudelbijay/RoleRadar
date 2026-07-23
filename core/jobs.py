"""Live public job-feed aggregation, ranking, requirement extraction and reports."""
from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib import error, parse, request

UA = "jobSearch/1.0 local dashboard"
STOP = {"a", "an", "and", "are", "as", "at", "for", "from", "in", "is", "job",
        "jobs", "of", "on", "or", "the", "to", "with", "hiring", "requirement",
        "requirements", "looking", "find", "show", "want", "need", "please",
        "level"}
ROBOTICS = {"robot", "robots", "robotic", "robotics"}
STRONG_ROBOTICS = {
    "robot learning", "autonomous systems", "autonomous robot",
    "manipulation", "motion planning", "slam", "robot operating system", "ros",
}
CONCEPTS = {
    "robotics": {
        "robot", "robots", "robotic", "robotics", "robot learning",
        "autonomous systems", "autonomous robot", "manipulation",
        "motion planning", "slam", "robot operating system", "ros",
    },
    "artificial intelligence": {
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "neural network", "computer vision", "perception",
        "reinforcement learning", "foundation model",
    },
    "advanced degree": {
        "phd", "doctorate", "doctoral", "postdoctoral", "postdoc",
        "advanced degree", "graduate degree",
    },
}
MAX_AGE_DAYS = 10
COUNTRIES = [
    "United States", "Canada", "United Kingdom", "Germany", "France", "India",
    "Australia", "Netherlands", "Switzerland", "Sweden", "Norway", "Denmark",
    "Finland", "Ireland", "Spain", "Italy", "Portugal", "Poland", "Austria",
    "Belgium", "Czech Republic", "Japan", "South Korea", "Singapore",
    "New Zealand", "Brazil", "Mexico", "United Arab Emirates", "Israel",
]
COUNTRY_ALIASES = {
    "united states": {"united states", "usa", "u.s.", "us"},
    "united kingdom": {"united kingdom", "uk", "u.k.", "great britain"},
    "canada": {"canada"}, "germany": {"germany", "deutschland"},
    "india": {"india"}, "australia": {"australia"},
    "france": {"france"}, "netherlands": {"netherlands", "holland"},
}


def _json(url: str):
    req = request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=25) as response:
            return json.loads(response.read().decode())
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{url}: {exc}") from exc


def clean(value) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h[1-6]>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def _job(source, source_id, title, company, location, description, url,
         published="", salary="", job_type="", tags=None):
    return {
        "id": f"{source}:{source_id}", "source": source,
        "title": clean(title) or "Untitled role",
        "company": clean(company) or "Company not specified",
        "location": clean(location) or "Not specified",
        "description": clean(description), "apply_url": url,
        "published": str(published or ""), "salary": clean(salary),
        "job_type": clean(job_type).replace("_", " "),
        "tags": [clean(tag) for tag in (tags or []) if tag],
    }


def remotive(query):
    url = "https://remotive.com/api/remote-jobs?" + parse.urlencode(
        {"search": query, "limit": 50})
    return [_job("Remotive", j.get("id"), j.get("title"), j.get("company_name"),
                 j.get("candidate_required_location", "Remote"), j.get("description"),
                 j.get("url"), j.get("publication_date"), j.get("salary"),
                 j.get("job_type"), [j.get("category")])
            for j in _json(url).get("jobs", []) if j.get("url")]


def jobicy(query):
    url = "https://jobicy.com/api/v2/remote-jobs?" + parse.urlencode(
        {"count": 50, "tag": query})
    return [_job("Jobicy", j.get("id"), j.get("jobTitle"), j.get("companyName"),
                 j.get("jobGeo", "Remote"), j.get("jobDescription"), j.get("url"),
                 j.get("pubDate"), " ".join(str(v) for v in
                 [j.get("annualSalaryMin"), j.get("annualSalaryMax"),
                  j.get("salaryCurrency")] if v), j.get("jobType"),
                 j.get("jobIndustry") or [])
            for j in _json(url).get("jobs", []) if j.get("url")]


def arbeitnow(query):
    data = _json("https://www.arbeitnow.com/api/job-board-api").get("data", [])
    return [_job("Arbeitnow", j.get("slug"), j.get("title"), j.get("company_name"),
                 j.get("location"), j.get("description"), j.get("url"),
                 j.get("created_at"), job_type="Remote" if j.get("remote") else "",
                 tags=j.get("tags") or [])
            for j in data[:60] if j.get("url")]


def remoteok(query):
    payload = _json("https://remoteok.com/api")
    return [_job("Remote OK", j.get("id"), j.get("position"), j.get("company"),
                 j.get("location", "Remote"), j.get("description"), j.get("url"),
                 j.get("date"), f"{j.get('salary_min', '')} {j.get('salary_max', '')}",
                 tags=j.get("tags") or [])
            for j in payload if isinstance(j, dict) and j.get("position") and j.get("url")]


def top_job_sites(query, country, city, max_age_days):
    """Retrieve public listings from major sites through python-jobspy."""
    try:
        from jobspy import scrape_jobs
    except ImportError as exc:
        raise RuntimeError(
            "python-jobspy is not installed; run pip install -r requirements.txt"
        ) from exc
    location = ", ".join(part for part in [city.strip(), country.strip()] if part)
    frame = scrape_jobs(
        site_name=["linkedin", "indeed", "google", "glassdoor"],
        search_term=query,
        google_search_term=f"{query} jobs in {location}",
        location=location,
        results_wanted=75,
        hours_old=max_age_days * 24,
        country_indeed=country,
        verbose=0,
    )
    jobs = []
    for _, row in frame.iterrows():
        item = row.to_dict()
        apply_url = item.get("job_url_direct") or item.get("job_url")
        if not apply_url:
            continue
        salary = " ".join(
            str(value) for value in [
                item.get("min_amount"), item.get("max_amount"), item.get("currency"),
                item.get("interval"),
            ] if value is not None and str(value) != "nan"
        )
        jobs.append(_job(
            str(item.get("site") or "Major job site").title(),
            item.get("id") or apply_url, item.get("title"), item.get("company"),
            item.get("location"), item.get("description"), apply_url,
            item.get("date_posted"), salary, item.get("job_type"),
            [item.get("job_level"), item.get("job_function")],
        ))
    return jobs


def major_search_links(query, location=""):
    q, loc = parse.quote_plus(query), parse.quote_plus(location)
    return [
        {"name": "LinkedIn", "url": f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}"},
        {"name": "Indeed", "url": f"https://www.indeed.com/jobs?q={q}&l={loc}"},
        {"name": "Glassdoor", "url": f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}&locKeyword={loc}"},
        {"name": "Google Jobs", "url": f"https://www.google.com/search?q={q}+jobs+{loc}"},
    ]


def requirements(description, limit=8):
    chunks = re.split(r"[\n•]+|(?<=[.!?])\s+", description)
    signals = ("require", "qualification", "experience", "phd", "master", "bachelor",
               "degree", "proficien", "knowledge", "skill", "must", "years",
               "ability", "expert", "familiar", "python", "c++", "robot")
    result = []
    for chunk in chunks:
        line = re.sub(r"\s+", " ", chunk).strip(" -–—:")
        if 10 <= len(line) <= 280 and any(s in line.lower() for s in signals):
            if line not in result:
                result.append(line)
        if len(result) == limit:
            break
    return result


def experience(description, limit=6):
    chunks = re.split(r"[\n•]+|(?<=[.!?])\s+", description)
    signals = ("experience", "senior", "junior", "entry level",
               "phd", "master", "bachelor", "degree", "postdoc")
    found = []
    for chunk in chunks:
        line = re.sub(r"\s+", " ", chunk).strip(" -–—:")
        if 10 <= len(line) <= 280 and any(s in line.lower() for s in signals):
            if line not in found:
                found.append(line)
        if len(found) == limit:
            break
    return found


def salary_evidence(job):
    if job["salary"]:
        return job["salary"]
    patterns = [
        r"(?i)(?:salary|compensation|pay)[^.\n]{0,80}"
        r"(?:[$€£]\s?[\d,.]+(?:\s*[-–—]\s*[$€£]?\s?[\d,.]+)?(?:\s*(?:k|per year|annually|/yr|/hour|/hr))?)",
        r"[$€£]\s?[\d,.]+\s*[-–—]\s*[$€£]?\s?[\d,.]+(?:\s*(?:k|/yr|/hour|/hr))?",
    ]
    for pattern in patterns:
        match = re.search(pattern, job["description"])
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return "Not disclosed in the posting"


def published_datetime(value):
    if value in ("", None):
        return None
    raw = str(value).strip()
    try:
        number = float(raw)
        if number > 10_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number, tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        pass
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def location_matches(location, country=""):
    value = location.lower()
    if country:
        requested = country.strip().lower()
        aliases = COUNTRY_ALIASES.get(requested, {requested})
        if not any(re.search(rf"\b{re.escape(alias)}\b", value) for alias in aliases):
            return False
    return True


def rank(jobs, query, limit=30, country="", city="", max_age_days=MAX_AGE_DAYS,
         include_diagnostics=False):
    words = {w for w in re.findall(r"[a-z0-9+#.]{2,}", query.lower()) if w not in STOP}
    query_text = query.lower()
    requested_concepts = {
        name: terms for name, terms in CONCEPTS.items()
        if any(re.search(rf"\b{re.escape(term)}\b", query_text) for term in terms)
    }
    unique = {}
    for job in jobs:
        unique.setdefault((job["company"].lower(), job["title"].lower()), job)
    for job in unique.values():
        title = job["title"].lower()
        body = " ".join([title, job["company"].lower(), job["location"].lower(),
                         job["description"].lower(), " ".join(job["tags"]).lower()])
        body_tokens = set(re.findall(r"[a-z0-9+#.]{2,}", body))
        title_tokens = set(re.findall(r"[a-z0-9+#.]{2,}", title))
        matched_words = words & body_tokens
        if words & ROBOTICS and body_tokens & ROBOTICS:
            matched_words |= words & ROBOTICS
        job["matched_keywords"] = sorted(matched_words)
        job["concept_evidence"] = {}
        for concept, terms in requested_concepts.items():
            evidence = sorted(
                term for term in terms
                if re.search(rf"\b{re.escape(term)}\b", body)
            )
            if evidence:
                job["concept_evidence"][concept] = evidence[:6]
        robotics_evidence = job["concept_evidence"].get("robotics", [])
        robotics_occurrences = sum(
            len(re.findall(rf"\b{re.escape(term)}\b", body))
            for term in CONCEPTS["robotics"]
        )
        title_has_robotics = any(
            re.search(rf"\b{re.escape(term)}\b", title)
            for term in CONCEPTS["robotics"]
        )
        job["robotics_role_evidence"] = (
            title_has_robotics
            or bool(set(robotics_evidence) & STRONG_ROBOTICS)
            or robotics_occurrences >= 2
        )
        job["keyword_coverage"] = (
            len(job["matched_keywords"]) / len(words) if words else 1.0
        )
        job["match_score"] = (
            10 * len(job["concept_evidence"])
            + len(job["matched_keywords"])
            + 3 * len(words & title_tokens)
        )
        job["requirements"] = requirements(job["description"])
        job["experience"] = experience(job["description"])
        job["salary_display"] = salary_evidence(job)
        job["_published_dt"] = published_datetime(job["published"])
        job["age_days"] = (
            (datetime.now(timezone.utc) - job["_published_dt"]).days
            if job["_published_dt"] else None
        )
        job["_robotics_match"] = bool(body_tokens & ROBOTICS)
        job["city_match"] = bool(
            city.strip() and city.strip().lower() in job["location"].lower()
        )
    diagnostics = {
        "normalized_unique": len(unique), "missing_requested_concept": 0,
        "weak_domain_evidence": 0,
        "insufficient_keyword_coverage": 0, "missing_or_invalid_date": 0,
        "outside_age_window": 0, "country_mismatch": 0, "eligible": 0,
        "requested_concepts": sorted(requested_concepts),
    }
    minimum_coverage = 0.5
    matched, near_matches = [], []
    now = datetime.now(timezone.utc)
    for job in unique.values():
        reasons = []
        if not all(c in job["concept_evidence"] for c in requested_concepts):
            reasons.append("missing requested concept")
            diagnostics["missing_requested_concept"] += 1
        if "robotics" in requested_concepts and not job["robotics_role_evidence"]:
            reasons.append("robotics mentioned only incidentally")
            diagnostics["weak_domain_evidence"] += 1
        if not requested_concepts and job["keyword_coverage"] < minimum_coverage:
            reasons.append("insufficient keyword coverage")
            diagnostics["insufficient_keyword_coverage"] += 1
        if job["_published_dt"] is None:
            reasons.append("missing or invalid date")
            diagnostics["missing_or_invalid_date"] += 1
        elif not (now - timedelta(days=max_age_days)
                  <= job["_published_dt"] <= now + timedelta(hours=1)):
            reasons.append("outside age window")
            diagnostics["outside_age_window"] += 1
        if not location_matches(job["location"], country):
            reasons.append("country mismatch")
            diagnostics["country_mismatch"] += 1
        job["rejection_reasons"] = reasons
        if not reasons:
            matched.append(job)
            diagnostics["eligible"] += 1
        elif job["concept_evidence"]:
            near_matches.append(job)
    ranked = sorted(
        matched,
        key=lambda j: (j["_published_dt"], j["city_match"], j["match_score"]),
        reverse=True,
    )[:limit]
    for job in ranked:
        job["published_iso"] = job["_published_dt"].date().isoformat()
        del job["_published_dt"]
        del job["_robotics_match"]
    near_ranked = sorted(
        near_matches,
        key=lambda j: (j["_published_dt"] or datetime.min.replace(tzinfo=timezone.utc),
                       j["match_score"]),
        reverse=True,
    )[:10]
    for job in near_ranked:
        job["published_iso"] = (
            job["_published_dt"].date().isoformat() if job["_published_dt"] else "Unknown"
        )
        del job["_published_dt"]
        del job["_robotics_match"]
    if include_diagnostics:
        return ranked, diagnostics, near_ranked
    return ranked


def search_jobs(query, log=print, max_results=30, country="", city="",
                max_age_days=MAX_AGE_DAYS):
    if not country.strip():
        raise ValueError("Country is required. City is optional.")
    if not 1 <= int(max_age_days) <= 90:
        raise ValueError("Maximum posting age must be between 1 and 90 days.")
    max_age_days = int(max_age_days)
    sources = [("Remotive", remotive), ("Jobicy", jobicy),
               ("Arbeitnow", arbeitnow), ("Remote OK", remoteok),
               ("LinkedIn / Indeed / Google / Glassdoor",
                lambda q: top_job_sites(q, country, city, max_age_days))]
    jobs, errors = [], []
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = {}
        for name, fetcher in sources:
            log(f"[source agent: {name}] searching live listings...")
            futures[pool.submit(fetcher, query)] = name
        for future in as_completed(futures):
            name = futures[future]
            try:
                batch = future.result()
                jobs.extend(batch)
                log(f"[source agent: {name}] collected {len(batch)} listings")
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                log(f"[source agent: {name}] failed: {exc}")
    location = ", ".join(part for part in [city.strip(), country.strip()] if part)
    ranked, diagnostics, near_matches = rank(
        jobs, query, max_results, country, city, max_age_days,
        include_diagnostics=True
    )
    return {"jobs": ranked, "diagnostics": diagnostics,
            "near_matches": near_matches, "source_errors": errors,
            "search_links": major_search_links(query, location),
            "country": country.strip(), "city": city.strip(),
            "max_age_days": max_age_days,
            "fetched_count": len(jobs),
            "generated_at": datetime.now(timezone.utc).isoformat()}


def build_report(query, result):
    jobs = result["jobs"]
    lines = [
        "# ✦ jobSearch Intelligence Report",
        "",
        f"> **Search mission:** {query}  ",
        f"> **Country:** {result.get('country') or 'Any'} · "
        f"**City:** {result.get('city') or 'Any'}  ",
        f"> **Generated:** {result['generated_at']}  ",
        f"> **Policy:** close concept match · robotics-domain gate · "
        f"≤ {result['max_age_days']} days old · newest first",
        "",
        "| Live listings scanned | Verified matches | Maximum age | Ranking |",
        "|---:|---:|---:|:---|",
        f"| {result['fetched_count']} | {len(jobs)} | "
        f"{result['max_age_days']} days | Newest → oldest |",
        "",
        "## 🎯 Curated opportunities",
        "",
    ]
    if not jobs:
        lines += [
            "> **No verified feed match was found.** This does not mean the job "
            "does not exist. None of the connected public feeds had a listing that "
            "passed the concept, country, date, and age checks.",
            "",
            "### Rejection audit",
            "",
            "| Gate | Listings rejected |",
            "|:---|---:|",
            f"| Missing requested concept | {result['diagnostics']['missing_requested_concept']} |",
            f"| Robotics mentioned only incidentally | {result['diagnostics']['weak_domain_evidence']} |",
            f"| Insufficient general keyword coverage | {result['diagnostics']['insufficient_keyword_coverage']} |",
            f"| Missing/invalid publication date | {result['diagnostics']['missing_or_invalid_date']} |",
            f"| Outside selected age window | {result['diagnostics']['outside_age_window']} |",
            f"| Country mismatch | {result['diagnostics']['country_mismatch']} |",
            "",
        ]
        if result["diagnostics"]["missing_requested_concept"] == result["diagnostics"]["normalized_unique"]:
            lines += [
                "> **Coverage diagnosis:** zero connected-feed listings contained "
                "the requested domain concept. The empty result is caused by source "
                "coverage—not by hiding valid matches behind location or recency.",
                "",
            ]
    for i, job in enumerate(jobs, 1):
        number = str(i).zfill(2)
        lines += [
            "---",
            "",
            f"## {number} · [{job['title']}]({job['apply_url']})",
            "",
            f"### {job['company']}",
            "",
            "| 📍 Location | 🗓 Posted | ⏱ Age | 🧭 Source |",
            "|:---|:---|:---|:---|",
            f"| {job['location']} | {job['published_iso']} | "
            f"{job['age_days']} day{'s' if job['age_days'] != 1 else ''} | "
            f"[{job['source']}]({job['apply_url']}) |",
            "",
            f"**Employment type**  \n{job['job_type'] or 'Not disclosed'}",
            "",
            f"**💰 Compensation evidence**  \n{job['salary_display']}",
            "",
            f"**🔑 Relevance signals**  \n"
            f"`{'` · `'.join(job['matched_keywords']) or 'concept match'}`",
            "",
            "### 🧠 Experience profile",
            "",
        ]
        lines += [f"- {item}" for item in job["experience"]] or [
            "- No explicit experience statement was found in the supplied posting text."
        ]
        lines += ["", "### ✅ Qualifications and requirements", ""]
        lines += [f"- {item}" for item in job["requirements"]] or [
            "- No additional explicit requirement statement was extracted."
        ]
        lines += [
            "",
            "### 📝 Role snapshot",
            "",
            job["description"][:1800] or "The source did not supply a description.",
            "",
            f"### [Apply on the original listing →]({job['apply_url']})",
            "",
        ]
    lines += ["---", "", "## 🌐 Continue on major platforms", ""]
    lines += [f"- **[{link['name']} — open this exact search ↗]({link['url']})**"
              for link in result["search_links"]]
    lines += [
        "",
        "## 🔍 Trust and methodology",
        "",
        "- Matching is concept-aware rather than literal: descriptions can qualify "
        "through closely related terminology.",
        "- Robotics queries require robotics-domain evidence such as robots, "
        "autonomous systems, manipulation, motion planning, SLAM, or ROS.",
        "- AI queries accept closely related evidence such as machine learning, "
        "perception, computer vision, deep learning, or reinforcement learning.",
        "- PhD/doctoral queries require explicit advanced-degree evidence in the "
        "posting rather than inferring education from the job title.",
        f"- Undated listings and listings older than "
        f"{result['max_age_days']} days are excluded.",
        "- Country is mandatory. City is optional and used only as a preference; "
        "jobs elsewhere in the selected country remain eligible.",
        "- Salary and experience text is quoted or extracted from the source posting; "
        "missing information is labeled rather than guessed.",
        "- Apply links always open the original source. Applications are never "
        "submitted automatically and credentials are never collected.",
    ]
    if result["source_errors"]:
        lines += ["", "## Source errors", ""] + [f"- {e}" for e in result["source_errors"]]
    return "\n".join(lines)
