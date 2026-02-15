# Document Upload UI

A Flask-based web interface for uploading and processing PDF and PPTX documents with session-scoped ChromaDB storage. Each user session gets an isolated ChromaDB instance for their documents.

## Session Flow

1. **Start Session**: User enters email address on the start page
2. **Redirect**: User is redirected to the upload page with an active session
3. **Upload & Process**: User uploads documents which are processed into a **session-scoped ChromaDB**
4. **Track Progress**: Upload button and file input are disabled while processing, with real-time progress updates
5. **View Results**: Session table shows all processed files with chunk counts
6. **Persistent Sessions**: Sessions are **persistent** - if you close the tab and log in again with the same email, you'll see all previously processed files and can continue adding more documents to the same ChromaDB

## Features

- **Session Isolation**: Each user gets their own ChromaDB instance (identified by email)
- **Persistent Sessions**: Sessions persist across browser sessions - log in with the same email to resume
- **File Upload**: Upload PDF, PPT, or PPTX files through a simple web interface
- **Background Processing**: Documents are processed asynchronously in background threads
- **Real-time Status**: Poll-based status updates with visual progress bar
- **Session Management**: Track all processed files per session, automatically loaded from ChromaDB

## Prerequisites

Before running the Document UI, ensure you have:

1. **Python 3.11+** installed
2. **Dependencies installed** from the project root:
   ```bash
   pip install -r requirements.txt
   ```
   This includes Flask, which is required for the UI.

3. **Ollama running** (if using Ollama for embeddings):
   ```bash
   ollama serve
   ```

4. **Embedding model downloaded** (if using Ollama):
   ```bash
   ollama pull nomic-embed-text
   # or
   ollama pull mxbai-embed-large
   ```

5. **Configuration file** (`config.yaml`) in the project root

## Installation

No additional installation needed beyond the main project dependencies. The UI uses Flask for the web server.

## Running the Server

### Method 1: Run as a module (Recommended)

From the project root directory:

```bash
PYTHONPATH=. python -m src.document_ui.app
```

### Method 2: Run directly

From the project root directory:

```bash
cd src/document_ui
PYTHONPATH=../.. python app.py
```

### Method 3: Using Flask CLI

From the project root:

```bash
export FLASK_APP=src.document_ui.app:create_app
export PYTHONPATH=.
flask run --host=0.0.0.0 --port=8000
```

## Accessing the UI

Once the server is running, open your web browser and navigate to:

```
http://localhost:8000
```

The default server runs on `0.0.0.0:8000` (accessible from all network interfaces).

## Usage

1. **Start the server** using one of the methods above
2. **Open your browser** to `http://localhost:8000`
3. **Enter your email** on the start page and click "Continue to Upload"
4. **Upload documents**: Click "Choose document" and select a PDF or PPTX file
5. **Process**: Click "Process Document" to start processing
6. **Monitor progress**: Watch the progress bar and status messages
7. **View results**: Success message shows number of chunks created, and the files table updates
8. **Upload more**: You can upload multiple files in the same session
9. **Close session**: Close the browser tab to automatically clean up session data

## API Endpoints

### POST `/api/session/start`

Start a new user session with an email address.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "redirect": "/upload"
}
```
- Status: `201 Created` on success
- Status: `400 Bad Request` for invalid email

### GET `/upload`

Upload page (requires active session). Redirects to `/` if no session.

### POST `/api/process`

Upload and start processing a document.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: Form data with `file` field containing the document
- Requires: Active session (set via cookie)

**Response:**
```json
{
  "job_id": "uuid-string"
}
```
- Status: `202 Accepted` on success
- Status: `400 Bad Request` for invalid files, missing file, or no active session

### GET `/api/process/<job_id>/status`

Get the current status of a processing job.

**Response:**
```json
{
  "state": "uploading|extracting|embedding|completed|failed",
  "progress": 0-100,
  "message": "Status message",
  "filename": "document.pdf",
  "app_session_id": "uuid",
  "chunks_created": 42,
  "error": null
}
```

**Job States:**
- `uploading`: File is being uploaded (progress: 10%)
- `extracting`: Document text is being extracted (progress: 35%)
- `embedding`: Creating embeddings and storing in ChromaDB (progress: 70%)
- `completed`: Processing finished successfully (progress: 100%)
- `failed`: Processing failed (progress: 100%, error field contains details)

### GET `/api/session/files`

Get list of all processed files for the current session.

**Response:**
```json
{
  "files": [
    {
      "file_name": "document.pdf",
      "chunks_created": 42
    }
  ],
  "email": "user@example.com"
}
```

### POST `/api/session/end`

End the current session. Optionally delete session data.

**Request (optional):**
```json
{
  "delete_data": true  // If true, deletes session directory and ChromaDB
}
```

**Response:**
```json
{
  "message": "Session closed."
}
```

**Note**: By default, session data is NOT deleted - it persists for future logins. Set `delete_data: true` to permanently remove the session.

## Session Management

### Session Storage

Each session creates:
- **Session directory**: `{TEMP}/rag_system_sessions/{session_id}/`
- **ChromaDB instance**: `{session_dir}/chroma_db/`
- **Session config**: `{session_dir}/session_config.yaml`

### Session Isolation

- Each email address gets a unique session ID (derived from email hash)
- Each session has its own ChromaDB instance
- Jobs are scoped to sessions (users can only see their own jobs)
- **Sessions are persistent** - closing the browser tab does NOT delete session data
- When you log in again with the same email, you'll see all previously processed files
- Existing files are automatically loaded from ChromaDB when resuming a session

### File Storage

Uploaded files are temporarily stored in:
- **Windows**: `%TEMP%\rag_system_uploads\`
- **Linux/macOS**: `/tmp/rag_system_uploads/`

Files are automatically deleted after processing completes.

## Architecture

```
src/document_ui/
├── app.py              # Flask application and routes
├── __init__.py         # Module exports
├── templates/
│   ├── email.html      # Email entry page
│   └── upload.html     # Document upload page
└── static/
    ├── app.js          # Upload page JavaScript (polling, UI updates)
    ├── email.js        # Email page JavaScript
    └── style.css       # Styling
```

**Key Components:**
- `create_app()`: Flask application factory
- `SessionState`: Tracks session data (email, directory, files)
- `JobStatus`: Tracks individual processing job state
- `_run_ingestion_job()`: Background thread function that calls `ingest_document`
- `_build_session_config()`: Creates session-specific config with isolated ChromaDB path
- `_cleanup_session()`: Removes session data and files

## Supported File Formats

- **PDF** (`.pdf`) - Fully supported
- **PPTX** (`.pptx`) - Fully supported (Office Open XML format)
- **PPT** (`.ppt`) - **Not supported** (old binary format). Users will see an error message suggesting conversion to PPTX.

## Error Handling

The UI handles various error scenarios:

- **Invalid email**: Returns 400 with error message
- **No active session**: Redirects to start page or returns 400
- **Invalid file type**: Returns 400 with error message
- **Missing file**: Returns 400 with error message
- **Processing errors**: Captured and displayed to user with error details
- **Session expiration**: User is redirected to start page
- **Network errors**: Frontend handles failed status requests gracefully

## Troubleshooting

### Server won't start

- **Port already in use**: Change the port in `app.py` or stop the process using port 8000
- **Module not found**: Ensure you're running from project root with `PYTHONPATH=.`
- **Flask not installed**: Run `pip install -r requirements.txt`

### Files not processing

- **Check Ollama**: Ensure Ollama is running if using Ollama embeddings
- **Check config.yaml**: Verify embedding provider and model settings
- **Check logs**: Server logs errors to console (Flask debug mode shows detailed errors)
- **File size**: Very large files may take longer or timeout
- **Session expired**: Re-enter email to start a new session

### UI not loading

- **Check browser console**: Open developer tools (F12) for JavaScript errors
- **Check static files**: Ensure `static/style.css` and `static/app.js` exist
- **CORS issues**: Should not occur with same-origin requests
- **Template errors**: Check Flask console for template rendering errors

### Processing fails

- **Context length errors**: Reduce `chunk_size_tokens` in `config.yaml`
- **File format errors**: Ensure PPTX (not PPT) files are used
- **ChromaDB errors**: Check write permissions for session directories
- **Session cleanup**: If sessions aren't cleaning up, manually delete `{TEMP}/rag_system_sessions/`

### Session issues

- **Session not persisting**: Check browser cookies are enabled
- **Multiple sessions**: Each browser tab gets its own session
- **Session cleanup**: Sessions are cleaned on tab close, but may persist if browser crashes

## Development

### Running in Development Mode

The app runs with `debug=True` by default when run directly:

```python
if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000, debug=True)
```

This enables:
- Auto-reload on code changes
- Detailed error pages
- Debug console

### Testing

Test files are located in `src/tests/test_document_upload_ui.py`. Run tests from project root:

```bash
python -m pytest src/tests/test_document_upload_ui.py
```

### Production Deployment

For production use:

1. **Set proper SECRET_KEY**: Change `app.config["SECRET_KEY"]` in `app.py`
2. **Use WSGI server**: Deploy with Gunicorn or uWSGI:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8000 "src.document_ui.app:create_app()"
   ```
3. **Add authentication**: Implement user authentication
4. **Add rate limiting**: Prevent abuse
5. **Use reverse proxy**: Use nginx with HTTPS
6. **Session cleanup**: Implement periodic cleanup of old sessions
7. **File size limits**: Add `MAX_CONTENT_LENGTH` to Flask config

## Security Notes

⚠️ **This is a development server, not production-ready:**

- **Weak secret key**: Uses hardcoded "dev-rag-system-secret" (change for production)
- **No authentication**: Anyone can access any session with the session ID
- **No file size limits**: Add `MAX_CONTENT_LENGTH` to Flask config
- **No rate limiting**: Add rate limiting to prevent abuse
- **Session storage**: Sessions stored in temp directory (consider database)
- **No HTTPS**: Use reverse proxy for production
- **Email validation**: Basic email validation (just checks for "@")

For production use, consider:
- Using a proper WSGI server (Gunicorn, uWSGI)
- Adding authentication and authorization
- Implementing file size limits
- Adding rate limiting
- Using a reverse proxy (nginx) with HTTPS
- Implementing proper session management (database-backed)
- Adding input validation and sanitization

## Dependencies

The UI module depends on:
- `Flask>=3.0.0` - Web framework
- `werkzeug` - WSGI utilities (comes with Flask)
- `pyyaml` - YAML config parsing
- `src.chunk_embed_store` - For document ingestion

All dependencies are in the main project `requirements.txt`.

## License

Part of the RAG System project.
