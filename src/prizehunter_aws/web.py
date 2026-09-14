"""Small judge-facing test build. Public browser routes never spend model credits."""

import copy
import json
import os
import threading
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .demo import NOW, replay_runtime, scenario
from .pipeline import run_analysis
from .watch import run_once

ASSETS = Path(__file__).parent / "assets"
LOCK = threading.Lock()


@lru_cache(maxsize=2)
def demo_result(country="Canada"):
    goal, bundle, drafts = scenario(country)
    return run_analysis(goal, [str(bundle.seed_url)], replay_runtime(bundle, drafts), now=NOW)


def baseline():
    saved = ASSETS / "saved-live.json"
    if saved.exists():
        value = json.loads(saved.read_text())
        if (
            value.get("mode") != "live_bedrock"
            or value.get("verification", {}).get("level") != "LIVE VERIFIED"
        ):
            raise ValueError("Saved artifact has no verified live provenance")
        value["display_mode"] = "SAVED LIVE RESULT — no new model call"
        return value
    value = copy.deepcopy(demo_result())
    value["display_mode"] = "OFFLINE VERIFIED — synthetic replay"
    return value


def watch_step(action, state_root):
    if action not in {"first", "same", "changed", "same_changed", "failure"}:
        raise ValueError("Unknown controlled watch step")
    value = baseline()
    original = copy.deepcopy(value)
    if action in {"changed", "same_changed"}:
        # Deliberate test data mutation, NEVER an observed organizer change.
        value["record"]["deadline"] = "CONTROLLED TEST: deadline moved by the test operator"
    if action == "failure":
        value["evidence"]["sources"][0].update(
            extraction_status="timeout", extracted_text=None, content_sha256=None
        )
    path = Path(state_root) / "judge-watch.json"
    with LOCK:
        if action == "first":
            # Explicit reset of this application's dedicated demonstration state only.
            path.parent.mkdir(parents=True, exist_ok=True)
            from .watch import digest

            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "goal_hash": digest(original["goal"]),
                        "goal": original["goal"],
                        "opportunities": {},
                    }
                )
            )
        result = run_once(value, path)
    result["evidence_level"] = "CONTROLLED TEST"
    result["baseline_mode"] = original["display_mode"]
    result["organizer_change_observed"] = False
    result["notifications_sent"] = 0
    return result


def dispatch(method, path, body, state_root):
    if method == "GET" and path == "/health":
        return 200, "application/json", json.dumps({"status": "ok", "paid_browser_calls": False}).encode()
    if method == "GET" and path in {"/", "/architecture.svg"}:
        file = ASSETS / ("index.html" if path == "/" else "architecture.svg")
        return 200, "text/html; charset=utf-8" if path == "/" else "image/svg+xml", file.read_bytes()
    if method == "GET" and path == "/api/result":
        return 200, "application/json", json.dumps(baseline()).encode()
    if method == "POST" and path == "/api/blocker":
        result = copy.deepcopy(demo_result("Taiwan"))
        result["display_mode"] = "CONTROLLED TEST — synthetic hard blocker"
        return 200, "application/json", json.dumps(result).encode()
    if method == "POST" and path == "/api/watch":
        payload = json.loads(body)
        if not isinstance(payload, dict) or set(payload) != {"action"}:
            raise ValueError("Expected one controlled action")
        return 200, "application/json", json.dumps(watch_step(payload["action"], state_root)).encode()
    return 404, "application/json", b'{"error":"Not found"}'


def serve(host="127.0.0.1", port=8080):
    state_root = os.environ.get("PH_WEB_STATE_DIR", "local-state/web")

    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 2048:
                    raise ValueError("Request body exceeds demo limit")
                path = urlsplit(self.path).path
                status, content_type, data = dispatch(self.command, path, self.rfile.read(size), state_root)
            except (ValueError, KeyError, TypeError):
                status, content_type, data = 400, "application/json", b'{"error":"Invalid demo request"}'
            except Exception:  # noqa: BLE001 -- never expose filesystem paths or internals to browsers.
                status, content_type, data = 500, "application/json", b'{"error":"Demo request failed"}'
            self.send_response(status)
            for key, value in {
                "Content-Type": content_type,
                "Content-Length": str(len(data)),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
            }.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        do_GET = handle_request
        do_POST = handle_request

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"PrizeHunter test build: http://{host}:{port} (browser model spend disabled)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    serve(args.host, args.port)
