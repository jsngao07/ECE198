// Browser-side USB Serial bridge for CCCARE Arduino V2/V3 upload and V4 bidirectional sync.
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
  const sendButton = document.getElementById("arduino-send");
  const prescriptionUrl = panel.dataset.prescriptionUrl;

  // Instructors must assign a plan before the connection controls are rendered.
  if (!connectButton || !disconnectButton || !planSelect || !statusNode || !csrfInput) return;

  let port = null;
  let reader = null;
  let connected = false;
  let buffer = "";
  let pendingDosage = null;
  let sending = false;
  let readyAt = 0;
  let activeWrite = Promise.resolve();
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();

  function status(message, isError = false) {
    statusNode.textContent = message;
    statusNode.style.color = isError ? "#d64e61" : "";
  }


  function rejectDosage(message) {
    if (!pendingDosage) return;
    clearTimeout(pendingDosage.timeout);
    const reject = pendingDosage.reject;
    pendingDosage = null;
    reject(new Error(message));
  }

  function handleDosageReply(line) {
    if (line.startsWith("ACK,")) {
      if (pendingDosage && line === "ACK," + pendingDosage.exerciseIndex) {
        clearTimeout(pendingDosage.timeout);
        const resolve = pendingDosage.resolve;
        pendingDosage = null;
        resolve();
      }
      return true;
    }
    if (line.startsWith("ERROR,")) {
      const message = line === "ERROR,BUSY"
        ? "Arduino is busy. Finish or reset the workout with B4 before sending dosage; pausing alone is not enough."
        : "Arduino rejected dosage (" + line + "). Check the firmware and plan values.";
      rejectDosage(message);
      return true;
    }
    return false;
  }

  async function sendDosage() {
    if (!connected || sending || !port?.writable) return;
    sending = true;
    sendButton.disabled = true;
    planSelect.disabled = true;
    try {
      status("Getting your latest instructor dosage...");
      const response = await fetch(prescriptionUrl.replace(/0$/, planSelect.value), {
        credentials: "same-origin", cache: "no-store"
      });
      const result = (response.headers.get("content-type") || "").includes("application/json")
        ? await response.json() : null;
      if (!response.ok || !result?.ok) {
        throw new Error(result?.error || "Reload the page and sign in again before sending dosage.");
      }
      if (!Number.isInteger(result.exercise_index) || result.exercise_index < 0 || result.exercise_index > 2 ||
          !Number.isInteger(result.reps) || result.reps < 1 || result.reps > 1000 ||
          !Number.isInteger(result.seconds) || result.seconds < 1 || result.seconds > 3600) {
        throw new Error("The assigned dosage is outside Arduino v4 limits.");
      }
      // Opening USB can reset a board. Allow startup before the first command.
      await new Promise(resolve => setTimeout(resolve, Math.max(0, readyAt - Date.now())));
      if (!connected || !port?.writable) throw new Error("Arduino disconnected. Reconnect and send again.");
      status("Sending " + result.exercise_name + ": " + result.reps + " reps, " + result.seconds + " seconds. Waiting for Arduino...");
      const acknowledgement = new Promise((resolve, reject) => {
        pendingDosage = { resolve, reject, exerciseIndex: result.exercise_index,
          timeout: setTimeout(() => {
            rejectDosage("No acknowledgement from Arduino. Install firmware v4, reconnect, and resend before starting.");
            // Do not let a late ACK confirm a later request with the same exercise ID.
            connected = false;
            if (reader) void reader.cancel().catch(() => {});
          }, 5000)
        };
      });
      // Attach a handler now, even if write() takes longer than the ACK timeout.
      acknowledgement.catch(() => {});
      let writer;
      try {
        writer = port.writable.getWriter();
        activeWrite = writer.write(encoder.encode("SET," + result.exercise_index + "," + result.reps + "," + result.seconds + "\n"));
        await activeWrite;
      } catch (error) {
        rejectDosage("Could not write dosage to Arduino. Reconnect and retry.");
        throw error;
      } finally {
        writer?.releaseLock();
      }
      await acknowledgement;
      status("Dosage confirmed by Arduino: " + result.exercise_name + " — " + result.reps +
        " reps, " + result.seconds + " seconds. Select this exercise on the device before starting. Sets and weekly frequency remain on the website.");
    } catch (error) {
      status(error.message || "Unable to send dosage.", true);
    } finally {
      sending = false;
      planSelect.disabled = false;
      sendButton.disabled = !connected;
    }
  }

  if (sendButton && prescriptionUrl) sendButton.addEventListener("click", sendDosage);

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
            if (done) { connected = false; break; }
            buffer += decoder.decode(value, { stream: true });
            let end;
            while ((end = buffer.indexOf("\n")) >= 0) {
              const line = buffer.slice(0, end).replace(/\r$/, "").trim();
              buffer = buffer.slice(end + 1);
              if (handleDosageReply(line)) continue;
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
      rejectDosage("Arduino disconnected before confirming dosage. Reconnect and resend.");
      if (sendButton) sendButton.disabled = true;
      disconnectButton.disabled = true;
      await activeWrite.catch(() => {});
      if (port) {
        try { await port.close(); } catch (_) { /* already disconnected */ }
        port = null;
      }
      connectButton.disabled = false;
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
      connectButton.disabled = true;
      port = await navigator.serial.requestPort();
      await port.open({ baudRate: 115200 });
      connected = true;
      readyAt = Date.now() + 2000;
      if (sendButton) sendButton.disabled = false;
      buffer = "";
      connectButton.disabled = true;
      disconnectButton.disabled = false;
      status("Connected. With firmware v4, send your dosage and wait for confirmation before starting. Confirm the completed workout on Arduino to upload it.");
      void readFromDevice();
    } catch (error) {
      status(error.message || "Could not connect. Close Arduino IDE Serial Monitor and try again.", true);
      try { await port?.close(); } catch (_) { /* ignore */ }
      port = null;
      connectButton.disabled = false;
      if (sendButton) sendButton.disabled = true;
    }
  });

  disconnectButton.addEventListener("click", async () => {
    connected = false;
    if (sendButton) sendButton.disabled = true;
    rejectDosage("Arduino disconnected before confirming dosage. Reconnect and resend.");
    if (reader) {
      try { await reader.cancel(); } catch (_) { /* already closed */ }
    }
    status("Disconnecting Arduino...");
  });
})();
