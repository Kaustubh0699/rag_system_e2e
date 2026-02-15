from io import BytesIO

import pytest

pytest.importorskip("flask")

from src.document_ui import app


@pytest.fixture(autouse=True)
def clear_state():
    app._jobs.clear()
    app._sessions.clear()


def test_start_session_requires_valid_email():
    flask_app = app.create_app()
    client = flask_app.test_client()

    response = client.post("/api/session/start", json={"email": "invalid"})

    assert response.status_code == 400


def test_upload_requires_active_session():
    flask_app = app.create_app()
    client = flask_app.test_client()

    response = client.post(
        "/api/process",
        data={"file": (BytesIO(b"data"), "sample.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_run_ingestion_job_updates_session_files(tmp_path):
    session_id = "session-1"
    session_dir = tmp_path / session_id
    session_dir.mkdir(parents=True)

    app._sessions[session_id] = app.SessionState(
        email="user@example.com",
        session_dir=session_dir,
        db_path=session_dir / "chroma_db",
        files=[],
    )

    app._jobs["job-success"] = app.JobStatus(
        state="uploading",
        progress=10,
        message="Uploading file...",
        filename="sample.pdf",
        app_session_id=session_id,
    )

    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"data")

    app._run_ingestion_job("job-success", file_path, session_id, ingest_fn=lambda *_args, **_kwargs: 4)

    status = app._jobs["job-success"]
    assert status.state == "completed"
    assert status.chunks_created == 4
    assert app._sessions[session_id].files[0].file_name == "sample.pdf"


def test_run_ingestion_job_rejects_legacy_ppt(tmp_path):
    session_id = "session-2"
    session_dir = tmp_path / session_id
    session_dir.mkdir(parents=True)

    app._sessions[session_id] = app.SessionState(
        email="user@example.com",
        session_dir=session_dir,
        db_path=session_dir / "chroma_db",
        files=[],
    )

    app._jobs["job-fail"] = app.JobStatus(
        state="uploading",
        progress=10,
        message="Uploading file...",
        filename="legacy.ppt",
        app_session_id=session_id,
    )

    file_path = tmp_path / "legacy.ppt"
    file_path.write_bytes(b"data")

    app._run_ingestion_job("job-fail", file_path, session_id)

    status = app._jobs["job-fail"]
    assert status.state == "failed"
    assert "convert to .pptx" in (status.error or "")
