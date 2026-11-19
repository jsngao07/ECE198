// Browser-side USB Serial bridge for CCCARE Arduino V2/V3.
// Data is assigned to the currently signed-in patient, not a patient ID from the device.
(() => {
  "use strict";

  const panel = document.getElementById("arduino-sync");
  if (!panel) return;

  const connectButton = document.getElementById("arduino-connect");
  const disconnectButton = document.getElementById("arduino-disconnect");
  const planSelect = document.getElementById("arduino-plan");
  const statusNode = document.getElementById("arduino-status");
  const csrfInput = document.getElementById("arduino-csrf");
  const uploadUrl = panel.dataset.uploadUrl;

  let port = null;
  let reader = null;
  let connected = false;
  let buffer = "";
  const decoder = new TextDecoder();

  function status(message, isError = false) {
    statusNode.textContent = message;
    statusNode.style.color = isError ? "#d64e61" : "";
  }

  function parseExerciseRecord(line) {
    const parts = line.trim().split(",");
    if (parts[0] !== "EXERCISE" || parts.length !== 10) return null;
    const fields = {};
    for (let i = 2; i + 1 < parts.length; i += 2) {
      fields[parts[i]] = parts[i + 1];
    }
    const reps = Number(fields.ACTUAL_REPS);
    const seconds = Number(fields.ACTUAL_SECONDS);
    if (!parts[1] || !Number.isInteger(reps) || !Number.isInteger(seconds) ||
        reps < 0 || seconds < 0) {
      throw new Error("Arduino exercise output is not valid.");
    }
    return { exercise_name: parts[1].trim(), actual_reps: reps, actual_seconds: seconds };
  }

  async function upload(record) {
    const candidates = Array.from(planSelect.options).filter(
      option => option.dataset.exercise?.trim().toLowerCase() === record.exercise_name.toLowerCase()
    );
    if (candidates.length === 0) {
      throw new Error("Received '" + record.exercise_name +
        "', but no active exercise plan with that name is assigned to this patient. Ask the instructor to assign it first.");
    }
    if (candidates.length === 1) planSelect.value = candidates[0].value;
    else if (!candidates.some(option => option.value === planSelect.value)) {
      throw new Error("Multiple matching plans exist. Select the correct exercise plan, then complete the session again.");
    }

    const payload = { ...record, plan_id: Number(planSelect.value) };
    status("Received " + record.exercise_name + " (" + record.actual_reps +
      " reps, " + record.actual_seconds + " seconds). Saving to your profile...");
    const response = await fetch(uploadUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfInput.value,
      },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    const contentType = response.headers.get("content-type") || "";
    const result = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok || !result?.ok) {
      throw new Error(result?.error || "Upload failed. Sign in again, reload this page, and retry.");
    }
    status("Saved successfully! Updating Recent progress...");
    // Reload shows the new database record. The user reconnects for the next session.
    window.location.reload();
  }

  async function readFromDevice() {
    try {
      while (connected && port?.readable) {
        reader = port.readable.getReader();
        try {
          while (connected) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            let end;
            while ((end = buffer.indexOf("\n")) >= 0) {
              const line = buffer.slice(0, end).replace(/\r$/, "").trim();
              buffer = buffer.slice(end + 1);
              const record = parseExerciseRecord(line);
              if (record) {
                await upload(record);
                return;
              }
            }
            if (buffer.length > 4096) buffer = buffer.slice(-1024);
          }
        } finally {
          reader.releaseLock();
          reader = null;
        }
      }
    } catch (error) {
      status(error.message || "Unable to read from Arduino.", true);
    } finally {
      connected = false;
      connectButton.disabled = false;
      disconnectButton.disabled = true;
      if (port) {
        try { await port.close(); } catch (_) { /* already disconnected */ }
        port = null;
      }
    }
  }

  connectButton.addEventListener("click", async () => {
    if (!("serial" in navigator)) {
      status("Use desktop Google Chrome or Microsoft Edge with HTTPS for USB Serial.", true);
      return;
    }
    if (!planSelect.options.length) {
      status("An instructor must assign an active exercise plan first.", true);
      return;
    }
    try {
      port = await navigator.serial.requestPort();
      await port.open({ baudRate: 115200 });
      connected = true;
      buffer = "";
      connectButton.disabled = true;
      disconnectButton.disabled = false;
      status("Connected at 115200 baud. Finish the Arduino exercise and press Confirm on the final confirmation screen.");
      void readFromDevice();
    } catch (error) {
      status(error.message || "Could not connect. Close Arduino IDE Serial Monitor and try again.", true);
      try { await port?.close(); } catch (_) { /* ignore */ }
      port = null;
    }
  });

  disconnectButton.addEventListener("click", async () => {
    connected = false;
    if (reader) {
      try { await reader.cancel(); } catch (_) { /* already closed */ }
    }
    status("Disconnecting Arduino...");
  });
})();
