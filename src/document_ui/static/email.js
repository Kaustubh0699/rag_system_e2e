const emailForm = document.getElementById("email-form");
const emailResult = document.getElementById("result");

emailForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const email = document.getElementById("email-input").value.trim();
  emailResult.className = "result";
  emailResult.textContent = "";

  const response = await fetch("/api/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  const data = await response.json();

  if (!response.ok) {
    emailResult.className = "result error";
    emailResult.textContent = data.error || "Unable to start session.";
    return;
  }

  window.location.href = data.redirect;
});
