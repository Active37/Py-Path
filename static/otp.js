(() => {
  const card = document.querySelector("[data-otp-expiry]");
  if (!card) return;

  const countdown = card.querySelector("[data-otp-countdown]");
  const resendButton = card.querySelector("[data-otp-resend-button]");
  const expiresAt = Number(card.dataset.otpExpiry);
  const resendAt = Number(card.dataset.otpResend);

  card.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector("[data-otp-submit]");
      if (!button) return;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      const label = button.querySelector("[data-otp-submit-label]");
      const spinner = button.querySelector("[data-otp-spinner]");
      if (label) label.textContent = button.dataset.loadingLabel || "Working...";
      if (spinner) spinner.hidden = false;
    });
  });

  const remainingTime = (timestamp) => {
    const remaining = Math.max(0, Math.ceil((timestamp - Date.now()) / 1000));
    const minutes = Math.floor(remaining / 60);
    const seconds = String(remaining % 60).padStart(2, "0");
    return { remaining, label: `${minutes}:${seconds}` };
  };

  const updateTimers = () => {
    const expiry = remainingTime(expiresAt);
    const resend = remainingTime(resendAt);
    if (countdown) {
      countdown.textContent = expiry.remaining
        ? `Code expires in ${expiry.label}.`
        : "This code has expired. Request a new one.";
    }
    if (resendButton) {
      resendButton.disabled = resend.remaining > 0;
      resendButton.textContent = resend.remaining
        ? `Resend code in ${resend.label}`
        : "Resend code";
    }
  };

  updateTimers();
  window.setInterval(updateTimers, 1000);
})();
