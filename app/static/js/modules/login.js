import { setButtonBusy } from "./utils.js?v=20260626-breakdowns-paper-fields";

export function initLogin() {
  const loginForm = document.querySelector("#login-form");
  if (!loginForm) {
    return;
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const error = document.querySelector("#login-error");
    const submitButton = loginForm.querySelector("button[type='submit']");
    const formData = new FormData(loginForm);
    const pin = String(formData.get("pin") || "");

    if (error) {
      error.hidden = true;
      error.textContent = "";
    }
    setButtonBusy(submitButton, true, "GiriÅŸ yapÄ±lÄ±yor");

    try {
      const response = await fetch("/api/login", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ pin }),
      });

      if (response.ok) {
        window.location.assign("/");
        return;
      }

      if (error) {
        error.textContent = "PIN geÃ§ersiz.";
        error.hidden = false;
      }
    } catch (_error) {
      if (error) {
        error.textContent = "GiriÅŸ baÅŸarÄ±sÄ±z. BaÄŸlantÄ±yÄ± kontrol edip tekrar deneyin.";
        error.hidden = false;
      }
    } finally {
      setButtonBusy(submitButton, false);
    }
  });
}
