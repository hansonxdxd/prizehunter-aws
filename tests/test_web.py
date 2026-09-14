import copy
import json
from pathlib import Path

import pytest

from prizehunter_aws import web


def test_web_executes_strands_replay_without_network(monkeypatch, tmp_path):
    import socket

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("No network in the test build"))
    web.demo_result.cache_clear()
    status, mime, data = web.dispatch("GET", "/api/result", b"", tmp_path)
    result = json.loads(data)
    assert status == 200 and mime == "application/json"
    assert result["mode"] == "offline_synthetic_replay"
    assert "OFFLINE VERIFIED" in result["display_mode"]
    assert result["execution"]["model_calls"] == 4


def test_watch_browser_walkthrough_persists_and_deduplicates(tmp_path):
    results = []
    for action in ["first", "same", "changed", "same_changed", "failure"]:
        status, _, data = web.dispatch(
            "POST", "/api/watch", json.dumps({"action": action}).encode(), tmp_path
        )
        assert status == 200
        results.append(json.loads(data))
    assert [len(r["pending_decisions"]) for r in results] == [1, 0, 1, 0, 0]
    assert results[-1]["baseline_updated"] is False
    assert all(r["organizer_change_observed"] is False for r in results)
    assert all(r["notifications_sent"] == 0 for r in results)
    assert json.loads((tmp_path / "judge-watch.json").read_text())["opportunities"]


def test_browser_routes_cannot_call_paid_model_or_arbitrary_files(tmp_path):
    for path in ["/api/live", "/api/fetch", "/.env", "/../../etc/passwd"]:
        status, _, _ = web.dispatch("POST", path, b"{}", tmp_path)
        assert status == 404
    with pytest.raises(ValueError):
        web.dispatch("POST", "/api/watch", b'{"action":"../some-state"}', tmp_path)


def test_saved_artifact_requires_live_provenance(monkeypatch, tmp_path):
    monkeypatch.setattr(web, "ASSETS", tmp_path)
    (tmp_path / "saved-live.json").write_text(json.dumps(web.demo_result()))
    with pytest.raises(ValueError, match="no verified live provenance"):
        web.baseline()


def test_saved_live_display_never_claims_fresh_inference(monkeypatch, tmp_path):
    artifact = copy.deepcopy(web.demo_result())
    # Controlled unit test of display labeling; this is not a live evidence fixture.
    artifact.update(mode="live_bedrock", verification={"level": "LIVE VERIFIED"})
    (tmp_path / "saved-live.json").write_text(json.dumps(artifact))
    monkeypatch.setattr(web, "ASSETS", tmp_path)
    assert web.baseline()["display_mode"] == "SAVED LIVE RESULT — no new model call"


def test_assets_are_packaged_and_untrusted_content_uses_text_content(tmp_path):
    status, _, html = web.dispatch("GET", "/", b"", tmp_path)
    assert status == 200
    assert b"innerHTML" not in html
    assert b"CONTROLLED TEST" in html
    assert Path(web.ASSETS / "architecture.svg").is_file()
