"""TokenForge iteration 3 feature tests:
  - Engine: table folding default on / off
  - Engine: token budget via /api/jobs and /api/playground
  - Cache: same /api/jobs upload returns cached:true 2nd call with same id
  - Cache: /v1/optimize same body -> cached false then true
  - Share: enable/disable; public report shape; privacy rules
  - Usage: /api/usage shape + by_key filled after v1; /api/admin/usage auth
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
U_EMAIL = f"it3_{RUN}@test.com"
U_PASSWORD = "Test@12345"
ADMIN_EMAIL = "admin@tokenforge.io"
ADMIN_PASSWORD = "Admin@12345"


def _s():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def user():
    s = _s()
    r = s.post(f"{API}/auth/register", json={"email": U_EMAIL, "password": U_PASSWORD, "name": f"It3 {RUN}"})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def user2():
    s = _s()
    r = s.post(f"{API}/auth/register", json={"email": f"it3b_{RUN}@test.com", "password": U_PASSWORD,
                                             "name": "It3 B"})
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def admin():
    s = _s()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def api_key(user):
    r = user.post(f"{API}/keys", json={"name": "TEST_it3"})
    assert r.status_code == 200
    return r.json()["api_key"]


def _poll(s, jid, timeout=60):
    for _ in range(timeout):
        r = s.get(f"{API}/jobs/{jid}")
        assert r.status_code == 200
        b = r.json()
        if b["status"] in ("completed", "failed"):
            return b
        time.sleep(1)
    pytest.fail(f"job {jid} did not complete")


def _upload(s, params=None, filename="customers.csv"):
    files = {"files": (filename, SAMPLES.joinpath(filename).read_bytes())}
    s2 = requests.Session()
    s2.cookies.update(s.cookies)
    r = s2.post(f"{API}/jobs", files=files, params=params or {})
    return r


# -------------------- Engine: table folding --------------------
class TestTableFolding:
    def test_csv_folded_header_and_rows(self, user):
        # unique threshold to avoid cache
        r = _upload(user, params={"threshold": 0.95, "fold_tables": "true"})
        assert r.status_code == 200, r.text
        jid = r.json()["id"]
        body = _poll(user, jid)
        assert body["status"] == "completed"
        stats = body["stats"]
        assert stats.get("tables_folded", 0) >= 1
        assert stats.get("rows_in_tables", 0) > 0
        # fetch optimized text via export txt
        tx = requests.get(f"{API}/jobs/{jid}/export?format=txt", cookies=user.cookies)
        assert tx.status_code == 200
        txt = tx.text
        assert "[table " in txt and "id|name|city|plan" in txt, txt[:400]
        # rows look like 'a|b|c' pipe-separated, not 'id: 0 | name: ...'
        assert "id: 0 | name:" not in txt

    def test_csv_fold_tables_false(self, user):
        # threshold=1.0 disables near-dup clustering so no templating either
        r = _upload(user, params={"threshold": 1.0, "fold_tables": "false"})
        assert r.status_code == 200
        jid = r.json()["id"]
        body = _poll(user, jid)
        tx = requests.get(f"{API}/jobs/{jid}/export?format=txt", cookies=user.cookies)
        assert tx.status_code == 200
        assert "id: 0 | name:" in tx.text, tx.text[:400]

    def test_jsonl_constant_column_folded(self, user):
        r = _upload(user, params={"threshold": 0.93, "fold_tables": "true"}, filename="events.jsonl")
        assert r.status_code == 200
        jid = r.json()["id"]
        body = _poll(user, jid)
        tx = requests.get(f"{API}/jobs/{jid}/export?format=txt", cookies=user.cookies).text
        # constant column(s) hoisted into header "every row: ..."
        assert "every row:" in tx, tx[:600]


# -------------------- Engine: budget --------------------
class TestBudget:
    def test_jobs_budget_truncates(self, user):
        r = _upload(user, params={"threshold": 0.88, "budget": 300}, filename="customers.csv")
        assert r.status_code == 200
        jid = r.json()["id"]
        body = _poll(user, jid)
        s = body["stats"]
        assert s["tokens_after"] <= 300
        assert s["budget_omitted_records"] > 0
        assert s["output_complete"] is False
        assert "token_reduction_pct_lossless" in s
        assert "tokens_after_full" in s
        tx = requests.get(f"{API}/jobs/{jid}/export?format=txt", cookies=user.cookies).text.rstrip()
        assert tx.rstrip().endswith("]") and "[budget:" in tx and "omitted" in tx, tx[-300:]
        # /reconstruct returns ALL original fragments regardless of budget
        rc = requests.get(f"{API}/jobs/{jid}/reconstruct", cookies=user.cookies)
        assert rc.status_code == 200
        assert int(rc.headers.get("X-Fragment-Count", "0")) == s["fragments_in"]

    def test_playground_budget(self):
        text = "\n".join([f"Order {i} shipped to Alice in Boston" for i in range(60)])
        r = requests.post(f"{API}/playground", json={"text": text, "budget": 100, "threshold": 0.9})
        assert r.status_code == 200, r.text
        s = r.json()["stats"]
        assert s["tokens_after"] <= 100
        assert s["budget_omitted_records"] > 0
        assert s["output_complete"] is False


# -------------------- Cache --------------------
class TestCache:
    def test_jobs_cache_returns_same_id(self, user):
        params = {"threshold": 0.77}  # unique threshold -> cold miss first
        r1 = _upload(user, params=params, filename="customers.csv")
        assert r1.status_code == 200
        jid1 = r1.json()["id"]
        assert r1.json().get("cached") is False
        _poll(user, jid1)
        r2 = _upload(user, params=params, filename="customers.csv")
        assert r2.status_code == 200
        b2 = r2.json()
        assert b2.get("cached") is True
        assert b2["status"] == "completed"
        assert b2["id"] == jid1

    def test_v1_cache_flag(self, api_key):
        body = {"text": f"hello world {RUN}\n" * 20, "threshold": 0.9}
        h = {"X-API-Key": api_key, "Content-Type": "application/json"}
        r1 = requests.post(f"{API}/v1/optimize", json=body, headers=h)
        assert r1.status_code == 200, r1.text
        assert r1.json()["stats"]["cached"] is False
        r2 = requests.post(f"{API}/v1/optimize", json=body, headers=h)
        assert r2.status_code == 200
        assert r2.json()["stats"]["cached"] is True


# -------------------- Share --------------------
class TestShare:
    def _completed_job(self, user, threshold):
        r = _upload(user, params={"threshold": threshold}, filename="customers.csv")
        assert r.status_code == 200
        jid = r.json()["id"]
        if not r.json().get("cached"):
            _poll(user, jid)
        return jid

    def test_share_enable_public_get_and_disable(self, user):
        jid = self._completed_job(user, 0.84)
        r = user.post(f"{API}/jobs/{jid}/share", json={"enabled": True})
        assert r.status_code == 200
        tok = r.json()["token"]
        assert tok
        # public (no auth)
        g = requests.get(f"{API}/share/{tok}")
        assert g.status_code == 200
        body = g.json()
        assert "filename" in body and "stats" in body and "preview_text" in body
        assert "preview_records" in body
        # should not leak originals or map or variants
        assert "map" not in body
        for rec in body["preview_records"]:
            assert "originals" not in rec
            assert "variants" not in rec
        # disable
        r2 = user.post(f"{API}/jobs/{jid}/share", json={"enabled": False})
        assert r2.status_code == 200
        g2 = requests.get(f"{API}/share/{tok}")
        assert g2.status_code == 404

    def test_share_other_user_cannot_share(self, user, user2):
        jid = self._completed_job(user, 0.86)
        r = user2.post(f"{API}/jobs/{jid}/share", json={"enabled": True})
        assert r.status_code == 404

    def test_share_processing_job_400(self, user):
        # kick off a fresh job and immediately try to share while processing
        r = _upload(user, params={"threshold": 0.79}, filename="customers.csv")
        assert r.status_code == 200
        body = r.json()
        if body.get("cached"):
            pytest.skip("cache hit -> can't test processing path")
        jid = body["id"]
        if body["status"] == "processing":
            sh = user.post(f"{API}/jobs/{jid}/share", json={"enabled": True})
            # may race; accept 400 or 200 depending on timing, but we want 400 most of the time
            if sh.status_code == 200:
                pytest.skip("job finished too fast to test processing path")
            assert sh.status_code == 400


# -------------------- Usage analytics --------------------
class TestUsage:
    def test_my_usage_shape(self, user, api_key):
        # Make at least one v1 call so by_key is populated
        requests.post(f"{API}/v1/optimize", json={"text": f"usage probe {RUN}\n" * 5},
                      headers={"X-API-Key": api_key, "Content-Type": "application/json"})
        r = user.get(f"{API}/usage?days=7")
        assert r.status_code == 200
        b = r.json()
        assert len(b["series"]) == 7
        for s in b["series"]:
            assert set(s.keys()) >= {"day", "requests", "tokens_before", "tokens_after", "tokens_saved"}
        t = b["totals"]
        assert "requests" in t and "tokens_saved" in t and "cached_hits" in t
        assert isinstance(b["by_key"], dict)
        # by_key is populated after v1 call
        assert len(b["by_key"]) >= 1
        for kid, v in b["by_key"].items():
            assert "requests" in v and "tokens_saved" in v
        assert isinstance(b["by_source"], dict)

    def test_admin_usage_requires_admin(self, user):
        r = user.get(f"{API}/admin/usage?days=7")
        assert r.status_code == 403

    def test_admin_usage_ok(self, admin):
        r = admin.get(f"{API}/admin/usage?days=7")
        assert r.status_code == 200
        b = r.json()
        assert "series" in b and "top_users" in b
        assert len(b["series"]) == 7
        if b["top_users"]:
            tu = b["top_users"][0]
            assert "email" in tu and "requests" in tu and "tokens_saved" in tu
