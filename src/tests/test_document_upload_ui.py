from io import BytesIO
import json
import pytest

pytest.importorskip("flask")

from src.document_ui import app


@pytest.fixture(autouse=True)
def clear_state():
    app._jobs.clear()
    app._sessions.clear()
    app._chat_pipelines.clear()
    app._chat_messages.clear()

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

def test_chat_endpoint_requires_documents():
    flask_app = app.create_app()
    client = flask_app.test_client()
    client.post("/api/session/start", json={"email": "user@example.com"})

    response = client.post("/api/chat", json={"question": "What is in my docs?"})

    assert response.status_code == 400
    assert "Upload at least one document" in response.json["error"]


def test_chat_endpoint_returns_answer(monkeypatch, tmp_path):
    class DummyResponse:
        response = "Here is your answer"
        context_chunk_ids = ["chunk-1", "chunk-2"]

    class DummyPipeline:
        def __init__(self, config_path):
            self.config_path = config_path

        def ask(self, session_id, question):
            assert session_id
            assert question == "Summarize"
            return DummyResponse()

    monkeypatch.setattr(
        "src.response_generator.orchestrator.GroundedRAGPipeline",
        DummyPipeline,
    )

    flask_app = app.create_app()
    client = flask_app.test_client()
    client.post("/api/session/start", json={"email": "user@example.com"})

    session_id = next(iter(app._sessions.keys()))
    app._sessions[session_id].files.append(
        app.SessionFileRecord(file_name="sample.pdf", chunks_created=3)
    )
    app._sessions[session_id].session_dir = tmp_path / session_id
    app._sessions[session_id].session_dir.mkdir(parents=True, exist_ok=True)

    response = client.post("/api/chat", json={"question": "Summarize"})

    assert response.status_code == 200
    assert response.json["answer"] == "Here is your answer"
    assert len(response.json["sources"]) == 2

def test_chat_stream_endpoint_streams_chunks(monkeypatch, tmp_path):
    class DummyResponse:
        response = "Here is streamed answer"
        context_chunk_ids = ["chunk-1", "chunk-2"]

    class DummyPipeline:
        def __init__(self, config_path):
            self.config_path = config_path

        def ask(self, session_id, question):
            return DummyResponse()

        def ask_stream(self, session_id, question):
            assert session_id
            assert question == "Stream it"

            def _generator():
                yield "Here "
                yield "is "
                yield "streamed answer"
                return DummyResponse()

            return _generator()

    monkeypatch.setattr(
        "src.response_generator.orchestrator.GroundedRAGPipeline",
        DummyPipeline,
    )

    flask_app = app.create_app()
    client = flask_app.test_client()
    client.post("/api/session/start", json={"email": "user@example.com"})

    session_id = next(iter(app._sessions.keys()))
    app._sessions[session_id].files.append(
        app.SessionFileRecord(file_name="sample.pdf", chunks_created=3)
    )
    app._sessions[session_id].session_dir = tmp_path / session_id
    app._sessions[session_id].session_dir.mkdir(parents=True, exist_ok=True)

    response = client.post("/api/chat/stream", json={"question": "Stream it"})

    assert response.status_code == 200
    events = [json.loads(line) for line in response.data.decode().splitlines() if line.strip()]
    assert events[0]["type"] == "chunk"
    assert events[-1]["type"] == "done"
    assert events[-1]["answer"] == "Here is streamed answer"