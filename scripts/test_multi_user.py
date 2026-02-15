#!/usr/bin/env python3
"""
Multi-user API test script: run against a live Document UI server or in-process (mock).

Verifies:
- Two users (different emails) have isolated sessions and file lists.
- Same email with different casing returns to the same session and sees same files.

Usage:
  Without server/Ollama (mock mode, no embeddings):
    python scripts/test_multi_user.py --mock

  Against live server (requires server + Ollama for embeddings):
    1. Start the server:  python -m src.document_ui.app
    2. Run:               python scripts/test_multi_user.py [BASE_URL]

  BASE_URL defaults to http://localhost:8000

  Run from the project root (or set PYTHONPATH) so the `src` package can be imported.
"""

import argparse
import sys
import time
from io import BytesIO

try:
    import requests
except ImportError:
    requests = None


def minimal_pdf():
    try:
        from pypdf import PdfWriter
        buf = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(buf)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"


def poll_until_completed(session: requests.Session, base_url: str, job_id: str, max_wait_sec: float = 30.0):
    deadline = time.monotonic() + max_wait_sec
    while time.monotonic() < deadline:
        r = session.get(f"{base_url}/api/process/{job_id}/status")
        r.raise_for_status()
        data = r.json()
        if data.get("state") == "completed":
            return data
        if data.get("state") == "failed":
            raise RuntimeError(f"Job failed: {data.get('error', data)}")
        time.sleep(0.5)
    raise RuntimeError(f"Job {job_id} did not complete within {max_wait_sec}s")


def run_tests(base_url: str) -> bool:
    base_url = base_url.rstrip("/")
    pdf = minimal_pdf()
    ok = True

    # --- Session isolation: User A and User B ---
    print("Test 1: Session isolation (User A vs User B)")
    session_a = requests.Session()
    session_b = requests.Session()

    r = session_a.post(f"{base_url}/api/session/start", json={"email": "alice_multi@test.com"})
    if r.status_code != 201:
        print(f"  FAIL: User A session start: {r.status_code} {r.text}")
        ok = False
    else:
        print("  User A session started.")

    r = session_a.post(
        f"{base_url}/api/process",
        files={"file": ("alice_file.pdf", BytesIO(pdf), "application/pdf")},
    )
    if r.status_code != 202:
        print(f"  FAIL: User A upload: {r.status_code} {r.text}")
        ok = False
    else:
        job_id_a = r.json()["job_id"]
        try:
            poll_until_completed(session_a, base_url, job_id_a)
            print("  User A upload completed.")
        except RuntimeError as e:
            print(f"  FAIL: {e}")
            ok = False

    r = session_a.get(f"{base_url}/api/session/files")
    if r.status_code != 200 or len(r.json().get("files", [])) != 1:
        print(f"  FAIL: User A should see 1 file: {r.status_code} {r.json()}")
        ok = False
    else:
        print("  User A sees 1 file.")

    r = session_b.post(f"{base_url}/api/session/start", json={"email": "bob_multi@test.com"})
    if r.status_code != 201:
        print(f"  FAIL: User B session start: {r.status_code} {r.text}")
        ok = False
    else:
        print("  User B session started.")

    r = session_b.get(f"{base_url}/api/session/files")
    if r.status_code != 200 or len(r.json().get("files", [])) != 0:
        print(f"  FAIL: User B should see 0 files (isolation): {r.status_code} {r.json()}")
        ok = False
    else:
        print("  User B sees 0 files (correct isolation).")

    r = session_b.post(
        f"{base_url}/api/process",
        files={"file": ("bob_file.pdf", BytesIO(pdf), "application/pdf")},
    )
    if r.status_code != 202:
        print(f"  FAIL: User B upload: {r.status_code} {r.text}")
        ok = False
    else:
        job_id_b = r.json()["job_id"]
        try:
            poll_until_completed(session_b, base_url, job_id_b)
            print("  User B upload completed.")
        except RuntimeError as e:
            print(f"  FAIL: {e}")
            ok = False

    r = session_a.get(f"{base_url}/api/session/files")
    if r.status_code != 200 or len(r.json().get("files", [])) != 1:
        print(f"  FAIL: User A should still see 1 file: {r.status_code} {r.json()}")
        ok = False
    else:
        print("  User A still sees only 1 file (isolation OK).")

    # --- Same email (different case) = same session ---
    print("\nTest 2: Same email, different casing (session persistence)")
    session_c1 = requests.Session()
    session_c2 = requests.Session()

    r = session_c1.post(f"{base_url}/api/session/start", json={"email": "carol_multi@test.com"})
    if r.status_code != 201:
        print(f"  FAIL: Carol session start: {r.status_code}")
        ok = False
    else:
        r = session_c1.post(
            f"{base_url}/api/process",
            files={"file": ("carol_file.pdf", BytesIO(pdf), "application/pdf")},
        )
        if r.status_code != 202:
            print(f"  FAIL: Carol upload: {r.status_code}")
            ok = False
        else:
            try:
                poll_until_completed(session_c1, base_url, r.json()["job_id"])
            except RuntimeError as e:
                print(f"  FAIL: {e}")
                ok = False

    r = session_c2.post(f"{base_url}/api/session/start", json={"email": "CAROL_MULTI@test.com"})
    if r.status_code != 201:
        print(f"  FAIL: CAROL session start: {r.status_code}")
        ok = False
    else:
        r = session_c2.get(f"{base_url}/api/session/files")
        if r.status_code != 200 or len(r.json().get("files", [])) != 1:
            print(f"  FAIL: Same email (different case) should see 1 file: {r.status_code} {r.json()}")
            ok = False
        else:
            print("  Same email (different case) sees same 1 file (persistence OK).")

    return ok


def run_tests_mock() -> bool:
    """Run the same multi-user tests in-process with mocked ingestion (no server or Ollama)."""
    from unittest.mock import patch

    from src.document_ui import app as app_module

    app_module._jobs.clear()
    app_module._sessions.clear()
    app_module._chat_pipelines.clear()
    app_module._chat_messages.clear()

    flask_app = app_module.create_app()
    client_a = flask_app.test_client()
    client_b = flask_app.test_client()
    client_c1 = flask_app.test_client()
    client_c2 = flask_app.test_client()

    pdf = minimal_pdf()
    ok = True

    def poll(client, job_id: str, max_wait_sec: float = 5.0):
        deadline = time.monotonic() + max_wait_sec
        while time.monotonic() < deadline:
            r = client.get(f"/api/process/{job_id}/status")
            assert r.status_code == 200
            data = r.get_json()
            if data.get("state") == "completed":
                return data
            if data.get("state") == "failed":
                raise RuntimeError(f"Job failed: {data.get('error', data)}")
            time.sleep(0.15)
        raise RuntimeError(f"Job {job_id} did not complete within {max_wait_sec}s")

    with patch("src.chunk_embed_store.ingest_document", return_value=1):
        # --- Test 1: Session isolation ---
        print("Test 1: Session isolation (User A vs User B)")
        r = client_a.post("/api/session/start", json={"email": "alice_multi@test.com"})
        if r.status_code != 201:
            print(f"  FAIL: User A session start: {r.status_code} {r.data.decode()}")
            ok = False
        else:
            print("  User A session started.")

        r = client_a.post(
            "/api/process",
            data={"file": (BytesIO(pdf), "alice_file.pdf")},
        )
        if r.status_code != 202:
            print(f"  FAIL: User A upload: {r.status_code}")
            ok = False
        else:
            try:
                poll(client_a, r.get_json()["job_id"])
                print("  User A upload completed.")
            except RuntimeError as e:
                print(f"  FAIL: {e}")
                ok = False

        r = client_a.get("/api/session/files")
        if r.status_code != 200 or len(r.get_json().get("files", [])) != 1:
            print(f"  FAIL: User A should see 1 file: {r.status_code} {r.get_json()}")
            ok = False
        else:
            print("  User A sees 1 file.")

        r = client_b.post("/api/session/start", json={"email": "bob_multi@test.com"})
        if r.status_code != 201:
            print(f"  FAIL: User B session start: {r.status_code}")
            ok = False
        else:
            print("  User B session started.")

        r = client_b.get("/api/session/files")
        if r.status_code != 200 or len(r.get_json().get("files", [])) != 0:
            print(f"  FAIL: User B should see 0 files (isolation): {r.get_json()}")
            ok = False
        else:
            print("  User B sees 0 files (correct isolation).")

        r = client_b.post(
            "/api/process",
            data={"file": (BytesIO(pdf), "bob_file.pdf")},
        )
        if r.status_code != 202:
            print(f"  FAIL: User B upload: {r.status_code}")
            ok = False
        else:
            try:
                poll(client_b, r.get_json()["job_id"])
                print("  User B upload completed.")
            except RuntimeError as e:
                print(f"  FAIL: {e}")
                ok = False

        r = client_a.get("/api/session/files")
        if r.status_code != 200 or len(r.get_json().get("files", [])) != 1:
            print(f"  FAIL: User A should still see 1 file: {r.get_json()}")
            ok = False
        else:
            print("  User A still sees only 1 file (isolation OK).")

        # --- Test 2: Same email (different case) ---
        print("\nTest 2: Same email, different casing (session persistence)")
        r = client_c1.post("/api/session/start", json={"email": "carol_multi@test.com"})
        if r.status_code != 201:
            print(f"  FAIL: Carol session start: {r.status_code}")
            ok = False
        else:
            r = client_c1.post(
                "/api/process",
                data={"file": (BytesIO(pdf), "carol_file.pdf")},
            )
            if r.status_code != 202:
                print(f"  FAIL: Carol upload: {r.status_code}")
                ok = False
            else:
                try:
                    poll(client_c1, r.get_json()["job_id"])
                except RuntimeError as e:
                    print(f"  FAIL: {e}")
                    ok = False

        r = client_c2.post("/api/session/start", json={"email": "CAROL_MULTI@test.com"})
        if r.status_code != 201:
            print(f"  FAIL: CAROL session start: {r.status_code}")
            ok = False
        else:
            r = client_c2.get("/api/session/files")
            if r.status_code != 200 or len(r.get_json().get("files", [])) != 1:
                print(f"  FAIL: Same email (different case) should see 1 file: {r.get_json()}")
                ok = False
            else:
                print("  Same email (different case) sees same 1 file (persistence OK).")

    return ok


def main():
    parser = argparse.ArgumentParser(description="Multi-user API test (live server or --mock)")
    parser.add_argument("--mock", action="store_true", help="Run in-process with mocked ingestion (no server or Ollama)")
    parser.add_argument("base_url", nargs="?", default="http://localhost:8000", help="Base URL when not using --mock")
    args = parser.parse_args()

    if args.mock:
        print("Testing multi-user behaviour (mock mode – no server or Ollama required)\n")
        try:
            if run_tests_mock():
                print("\nAll multi-user tests passed.")
                sys.exit(0)
            else:
                print("\nSome tests failed.")
                sys.exit(1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if requests is None:
            print("Live mode requires 'requests'. Install with: pip install requests", file=sys.stderr)
            sys.exit(1)
        print(f"Testing multi-user behaviour at {args.base_url}\n")
        try:
            if run_tests(args.base_url):
                print("\nAll multi-user tests passed.")
                sys.exit(0)
            else:
                print("\nSome tests failed.")
                sys.exit(1)
        except requests.RequestException as e:
            print(f"Request error: {e}", file=sys.stderr)
            print("Make sure the Document UI server is running: python -m src.document_ui.app", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
