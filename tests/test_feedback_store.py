import json
from pathlib import Path

from utils import feedback_store


def test_feedback_store_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)
    entry = {
        "report_title": "ESG Test Report",
        "rating": "Excellent",
        "comment": "Very useful and actionable.",
    }

    saved = feedback_store.save_feedback(entry, username="tester")
    assert saved["rating"] == "Excellent"
    assert saved["username"] == "tester"
    assert "timestamp" in saved

    loaded = feedback_store.load_feedback("tester")
    assert isinstance(loaded, list)
    assert loaded[0]["comment"] == entry["comment"]

    recent = feedback_store.load_recent_feedback(limit=5)
    assert recent[0]["report_title"] == "ESG Test Report"

    file_path = tmp_path / "tester.json"
    assert file_path.exists()
    with file_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert data[0]["rating"] == "Excellent"
