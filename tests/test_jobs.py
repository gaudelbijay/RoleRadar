from datetime import datetime, timedelta, timezone

import pytest
import core.jobs as jobs
from rl_scheduler.replay import load_scenario


def listing(title, description, *, location="Boston, MA", days_old=0, salary=""):
    published = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    return jobs._job(
        "Test", title, title, "Example", location, description,
        "https://example.com/apply", published, salary,
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
        minimum_salary=0,
    )

    assert sorted(calls) == sorted([
        "computer vision robotics research engineer intern",
        "robotics intern",
        "computer vision intern",
    ])
    assert len(result["jobs"]) == 1
    assert result["ranking_mode"] == "bm25"
    assert result["source_errors"] == []


def test_default_rl_scheduler_stops_after_verified_yield_and_can_record(monkeypatch, tmp_path):
    calls = []
    result_job = listing(
        "Robotics Engineer",
        "PhD robotics engineer building robot manipulation and motion planning systems.",
    )

    def productive(name):
        def fetch(*_args, **_kwargs):
            calls.append(name)
            item = result_job.copy()
            item["id"] = f"Test:{name}"
            return [item]
        return fetch

    monkeypatch.setattr(jobs, "remotive", productive("remotive"))
    monkeypatch.setattr(jobs, "jobicy", productive("jobicy"))
    monkeypatch.setattr(jobs, "arbeitnow", productive("arbeitnow"))
    monkeypatch.setattr(jobs, "remoteok", productive("remoteok"))
    monkeypatch.setattr(jobs, "top_job_sites", productive("major"))
    monkeypatch.setenv("JOBSEARCH_RL_TARGET_RESULTS", "1")
    monkeypatch.setenv("JOBSEARCH_RL_MIN_RESULTS", "1")

    result = jobs.search_jobs(
        "robotics engineer", country="United States", education="PhD",
        minimum_salary=0, record_scenario_path=tmp_path / "scenario.json",
    )

    assert set(calls) == {"major", "remotive"}
    assert result["source_scheduler"]["mode"] == "rl"
    assert result["source_scheduler"]["launched_agents"] == 2
    assert result["source_scheduler"]["skipped_agents"] == 3
    assert result["scheduler_trace"]
    recorded = load_scenario(tmp_path / "scenario.json")
    assert recorded["query"] == "robotics engineer"
    assert {source["name"] for source in recorded["sources"]} == {
        "LinkedIn / Indeed / Google", "Remotive"
    }


def test_annual_salary_bounds_parse_k_and_hourly_pay():
    annual = listing(
        "Robotics Engineer", "PhD robot manipulation and motion planning.",
        salary="80k - 120k USD yearly",
    )
    hourly = listing(
        "Controls Engineer", "PhD robot manipulation and motion planning.",
        salary="USD 50 - 60 /hour",
    )

    assert jobs.annual_salary_bounds(annual) == (80_000, 120_000)
    assert jobs.annual_salary_bounds(hourly) == (104_000, 124_800)


def test_minimum_salary_rejects_missing_and_below_threshold():
    high = listing(
        "Robotics Engineer", "PhD robot manipulation and motion planning.",
        salary="110000 - 140000 USD yearly",
    )
    low = listing(
        "Robotics Research Scientist", "PhD robot manipulation and motion planning.",
        salary="70000 - 90000 USD yearly",
    )
    missing = listing(
        "Robotics Software Engineer", "PhD robot manipulation and motion planning.",
    )

    ranked, diagnostics, _ = jobs.rank(
        [high, low, missing], "robotics", country="United States",
        education="PhD", search_type="Jobs", minimum_salary=100_000,
        include_diagnostics=True,
    )

    assert [job["title"] for job in ranked] == ["Robotics Engineer"]
    assert diagnostics["salary_below_minimum"] == 1
    assert diagnostics["salary_missing_or_unusable"] == 1


def test_zero_minimum_salary_keeps_undisclosed_jobs():
    missing = listing(
        "Robotics Engineer", "PhD robot manipulation and motion planning.",
    )

    ranked = jobs.rank(
        [missing], "robotics", country="United States", education="PhD",
        search_type="Jobs", minimum_salary=0,
    )

    assert len(ranked) == 1


def test_bm25_failure_falls_back_to_deterministic_ranking(monkeypatch):
    first = listing(
        "Robotics Engineer", "PhD robot manipulation and motion planning.",
        days_old=0,
    )
    second = listing(
        "Robotics Scientist", "PhD robotics perception and autonomous systems.",
        days_old=1,
    )

    def unavailable(_query, _jobs):
        raise RuntimeError("not installed")

    monkeypatch.setattr(jobs, "bm25_score_jobs", unavailable)
    ranked, diagnostics, _ = jobs.rank(
        [first, second], "robotics", country="United States", education="PhD",
        ranking_mode="bm25", include_diagnostics=True,
    )

    assert [item["title"] for item in ranked] == ["Robotics Engineer", "Robotics Scientist"]
    assert diagnostics["ranking_mode_requested"] == "bm25"
    assert diagnostics["ranking_mode_active"] == "deterministic"
    assert diagnostics["ranking_fallback"] is True


def test_unknown_ranking_mode_is_rejected():
    with pytest.raises(ValueError, match="Ranking mode"):
        jobs.rank([], "robotics", ranking_mode="mystery")


def test_semantic_mode_orders_eligible_jobs_by_cosine_score(monkeypatch):
    recent = listing(
        "Robotics Engineer", "PhD robot manipulation and motion planning.",
        days_old=0,
    )
    older = listing(
        "Robotics Scientist", "PhD robotics perception and autonomous systems.",
        days_old=1,
    )
    monkeypatch.setattr(jobs, "semantic_score_jobs", lambda _query, _jobs: [0.1, 0.9])

    ranked, diagnostics, _ = jobs.rank(
        [recent, older], "robotics", country="United States", education="PhD",
        ranking_mode="semantic", include_diagnostics=True,
    )

    assert [item["title"] for item in ranked] == ["Robotics Scientist", "Robotics Engineer"]
    assert ranked[0]["semantic_score"] == pytest.approx(0.9)
    assert diagnostics["ranking_mode_active"] == "semantic"
    assert diagnostics["ranking_fallback"] is False


def test_semantic_failure_falls_back_to_bm25(monkeypatch):
    first = listing(
        "Robotics Engineer", "PhD robot manipulation and motion planning.",
        days_old=0,
    )
    second = listing(
        "Robotics Scientist", "PhD robotics perception and autonomous systems.",
        days_old=1,
    )

    def unavailable(_query, _jobs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(jobs, "semantic_score_jobs", unavailable)
    monkeypatch.setattr(jobs, "bm25_score_jobs", lambda _query, _jobs: [0.2, 0.8])
    ranked, diagnostics, _ = jobs.rank(
        [first, second], "robotics", country="United States", education="PhD",
        ranking_mode="semantic", include_diagnostics=True,
    )

    assert [item["title"] for item in ranked] == ["Robotics Scientist", "Robotics Engineer"]
    assert diagnostics["ranking_mode_requested"] == "semantic"
    assert diagnostics["ranking_mode_active"] == "bm25"
    assert diagnostics["ranking_fallback"] is True
    assert diagnostics["ranking_fallback_from"] == "semantic"


def test_hybrid_mode_fuses_bm25_and_semantic_rank_positions(monkeypatch):
    first = listing("Robotics Engineer", "PhD robot manipulation and motion planning.", days_old=0)
    consensus = listing("Robotics Scientist", "PhD robotics perception and autonomous systems.", days_old=1)
    third = listing("Robotics Developer", "PhD robot controls, manipulation, and ROS.", days_old=2)
    monkeypatch.setattr(jobs, "bm25_score_jobs", lambda _query, _jobs: [0.9, 0.8, 0.7])
    monkeypatch.setattr(jobs, "semantic_score_jobs", lambda _query, _jobs: [0.1, 0.9, 0.8])

    ranked, diagnostics, _ = jobs.rank(
        [first, consensus, third], "robotics", country="United States",
        education="PhD", ranking_mode="hybrid", include_diagnostics=True,
    )

    assert ranked[0]["title"] == "Robotics Scientist"
    assert ranked[0]["bm25_rank"] == 2
    assert ranked[0]["semantic_rank"] == 1
    assert ranked[0]["rrf_score"] == pytest.approx(1 / 62 + 1 / 61)
    assert diagnostics["ranking_mode_active"] == "hybrid"
    assert diagnostics["rrf_k"] == 60
    assert diagnostics["ranking_fallback"] is False


def test_hybrid_mode_uses_available_ranker_when_semantic_fails(monkeypatch):
    first = listing("Robotics Engineer", "PhD robot manipulation and motion planning.", days_old=0)
    second = listing("Robotics Scientist", "PhD robotics perception and autonomous systems.", days_old=1)

    def unavailable(_query, _jobs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(jobs, "semantic_score_jobs", unavailable)
    monkeypatch.setattr(jobs, "bm25_score_jobs", lambda _query, _jobs: [0.1, 0.9])
    ranked, diagnostics, _ = jobs.rank(
        [first, second], "robotics", country="United States", education="PhD",
        ranking_mode="hybrid", include_diagnostics=True,
    )

    assert ranked[0]["title"] == "Robotics Scientist"
    assert diagnostics["ranking_mode_requested"] == "hybrid"
    assert diagnostics["ranking_mode_active"] == "bm25"
    assert diagnostics["ranking_fallback"] is True
    assert diagnostics["ranking_fallback_from"] == "semantic"
    assert diagnostics["rrf_k"] is None


def test_rerank_mode_cross_encodes_only_retrieved_candidates(monkeypatch):
    first = listing("Robotics Engineer", "PhD robot manipulation and motion planning.", days_old=0)
    second = listing("Robotics Scientist", "PhD robotics perception and autonomous systems.", days_old=1)
    third = listing("Robotics Developer", "PhD robot controls, manipulation, and ROS.", days_old=2)
    monkeypatch.setattr(jobs, "bm25_score_jobs", lambda _query, _jobs: [0.9, 0.8, 0.7])
    monkeypatch.setattr(jobs, "semantic_score_jobs", lambda _query, _jobs: [0.9, 0.8, 0.7])
    seen = []

    def cross_scores(_query, candidates):
        seen.extend(item["title"] for item in candidates)
        return [0.1, 0.9, 0.2]

    monkeypatch.setattr(jobs, "cross_encoder_score_jobs", cross_scores)
    ranked, diagnostics, _ = jobs.rank(
        [first, second, third], "robotics", country="United States",
        education="PhD", ranking_mode="rerank", include_diagnostics=True,
    )

    assert seen == ["Robotics Engineer", "Robotics Scientist", "Robotics Developer"]
    assert ranked[0]["title"] == "Robotics Scientist"
    assert ranked[0]["cross_encoder_score"] == pytest.approx(0.9)
    assert ranked[0]["rrf_score"] is not None
    assert diagnostics["ranking_mode_active"] == "rerank"
    assert diagnostics["rerank_candidates"] == 3
    assert diagnostics["ranking_fallback"] is False


def test_cross_encoder_failure_keeps_hybrid_order(monkeypatch):
    first = listing("Robotics Engineer", "PhD robot manipulation and motion planning.", days_old=0)
    second = listing("Robotics Scientist", "PhD robotics perception and autonomous systems.", days_old=1)
    monkeypatch.setattr(jobs, "bm25_score_jobs", lambda _query, _jobs: [0.9, 0.8])
    monkeypatch.setattr(jobs, "semantic_score_jobs", lambda _query, _jobs: [0.9, 0.8])

    def unavailable(_query, _jobs):
        raise RuntimeError("reranker unavailable")

    monkeypatch.setattr(jobs, "cross_encoder_score_jobs", unavailable)
    ranked, diagnostics, _ = jobs.rank(
        [first, second], "robotics", country="United States", education="PhD",
        ranking_mode="rerank", include_diagnostics=True,
    )

    assert ranked[0]["title"] == "Robotics Engineer"
    assert diagnostics["ranking_mode_requested"] == "rerank"
    assert diagnostics["ranking_mode_active"] == "hybrid"
    assert diagnostics["ranking_fallback"] is True
    assert diagnostics["ranking_fallback_from"] == "cross_encoder"
