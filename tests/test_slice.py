import copy
import hashlib
import importlib.metadata
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from prizehunter_aws.cli import main
from prizehunter_aws.demo import NOW, URL, replay_runtime, scenario
from prizehunter_aws.pipeline import run_analysis, validate_record
from prizehunter_aws.retrieval import PublicRetriever, canonical_url, make_source, verify_bundle
from prizehunter_aws.retrieval_worker import Reader, resolve_public
from prizehunter_aws.runtime import (
    ReplayModel,
    ReplayStep,
    ResearchTools,
    StrandsRuntime,
    configured_bedrock,
)
from prizehunter_aws.search import ReplaySearch, SearchResult, UnavailableSearch
from prizehunter_aws.watch import run_once


def analysis(country="Canada", revision=1):
    goal, bundle, drafts = scenario(country, revision)
    runtime = replay_runtime(bundle, drafts)
    return run_analysis(goal, [URL], runtime, now=NOW), runtime


def test_real_strands_tool_loop_and_core_gates():
    result, runtime = analysis()
    assert importlib.metadata.version("strands-agents") == "1.55.1"
    assert len(runtime.model.seen_results) == 1
    assert "Build a working prototype" in json.dumps(runtime.model.seen_results[0])
    assert result["eligibility"]["overall_status"] == "uncertain"
    assert result["fit"]["recommendation"] == "verify_first"  # Model draft requested go.
    assert result["plan"]["plan_status"] == "verification_first"
    assert result["plan"]["actions"][0]["requires_human_confirmation"] is True
    assert result["execution"]["model_calls"] == 4
    assert result["execution"]["agent_instances"] == 1
    assert result["execution"]["live_model"] is False


def test_same_competition_different_profile_blocks_both_inferences():
    canada, _ = analysis()
    taiwan, runtime = analysis("Taiwan")
    assert canada["competition_id"] == taiwan["competition_id"]
    assert taiwan["eligibility"]["overall_status"] == "ineligible"
    assert taiwan["fit"]["inference_skipped"] is True
    assert taiwan["plan"]["inference_skipped"] is True
    assert taiwan["execution"]["model_calls"] == 2
    assert len(runtime.model.steps) == 2  # Fit/Plan responses never consumed.


def test_claim_conflict_and_rejected_excerpt_preserved_end_to_end():
    goal, bundle, drafts = scenario("Taiwan")
    other = make_source(
        "https://example.com/faq", text="Open only to legal residents of Taiwan.", official=True, now=NOW
    )
    bundle.sources.append(other)
    claim = copy.deepcopy(drafts["research"]["claims"]["claims"][0])
    claim.update(
        source_id=other.source_id,
        evidence_text=other.extracted_text,
        value_json=json.dumps({"mode": "allowed_countries", "allowed_countries": ["Taiwan"]}),
    )
    forged = copy.deepcopy(claim)
    forged["evidence_text"] = "Residents worldwide are eligible."
    drafts["research"]["claims"]["claims"] += [claim, forged]
    # Keep the legacy Canada-only wording: Core must prevent it overriding the conflict.
    result = run_analysis(goal, [URL, str(other.source_url)], replay_runtime(bundle, drafts), now=NOW)
    assert len(result["claims"]["rejected_claims"]) == 1
    field = result["claims"]["intelligence"]["resolved_fields"][0]
    assert field["resolution_status"] == "unresolved_conflict"
    assert field["effective_value"] is None
    assert result["eligibility"]["overall_status"] == "uncertain"


@pytest.mark.parametrize("target", ["excerpt", "fact", "source_url"])
def test_record_fabrication_cannot_reach_core(target):
    from prizehunter_core.schemas import CompetitionRecord

    _, bundle, drafts = scenario()
    record = drafts["research"]["record"]
    if target == "excerpt":
        record["source_evidence"][0]["excerpt"] = "Invented official evidence"
    elif target == "fact":
        record["geographic_restrictions"] = ["Open worldwide"]
    else:
        record["source_url"] = "https://attacker.example/rules"
    with pytest.raises(ValueError):
        validate_record(CompetitionRecord.model_validate(record), bundle)


def test_saved_evidence_hash_tampering_fails():
    _, bundle, _ = scenario()
    bundle.sources[0].extracted_text += " fabricated text"
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_bundle(bundle)


def test_all_failed_sources_do_not_trigger_fit_or_imply_no_rules():
    goal, bundle, drafts = scenario()
    failed = make_source(URL, status="timeout", now=NOW)
    bundle.sources = [failed]
    drafts["research"] = {"record": {}, "claims": {"uncertainties": ["Could not retrieve rules"]}}
    runtime = replay_runtime(bundle, drafts)
    with pytest.raises(ValueError, match="eligibility remains unknown"):
        run_analysis(goal, [URL], runtime, now=NOW)
    assert runtime.budget.calls == 2


def test_agent_cannot_silently_omit_supplied_conflicting_source():
    goal, bundle, drafts = scenario()
    bundle.sources.append(make_source("https://example.com/faq", text="Conflicting rules.", now=NOW))
    runtime = replay_runtime(bundle, drafts)
    runtime.model.steps.pop(1)  # Deliberately skip FAQ read in this adversarial scripted model.
    with pytest.raises(ValueError, match="all supplied sources"):
        run_analysis(goal, [URL, "https://example.com/faq"], runtime, now=NOW)


def test_strands_fit_forgery_rejected_after_core_one_correction():
    goal, bundle, drafts = scenario()
    drafts["fit"]["why"][0]["competition_evidence"][0]["excerpt"] = "Invented organizer permission"
    runtime = replay_runtime(bundle, drafts)
    runtime.model.steps.insert(3, copy.deepcopy(runtime.model.steps[2]))
    with pytest.raises(ValueError, match="excerpt is not present"):
        run_analysis(goal, [URL], runtime, now=NOW)
    assert runtime.budget.calls == 4
    assert "VALIDATION FEEDBACK FROM THE APPLICATION" in json.dumps(runtime.agent.messages)


def test_strands_cannot_follow_document_instructions_to_unapproved_url():
    goal, bundle, drafts = scenario()
    runtime = replay_runtime(bundle, drafts)
    runtime.model.steps[0] = ReplayStep("read_evidence", {"url": "https://attacker.example/steal"})
    with pytest.raises(Exception, match="actual successful Strands tool result"):
        run_analysis(goal, [URL], runtime, now=NOW)
    assert not runtime.tools.sources


def test_no_implicit_cloud_or_google_import_during_demo():
    script = """
import importlib.abc, sys
class Reject(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'google', 'app'}:
            raise AssertionError(fullname)
sys.meta_path.insert(0, Reject())
import socket
def deny(*a, **k): raise AssertionError('offline attempted network')
socket.socket.connect = deny
socket.getaddrinfo = deny
from prizehunter_aws.cli import main
assert main(['demo']) == 0
"""
    process = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert process.returncode == 0, process.stderr


def test_pinned_core_and_fixture_bytes_match_manifest():
    for item in json.loads(Path("SOURCE_MANIFEST.json").read_text())["files"]:
        assert hashlib.sha256(Path(item["export_path"]).read_bytes()).hexdigest() == item["sha256"]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://user:pass@example.com/",
        "ftp://example.com",
        "https://example.com:8443/",
        "https://example.com/\nHost:localhost",
        "https://example.com\\@localhost/",
    ],
)
def test_url_syntax_rejected(url):
    with pytest.raises(ValueError):
        canonical_url(url)


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1", "0.0.0.0"]
)
def test_ssrf_dns_rejected(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (address, 0))])
    with pytest.raises(ValueError, match="SSRF"):
        resolve_public("example.com")


def test_mixed_public_private_dns_rejected(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (a, 0)) for a in ["8.8.8.8", "127.0.0.1"]]
    )
    with pytest.raises(ValueError):
        resolve_public("example.com")


def test_connection_uses_verified_ip_and_tls_original_host(monkeypatch):
    from prizehunter_aws.retrieval_worker import PinnedHTTPS

    events = []
    monkeypatch.setattr(
        socket, "create_connection", lambda endpoint, timeout: events.append(endpoint) or object()
    )
    conn = PinnedHTTPS("example.com")
    conn.pinned_ip = "8.8.8.8"

    class Context:
        def wrap_socket(self, sock, server_hostname):
            events.append(server_hostname)
            return sock

    conn._context = Context()
    conn.connect()
    assert events == [("8.8.8.8", 443), "example.com"]


@pytest.mark.parametrize(
    "location", ["http://169.254.169.254/", "http://example.com/", "https://evil.example/"]
)
def test_redirect_cannot_escape_scope_or_downgrade(location):
    calls = []

    def exchange(url):
        calls.append(url)
        return (404, {}, b"") if url.endswith("robots.txt") else (302, {"location": location}, b"")

    reader = Reader({"https://example.com", "http://example.com"}, exchange=exchange)
    with pytest.raises(ValueError):
        reader.fetch(URL)
    assert len(calls) == 2


def test_redirect_dns_is_validated_again(monkeypatch):
    from prizehunter_aws.retrieval_worker import PinnedHTTPS

    resolved = []
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, *a, **k: (
            resolved.append(host) or [(0, 0, 0, "", ("8.8.8.8" if len(resolved) == 1 else "127.0.0.1", 0))]
        ),
    )
    monkeypatch.setattr(PinnedHTTPS, "request", lambda *a, **k: None)

    class Response:
        status = 302

        def getheaders(self):
            return [("Location", "/next")]

        def read(self, size):
            return b""

    monkeypatch.setattr(PinnedHTTPS, "getresponse", lambda self: Response())
    reader = Reader({"https://example.com"})
    monkeypatch.setattr(reader, "robots_allowed", lambda u: True)
    with pytest.raises(ValueError, match="SSRF"):
        reader.fetch(URL)
    assert resolved == ["example.com", "example.com"]


def test_http_retries_and_total_call_cap():
    reader = Reader({"https://example.com"}, exchange=lambda u: (503, {}, b""))
    assert reader.request(URL)[0] == 503
    assert reader.calls == 2
    reader.calls = 12
    with pytest.raises(TimeoutError):
        reader.request(URL)


def test_redirect_loop_is_bounded():
    reader = Reader(
        {"https://example.com"},
        exchange=lambda u: (404, {}, b"") if u.endswith("robots.txt") else (302, {"location": "/again"}, b""),
    )
    with pytest.raises(ValueError, match="Redirect budget"):
        reader.fetch(URL)
    assert reader.calls == 8


def test_robots_refusal_and_thin_page_do_not_become_facts():
    reader = Reader({"https://example.com"}, exchange=lambda u: (200, {}, b"User-agent: *\nDisallow: /"))
    assert reader.fetch(URL)["status"] == "robots_disallowed"
    reader = Reader(
        {"https://example.com"},
        exchange=lambda u: (
            (404, {}, b"")
            if u.endswith("robots.txt")
            else (200, {"content-type": "text/html"}, b"<script>invented rules</script><p>Loading</p>")
        ),
    )
    result = reader.fetch(URL)
    assert result["status"] == "dynamic_page"
    assert "text" not in result


def test_pdf_bounded_parser_extracts_saved_fixture():
    # Tiny self-contained PDF assembled from the standard PDF objects (no external corpus).
    text = "Synthetic official evidence for testing PDF extraction. " * 3
    stream = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 500] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += f"{index} 0 obj\n".encode() + value + b"\nendobj\n"
    start = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(
        f"{o:010d} 00000 n \n".encode() for o in offsets[1:]
    )
    pdf += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()
    reader = Reader(
        {"https://example.com"},
        exchange=lambda u: (
            (404, {}, b"") if u.endswith("robots.txt") else (200, {"content-type": "application/pdf"}, pdf)
        ),
    )
    result = reader.fetch(URL)
    assert result["status"] == "success"
    assert result["page_count"] == 1
    assert "Synthetic official evidence" in result["text"]


def test_worker_timeout_is_failure_without_evidence(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("worker", 0.01)

    monkeypatch.setattr(subprocess, "run", timeout)
    result = PublicRetriever({"https://example.com"}).fetch(URL)
    assert result.extraction_status.value == "timeout"
    assert result.extracted_text is None


def test_tool_bounds_and_page_instructions_cannot_expand_scope():
    _, bundle, _ = scenario()
    tools = ResearchTools(bundle=bundle)
    for _ in range(6):
        assert tools.search_query("find opportunities")["status"] == "unavailable"
    with pytest.raises(ValueError, match="budget"):
        tools.read(URL)
    tools = ResearchTools(bundle=bundle)
    with pytest.raises(ValueError, match="saved evidence"):
        tools.read("https://attacker.example/?steal=credential")
    tools.closed = True
    with pytest.raises(ValueError):
        tools.search_query("anything")


def test_strands_loop_honors_model_budget():
    _, bundle, _ = scenario()
    model = ReplayModel([ReplayStep("read_evidence", {"url": URL})] * 8)
    runtime = StrandsRuntime(model, ResearchTools(bundle=bundle))
    runtime.budget.maximum = 2
    from prizehunter_aws.contracts import ResearchDraft

    with pytest.raises(Exception, match="budget exhausted"):
        runtime.generate("Read evidence", ResearchDraft)
    assert runtime.budget.calls == 2


def test_search_is_distinct_from_evidence():
    missing = UnavailableSearch().search("AI hackathons")
    assert missing.status == "unavailable" and missing.candidates == []
    result = SearchResult(
        query="fixture",
        provider="synthetic",
        status="replay",
        observed_at=NOW,
        candidates=[{"url": URL, "title": "Synthetic", "snippet": "Not an official fact"}],
    )
    provider = ReplaySearch({"fixture": result})
    assert provider.search("fixture").candidates[0].evidence_status == "discovery_only"
    assert provider.search("unseen").status == "unavailable"


def test_search_unavailable_runs_through_strands():
    goal, bundle, drafts = scenario()
    runtime = replay_runtime(bundle, drafts)
    runtime.model.steps.insert(0, ReplayStep("search_opportunities", {"query": "synthetic"}))
    result = run_analysis(goal, [URL], runtime, now=NOW)
    assert result["execution"]["tools"][0] == {"tool": "search_opportunities", "status": "unavailable"}


def test_live_authorization_checked_before_client(monkeypatch):
    monkeypatch.delenv("PH_ALLOW_PAID_BEDROCK", raising=False)
    import boto3

    monkeypatch.setattr(
        boto3, "Session", lambda *a, **k: pytest.fail("Client constructed before authorization")
    )
    with pytest.raises(ValueError, match="authorization"):
        configured_bedrock()


def test_cli_returns_json_failure_not_absence(tmp_path, capsys):
    output = tmp_path / "failure.json"
    assert main(["analyze", "--goal", str(tmp_path / "missing.json"), "--output", str(output)]) == 2
    error = json.loads(output.read_text())
    assert error["status"] == "failed"
    assert error["official_rules_absent"] is False


def test_watch_save_repeat_change_and_profile_isolation(tmp_path):
    path = tmp_path / "watch.json"
    initial, _ = analysis()
    first = run_once(initial, path)
    assert first["pending_decisions"][0]["kind"] == "new_opportunity"
    assert json.loads(path.read_text())["goal"]["profile"]["profile_id"] == "synthetic-canada"
    repeat, _ = analysis()
    assert run_once(repeat, path)["pending_decisions"] == []
    changed, _ = analysis(revision=2)
    event = run_once(changed, path)["pending_decisions"][0]
    assert event["kind"] == "changed" and "record" in event["changed_fields"]
    assert run_once(changed, path)["pending_decisions"] == []
    other, _ = analysis("Taiwan")
    with pytest.raises(ValueError, match="different goal/profile"):
        run_once(other, path)


def test_watch_failure_preserves_last_good_baseline(tmp_path):
    path = tmp_path / "watch.json"
    result, _ = analysis()
    run_once(result, path)
    before = path.read_bytes()
    result["evidence"]["sources"][0].update(
        extraction_status="timeout", extracted_text=None, content_sha256=None
    )
    assert run_once(result, path)["status"] == "retrieval_failed"
    assert path.read_bytes() == before


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("PH_ALLOW_PAID_BEDROCK") != "1", reason="Paid Bedrock live test not authorized"
)
def test_live_bedrock_saved_evidence():
    goal, bundle, _ = scenario()
    runtime = StrandsRuntime(configured_bedrock(), ResearchTools(bundle=bundle))
    result = run_analysis(goal, [URL], runtime)
    assert result["execution"]["live_model"] is True
    assert any(event["tool"] == "read_evidence" for event in result["execution"]["tools"])
    assert result["plan"]["external_actions_executed"] is False
