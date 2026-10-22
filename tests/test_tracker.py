import json
from pathlib import Path

import pytest

import tracker

SAMPLES = json.loads((Path(__file__).resolve().parents[1] / "examples" / "sample-jobs.json").read_text())


@pytest.fixture(autouse=True)
def temp_tracker(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "PATH", tmp_path / "tracker.xlsx")


def test_add_sample_jobs_and_skip_duplicates(capsys):
    tracker.add([dict(j) for j in SAMPLES])
    first = json.loads(capsys.readouterr().out)
    assert len(first["added"]) == len(SAMPLES)

    tracker.add([dict(j) for j in SAMPLES])
    second = json.loads(capsys.readouterr().out)
    assert not second["added"] and len(second["skipped_duplicates"]) == len(SAMPLES)


def test_duplicate_detected_by_company_and_title_without_link(capsys):
    tracker.add({"Company": "Acme", "Title": "Engineer"})
    tracker.add({"Company": "ACME ", "Title": "engineer"})
    out = capsys.readouterr().out
    assert '"skipped_duplicates": [\n    {' in out


def test_defaults_and_applied_date(capsys):
    tracker.add({"Company": "Acme", "Title": "Engineer", "Link": "https://example.com/1"})
    ws = tracker.init()[tracker.SHEET]
    row = dict(next(tracker.rows(ws))[1])
    assert row["Status"] == "To Review" and row["Date Found"] and row["Track"] in tracker.TRACKS

    tracker.update(2, {"Status": "Applied"})
    ws = tracker.init()[tracker.SHEET]
    assert dict(tracker.rows_by_num(ws, 2))["Date Applied"]


@pytest.mark.parametrize("change", [{"Status": "Maybe"}, {"Track": "Astronaut"}, {"Bogus": 1}])
def test_update_rejects_bad_values(change, capsys):
    tracker.add({"Company": "Acme", "Title": "Engineer"})
    with pytest.raises(SystemExit):
        tracker.update(2, change)


def test_add_rejects_unknown_columns():
    with pytest.raises(SystemExit):
        tracker.add({"Company": "Acme", "Title": "Engineer", "Shoe size": 9})
