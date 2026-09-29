"use strict";

// Ordinary form submissions still work when JavaScript is unavailable.
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== "post") return;
  if (form.dataset.submitting === "true") {
    event.preventDefault();
    return;
  }
  if (event.defaultPrevented) return;
  form.dataset.submitting = "true";
  form.setAttribute("aria-busy", "true");
  for (const button of form.querySelectorAll("button[type=submit], button:not([type])")) {
    button.disabled = true;
    button.dataset.originalLabel = button.textContent;
    button.textContent = "処理中…";
  }
  document.getElementById("busy-message").hidden = false;
});

// Back navigation may restore the previous document, including disabled controls.
window.addEventListener("pageshow", () => {
  for (const form of document.querySelectorAll('form[data-submitting="true"]')) {
    delete form.dataset.submitting;
    form.removeAttribute("aria-busy");
    for (const button of form.querySelectorAll("button[data-original-label]")) {
      button.disabled = false;
      button.textContent = button.dataset.originalLabel;
      delete button.dataset.originalLabel;
    }
  }
  document.getElementById("busy-message").hidden = true;
});
