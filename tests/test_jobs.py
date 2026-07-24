from datetime import datetime, timedelta, timezone

import core.jobs as jobs


def listing(title, description, *, location="Boston, MA", days_old=0):
    published = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    return jobs._job(
        "Test", title, title, "Example", location, description,
        "https://example.com/apply", published,
    )


def test_clean_removes_html_and_markdown_escapes():
    raw = r"<h2>Job Description</h2><p>Build **robotics** systems \& tools.</p>"
    cleaned = jobs.clean(raw)
    assert "<h2>" not in cleaned
    assert "**" not in cleaned
    assert "robotics" in cleaned
    assert "& tools" in cleaned


def test_us_state_location_satisfies_country_gate():
    assert jobs.location_matches("Boston, MA", "United States")
    assert jobs.location_matches("Austin, TX, US", "United States")
    assert not jobs.location_matches("Berlin, Germany", "United States")


def test_jobs_mode_excludes_internships():
    description = "PhD robotics engineer developing robot manipulation and motion planning."
    regular = listing("Robotics Engineer", description)
    internship = listing("Robotics Engineering Intern", description)

    ranked, diagnostics, _ = jobs.rank(
        [regular, internship], "robotics", country="United States",
        education="PhD", search_type="Jobs", include_diagnostics=True,
    )

    assert [job["title"] for job in ranked] == ["Robotics Engineer"]
    assert diagnostics["search_type_mismatch"] == 1


def test_internship_mode_accepts_graduate_eligibility_without_literal_phd():
    internship = listing(
        "Computer Vision Robotics Research Intern",
        "Currently pursuing a graduate degree program. Develop computer vision, "
        "robot manipulation, motion planning, and autonomous systems.",
    )

    ranked, diagnostics, _ = jobs.rank(
        [internship], "computer vision robotics research engineer",
        country="United States", education="PhD", search_type="Internships",
        include_diagnostics=True,
    )

    assert [job["title"] for job in ranked] == [
        "Computer Vision Robotics Research Intern"
    ]
    assert diagnostics["requested_concepts"] == [
        "artificial intelligence", "education: PhD", "robotics"
    ]


def test_incidental_robotics_marketing_role_is_rejected():
    internship = listing(
        "Social Media and Video Production Intern",
        "Currently pursuing a graduate degree. Create marketing content about "
        "robot manipulation, motion planning, autonomous systems, and computer vision.",
    )

    ranked, diagnostics, _ = jobs.rank(
        [internship], "computer vision robotics", country="United States",
        education="PhD", search_type="Internships", include_diagnostics=True,
    )

    assert ranked == []
    assert diagnostics["weak_domain_evidence"] == 1


def test_stale_and_wrong_country_jobs_fail_hard_gates():
    stale = listing(
        "Robotics Engineer", "PhD robot manipulation and motion planning.",
        days_old=20,
    )
    foreign = listing(
        "Robotics Research Scientist", "PhD robot manipulation and motion planning.",
        location="Berlin, Germany",
    )

    ranked, diagnostics, _ = jobs.rank(
        [stale, foreign], "robotics", country="United States",
        max_age_days=10, education="PhD", search_type="Jobs",
        include_diagnostics=True,
    )

    assert ranked == []
    assert diagnostics["outside_age_window"] == 1
    assert diagnostics["country_mismatch"] == 1


def test_internship_search_uses_focused_major_site_queries(monkeypatch):
    calls = []
    result_job = listing(
        "Robotics Research Intern",
        "Graduate degree program. Computer vision, robot manipulation, "
        "motion planning, and autonomous systems.",
    )

    def fake_sites(query, country, city, age, results_wanted=75):
        calls.append(query)
        return [result_job.copy()] if query == "robotics intern" else []

    monkeypatch.setattr(jobs, "top_job_sites", fake_sites)
    result = jobs.search_jobs(
        "computer vision robotics research engineer",
        country="United States", education="PhD", search_type="Internships",
    )

    assert calls == [
        "computer vision robotics research engineer intern",
        "robotics intern",
        "computer vision intern",
    ]
    assert len(result["jobs"]) == 1
    assert result["source_errors"] == []
