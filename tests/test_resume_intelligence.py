from urllib import error

import pytest

import core.resume_intelligence as resume


def test_extract_urls_normalizes_and_deduplicates():
    text = (
        "GitHub github.com/example and https://github.com/example. "
        "Portfolio https://portfolio.example.com/work?tracking=yes"
    )

    assert resume.extract_urls(text) == [
        "https://github.com/example",
        "https://portfolio.example.com/work",
    ]


def test_private_portfolio_address_is_blocked():
    with pytest.raises(ValueError, match="non-global"):
        resume._validate_public_url("http://127.0.0.1/profile")


def test_github_agent_discovers_profile_and_repository_websites(monkeypatch):
    profile = {
        "name": "Example", "bio": "Robotics engineer", "company": "Lab",
        "location": "Boston", "blog": "portfolio.example.com",
    }
    repositories = [{
        "name": "robot", "description": "Motion planning", "fork": False,
        "language": "Python", "topics": ["robotics"],
        "homepage": "https://demo.example.com",
    }]
    responses = iter([profile, repositories])
    monkeypatch.setattr(resume, "_github_json", lambda _url: next(responses))

    result = resume._github_agent("https://github.com/example")

    assert result["status"] == "analyzed"
    assert result["discovered_urls"] == [
        "https://portfolio.example.com",
        "https://demo.example.com",
    ]
    assert result["languages"] == ["Python"]


def test_github_websites_are_fetched_only_with_portfolio_opt_in(monkeypatch):
    portfolio_calls = []

    def fake_github(url):
        return {
            "url": url, "kind": "github", "status": "analyzed",
            "text": "Python robotics",
            "discovered_urls": ["https://portfolio.example.com"],
        }

    def fake_portfolio(url):
        portfolio_calls.append(url)
        return {
            "url": url, "kind": "portfolio", "status": "analyzed",
            "text": "mechanical engineering CAD", "summary": "read",
        }

    monkeypatch.setattr(resume, "_github_agent", fake_github)
    monkeypatch.setattr(resume, "_portfolio_agent", fake_portfolio)

    resume.analyze_candidate(
        "https://github.com/example", use_github=True,
        use_portfolios=False, log=lambda _message: None,
    )
    assert portfolio_calls == []

    result = resume.analyze_candidate(
        "https://github.com/example", use_github=True,
        use_portfolios=True, log=lambda _message: None,
    )
    assert portfolio_calls == ["https://portfolio.example.com"]
    assert any(
        source["url"] == "https://portfolio.example.com"
        for source in result["sources"]
    )


def test_portfolio_timeout_has_friendly_message(monkeypatch):
    class BrokenOpener:
        def open(self, *_args, **_kwargs):
            raise error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr(resume, "_validate_public_url", lambda _url: None)
    monkeypatch.setattr(
        resume.request, "build_opener", lambda *_args: BrokenOpener()
    )

    result = resume._portfolio_agent("https://portfolio.example.com")

    assert result["status"] == "blocked"
    assert "did not respond in time" in result["summary"]
    assert "urlopen" not in result["summary"]
