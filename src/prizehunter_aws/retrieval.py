"""Bounded public read transport. No Google app imports or cloud clients."""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from prizehunter_core.evidence import CompetitionEvidenceBundle, CompetitionEvidenceSource


def canonical_url(url: str) -> str:
    if len(url) > 2048 or any(ord(c) < 33 for c in url) or "\\" in url:
        raise ValueError("Invalid public URL")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Only credential-free HTTP(S) URLs are allowed")
    host = parts.hostname.encode("idna").decode().lower().rstrip(".")
    if parts.port not in {None, 80 if parts.scheme == "http" else 443}:
        raise ValueError("Nonstandard ports are not allowed")
    if ":" in host:
        host = f"[{host}]"
    return urlunsplit((parts.scheme, host, parts.path or "/", parts.query, ""))


def origin(url: str) -> str:
    parts = urlsplit(canonical_url(url))
    return f"{parts.scheme}://{parts.netloc}"


def source_id(url: str) -> str:
    return "src_" + hashlib.sha256(canonical_url(url).encode()).hexdigest()[:12]


def make_source(url, *, text=None, status="success", official=False, now=None, **metadata):
    now = now or datetime.now(UTC)
    return CompetitionEvidenceSource.model_validate_json(
        json.dumps(
            {
                "source_id": source_id(url),
                "source_url": canonical_url(url),
                "final_url": metadata.pop("final_url", canonical_url(url)),
                "source_type": "official_page" if official else "unknown",
                "content_type": metadata.pop("content_type", "html"),
                "authority_hint": "organizer_controlled" if official else "unknown",
                "relation_to_seed": "seed",
                "retrieved_at": now.isoformat(),
                "extraction_status": status,
                "extracted_text": text,
                "content_sha256": hashlib.sha256(text.encode()).hexdigest() if text else None,
                "metadata": {"depth": 0, "retrieval_method": "aws-public-http-v1", **metadata},
            }
        )
    )


def verify_bundle(bundle: CompetitionEvidenceBundle):
    """AWS saved evidence uses SHA256 of exact extracted UTF-8 text."""
    if len(bundle.sources) > 4:
        raise ValueError("At most four evidence sources per local run")
    for source in bundle.sources:
        canonical_url(str(source.source_url))
        if source.final_url:
            canonical_url(str(source.final_url))
        if source.extracted_text:
            if len(source.extracted_text) > 60000:
                raise ValueError("Saved evidence exceeds text budget")
            if hashlib.sha256(source.extracted_text.encode()).hexdigest() != source.content_sha256:
                raise ValueError("Saved evidence hash mismatch")


class PublicRetriever:
    def __init__(
        self, allowed_origins: set[str], official_origins: set[str] | None = None, timeout: float = 25
    ):
        self.allowed_origins = {origin(u) for u in allowed_origins}
        self.official_origins = {origin(u) for u in (official_origins or set())}
        self.timeout = timeout

    def fetch(self, url: str):
        url = canonical_url(url)
        if origin(url) not in self.allowed_origins:
            raise ValueError("URL outside caller-approved research scope")
        request = {"url": url, "allowed_origins": sorted(self.allowed_origins)}
        try:
            # DNS, HTTP and PDF parsing all die with this process on total timeout.
            process = subprocess.run(
                [sys.executable, "-m", "prizehunter_aws.retrieval_worker"],
                input=json.dumps(request),
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=True,
            )
            payload = json.loads(process.stdout)
        except subprocess.TimeoutExpired:
            payload = {"status": "timeout", "warnings": ["Total retrieval deadline exceeded"]}
        except (subprocess.CalledProcessError, ValueError):
            payload = {"status": "parser_failed", "warnings": ["Retrieval worker failed"]}
        final = payload.pop("final_url", url)
        return make_source(url, official=origin(final) in self.official_origins, final_url=final, **payload)
