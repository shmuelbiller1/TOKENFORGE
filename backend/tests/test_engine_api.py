"""TokenForge v2 engine API tests (iteration 2):
  - /api/formats, /api/playground
  - /api/jobs multi-file (incl. legacy 'file'), ZIP expansion, options
  - /api/jobs/{id}/fragments (search w/ regex special chars, kind filter)
  - /api/jobs/{id}/export (json/txt/annotated/md/jsonl/csv/bundle)
  - /api/jobs/{id}/reconstruct (lossless headers)
  - DELETE /api/jobs/{id} + invalid ObjectId -> 404
  - /api/v1/optimize + /api/v1/optimize/file with X-API-Key
"""
from __future__ import annotations

import io
import os
import time
import uuid
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

SAMPLES = Path("/app/samples")
RUN = uuid.uuid4().hex[:8]
USER_EMAIL = f"engine_{RUN}@test.com"
USER_PASSWORD = "Test@12345"


def _session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def user():
    s = _session()
    r = s.post(f"{API}/auth/register", json={
        "email": USER_EMAIL, "password": USER_PASSWORD, "name": f"Eng {RUN}"})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def api_key(user):
    r = user.post(f"{API}/keys", json={"name": "TEST_engine_key"})
    assert r.status_code == 200
    return r.json()["api_key"]


def _poll_job(s, job_id, timeout=60) -> dict:
    for _ in range(timeout):
        r = s.get(f"{API}/jobs/{job_id}")
        assert r.status_code == 200
        body = r.json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(1)
    pytest.fail(f"job {job_id} did not complete")


# ---------------- META ----------------
class TestFormats:
    def test_formats_public(self):
        r = requests.get(f"{API}/formats")
        assert r.status_code == 200
        body = r.json()
        for k in ("extensions", "modes", "guards", "orders", "export_formats"):
            assert k in body and isinstance(body[k], list)
        assert "auto" in body["modes"]
        assert "facts" in body["guards"]
        assert "bundle" in body["export_formats"]
        # a handful of expected extensions
        exts = {e.lstrip(".").lower() for e in body["extensions"]}
        for want in ("md", "html", "xml", "yaml", "jsonl", "tsv",
                     "log", "py", "xlsx", "pptx", "rtf", "eml", "zip"):
            assert want in exts, f"missing extension {want} in {sorted(exts)}"


# ---------------- PLAYGROUND ----------------
class TestPlayground:
    def test_playground_basic(self):
        text = "\n".join([
            "The quick brown fox.", "The quick brown fox.", "The quick brown fox!",
            "Different sentence.", "Another different one about rabbits.",
        ])
        r = requests.post(f"{API}/playground", json={
            "text": text, "threshold": 0.75, "mode": "auto",
            "guard": "facts", "order": "original"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "stats" in body and "records" in body and "map" in body
        assert body["reconstructed_matches"] is True
        assert body["detected_kind"] in ("prose", "code", "logs", "data", "mixed")
        assert body["stats"]["tokens_after"] <= body["stats"]["tokens_before"]
        assert body["optimized_text"]
        assert body["annotated_text"]

    def test_playground_too_large(self):
        text = "a " * (260 * 1024)  # > 256KB
        r = requests.post(f"{API}/playground", json={"text": text})
        assert r.status_code == 413

    def test_playground_invalid_mode(self):
        r = requests.post(f"{API}/playground",
                          json={"text": "hello world", "mode": "not_a_mode"})
        assert r.status_code == 400


# ---------------- JOBS: multi-file + legacy ----------------
class TestJobsMulti:
    def test_multi_files_and_sources(self, user):
        user.headers.pop("Content-Type", None)
        files = [
            ("files", ("a.txt", io.BytesIO(b"Hello world.\nHello world.\nUnique one."), "text/plain")),
            ("files", ("b.txt", io.BytesIO(b"Hello world.\nAnother thing."), "text/plain")),
        ]
        r = user.post(f"{API}/jobs?threshold=0.75&mode=auto&guard=facts&order=original",
                      files=files)
        assert r.status_code == 200, r.text
        job_id = r.json()["id"]
        job = _poll_job(user, job_id)
        assert job["status"] == "completed", job
        stats = job["stats"]
        assert "sources" in stats and len(stats["sources"]) == 2
        assert "cross_source_records" in stats
        assert stats.get("lossless_verified") is True
        assert "timings_ms" in stats
        TestJobsMulti.job_id = job_id

    def test_legacy_single_file_field(self, user):
        user.headers.pop("Content-Type", None)
        files = {"file": ("legacy.txt", io.BytesIO(b"Line one.\nLine one.\nLine two."), "text/plain")}
        r = user.post(f"{API}/jobs", files=files)
        assert r.status_code == 200, r.text
        job = _poll_job(user, r.json()["id"])
        assert job["status"] == "completed"
        assert job["stats"]["lossless_verified"] is True

    def test_invalid_mode_returns_400(self, user):
        user.headers.pop("Content-Type", None)
        files = {"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")}
        r = user.post(f"{API}/jobs?mode=garbage", files=files)
        assert r.status_code == 400


# ---------------- JOBS: sample files ----------------
SAMPLE_FILES = [
    "server.log", "customers.csv", "catalog.json", "events.jsonl",
    "config.yaml", "page.html", "feed.xml", "mail.eml", "doc.rtf",
    "util.py", "report.docx", "sales.xlsx", "deck.pptx",
    "release-notes.md", "bundle.zip",
]


class TestSampleFiles:
    @pytest.mark.parametrize("fname", SAMPLE_FILES)
    def test_sample_completes(self, user, fname):
        p = SAMPLES / fname
        if not p.exists():
            pytest.skip(f"sample {fname} missing")
        user.headers.pop("Content-Type", None)
        with p.open("rb") as fh:
            data = fh.read()
        r = user.post(f"{API}/jobs",
                      files={"file": (fname, io.BytesIO(data), "application/octet-stream")})
        assert r.status_code == 200, r.text
        job = _poll_job(user, r.json()["id"], timeout=90)
        assert job["status"] == "completed", f"{fname}: {job}"
        assert job["stats"]["lossless_verified"] is True
        if fname == "bundle.zip":
            # zip members should expand into sources named bundle.zip/<member>
            srcs = job["stats"].get("sources", [])
            names = [s.get("name", "") for s in srcs]
            assert any(n.startswith("bundle.zip/") for n in names), f"zip not expanded: {names}"


# ---------------- FRAGMENTS, EXPORT, RECONSTRUCT, DELETE ----------------
class TestFragmentsExport:
    @pytest.fixture(scope="class")
    def job_id(self, user):
        user.headers.pop("Content-Type", None)
        # include regex special chars to validate escape
        payload = ("Pricing (basic) is $9.99.\n" * 5 +
                   "Pricing (basic) is $9.99!\n" * 2 +
                   "Totally unrelated line about pineapples.\n" * 3 +
                   "Final unique line.")
        r = user.post(f"{API}/jobs",
                      files={"file": ("frag.txt", io.BytesIO(payload.encode()), "text/plain")})
        job = _poll_job(user, r.json()["id"])
        assert job["status"] == "completed"
        return r.json()["id"]

    def test_fragment_search_regex_safe(self, user, job_id):
        # '(' is a regex meta char; must not 500
        r = user.get(f"{API}/jobs/{job_id}/fragments", params={"search": "("})
        assert r.status_code == 200
        r = user.get(f"{API}/jobs/{job_id}/fragments", params={"search": "pricing"})
        assert r.status_code == 200

    def test_fragment_kind_filter(self, user, job_id):
        for k in ("template", "near_duplicate", "duplicate", "unique"):
            r = user.get(f"{API}/jobs/{job_id}/fragments", params={"kind": k})
            assert r.status_code == 200
            body = r.json()
            for it in body["items"]:
                assert it.get("kind") == k

    @pytest.mark.parametrize("fmt", ["json", "txt", "annotated", "md", "jsonl", "csv", "bundle"])
    def test_export_formats(self, user, job_id, fmt):
        r = user.get(f"{API}/jobs/{job_id}/export", params={"format": fmt})
        assert r.status_code == 200, f"{fmt}: {r.text[:200]}"
        content = r.content
        assert content, f"empty content for {fmt}"
        if fmt in ("json", "bundle"):
            import json as _j
            body = _j.loads(content)
            assert "records" in body
            if fmt == "bundle":
                assert "map" in body
                assert body["records"] and "originals" in body["records"][0]

    def test_reconstruct_headers(self, user, job_id):
        job = user.get(f"{API}/jobs/{job_id}").json()
        frags_in = job["stats"]["fragments_in"]
        r = user.get(f"{API}/jobs/{job_id}/reconstruct")
        assert r.status_code == 200
        assert r.headers.get("X-Lossless-Verified") == "true"
        assert int(r.headers["X-Fragment-Count"]) == frags_in
        lines = [ln for ln in r.text.split("\n") if ln]
        assert len(lines) == frags_in

    def test_delete_invalid_objectid_404(self, user):
        r = user.delete(f"{API}/jobs/not-a-valid-id")
        assert r.status_code == 404

    def test_delete_removes_fragments_and_bundle(self, user, job_id):
        r = user.delete(f"{API}/jobs/{job_id}")
        assert r.status_code == 200
        # fragments gone
        r = user.get(f"{API}/jobs/{job_id}/fragments")
        assert r.status_code == 404
        # bundle gone -> reconstruct 404
        r = user.get(f"{API}/jobs/{job_id}/reconstruct")
        assert r.status_code == 404


# ---------------- V1 API ----------------
class TestV1:
    def test_v1_optimize_with_new_fields(self, api_key):
        text = ("Pricing is $9.99 per month.\n" * 3 +
                "Refunds within 7 days.\nRefunds within seven days.\n" +
                "Totally unrelated line.")
        r = requests.post(f"{API}/v1/optimize",
                          headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                          json={"text": text, "threshold": 0.75, "mode": "auto",
                                "guard": "facts", "order": "frequency",
                                "include_map": True, "format": "annotated"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "stats" in body and "optimized_text" in body
        assert "map" in body  # include_map true
        assert body["records"] and "originals" in body["records"][0]

    def test_v1_optimize_file(self, api_key):
        p = SAMPLES / "customers.csv"
        if not p.exists():
            pytest.skip("sample missing")
        r = requests.post(f"{API}/v1/optimize/file?threshold=0.8&mode=auto",
                          headers={"X-API-Key": api_key},
                          files={"files": ("customers.csv", p.open("rb"), "text/csv")})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["stats"]["tokens_after"] <= body["stats"]["tokens_before"]

    def test_v1_missing_key(self):
        r = requests.post(f"{API}/v1/optimize", json={"text": "hi"})
        assert r.status_code == 401

    def test_v1_bad_key(self):
        r = requests.post(f"{API}/v1/optimize",
                          headers={"X-API-Key": "tio_bad"},
                          json={"text": "hi"})
        assert r.status_code == 401
