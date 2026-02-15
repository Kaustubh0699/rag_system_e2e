"""
Multi-user API tests: session isolation and same-email persistence.

Uses the Document UI APIs (session start, process, session files) to verify:
- Different users (emails) have isolated sessions and file lists.
- Same email (different casing) returns to the same session and sees same files.
"""

import json
import time
from io import BytesIO
from unittest.mock import patch

import pytest

pytest.importorskip("flask")

from src.document_ui import app


def _minimal_pdf_bytes():
    """Minimal valid PDF (one empty page) for upload tests."""
    try:
        from pypdf import PdfWriter
        buf = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(buf)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"


@pytest.fixture(autouse=True)
def clear_state():
    app._jobs.clear()
    app._sessions.clear()
    app._chat_pipelines.clear()
    app._chat_messages.clear()


def _poll_until_completed(client, job_id, max_wait_sec=5.0, poll_interval=0.15):
    """Poll GET /api/process/<job_id>/status until state is completed or failed."""
    deadline = time.monotonic() + max_wait_sec
    while time.monotonic() < deadline:
        r = client.get(f"/api/process/{job_id}/status")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        if data.get("state") == "completed":
            return data
        if data.get("state") == "failed":
            pytest.fail(f"Job failed: {data.get('error', data)}")
        time.sleep(poll_interval)
    pytest.fail(f"Job {job_id} did not complete within {max_wait_sec}s")


@patch("src.chunk_embed_store.ingest_document", return_value=1)
def test_multi_user_session_isolation(mock_ingest):
    """Two users get separate sessions; each sees only their own files."""
    flask_app = app.create_app()
    client_a = flask_app.test_client()
    client_b = flask_app.test_client()

    pdf = _minimal_pdf_bytes()

    # --- User A: start session, upload, get files ---
    r = client_a.post("/api/session/start", json={"email": "alice@example.com"})
    assert r.status_code == 201
    assert "redirect" in r.get_json()

    r = client_a.post(
        "/api/process",
        data={"file": (BytesIO(pdf), "alice_doc.pdf")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 202
    job_id_a = r.get_json()["job_id"]

    _poll_until_completed(client_a, job_id_a)

    r = client_a.get("/api/session/files")
    assert r.status_code == 200
    files_a = r.get_json()["files"]
    assert len(files_a) == 1
    assert files_a[0]["file_name"] == "alice_doc.pdf"

    # --- User B: start session (different email), no files yet ---
    r = client_b.post("/api/session/start", json={"email": "bob@example.com"})
    assert r.status_code == 201

    r = client_b.get("/api/session/files")
    assert r.status_code == 200
    files_b = r.get_json()["files"]
    assert len(files_b) == 0, "User B must not see User A's files"

    # --- User B: upload own file ---
    r = client_b.post(
        "/api/process",
        data={"file": (BytesIO(pdf), "bob_doc.pdf")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 202
    job_id_b = r.get_json()["job_id"]
    _poll_until_completed(client_b, job_id_b)

    r = client_b.get("/api/session/files")
    assert r.status_code == 200
    files_b = r.get_json()["files"]
    assert len(files_b) == 1
    assert files_b[0]["file_name"] == "bob_doc.pdf"

    # --- User A: still sees only own file ---
    r = client_a.get("/api/session/files")
    assert r.status_code == 200
    files_a_again = r.get_json()["files"]
    assert len(files_a_again) == 1
    assert files_a_again[0]["file_name"] == "alice_doc.pdf"


@patch("src.chunk_embed_store.ingest_document", return_value=1)
def test_same_email_same_session(mock_ingest):
    """Same email with different casing returns to same session and sees same files."""
    flask_app = app.create_app()
    client1 = flask_app.test_client()
    client2 = flask_app.test_client()

    pdf = _minimal_pdf_bytes()

    # User signs in as "carol@test.com" and uploads
    r = client1.post("/api/session/start", json={"email": "carol@test.com"})
    assert r.status_code == 201

    r = client1.post(
        "/api/process",
        data={"file": (BytesIO(pdf), "carol_doc.pdf")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 202
    _poll_until_completed(client1, r.get_json()["job_id"])

    r = client1.get("/api/session/files")
    assert r.status_code == 200 and len(r.get_json()["files"]) == 1

    # Same user returns with "CAROL@test.com" (different case) - should see same session
    r = client2.post("/api/session/start", json={"email": "CAROL@test.com"})
    assert r.status_code == 201

    r = client2.get("/api/session/files")
    assert r.status_code == 200
    files = r.get_json()["files"]
    assert len(files) == 1, "Normalized email should restore same session and files"
    assert files[0]["file_name"] == "carol_doc.pdf"
