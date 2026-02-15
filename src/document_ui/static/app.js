const form = document.getElementById("upload-form");
const processButton = document.getElementById("process-button");
const fileInput = document.getElementById("file-input");
const statusSection = document.getElementById("status-section");
const statusMessage = document.getElementById("status-message");
const progressBar = document.getElementById("progress-bar");
const resultSection = document.getElementById("result");
const filesBody = document.getElementById("files-body");
const talkButton = document.getElementById("talk-button");

const setStatus = (message, progress) => {
  statusMessage.textContent = message;
  progressBar.style.width = `${progress}%`;
  document.querySelector(".progress-wrapper").setAttribute("aria-valuenow", progress.toString());
};

const escapeHtml = (str) => {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
};

const renderFilesTable = (files) => {
  talkButton.disabled = files.length === 0;

  if (!files.length) {
    filesBody.innerHTML = `<tr><td colspan="3">No files processed yet.</td></tr>`;
    return;
  }

  filesBody.innerHTML = files
    .map(
      (item) =>
        `<tr>
          <td>${escapeHtml(item.file_name)}</td>
          <td>${Number(item.chunks_created)}</td>
          <td><button class="delete-btn" data-file-name="${escapeHtml(item.file_name)}">Delete</button></td>
        </tr>`,
    )
    .join("");
  
  // Add event listeners to delete buttons
  document.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const fileName = btn.getAttribute("data-file-name");
      if (confirm(`Are you sure you want to delete "${fileName}" and all its chunks?`)) {
        await deleteFile(fileName);
      }
    });
  });
};

const refreshFiles = async () => {
  const response = await fetch("/api/session/files");
  if (!response.ok) {
    return;
  }

  const data = await response.json();
  renderFilesTable(data.files || []);
};

const deleteFile = async (fileName) => {
  try {
    const response = await fetch(`/api/session/files/${encodeURIComponent(fileName)}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      const error = await response.json();
      resultSection.className = "result error";
      resultSection.textContent = error.error || "Failed to delete file.";
      return;
    }

    // Refresh the files table
    await refreshFiles();
    resultSection.className = "result success";
    resultSection.textContent = `Successfully deleted "${fileName}" and all its chunks.`;
  } catch (error) {
    resultSection.className = "result error";
    resultSection.textContent = `Error deleting file: ${error.message}`;
  }
};

const pollStatus = async (jobId) => {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/process/${jobId}/status`);
    if (!response.ok) {
      clearInterval(interval);
      processButton.disabled = false;
      fileInput.disabled = false;
      resultSection.className = "result error";
      resultSection.textContent = "Unable to retrieve status.";
      return;
    }

    const data = await response.json();
    setStatus(data.message, data.progress);

    if (data.state === "completed") {
      clearInterval(interval);
      processButton.disabled = false;
      fileInput.disabled = false;
      resultSection.className = "result success";
      resultSection.textContent = `Success: ${data.filename} processed with ${data.chunks_created} chunks.`;
      await refreshFiles();
    }

    if (data.state === "failed") {
      clearInterval(interval);
      processButton.disabled = false;
      fileInput.disabled = false;
      resultSection.className = "result error";
      resultSection.textContent = `Failed: ${data.error || "Unknown error"}`;
    }
  }, 1000);
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) {
    return;
  }

  processButton.disabled = true;
  fileInput.disabled = true;
  statusSection.classList.remove("hidden");
  resultSection.className = "result";
  resultSection.textContent = "";
  setStatus("Uploading file...", 5);

  const payload = new FormData();
  payload.append("file", fileInput.files[0]);

  const response = await fetch("/api/process", {
    method: "POST",
    body: payload,
  });

  if (!response.ok) {
    processButton.disabled = false;
    fileInput.disabled = false;
    const error = await response.json();
    resultSection.className = "result error";
    resultSection.textContent = error.error || "Failed to start processing.";
    return;
  }

  const data = await response.json();
  pollStatus(data.job_id);
  fileInput.value = "";
});

// Session is kept persistent; user can end it via a future "End session" action if needed.
// Do not call session/end on beforeunload or navigating to /chat would log them out.

refreshFiles();

talkButton.addEventListener("click", () => {
  window.location.href = "/chat";
});