"""Single fetch subprocess: pinned DNS addresses, no proxies, bounded HTTP/PDF."""

import http.client
import io
import ipaddress
import json
import socket
import sys
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .retrieval import canonical_url, origin

MAX_BYTES = 2_000_000
USER_AGENT = "PrizeHunterResearch/0.1"


def resolve_public(host: str):
    addresses = list(
        dict.fromkeys(row[4][0] for row in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM))
    )
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError("SSRF blocked: DNS contains non-public address")
    return addresses


class PinnedHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.create_connection((self.pinned_ip, self.port), self.timeout)


class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        raw = socket.create_connection((self.pinned_ip, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class Reader:
    def __init__(self, allowed_origins, exchange=None):
        self.allowed = set(allowed_origins)
        self.calls = 0
        self.exchange = exchange or self._exchange
        self.deadline = time.monotonic() + 22

    def _exchange(self, url):
        parts = urlsplit(url)
        addresses = resolve_public(parts.hostname)
        cls = PinnedHTTPS if parts.scheme == "https" else PinnedHTTP
        connection = cls(parts.hostname, timeout=min(6, max(0.1, self.deadline - time.monotonic())))
        connection.pinned_ip = addresses[0]
        try:
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection.request(
                "GET",
                path,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Encoding": "identity",
                    "Accept": "text/html,application/pdf,text/plain",
                },
            )
            response = connection.getresponse()
            headers = {key.lower(): value for key, value in response.getheaders()}
            if int(headers.get("content-length", "0")) > MAX_BYTES:
                raise OverflowError("Document exceeds byte limit")
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise OverflowError("Document exceeds byte limit")
            return response.status, headers, data
        finally:
            connection.close()

    def request(self, url):
        url = canonical_url(url)
        if origin(url) not in self.allowed:
            raise ValueError("Redirect or URL outside approved origins")
        for attempt in range(2):
            if self.calls >= 12 or time.monotonic() >= self.deadline:
                raise TimeoutError("HTTP call/time budget exhausted")
            self.calls += 1
            try:
                status, headers, body = self.exchange(url)
            except (OSError, http.client.HTTPException):
                if attempt:
                    raise
                continue
            if status >= 500 and not attempt:
                continue
            return status, headers, body
        raise TimeoutError("HTTP attempts exhausted")

    def robots_allowed(self, url):
        status, _headers, body = self.request(origin(url) + "/robots.txt")
        if status == 404:
            return True
        if status != 200:  # Fail closed on redirects/errors, no hidden extra requests.
            return False
        parser = RobotFileParser()
        parser.parse(body.decode("utf-8", errors="replace").splitlines())
        return parser.can_fetch(USER_AGENT, url)

    def fetch(self, url):
        for _ in range(4):
            url = canonical_url(url)
            if not self.robots_allowed(url):
                return {
                    "status": "robots_disallowed",
                    "final_url": url,
                    "warnings": ["Robots disallowed or robots could not be safely verified"],
                }
            status, headers, data = self.request(url)
            if status in {301, 302, 303, 307, 308}:
                location = headers.get("location")
                if not location:
                    raise ValueError("Redirect without Location")
                next_url = canonical_url(urljoin(url, location))
                if origin(next_url) not in self.allowed:
                    raise ValueError("Redirect outside approved origins")
                if urlsplit(url).scheme == "https" and urlsplit(next_url).scheme != "https":
                    raise ValueError("HTTPS downgrade blocked")
                url = next_url
                continue
            base = {"final_url": url, "http_status": status}
            if status != 200:
                return {**base, "status": "login_required" if status in {401, 403} else "inaccessible"}
            if headers.get("content-encoding", "identity") != "identity":
                return {**base, "status": "unsupported_content", "warnings": ["Compressed payload refused"]}
            content_type = headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type == "application/pdf":
                document = PdfReader(io.BytesIO(data))
                if document.is_encrypted or not 1 <= len(document.pages) <= 25:
                    return {**base, "status": "unsupported_content", "content_type": "pdf"}
                text = "\n".join(page.extract_text() or "" for page in document.pages)
                base.update(content_type="pdf", parser="pypdf", page_count=len(document.pages))
            elif content_type in {"text/html", "application/xhtml+xml", "text/plain"}:
                soup = BeautifulSoup(data, "html.parser")
                for tag in soup(["script", "style", "noscript", "template"]):
                    tag.decompose()
                text = soup.get_text("\n", strip=True)
                base.update(content_type="html", parser="beautifulsoup4")
            else:
                return {**base, "status": "unsupported_content"}
            if len(text.strip()) < 100:
                return {
                    **base,
                    "status": "dynamic_page",
                    "warnings": ["Thin/empty text; requires another approved official source"],
                }
            if len(text) > 60000:
                return {**base, "status": "too_large"}
            return {**base, "text": text, "status": "success"}
        raise ValueError("Redirect budget exceeded")


def main():
    request = json.load(sys.stdin)
    reader = Reader(request["allowed_origins"])
    try:
        result = reader.fetch(request["url"])
    except TimeoutError:
        result = {"status": "timeout", "warnings": ["Retrieval timed out; rules remain unknown"]}
    except OverflowError:
        result = {"status": "too_large"}
    except Exception as exc:  # noqa: BLE001 -- Isolated parser boundary; never promote failures to evidence.
        result = {
            "status": "inaccessible",
            "warnings": [f"{type(exc).__name__}: retrieval refused or failed"],
        }
    result.setdefault("warnings", []).append(f"HTTP attempts: {reader.calls}; max 12")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
