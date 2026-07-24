import core.company_people as people


def job(**overrides):
    value = {
        "company": "Example Robotics",
        "company_url": "https://example.com",
        "apply_url": "https://linkedin.com/jobs/1",
    }
    value.update(overrides)
    return value


def test_explicit_official_url_wins_and_aggregators_are_blocked():
    assert people.official_company_url(job()) == "https://example.com/"
    assert people.official_company_url(job(company_url="")) == ""
    assert people.official_company_url(job(
        company_url="", apply_url="https://jobs.example.org/opening/1"
    )) == "https://jobs.example.org/"


def test_json_ld_extracts_technical_people_and_official_profiles():
    page = """
    <script type="application/ld+json">
    {"@type":"Person","name":"Ada Example","jobTitle":"VP Engineering",
     "url":"https://example.com/team/ada"}
    </script>
    <script type="application/ld+json">
    {"@type":"Person","name":"Sam Example","jobTitle":"Chief Financial Officer"}
    </script>
    """

    result = people.extract_people(page, "https://example.com/team")

    assert result == [{
        "name": "Ada Example",
        "title": "VP Engineering",
        "technical_area": "Engineering leadership",
        "official_profile_url": "https://example.com/team/ada",
        "source_url": "https://example.com/team",
        "bio": "",
        "bio": "",
        "public_links": [],
        "hiring_manager": False,
        "hiring_manager": False,
    }]


def test_team_card_marks_only_explicit_hiring_manager():
    page = """
    <div class="team-member">
      <h3><a href="/people/grace">Grace Hopper</a></h3>
      <p>Engineering Hiring Manager</p>
    </div>
    <div class="team-member">
      <h3>Alan Turing</h3>
      <p>Director of AI Research</p>
    </div>
    """

    result = people.extract_people(page, "https://example.com/team")
    by_name = {item["name"]: item for item in result}

    assert by_name["Grace Hopper"]["hiring_manager"] is True
    assert by_name["Grace Hopper"]["official_profile_url"] == "https://example.com/people/grace"
    assert by_name["Alan Turing"]["hiring_manager"] is False


def test_research_company_scans_discovered_official_pages(monkeypatch):
    home = '<a href="/team">Engineering Team</a>'
    team = '<div class="team-member"><h3>Ada Example</h3><p>Robotics Engineer</p></div>'
    pages = {
        "https://example.com/": home,
        "https://example.com/team": team,
    }
    monkeypatch.setattr(people, "_fetch_html", lambda url: pages[url])

    result = people.research_company(job())

    assert result["status"] == "analyzed"
    assert result["pages_scanned"] == 2
    assert [item["name"] for item in result["people"]] == ["Ada Example"]


def test_research_all_deduplicates_the_same_company(monkeypatch):
    calls = []

    def fake_research(item, log=lambda _message: None):
        calls.append(item["company"])
        return {"company": item["company"], "status": "analyzed", "official_url": "",
                "people": [], "pages_scanned": 0, "note": ""}

    monkeypatch.setattr(people, "research_company", fake_research)
    result = people.research_all_companies([job(), job()])

    assert calls == ["Example Robotics"]
    assert len(result) == 1


def test_explicit_hiring_manager_can_come_from_job_posting():
    result = people.research_company(job(
        company_url="",
        description="The hiring manager is Katherine Johnson, Director of Engineering.",
    ))

    assert result["status"] == "analyzed"
    assert result["people"][0]["name"] == "Katherine Johnson"
    assert result["people"][0]["hiring_manager"] is True


def test_extracts_bio_public_github_and_portfolio_but_not_arbitrary_social_links():
    page = """
    <div class="team-member">
      <h3><a href="/people/ada">Ada Example</a></h3>
      <p>Robotics Research Engineer</p>
      <p>Ada develops robot-learning systems for manipulation and autonomous inspection.</p>
      <a href="https://github.com/ada-example">GitHub</a>
      <a href="https://ada.dev">Personal website</a>
      <a href="https://facebook.com/ada">Facebook</a>
    </div>
    """
    person = people.extract_people(page, "https://example.com/team")[0]
    assert "robot-learning systems" in person["bio"]
    assert person["public_links"] == [
        {"label": "GitHub", "url": "https://github.com/ada-example"},
        {"label": "Portfolio", "url": "https://ada.dev/"},
    ]


def test_company_contacts_keep_generic_addresses_and_same_host_pages_only():
    page = """
    <a href="mailto:careers@example.com">Careers</a>
    <a href="mailto:ada.personal@gmail.com">Ada</a>
    <a href="/careers">Join us</a>
    <a href="https://evil.example/jobs">Jobs elsewhere</a>
    """
    result = people.extract_company_contacts(page, "https://example.com/")
    assert result["generic_emails"] == ["careers@example.com"]
    assert result["contact_urls"] == ["https://example.com/careers"]


def test_json_ld_includes_public_bio_and_github_same_as_only():
    page = """
    <script type="application/ld+json">
    {"@type":"Person","name":"Ada Example","jobTitle":"Robotics Scientist",
     "description":"Leads research in dexterous manipulation.",
     "sameAs":["https://github.com/ada-example","https://linkedin.com/in/ada"]}
    </script>
    """
    person = people.extract_people(page, "https://example.com/team")[0]
    assert person["bio"] == "Leads research in dexterous manipulation."
    assert person["public_links"] == [
        {"label": "GitHub", "url": "https://github.com/ada-example"}
    ]
