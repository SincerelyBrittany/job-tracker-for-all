from datetime import datetime, timezone

import fetch_jobs as fj

NOW = datetime.now(timezone.utc)


def job(title, location="Remote (US)", company="Acme", desc="", salary=None, source="Remotive"):
    j = fj.job(source, company, title, location, "https://example.com/x", NOW.isoformat(), salary, desc, True)
    return j


def reason(j):
    return fj.reject_reason(j, NOW)


def test_titles_are_sorted_into_tracks():
    assert fj.classify("SOC Analyst") == "Cyber"
    assert fj.classify("Cloud Engineer") == "Cloud"
    assert fj.classify("Frontend Engineer") == "SWE"
    assert fj.classify("Head Chef") is None


def test_good_remote_job_passes():
    assert reason(job("Frontend Engineer")) is None


def test_seniority_and_excluded_titles():
    assert "excluded" in reason(job("Staff Frontend Engineer"))
    assert "excluded" in reason(job("Senior SOC Analyst"))
    assert "excluded" in reason(job("Software Engineer Intern"))


def test_location_rules():
    assert reason(job("Frontend Engineer", location="Remote - India")) == "non-US location"
    assert reason(job("Frontend Engineer", location="Hybrid - New York")) == "hybrid/on-site"


def test_salary_floor():
    assert reason(job("Frontend Engineer", salary="$50,000 - $60,000")) == "below salary floor"
    assert reason(job("Frontend Engineer", salary="$110,000 - $130,000")) is None


def test_agencies_are_skipped():
    assert reason(job("Frontend Engineer", company="Toptal")) == "marketplace/agency"


def test_scoring_rewards_matching_skills():
    weak = fj.score(job("Frontend Engineer", desc="We like teamwork."), "SWE")[0]
    strong = fj.score(job("Frontend Engineer", desc="React, TypeScript, Node, SQL, AWS, Docker"), "SWE")[0]
    assert strong > weak


def test_years_required():
    assert fj.years_required("Requires 3+ years of professional experience with React.") == 3
    assert fj.years_required("No experience needed.") is None
