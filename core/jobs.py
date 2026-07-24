"""Live public job-feed aggregation, ranking, requirement extraction and reports."""
from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib import error, parse, request

from core.resume_intelligence import score_job_fit
from core.skill_taxonomy import DOMAIN_ALIASES as BROAD_DOMAIN_CONCEPTS

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
# Apply concept-aware matching across the broad occupational domain taxonomy.
for _domain_name, _domain_terms in BROAD_DOMAIN_CONCEPTS.items():
    CONCEPTS.setdefault(_domain_name, set()).update(_domain_terms)
MAX_AGE_DAYS = 10
COUNTRIES = [
    "United States", "Canada", "United Kingdom", "Germany", "France", "India",
    "Australia", "Netherlands", "Switzerland", "Sweden", "Norway", "Denmark",
    "Finland", "Ireland", "Spain", "Italy", "Portugal", "Poland", "Austria",
    "Belgium", "Czech Republic", "Japan", "South Korea", "Singapore",
    "New Zealand", "Brazil", "Mexico", "United Arab Emirates", "Israel",
]
EDUCATION_LEVELS = ["High School", "Bachelor's", "Master's", "PhD"]
EDUCATION_TERMS = {
    "High School": {"high school", "secondary school", "diploma", "ged"},
    "Bachelor's": {
        "bachelor", "bachelors", "bachelor's", "undergraduate degree",
        "college degree",
    },
    "Master's": {
        "master", "masters", "master's", "graduate degree", "phd",
        "doctorate", "doctoral",
    },
    "PhD": {"phd", "doctorate", "doctoral", "postdoctoral", "postdoc"},
}
US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY", "DC",
}
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
    """Normalize HTML and Markdown-ish source text into readable plain text."""
    if value is None or str(value).strip().lower() in {"nan", "nat", "none", "<na>"}:
        return ""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h[1-6]>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    # JobSpy sources can return Markdown with every punctuation mark escaped.
    text = re.sub(r"\\+([\\`*_{}\[\]()#+\-.!&>'])", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*(?:={3,}|-{3,})\s*$", "", text)
    text = re.sub(r"(?m)^\s*[*+-]\s+", "• ", text)
    text = re.sub(r"[*_]{1,3}([^\n*_]+?)[*_]{1,3}", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return re.sub(r"\n\s*\n(?:\s*\n)+", "\n\n", text).strip()


def role_overview(description: str, limit: int = 700) -> str:
    """Return a concise introductory role paragraph without later sections."""
    text = clean(description)
    if not text:
        return "The source did not provide a role overview."
    section_names = re.compile(
        r"(?i)^(?:job description|essential responsibilities|responsibilities|"
        r"position requirements|requirements|qualifications|what you(?:ll| will) do|"
        r"what you(?:ll| will) bring|about us|benefits|compensation)\s*:?$"
    )
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n|(?=^• )", text, flags=re.M):
        paragraph = re.sub(r"\s+", " ", paragraph).strip(" •")
        if not paragraph or section_names.match(paragraph):
            if paragraphs:
                break
            continue
        if paragraph.lower().startswith(("essential responsibilities", "position requirements")):
            break
        if len(paragraph) >= 60:
            paragraphs.append(paragraph)
        if paragraphs:
            break
    overview = paragraphs[0] if paragraphs else re.sub(r"\s+", " ", text)
    if len(overview) <= limit:
        return overview
    clipped = overview[:limit]
    sentence_end = max(clipped.rfind(". "), clipped.rfind("! "), clipped.rfind("? "))
    return (clipped[:sentence_end + 1] if sentence_end >= 220 else clipped.rstrip()) + "…"



def valid_url(value) -> str:
    candidate = clean(value)
    return candidate if candidate.startswith(("https://", "http://")) else ""


def _job(source, source_id, title, company, location, description, url,
         published="", salary="", job_type="", tags=None):
    return {
        "id": f"{source}:{source_id}", "source": source,
        "title": clean(title) or "Untitled role",
        "company": clean(company) or "Company not specified",
        "location": clean(location) or "Not specified",
        "description": clean(description), "apply_url": valid_url(url),
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


def top_job_sites(query, country, city, max_age_days, results_wanted=75):
    """Retrieve public listings from major sites through python-jobspy."""
    try:
        from jobspy import scrape_jobs
    except ImportError as exc:
        raise RuntimeError(
            "python-jobspy is not installed; run pip install -r requirements.txt"
        ) from exc
    location = ", ".join(part for part in [city.strip(), country.strip()] if part)
    frame = scrape_jobs(
        site_name=["linkedin", "indeed", "google"],
        search_term=query,
        google_search_term=f"{query} jobs in {location}",
        location=location,
        results_wanted=results_wanted,
        hours_old=max_age_days * 24,
        country_indeed=country,
        verbose=0,
    )
    jobs = []
    for _, row in frame.iterrows():
        item = row.to_dict()
        apply_url = (
            valid_url(item.get("job_url_direct"))
            or valid_url(item.get("job_url"))
        )
        if not apply_url:
            continue
        salary = " ".join(
            str(value) for value in [
                item.get("min_amount"), item.get("max_amount"), item.get("currency"),
                item.get("interval"),
            ] if value is not None and str(value) != "nan"
        )
        location_parts = []
        for value in (item.get("location"), item.get("country")):
            cleaned = clean(value)
            if cleaned and cleaned.lower() not in {x.lower() for x in location_parts}:
                location_parts.append(cleaned)
        jobs.append(_job(
            str(item.get("site") or "Major job site").title(),
            item.get("id") or apply_url, item.get("title"), item.get("company"),
            ", ".join(location_parts), item.get("description"), apply_url,
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


def _section_heading(line: str) -> bool:
    normalized = line.lower().strip(" :")
    return normalized in {
        "job description", "essential responsibilities", "responsibilities",
        "position requirements", "requirements", "qualifications",
        "minimum qualifications", "preferred qualifications", "education",
        "experience", "benefits", "compensation", "about us",
    }


def requirements(description, limit=8):
    chunks = re.split(r"[\n•]+|(?<=[.!?])\s+", description)
    signals = ("require", "qualification", "experience", "phd", "master", "bachelor",
               "degree", "proficien", "knowledge", "skill", "must", "years",
               "ability", "expert", "familiar", "python", "c++", "robot")
    result = []
    for chunk in chunks:
        line = re.sub(r"\s+", " ", chunk).strip(" -–—:")
        if (not _section_heading(line) and 10 <= len(line) <= 280
                and any(s in line.lower() for s in signals)):
            if line not in result:
                result.append(line)
        if len(result) == limit:
            break
    return result


def experience(description, limit=6):
    chunks = re.split(r"[\n•]+|(?<=[.!?])\s+", description)
    signals = ("experience", "entry level",
               "phd", "master", "bachelor", "degree", "postdoc")
    found = []
    for chunk in chunks:
        line = re.sub(r"\s+", " ", chunk).strip(" -–—:")
        if (not _section_heading(line) and 10 <= len(line) <= 280
                and any(s in line.lower() for s in signals)):
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


def annual_salary_bounds(job):
    """Return disclosed annualized numeric bounds, or None when unusable."""
    evidence = salary_evidence(job)
    if not evidence or evidence == "Not disclosed in the posting":
        return None
    matches = re.findall(
        r"(?<![A-Za-z0-9])(?:(?:\x24|\u20ac|\u00a3)\s*)?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*([kK]?)",
        evidence,
    )
    values = []
    for raw, suffix in matches:
        value = float(raw.replace(",", ""))
        if suffix:
            value *= 1000
        values.append(value)
    if not values:
        return None
    lowered = evidence.lower()
    if any(term in lowered for term in ("/hour", "/hr", "per hour", "hourly")):
        values = [value * 2080 for value in values]
    elif any(term in lowered for term in ("/month", "per month", "monthly")):
        values = [value * 12 for value in values]
    elif any(term in lowered for term in ("/week", "per week", "weekly")):
        values = [value * 52 for value in values]
    elif any(term in lowered for term in ("/day", "per day", "daily")):
        values = [value * 260 for value in values]
    elif max(values) < 1000:
        return None
    return round(min(values)), round(max(values))


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
        explicit_country = any(
            re.search(rf"\b{re.escape(alias)}\b", value) for alias in aliases
        )
        us_state_location = (
            requested == "united states"
            and bool(re.search(r",\s*(?:" + "|".join(sorted(US_STATE_CODES)) + r")\b", location, re.I))
        )
        if not explicit_country and not us_state_location:
            return False
    return True


def rank(jobs, query, limit=30, country="", city="", max_age_days=MAX_AGE_DAYS,
         education="PhD", include_diagnostics=False, resume_profile=None,
         search_type="Jobs", minimum_salary=0):
    if education not in EDUCATION_LEVELS:
        raise ValueError(f"Education must be one of: {', '.join(EDUCATION_LEVELS)}")
    if search_type not in {"Jobs", "Internships"}:
        raise ValueError("Search type must be Jobs or Internships.")
    if not 0 <= int(minimum_salary) <= 500_000:
        raise ValueError("Minimum salary must be between 0 and 500000.")
    minimum_salary = int(minimum_salary)
    words = {w for w in re.findall(r"[a-z0-9+#.]{2,}", query.lower()) if w not in STOP}
    query_text = query.lower()
    requested_concepts = {}
    covered_query_terms = set()
    for name, terms in CONCEPTS.items():
        query_evidence = {
            term for term in terms
            if re.search(rf"\b{re.escape(term)}\b", query_text)
        }
        if (name not in {"research"} and query_evidence
                and not query_evidence.issubset(covered_query_terms)):
            requested_concepts[name] = terms
            covered_query_terms.update(query_evidence)
    requested_concepts[f"education: {education}"] = EDUCATION_TERMS[education]
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
        education_key = f"education: {education}"
        if (search_type == "Internships" and education_key not in job["concept_evidence"]
                and re.search(r"\b(?:currently pursuing|enrolled in|graduate student|graduate program|degree program|doctoral candidate)\b", body)):
            job["concept_evidence"][education_key] = ["student eligibility"]
        robotics_evidence = job["concept_evidence"].get("robotics", [])
        robotics_occurrences = sum(
            len(re.findall(rf"\b{re.escape(term)}\b", body))
            for term in CONCEPTS["robotics"]
        )
        title_has_robotics = any(
            re.search(rf"\b{re.escape(term)}\b", title)
            for term in CONCEPTS["robotics"]
        )
        strong_robotics_evidence = set(robotics_evidence) & STRONG_ROBOTICS
        technical_title = bool(re.search(
            r"\b(?:engineer|engineering|scientist|research|developer|software|hardware|"
            r"computer vision|machine learning|perception|controls?|autonomy|technical)\b",
            title,
        ))
        job["robotics_role_evidence"] = (
            title_has_robotics
            or (technical_title and len(strong_robotics_evidence) >= 2)
        )
        job["keyword_coverage"] = (
            len(job["matched_keywords"]) / len(words) if words else 1.0
        )
        job["match_score"] = (
            10 * len(job["concept_evidence"])
            + len(job["matched_keywords"])
            + 3 * len(words & title_tokens)
        )
        job["role_overview"] = role_overview(job["description"])
        job["requirements"] = requirements(job["description"])
        job["experience"] = experience(job["description"])
        job["salary_display"] = salary_evidence(job)
        salary_bounds = annual_salary_bounds(job)
        job["salary_min_annual"] = salary_bounds[0] if salary_bounds else None
        job["salary_max_annual"] = salary_bounds[1] if salary_bounds else None
        job["_published_dt"] = published_datetime(job["published"])
        job["age_days"] = (
            (datetime.now(timezone.utc) - job["_published_dt"]).days
            if job["_published_dt"] else None
        )
        job["_robotics_match"] = bool(body_tokens & ROBOTICS)
        internship_terms = {"intern", "internship", "internships", "co-op", "coop", "trainee"}
        job["internship_evidence"] = bool(title_tokens & internship_terms) or bool(
            re.search(r"\b(?:intern(?:ship)?s?|co[- ]?op|trainee)\b", title)
        ) or any(
            term in str(job.get("job_type") or "").lower() for term in internship_terms
        )
        job["city_match"] = bool(
            city.strip() and city.strip().lower() in job["location"].lower()
        )
        job["resume_fit"] = score_job_fit(job, resume_profile)
        resume_score = job["resume_fit"]["score"] if job["resume_fit"] else 0
        query_score = min(100, job["match_score"] * 5)
        job["personalized_score"] = round(
            0.65 * resume_score + 0.25 * query_score
            + (10 if job["city_match"] else 0), 1
        ) if resume_profile else None
    diagnostics = {
        "normalized_unique": len(unique), "missing_requested_concept": 0,
        "weak_domain_evidence": 0,
        "insufficient_keyword_coverage": 0, "missing_or_invalid_date": 0,
        "outside_age_window": 0, "country_mismatch": 0, "search_type_mismatch": 0,
        "salary_missing_or_unusable": 0, "salary_below_minimum": 0,
        "eligible": 0,
        "requested_concepts": sorted(requested_concepts),
    }
    minimum_coverage = 0.5
    matched, near_matches = [], []
    now = datetime.now(timezone.utc)
    for job in unique.values():
        reasons = []
        wrong_search_type = (
            search_type == "Internships" and not job["internship_evidence"]
        ) or (search_type == "Jobs" and job["internship_evidence"])
        if wrong_search_type:
            reasons.append("search type mismatch")
            diagnostics["search_type_mismatch"] += 1
        hard_concepts = [
            concept for concept in requested_concepts
            if not (search_type == "Internships" and concept.startswith("education:"))
        ]
        if not all(c in job["concept_evidence"] for c in hard_concepts):
            reasons.append("missing requested concept")
            diagnostics["missing_requested_concept"] += 1
        if "robotics" in requested_concepts and not job["robotics_role_evidence"]:
            reasons.append("robotics mentioned only incidentally")
            diagnostics["weak_domain_evidence"] += 1
        if not requested_concepts and job["keyword_coverage"] < minimum_coverage:
            reasons.append("insufficient keyword coverage")
            diagnostics["insufficient_keyword_coverage"] += 1
        if minimum_salary > 0 and job["salary_max_annual"] is None:
            reasons.append("salary missing or unusable")
            diagnostics["salary_missing_or_unusable"] += 1
        elif minimum_salary > 0 and job["salary_max_annual"] < minimum_salary:
            reasons.append("salary below minimum")
            diagnostics["salary_below_minimum"] += 1
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
    if resume_profile:
        ranked = sorted(
            matched,
            key=lambda j: (j["personalized_score"], j["_published_dt"],
                           j["city_match"], j["match_score"]),
            reverse=True,
        )[:limit]
    else:
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
                max_age_days=MAX_AGE_DAYS, education="PhD", resume_profile=None,
                search_type="Jobs", minimum_salary=100_000):
    if not country.strip():
        raise ValueError("Country is required. City is optional.")
    if education not in EDUCATION_LEVELS:
        raise ValueError(f"Education must be one of: {', '.join(EDUCATION_LEVELS)}")
    if not 1 <= int(max_age_days) <= 90:
        raise ValueError("Maximum posting age must be between 1 and 90 days.")
    if not 0 <= int(minimum_salary) <= 500_000:
        raise ValueError("Minimum salary must be between 0 and 500000.")
    max_age_days = int(max_age_days)
    has_intern_term = bool(re.search(r"\b(?:intern(?:ship)?s?|co[- ]?op|trainee)\b", query, re.I))
    source_query = (f"{query} intern" if search_type == "Internships" and not has_intern_term
                    else query if search_type == "Internships"
                    else f"{query} {education}").strip()
    if search_type == "Internships":
        internship_queries = [source_query]
        query_lower = query.lower()
        for focused in (
            "robotics intern" if any(x in query_lower for x in ROBOTICS) else "",
            "computer vision intern" if "computer vision" in query_lower else "",
            "machine learning intern" if any(x in query_lower for x in ("machine learning", " ai ")) else "",
        ):
            if focused and focused not in internship_queries:
                internship_queries.append(focused)
        sources = [
            (f"Major internship sites {index}",
             lambda _q, focused=focused: top_job_sites(
                 focused, country, city, max_age_days, results_wanted=50))
            for index, focused in enumerate(internship_queries[:3], 1)
        ]
    else:
        sources = [("Remotive", remotive), ("Jobicy", jobicy),
                   ("Arbeitnow", arbeitnow), ("Remote OK", remoteok),
                   ("LinkedIn / Indeed / Google",
                    lambda q: top_job_sites(q, country, city, max_age_days))]
    jobs, errors = [], []
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = {}
        for name, fetcher in sources:
            log(f"[source agent: {name}] searching live listings...")
            futures[pool.submit(fetcher, source_query)] = name
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
        jobs, query, max_results, country, city, max_age_days, education,
        include_diagnostics=True, resume_profile=resume_profile, search_type=search_type,
        minimum_salary=minimum_salary
    )
    return {"jobs": ranked, "diagnostics": diagnostics,
            "near_matches": near_matches, "source_errors": errors,
            "search_links": major_search_links(source_query, location),
            "country": country.strip(), "city": city.strip(),
            "education": education, "search_type": search_type,
            "max_age_days": max_age_days, "minimum_salary": int(minimum_salary),
            "fetched_count": len(jobs),
            "resume_personalized": bool(resume_profile),
            "resume_summary": ({
                "summary": resume_profile.get("summary", ""),
                "skills": resume_profile.get("skills", [])[:20],
                "domains": resume_profile.get("domains", [])[:10],
                "source_statuses": [
                    {"kind": item.get("kind"), "status": item.get("status")}
                    for item in resume_profile.get("sources", [])
                ],
            } if resume_profile else None),
            "generated_at": datetime.now(timezone.utc).isoformat()}


def build_report(query, result):
    jobs = result["jobs"]
    ranking_label = "Resume fit → recency" if result.get("resume_personalized") else "Newest → oldest"
    lines = [
        "# ✦ jobSearch Intelligence Report",
        "",
        f"> **Search mission:** {query}  ",
        f"> **Search type:** {result.get('search_type', 'Jobs')}  ",
        f"> **Country:** {result.get('country') or 'Any'} · "
        f"**City:** {result.get('city') or 'Any'}  ",
        f"> **Education:** {result.get('education', 'PhD')}  ",
        f"> **Minimum annual salary:** {result.get('minimum_salary', 0):,}  ",
        f"> **Generated:** {result['generated_at']}  ",
        f"> **Policy:** close concept match · robotics-domain gate · "
        f"≤ {result['max_age_days']} days old · salary ≥ {result.get('minimum_salary', 0):,} · {ranking_label}",
        "",
        "| Live listings scanned | Verified matches | Maximum age | Ranking |",
        "|---:|---:|---:|:---|",
        f"| {result['fetched_count']} | {len(jobs)} | "
        f"{result['max_age_days']} days | {ranking_label} |",
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
            f"| Salary missing or unusable | {result['diagnostics']['salary_missing_or_unusable']} |",
            f"| Salary below selected minimum | {result['diagnostics']['salary_below_minimum']} |",
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
            *(
                [f"**🎯 Estimated resume fit**  \n{job['resume_fit']['score']}% — "
                 + (", ".join(job['resume_fit'].get("matched_skills", [])[:8])
                    or "limited direct skill overlap"), ""]
                if job.get("resume_fit") else []
            ),
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
            job.get("role_overview") or "The source did not supply a description.",
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
        f"- The selected education filter is **{result.get('education', 'PhD')}** "
        "and must be supported by the posting text.",
        f"- Undated listings and listings older than "
        f"{result['max_age_days']} days are excluded.",
        "- Country is mandatory. City is optional and used only as a preference; "
        "jobs elsewhere in the selected country remain eligible.",
        f"- Listings must disclose an annualized salary range reaching at least {result.get('minimum_salary', 0):,}; set the filter to 0 to include undisclosed salaries.",
        "- Hourly, daily, weekly, and monthly pay is annualized with fixed work-year multipliers; currencies are not converted.",
        "- Salary and experience text is quoted or extracted from the source posting; missing information is labeled rather than guessed.",
        "- Apply links always open the original source. Applications are never "
        "submitted automatically and credentials are never collected.",
    ]
    if result["source_errors"]:
        lines += ["", "## Source errors", ""] + [f"- {e}" for e in result["source_errors"]]
    return "\n".join(lines)
    if education not in EDUCATION_LEVELS:
        raise ValueError(f"Education must be one of: {', '.join(EDUCATION_LEVELS)}")
