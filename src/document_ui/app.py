"""Flask UI for session-scoped document upload and embedding ingestion."""

from __future__ import annotations

import hashlib
import logging
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import gettempdir
from time import time
from typing import Dict

import yaml
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".ppt", ".pptx"}
# Use project directory for sessions and uploads
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_ROOT = PROJECT_ROOT / "uploads"
SESSION_ROOT = PROJECT_ROOT / "sessions"
BASE_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@dataclass
class SessionFileRecord:
    file_name: str
    chunks_created: int


@dataclass
class SessionState:
    email: str
    session_dir: Path
    db_path: Path
    files: list[SessionFileRecord]


@dataclass
class JobStatus:
    state: str
    progress: int
    message: str
    filename: str
    app_session_id: str
    chunks_created: int | None = None
    error: str | None = None


_jobs: Dict[str, JobStatus] = {}
_sessions: Dict[str, SessionState] = {}
_state_lock = threading.Lock()


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = "dev-rag-system-secret"

    @app.get("/")
    def index():
        return render_template("email.html")

    @app.get("/upload")
    def upload_page():
        app_session_id = session.get("app_session_id")
        if not app_session_id or app_session_id not in _sessions:
            return redirect(url_for("index"))

        return render_template("upload.html", email=_sessions[app_session_id].email)

    @app.post("/api/session/start")
    def start_session():
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or "").strip()

        if not email or "@" not in email:
            return jsonify({"error": "Please enter a valid email address."}), 400

        # Create session ID from email hash for persistence
        email_hash = hashlib.md5(email.encode()).hexdigest()
        app_session_id = email_hash
        
        session_dir = SESSION_ROOT / app_session_id
        db_path = session_dir / "chroma_db"
        session_dir.mkdir(parents=True, exist_ok=True)

        # Check if session already exists and load existing files
        existing_files = []
        if app_session_id in _sessions:
            # Session already in memory, reuse it
            existing_files = _sessions[app_session_id].files
        else:
            # Try to load existing files from ChromaDB
            existing_files = _load_existing_files(db_path)

        with _state_lock:
            _sessions[app_session_id] = SessionState(
                email=email,
                session_dir=session_dir,
                db_path=db_path,
                files=existing_files,
            )

        session["app_session_id"] = app_session_id
        return jsonify({"redirect": url_for("upload_page")}), 201

    @app.post("/api/process")
    def process_document():
        app_session_id = session.get("app_session_id")
        if not app_session_id:
            return jsonify({"error": "No active session. Please enter email first."}), 400

        with _state_lock:
            session_state = _sessions.get(app_session_id)

        if session_state is None:
            return jsonify({"error": "Session expired. Please enter email again."}), 400

        if "file" not in request.files:
            return jsonify({"error": "No file provided."}), 400

        uploaded_file = request.files["file"]
        if not uploaded_file.filename:
            return jsonify({"error": "Empty filename."}), 400

        filename = secure_filename(uploaded_file.filename)
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            return jsonify({"error": "Unsupported file type. Use PDF, PPT, or PPTX."}), 400

        UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        job_id = str(uuid.uuid4())
        destination = UPLOAD_ROOT / f"{job_id}_{filename}"

        with _state_lock:
            _jobs[job_id] = JobStatus(
                state="uploading",
                progress=10,
                message="Uploading file...",
                filename=filename,
                app_session_id=app_session_id,
            )

        uploaded_file.save(destination)

        thread = threading.Thread(
            target=_run_ingestion_job,
            args=(job_id, destination, app_session_id),
            daemon=True,
        )
        thread.start()

        return jsonify({"job_id": job_id}), 202

    @app.get("/api/process/<job_id>/status")
    def process_status(job_id: str):
        app_session_id = session.get("app_session_id")
        if not app_session_id:
            return jsonify({"error": "No active session."}), 400

        with _state_lock:
            job = _jobs.get(job_id)
        if not job or job.app_session_id != app_session_id:
            return jsonify({"error": "Job not found."}), 404

        return jsonify(asdict(job))

    @app.get("/api/session/files")
    def session_files():
        app_session_id = session.get("app_session_id")
        if not app_session_id:
            return jsonify({"error": "No active session."}), 400

        with _state_lock:
            state = _sessions.get(app_session_id)

        if state is None:
            return jsonify({"error": "Session expired."}), 400

        files = [asdict(record) for record in state.files]
        return jsonify({"files": files, "email": state.email})

    @app.delete("/api/session/files/<file_name>")
    def delete_file(file_name: str):
        app_session_id = session.get("app_session_id")
        if not app_session_id:
            return jsonify({"error": "No active session."}), 400

        with _state_lock:
            session_state = _sessions.get(app_session_id)

        if session_state is None:
            return jsonify({"error": "Session expired."}), 400

        try:
            deleted_count = _delete_file_from_db(session_state.db_path, file_name)
            
            # Remove from session files list
            with _state_lock:
                session_state.files = [
                    f for f in session_state.files if f.file_name != file_name
                ]
            
            return jsonify({"message": f"Deleted {deleted_count} chunks for {file_name}"}), 200
        except Exception as e:
            return jsonify({"error": f"Failed to delete file: {str(e)}"}), 500

    @app.post("/api/session/end")
    def end_session():
        payload = request.get_json(silent=True) or {}
        delete_data = payload.get("delete_data", False)
        
        app_session_id = session.get("app_session_id")
        if app_session_id:
            _cleanup_session(app_session_id, delete_data=delete_data)
            session.pop("app_session_id", None)
        return jsonify({"message": "Session closed."}), 200

    return app


def _run_ingestion_job(job_id: str, file_path: Path, app_session_id: str, ingest_fn=None) -> None:
    with _state_lock:
        job = _jobs[job_id]
        session_state = _sessions.get(app_session_id)

    if session_state is None:
        job.state = "failed"
        job.progress = 100
        job.error = "Session expired before processing started."
        job.message = "Document processing failed."
        return

    try:
        if file_path.suffix.lower() == ".ppt":
            raise ValueError(".ppt binary format is not supported by parser. Please convert to .pptx.")

        job.state = "extracting"
        job.progress = 35
        job.message = "Extracting document text..."

        start_time = time()

        job.state = "embedding"
        job.progress = 70
        job.message = "Creating embeddings and storing chunks..."

        config_path = _build_session_config(session_state)

        if ingest_fn is None:
            from src.chunk_embed_store import ingest_document

            ingest_fn = ingest_document

        chunks_created = ingest_fn(file_path, config_path=config_path)
        elapsed = round(time() - start_time, 2)

        with _state_lock:
            latest_state = _sessions.get(app_session_id)
            if latest_state is not None:
                latest_state.files.append(
                    SessionFileRecord(file_name=job.filename, chunks_created=chunks_created)
                )

        job.state = "completed"
        job.progress = 100
        job.chunks_created = chunks_created
        job.message = f"Document processed successfully in {elapsed}s."
    except Exception as exc:  # noqa: BLE001
        job.state = "failed"
        job.progress = 100
        job.error = str(exc)
        job.message = "Document processing failed."
    finally:
        if file_path.exists():
            file_path.unlink(missing_ok=True)


def _build_session_config(session_state: SessionState) -> Path:
    with BASE_CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    config.setdefault("chromadb", {})
    config["chromadb"]["db_path"] = str(session_state.db_path)
    config["chromadb"]["collection_name"] = "documents"

    config_path = session_state.session_dir / "session_config.yaml"
    with config_path.open("w", encoding="utf-8") as config_file:
        yaml.safe_dump(config, config_file, sort_keys=False)

    return config_path


def _load_existing_files(db_path: Path) -> list[SessionFileRecord]:
    """Load existing files from ChromaDB collection."""
    try:
        import chromadb
        from chromadb.config import Settings
        
        if not db_path.exists():
            return []
        
        client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        try:
            collection = client.get_collection(name="documents")
        except Exception:
            # Collection doesn't exist yet
            return []
        
        # Get all documents from the collection
        results = collection.get()
        
        if not results or not results.get("ids"):
            return []
        
        # Group by document ID to count chunks per file
        doc_chunks: Dict[str, int] = {}
        metadatas = results.get("metadatas", [])
        
        for metadata in metadatas:
            if metadata and "file_name" in metadata:
                file_name = metadata["file_name"]
                doc_chunks[file_name] = doc_chunks.get(file_name, 0) + 1
        
        # Convert to SessionFileRecord list
        files = [
            SessionFileRecord(file_name=file_name, chunks_created=chunk_count)
            for file_name, chunk_count in doc_chunks.items()
        ]
        
        return files
    except Exception:
        # If anything fails, return empty list
        return []


def _delete_file_from_db(db_path: Path, file_name: str) -> int:
    """Delete all chunks for a specific file from ChromaDB."""
    try:
        import chromadb
        from chromadb.config import Settings
        
        if not db_path.exists():
            return 0
        
        client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        try:
            collection = client.get_collection(name="documents")
        except Exception:
            # Collection doesn't exist
            return 0
        
        # Get all documents and filter by file_name in metadata
        all_results = collection.get()
        
        if not all_results or not all_results.get("ids"):
            return 0
        
        # Filter chunks by file_name in metadata
        chunk_ids_to_delete = []
        ids = all_results.get("ids", [])
        metadatas = all_results.get("metadatas", [])
        
        for idx, metadata in enumerate(metadatas):
            if metadata and metadata.get("file_name") == file_name:
                if idx < len(ids):
                    chunk_ids_to_delete.append(ids[idx])
        
        if not chunk_ids_to_delete:
            return 0
        
        # Delete all chunks for this file
        collection.delete(ids=chunk_ids_to_delete)
        
        return len(chunk_ids_to_delete)
    except Exception as e:
        logger.error(f"Failed to delete file from DB: {e}")
        raise


def _cleanup_session(app_session_id: str, delete_data: bool = False) -> None:
    """Clean up a session by ID.
    
    Args:
        app_session_id: Session ID to clean up
        delete_data: If True, delete the session directory. If False, just remove from memory.
    """
    with _state_lock:
        state = _sessions.pop(app_session_id, None)
        # Remove all jobs for this session
        job_ids_to_remove = [
            job_id for job_id, job in _jobs.items() if job.app_session_id == app_session_id
        ]
        for job_id in job_ids_to_remove:
            _jobs.pop(job_id, None)

    if delete_data and state and state.session_dir.exists():
        shutil.rmtree(state.session_dir, ignore_errors=True)


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000, debug=True)
