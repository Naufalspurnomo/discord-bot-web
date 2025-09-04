document.addEventListener("DOMContentLoaded", () => {
  const elements = {
    themeToggle: document.getElementById("theme-toggle"),
    profileSelect: document.getElementById("profile-select"),
    profileNameInput: document.getElementById("profile_name"),
    tokenInput: document.getElementById("token"),
    channelIdInput: document.getElementById("channelid"),
    messageTypeRadios: document.getElementsByName("message_type"),
    textMessageField: document.getElementById("text_message_field"),
    embedMessageField: document.getElementById("embed_message_field"),
    attachmentMessageField: document.getElementById("attachment_message_field"),
    startBtn: document.getElementById("start-btn"),
    stopBtn: document.getElementById("stop-btn"),
    saveBtn: document.getElementById("save-btn"),
    testBtn: document.getElementById("test-btn"),
    logPanel: document.getElementById("log-panel"),
    logRefreshCheckbox: document.getElementById("auto-refresh-log"),
    logRefreshBtn: document.getElementById("log-refresh-btn"),
    logClearBtn: document.getElementById("log-clear-btn"),
    statusContainer: document.getElementById("status-container"),
    analyticsChartCtx: document
      .getElementById("analytics-chart")
      .getContext("2d"),
    analyticsTimeRange: document.getElementById("analytics-time-range"),
    analyticsRefresh: document.getElementById("analytics-refresh"),
    analyticsExport: document.getElementById("analytics-export"),
    analyticsStats: document.getElementById("analytics-stats"),
    scheduleMode: document.getElementById("schedule_mode"),
    intervalField: document.getElementById("interval_field"),
    intervalInput: document.getElementById("interval_seconds"),
    cronSimpleField: document.getElementById("cron_simple_field"),
    cronPreset: document.getElementById("cron_preset"),
    cronAdvancedField: document.getElementById("cron_advanced_field"),
    cronTime: document.getElementById("cron_time"),
    cronDay: document.getElementById("cron_day"),
    cronExpression: document.getElementById("cron_expression"),
    fetchTokenBtn: document.getElementById("fetch-token-btn"),
    logoutBtn: document.getElementById("logout-btn"),
    messageList: document.getElementById("message-list"),
    addMessageBtn: document.getElementById("add-message-btn"),
    importMessages: document.getElementById("import-messages"),
    embedPreview: document.getElementById("embed-preview"),
    embedPreviewTitle: document.getElementById("embed-preview-title"),
    embedPreviewDescription: document.getElementById(
      "embed-preview-description"
    ),
    embedTitle: document.getElementById("embed_title"),
    embedDescription: document.getElementById("embed_description"),
    embedColor: document.getElementById("embed_color"),
    toastContainer: document.getElementById("toast-container"),
    dashboardStatus: document.getElementById("dashboard-status"),
    dashboardMessages: document.getElementById("dashboard-messages"),
    dashboardLogs: document.getElementById("dashboard-logs"),
    dashboardSchedule: document.getElementById("dashboard-schedule"),
    duplicateProfileBtn: document.getElementById("duplicate-profile-btn"),
    deleteProfileBtn: document.getElementById("delete-profile-btn"),
    profileNameError: document.getElementById("profile_name_error"),
    tokenError: document.getElementById("token_error"),
    channelIdError: document.getElementById("channelid_error"),
    attachmentSourceRadios: document.getElementsByName("attachment_source"),
    attachmentUrlField: document.getElementById("attachment_url_field"),
    attachmentLocalField: document.getElementById("attachment_local_field"),
    attachmentUrlInput: document.getElementById("attachment_url"),
    attachmentFileInput: document.getElementById("attachment_file_input"),
    attachmentFileName: document.getElementById("attachment_file_name"),
    currentAttachmentPath: document.getElementById("current_attachment_path"),
  };

  let analyticsChart;
  let messageInputs = [];
  let selectedAttachmentFile = null;

  // --- INITIALIZATION & HELPERS ---
  initializeTheme();
  loadProfiles();
  startPeriodicUpdates();
  addEventListeners();
  updateEmbedPreview();
  validateInputs();
  function initializeTheme() {
    const isDarkMode =
      localStorage.getItem("theme") === "dark" ||
      (!localStorage.theme &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    updateTheme(isDarkMode);
  }
  function toggleTheme() {
    const isDarkMode = !document.documentElement.classList.contains("dark");
    localStorage.setItem("theme", isDarkMode ? "dark" : "light");
    updateTheme(isDarkMode);
  }
  function updateTheme(isDarkMode) {
    document.documentElement.classList.toggle("dark", isDarkMode);
    elements.themeToggle.innerHTML = isDarkMode
      ? '<i class="fa-solid fa-moon"></i>'
      : '<i class="fa-solid fa-sun"></i>';
  }
  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast p-4 rounded-lg shadow-lg text-white max-w-sm w-full transform transition-all duration-500 opacity-0 translate-y-4`;
    toast.style.backgroundColor =
      type === "success" ? "#10b981" : type === "error" ? "#ef4444" : "#3b82f6";
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => toast.classList.add("opacity-100", "translate-y-0"), 10);
    setTimeout(() => {
      toast.classList.remove("opacity-100");
      toast.classList.add("opacity-0");
      setTimeout(() => toast.remove(), 500);
    }, 4000);
  }
  function showConfirmationModal({
    title,
    message,
    confirmText = "Ya",
    cancelText = "Batal",
    onConfirm,
  }) {
    const oldModal = document.getElementById("confirm-modal");
    if (oldModal) oldModal.remove();

    const modalHTML = `
    <div id="confirm-modal" class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
      <div class="bg-gray-800 text-white rounded-lg shadow-xl p-8 max-w-sm w-full transform transition-all duration-300 scale-95 opacity-0 animate-fade-in-scale text-center">
        <h2 class="text-2xl font-bold mb-4">${title}</h2>
        <p class="mb-8 text-gray-300">${message}</p>
        <div class="flex gap-4">
          <button id="cancel-btn" class="w-full py-2 rounded-md font-bold text-gray-800 bg-gray-300 hover:bg-gray-400 transition">${cancelText}</button>
          <button id="confirm-btn" class="w-full py-2 rounded-md font-bold text-white bg-red-600 hover:bg-red-700 transition">${confirmText}</button>
        </div>
      </div>
    </div>
    <style> @keyframes fadeInScale { from { transform: scale(0.95); opacity: 0; } to { transform: scale(1); opacity: 1; } } .animate-fade-in-scale { animation: fadeInScale 0.3s ease-out forwards; } </style>`;

    document.body.insertAdjacentHTML("beforeend", modalHTML);

    const closeModal = () => document.getElementById("confirm-modal")?.remove();

    document.getElementById("confirm-btn").addEventListener("click", () => {
      onConfirm();
      closeModal();
    });
    document.getElementById("cancel-btn").addEventListener("click", closeModal);
  }

  function setButtonLoading(button, isLoading) {
    if (isLoading) {
      if (!button.dataset.originalText)
        button.dataset.originalText = button.innerHTML;
      button.disabled = true;
      button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
      button.classList.add("cursor-not-allowed", "opacity-75");
    } else {
      if (button.dataset.originalText)
        button.innerHTML = button.dataset.originalText;
      button.disabled = false;
      button.classList.remove("cursor-not-allowed", "opacity-75");
      delete button.dataset.originalText;
    }
  }

  async function apiRequest(endpoint, options = {}) {
    try {
      const isFormData = options.body instanceof FormData;
      const fetchOptions = {
        ...options,
        headers: {
          ...(isFormData ? {} : { "Content-Type": "application/json" }),
          ...(options.headers || {}),
        },
      };
      const response = await fetch(`/api${endpoint}`, fetchOptions);
      if (response.status === 401) {
        showToast("Sesi berakhir, harap login kembali.", "error");
        setTimeout(() => (window.location.href = "/login"), 2000);
        return null;
      }
      const responseData = await response.json();
      if (!response.ok) {
        throw new Error(
          responseData.message || `HTTP error! status: ${response.status}`
        );
      }
      return responseData;
    } catch (error) {
      console.error(`API Error at ${endpoint}:`, error);
      showToast(`Error: ${error.message}`, "error");
      return null;
    }
  }

  // --- DASHBOARD & STATUS ---
  async function updateDashboard() {
    const data = await apiRequest("/dashboard");
    if (!data) return;
    elements.dashboardStatus.textContent = data.status;
    elements.dashboardMessages.textContent = data.messages;
    elements.dashboardSchedule.textContent = data.next_schedule;
    elements.dashboardLogs.innerHTML = data.recent_logs
      .map((log) => `<div>${log.trim()}</div>`)
      .join("");
    elements.dashboardLogs.scrollTop = elements.dashboardLogs.scrollHeight;
  }
  async function updateStatus() {
    const data = await apiRequest("/status");
    if (!data) return;
    elements.statusContainer.innerHTML = "";
    const profileNames = Array.from(elements.profileSelect.options).map(
      (opt) => opt.value
    );
    if (profileNames.length === 0) {
      elements.statusContainer.innerHTML =
        '<p class="text-muted">No profiles configured.</p>';
      return;
    }
    profileNames.forEach((profileName) => {
      const status = data[profileName] || {
        running: false,
        sent_count: 0,
        last_run: "-",
      };
      const div = document.createElement("div");
      div.className = "flex justify-between items-center text-sm";
      div.innerHTML = `<span>${profileName}</span><span class="text-right">${
        status.running ? "🟢 Running" : "🔴 Stopped"
      } | Sent: ${status.sent_count} | Last: ${status.last_run}</span>`;
      elements.statusContainer.appendChild(div);
    });
  }

  // --- BULK MESSAGE & ATTACHMENT ---
  function addMessageInput(content = "") {
    const messageItem = document.createElement("div");
    messageItem.className = "flex items-center space-x-2";
    messageItem.innerHTML = `<input type="text" class="form-input w-full p-2 rounded-md" value="${content.replace(
      /"/g,
      "&quot;"
    )}" placeholder="Enter message content"><button class="delete-message-btn p-2 text-red-500 hover:bg-red-200 dark:hover:bg-red-900 rounded-md"><i class="fa-solid fa-trash"></i></button>`;
    elements.messageList.appendChild(messageItem);
    messageInputs.push(messageItem.querySelector("input"));
    messageItem
      .querySelector(".delete-message-btn")
      .addEventListener("click", () => {
        messageItem.remove();
        messageInputs = messageInputs.filter(
          (input) => input !== messageItem.querySelector("input")
        );
      });
  }
  function importMessages(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const messages = e.target.result.split("\n").filter((m) => m.trim());
      elements.messageList.innerHTML = "";
      messageInputs = [];
      messages.forEach((msg) => addMessageInput(msg));
      showToast(
        `${messages.length} messages imported successfully!`,
        "success"
      );
    };
    reader.readAsText(file);
    event.target.value = "";
  }

  // --- PROFILE MANAGEMENT ---
  async function loadProfiles(profileToSelect) {
    const data = await apiRequest("/profiles");
    if (!data) return;
    const currentSelected = profileToSelect || elements.profileSelect.value;
    elements.profileSelect.innerHTML = "";
    let profileExists = false;
    data.profiles.forEach((name) => {
      if (name === currentSelected) profileExists = true;
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      elements.profileSelect.appendChild(option);
    });
    const finalSelection = profileExists
      ? currentSelected
      : data.profiles[0] || null;
    if (finalSelection) {
      elements.profileSelect.value = finalSelection;
      await loadProfileDetails(finalSelection);
    } else {
      elements.profileNameInput.value = "default";
      toggleMessageFields();
    }
  }
  async function loadProfileDetails(profileName) {
    if (!profileName) return;
    const data = await apiRequest(`/profile/${profileName}`);
    if (!data) return;
    elements.profileNameInput.value = profileName || "";
    elements.tokenInput.value = data.token || "";
    elements.channelIdInput.value = data.channelid || "";
    elements.scheduleMode.value = data.schedule_mode || "interval";
    elements.intervalInput.value = data.interval_seconds || 300;
    elements.cronExpression.value = data.cron_expression || "";
    toggleScheduleFields();
    const firstMessage = data.messages?.[0] || { type: "text", content: "" };
    elements.messageTypeRadios.forEach(
      (radio) => (radio.checked = radio.value === firstMessage.type)
    );
    toggleMessageFields();
    elements.messageList.innerHTML = "";
    messageInputs = [];
    if (data.messages && firstMessage.type === "text") {
      data.messages.forEach((m) => addMessageInput(m.content));
    } else if (firstMessage.type === "embed") {
      elements.embedTitle.value = firstMessage.data?.title || "";
      elements.embedDescription.value = firstMessage.data?.description || "";
      const colorHex = `#${(firstMessage.data?.color || 0)
        .toString(16)
        .padStart(6, "0")}`;
      elements.embedColor.value = colorHex === "#000000" ? "#5865f2" : colorHex;
      updateEmbedPreview();
    } else if (firstMessage.type === "attachment") {
      const source = firstMessage.source || "url";
      document.querySelector(
        `input[name="attachment_source"][value="${source}"]`
      ).checked = true;
      toggleAttachmentFields();
      elements.attachmentUrlInput.value =
        source === "url" ? firstMessage.path : "";
      const fullPath = source === "local" ? firstMessage.path : "None";
      elements.currentAttachmentPath.textContent =
        fullPath !== "None" ? fullPath.split(/[/\\]/).pop() : "None";
      elements.currentAttachmentPath.dataset.fullPath = fullPath;
      elements.attachmentFileName.textContent = "No new file chosen";
      selectedAttachmentFile = null;
    }
  }

  // --- UI TOGGLES & UPDATES ---
  function updateEmbedPreview() {
    const title = elements.embedTitle.value || "Embed Title";
    const description = elements.embedDescription.value || "Embed Description";
    const color = elements.embedColor.value || "#5865F2";
    elements.embedPreview.style.borderColor = color;
    elements.embedPreviewTitle.textContent = title;
    elements.embedPreviewDescription.textContent = description;
  }
  function validateInputs() {
    const channelIdRegex = /^\d{17,19}$/,
      tokenRegex = /.+[.].+[.].+/;
    function v(el, errEl, regex, msg) {
      const val = el.value.trim();
      if (val && !regex.test(val)) {
        el.classList.add("error");
        errEl.textContent = msg;
        errEl.classList.remove("hidden");
      } else {
        el.classList.remove("error");
        errEl.classList.add("hidden");
      }
    }
    function vp(el, errEl, msg) {
      if (!el.value.trim()) {
        el.classList.add("error");
        errEl.textContent = msg;
        errEl.classList.remove("hidden");
      } else {
        el.classList.remove("error");
        errEl.classList.add("hidden");
      }
    }
    elements.channelIdInput.addEventListener("input", () =>
      v(
        elements.channelIdInput,
        elements.channelIdError,
        channelIdRegex,
        "Channel ID must be 17-19 digits."
      )
    );
    elements.tokenInput.addEventListener("input", () =>
      v(
        elements.tokenInput,
        elements.tokenError,
        tokenRegex,
        "Invalid token format (must contain dots)."
      )
    );
    elements.profileNameInput.addEventListener("input", () =>
      vp(
        elements.profileNameInput,
        elements.profileNameError,
        "Profile name cannot be empty."
      )
    );
  }
  function toggleScheduleFields() {
    const mode = elements.scheduleMode.value;
    elements.intervalField.classList.toggle("hidden", mode !== "interval");
    elements.cronSimpleField.classList.toggle("hidden", mode !== "cron_simple");
    elements.cronAdvancedField.classList.toggle(
      "hidden",
      mode !== "cron_advanced"
    );
    updateCronExpression();
  }
  function updateCronExpression() {
    let cronValue = "";
    if (elements.scheduleMode.value === "cron_simple") {
      cronValue = elements.cronPreset.value;
    } else if (elements.scheduleMode.value === "cron_advanced") {
      const [hour, minute] = (elements.cronTime.value || "00:00").split(":");
      cronValue = `${minute} ${hour} * * ${elements.cronDay.value}`;
    }
    elements.cronExpression.value = cronValue;
  }
  function toggleAttachmentFields() {
    const source = document.querySelector(
      'input[name="attachment_source"]:checked'
    ).value;
    elements.attachmentUrlField.classList.toggle("hidden", source !== "url");
    elements.attachmentLocalField.classList.toggle(
      "hidden",
      source !== "local"
    );
  }
  function toggleMessageFields() {
    const messageType = document.querySelector(
      'input[name="message_type"]:checked'
    ).value;
    elements.textMessageField.classList.toggle(
      "hidden",
      messageType !== "text"
    );
    elements.embedMessageField.classList.toggle(
      "hidden",
      messageType !== "embed"
    );
    elements.attachmentMessageField.classList.toggle(
      "hidden",
      messageType !== "attachment"
    );
    if (messageType === "attachment") toggleAttachmentFields();
  }

  // --- EVENT LISTENERS ---
  function addEventListeners() {
    elements.themeToggle.addEventListener("click", toggleTheme);
    elements.logoutBtn.addEventListener("click", showLogoutConfirmation);
    elements.fetchTokenBtn.addEventListener("click", fetchAuthorizationToken);
    elements.messageTypeRadios.forEach((radio) =>
      radio.addEventListener("change", toggleMessageFields)
    );
    elements.attachmentSourceRadios.forEach((radio) =>
      radio.addEventListener("change", toggleAttachmentFields)
    );
    elements.profileSelect.addEventListener("change", () =>
      loadProfileDetails(elements.profileSelect.value)
    );
    elements.logRefreshBtn.addEventListener("click", updateLogs);
    elements.scheduleMode.addEventListener("change", toggleScheduleFields);
    elements.cronPreset.addEventListener("change", updateCronExpression);
    elements.cronTime.addEventListener("change", updateCronExpression);
    elements.cronDay.addEventListener("change", updateCronExpression);
    elements.embedTitle.addEventListener("input", updateEmbedPreview);
    elements.embedDescription.addEventListener("input", updateEmbedPreview);
    elements.embedColor.addEventListener("input", updateEmbedPreview);
    elements.addMessageBtn.addEventListener("click", () => addMessageInput());
    elements.importMessages.addEventListener("change", importMessages);
    elements.logClearBtn.addEventListener("click", handleClearLogs);
    elements.saveBtn.addEventListener("click", handleSaveProfile);
    elements.startBtn.addEventListener("click", handleStartBot);
    elements.stopBtn.addEventListener("click", handleStopBot);
    elements.testBtn.addEventListener("click", handleSendOnce);
    elements.analyticsRefresh.addEventListener("click", updateAnalytics);
    elements.analyticsTimeRange.addEventListener("change", updateAnalytics);
    elements.analyticsExport.addEventListener("click", exportAnalyticsToCSV);
    elements.duplicateProfileBtn.addEventListener(
      "click",
      handleDuplicateProfile
    );
    elements.deleteProfileBtn.addEventListener("click", handleDeleteProfile);
    elements.attachmentFileInput.addEventListener("change", (event) => {
      const file = event.target.files[0];
      if (file) {
        selectedAttachmentFile = file;
        elements.attachmentFileName.textContent = file.name;
      } else {
        selectedAttachmentFile = null;
        elements.attachmentFileName.textContent = "No file chosen";
      }
    });
  }

  // --- ACTION HANDLERS ---
  async function handleSaveProfile() {
    const profileName = elements.profileNameInput.value.trim();
    if (!profileName) return showToast("Nama profil kosong!", "error");
    setButtonLoading(elements.saveBtn, true);
    updateCronExpression();
    const messageType = document.querySelector(
      'input[name="message_type"]:checked'
    ).value;
    let messages = [];
    try {
      if (messageType === "text") {
        messages = messageInputs
          .map((input) => input.value.trim())
          .filter((m) => m)
          .map((m) => ({ type: "text", content: m }));
      } else if (messageType === "embed") {
        messages = [
          {
            type: "embed",
            data: {
              title: elements.embedTitle.value,
              description: elements.embedDescription.value,
              color:
                parseInt(elements.embedColor.value.replace("#", ""), 16) || 0,
            },
          },
        ];
      } else if (messageType === "attachment") {
        const source = document.querySelector(
          'input[name="attachment_source"]:checked'
        ).value;
        if (source === "local") {
          if (selectedAttachmentFile) {
            const formData = new FormData();
            formData.append("file", selectedAttachmentFile);
            const uploadResult = await apiRequest("/upload_attachment", {
              method: "POST",
              body: formData,
            });
            if (!uploadResult?.filepath) throw new Error("File upload failed.");
            messages = [
              {
                type: "attachment",
                source: "local",
                path: uploadResult.filepath,
              },
            ];
          } else {
            const existingPath =
              elements.currentAttachmentPath.dataset.fullPath;
            if (!existingPath || existingPath === "None")
              throw new Error("No attachment file specified.");
            messages = [
              { type: "attachment", source: "local", path: existingPath },
            ];
          }
        } else {
          const urlPath = elements.attachmentUrlInput.value.trim();
          if (!urlPath) throw new Error("Attachment URL cannot be empty.");
          messages = [{ type: "attachment", source: "url", path: urlPath }];
        }
      }
      if (messages.length === 0)
        throw new Error("Messages/Attachment cannot be empty.");
      const profileData = {
        profile_name: profileName,
        token: elements.tokenInput.value,
        channelid: elements.channelIdInput.value,
        schedule_mode: elements.scheduleMode.value,
        interval_seconds: parseInt(elements.intervalInput.value) || 300,
        cron_expression: elements.cronExpression.value,
        messages,
      };
      const result = await apiRequest("/save_profile", {
        method: "POST",
        body: JSON.stringify(profileData),
      });
      if (result) {
        showToast(result.message, "success");
        await loadProfiles(profileName);
      }
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setButtonLoading(elements.saveBtn, false);
    }
  }

  async function handleSendOnce() {
    setButtonLoading(elements.testBtn, true);
    const messageType = document.querySelector(
      'input[name="message_type"]:checked'
    ).value;
    let messages = [];
    try {
      if (messageType === "text") {
        messages = messageInputs
          .map((input) => input.value.trim())
          .filter((m) => m)
          .map((m) => ({ type: "text", content: m }));
      } else if (messageType === "embed") {
        messages = [
          {
            type: "embed",
            data: {
              title: elements.embedTitle.value,
              description: elements.embedDescription.value,
              color:
                parseInt(elements.embedColor.value.replace("#", ""), 16) || 0,
            },
          },
        ];
      } else if (messageType === "attachment") {
        const source = document.querySelector(
          'input[name="attachment_source"]:checked'
        ).value;
        if (source === "local") {
          if (selectedAttachmentFile) {
            const formData = new FormData();
            formData.append("file", selectedAttachmentFile);
            const uploadResult = await apiRequest("/upload_attachment", {
              method: "POST",
              body: formData,
            });
            if (!uploadResult?.filepath)
              throw new Error("Gagal mengunggah file untuk tes.");
            messages = [
              {
                type: "attachment",
                source: "local",
                path: uploadResult.filepath,
              },
            ];
          } else {
            const existingPath =
              elements.currentAttachmentPath.dataset.fullPath;
            if (!existingPath || existingPath === "None")
              throw new Error("Tidak ada file yang disimpan untuk dites.");
            messages = [
              { type: "attachment", source: "local", path: existingPath },
            ];
          }
        } else {
          const urlPath = elements.attachmentUrlInput.value.trim();
          if (!urlPath) throw new Error("Attachment URL kosong untuk dites.");
          messages = [{ type: "attachment", source: "url", path: urlPath }];
        }
      }
      if (messages.length === 0)
        throw new Error("Cannot send an empty test message.");
      const data = {
        profile: elements.profileSelect.value,
        token: elements.tokenInput.value,
        channelid: elements.channelIdInput.value,
        messages,
      };
      const result = await apiRequest("/send_once", {
        method: "POST",
        body: JSON.stringify(data),
      });
      if (result)
        showToast(
          result.success ? result.message : `Test gagal: ${result.message}`,
          result.success ? "success" : "error"
        );
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setButtonLoading(elements.testBtn, false);
    }
  }

  async function handleClearLogs() {
    if (!confirm("Hapus semua log?")) return;
    setButtonLoading(elements.logClearBtn, true);
    const result = await apiRequest("/clear_logs", { method: "POST" });
    if (result) {
      showToast(result.message, "success");
      updateLogs();
    }
    setButtonLoading(elements.logClearBtn, false);
  }
  async function handleStartBot() {
    setButtonLoading(elements.startBtn, true);
    const result = await apiRequest("/start", {
      method: "POST",
      body: JSON.stringify({ profile: elements.profileSelect.value }),
    });
    if (result) showToast(result.message, "info");
    updateStatus();
    setButtonLoading(elements.startBtn, false);
  }
  async function handleStopBot() {
    setButtonLoading(elements.stopBtn, true);
    const result = await apiRequest("/stop", {
      method: "POST",
      body: JSON.stringify({ profile: elements.profileSelect.value }),
    });
    if (result) showToast(result.message, "info");
    updateStatus();
    setButtonLoading(elements.stopBtn, false);
  }
  async function handleDuplicateProfile() {
    const profileName = elements.profileSelect.value;
    showConfirmationModal({
      title: "Konfirmasi Duplikasi",
      message: `Apakah Anda yakin ingin menduplikasi profil '${profileName}'?`,
      confirmText: "Ya, Duplikasi",
      async onConfirm() {
        setButtonLoading(elements.duplicateProfileBtn, true);
        const data = { profile: profileName };
        const result = await apiRequest("/duplicate_profile", {
          method: "POST",
          body: JSON.stringify(data),
          headers: { "Content-Type": "application/json" },
        });
        if (result) {
          showToast(result.message, "success");
          await loadProfiles();
        }
        setButtonLoading(elements.duplicateProfileBtn, false);
      },
    });
  }

  async function handleDeleteProfile() {
    const profileName = elements.profileSelect.value;
    if (profileName === "default") {
      showToast("Profil default tidak dapat dihapus!", "error");
      return;
    }

    showConfirmationModal({
      title: "Konfirmasi Hapus",
      message: `Apakah Anda yakin ingin menghapus profil '${profileName}'? Tindakan ini tidak dapat dibatalkan.`,
      confirmText: "Ya, Hapus",
      async onConfirm() {
        setButtonLoading(elements.deleteProfileBtn, true);
        const data = { profile: profileName };
        const result = await apiRequest("/delete_profile", {
          method: "POST",
          body: JSON.stringify(data),
          headers: { "Content-Type": "application/json" },
        });
        if (result) {
          showToast(result.message, "success");
          await loadProfiles();
        }
        setButtonLoading(elements.deleteProfileBtn, false);
      },
    });
  }

  function fetchAuthorizationToken() {
    const confirmed = confirm(
      "PERINGATAN PENTING:\n\nAnda akan membuka Discord untuk mengambil token otorisasi yang SANGAT SENSITIF.\n\n- JANGAN PERNAH bagikan token ini dengan siapa pun.\n- Jika token bocor, segera ubah kata sandi Discord Anda.\n\nApakah Anda memahami risikonya dan setuju untuk melanjutkan?"
    );
    if (!confirmed) return showToast("Dibatalkan.", "info");
    showToast("Membuka Discord...", "info");
    const discordTab = window.open(
      "https://discord.com/channels/@me",
      "_blank"
    );
    if (!discordTab)
      return showToast(
        "Gagal membuka tab baru. Pastikan pop-up tidak diblokir.",
        "error"
      );
    setTimeout(showInstructionModal, 2500);
  }
  function showInstructionModal() {
    const oldModal = document.getElementById("token-instruction-modal");
    if (oldModal) oldModal.remove();
    const modalHTML = `<div id="token-instruction-modal" class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4"><div class="bg-gray-800 text-white rounded-lg shadow-xl p-6 max-w-2xl w-full"><h2 class="text-2xl font-bold mb-4 border-b border-gray-600 pb-2">Cara Mengambil Token</h2><ol class="list-decimal list-inside space-y-3 text-left mb-6"><li>Buka <strong>Developer Tools</strong>: <code class="bg-gray-900 px-2 py-1 rounded-md text-sm">Ctrl+Shift+I</code></li><li>Klik tab <strong>"Network"</strong>.</li><li>Di filter, ketik <code class="bg-gray-900 px-2 py-1 rounded-md text-sm">/api/v9/</code> lalu segarkan halaman (Ctrl+R).</li><li>Klik salah satu permintaan (misal: <code class="bg-gray-900 px-2 py-1 rounded-md text-sm">library</code>).</li><li>Di panel kanan, cari <strong>Request Headers</strong> &gt; <strong class="text-cyan-400">authorization</strong>.</li><li>Klik kanan pada nilainya &gt; <strong>"Copy value"</strong>.</li></ol><div class="space-y-3"><input type="text" id="pasted-token-input" placeholder="Tempelkan token di sini..." class="w-full p-3 bg-gray-900 rounded-md"><div class="flex gap-3"><button id="submit-token-btn" class="w-full py-2 rounded-md font-bold text-white bg-green-600">Simpan</button><button id="close-modal-btn" class="w-full py-2 rounded-md font-bold text-white bg-gray-600">Tutup</button></div></div></div></div>`;
    document.body.insertAdjacentHTML("beforeend", modalHTML);
    document
      .getElementById("submit-token-btn")
      .addEventListener("click", () => {
        const token = document
          .getElementById("pasted-token-input")
          .value.trim();
        if (token) {
          elements.tokenInput.value = token.replace(/^"|"$/g, "");
          showToast("Token berhasil disimpan!", "success");
          document.getElementById("token-instruction-modal").remove();
        } else {
          showToast("Kolom token kosong.", "error");
        }
      });
    document
      .getElementById("close-modal-btn")
      .addEventListener("click", () =>
        document.getElementById("token-instruction-modal").remove()
      );
  }
  function showLogoutConfirmation(event) {
    event.preventDefault();

    // Remove any existing modal to prevent duplicates
    const oldModal = document.getElementById("logout-confirm-modal");
    if (oldModal) oldModal.remove();

    // Create modal HTML
    const modalHTML = `
    <div id="logout-confirm-modal" class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
      <div class="bg-gray-800 text-white rounded-lg shadow-xl p-8 max-w-sm w-full transform transition-all duration-300 scale-95 opacity-0 animate-fade-in-scale text-center">
        <h2 class="text-2xl font-bold mb-4">Konfirmasi Logout</h2>
        <p class="mb-8 text-gray-300">Apakah Anda yakin ingin keluar?</p>
        <div class="flex gap-4">
          <button id="cancel-logout-btn" class="w-full py-2 rounded-md font-bold text-gray-800 bg-gray-300 hover:bg-gray-400 transition">Batal</button>
          <button id="confirm-logout-btn" class="w-full py-2 rounded-md font-bold text-white bg-red-600 hover:bg-red-700 transition">Ya, Keluar</button>
        </div>
      </div>
    </div>
    <style>
      @keyframes fadeInScale {
        from { transform: scale(0.95); opacity: 0; }
        to { transform: scale(1); opacity: 1; }
      }
      .animate-fade-in-scale {
        animation: fadeInScale 0.3s ease-out forwards;
      }
    </style>
  `;

    // Append modal to body
    document.body.insertAdjacentHTML("beforeend", modalHTML);

    // Get modal buttons
    const confirmBtn = document.getElementById("confirm-logout-btn");
    const cancelBtn = document.getElementById("cancel-logout-btn");

    // Add event listeners
    confirmBtn.addEventListener(
      "click",
      () => {
        showToast("Anda telah logout.", "info");
        // Remove modal immediately to prevent interaction
        document.getElementById("logout-confirm-modal").remove();
        // Redirect to /logout after a short delay
        setTimeout(() => {
          window.location.href = "/logout"; // Use fixed URL instead of event.currentTarget.href
        }, 500);
      },
      { once: true }
    ); // Use { once: true } to prevent duplicate listeners

    cancelBtn.addEventListener(
      "click",
      () => {
        document.getElementById("logout-confirm-modal").remove();
      },
      { once: true }
    );
  }

  // --- ANALYTICS & LOGS ---
  function startPeriodicUpdates() {
    updateStatus();
    updateLogs();
    updateAnalytics();
    updateDashboard();
    setInterval(() => {
      updateAnalytics();
      updateStatus();
      if (elements.logRefreshCheckbox.checked) updateLogs();
      updateDashboard();
    }, 5000);
  }
  async function updateLogs() {
    const data = await apiRequest("/logs");
    if (!data) return;
    elements.logPanel.textContent = data.logs;
    elements.logPanel.scrollTop = elements.logPanel.scrollHeight;
  }
  async function updateAnalytics() {
    const timeRange = elements.analyticsTimeRange.value;
    const data = await apiRequest(`/analytics?range=${timeRange}`);
    if (!data) return;

    // Update stats
    elements.analyticsStats.innerHTML = `
      <p>Total: ${data.total}</p>
      <p>Success: ${data.success}</p>
      <p>Failure: ${data.failure}</p>
    `;

    // Destroy existing chart if it exists
    if (analyticsChart) {
      analyticsChart.destroy();
    }

    // Prepare chart data
    const labels = Object.keys(data.profiles);
    const successData = labels.map((profile) => data.profiles[profile].success);
    const failureData = labels.map((profile) => data.profiles[profile].failure);

    analyticsChart = new Chart(elements.analyticsChartCtx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Success",
            data: successData,
            backgroundColor: "rgba(75, 192, 192, 0.2)",
            borderColor: "rgba(75, 192, 192, 1)",
            borderWidth: 1,
          },
          {
            label: "Failure",
            data: failureData,
            backgroundColor: "rgba(255, 99, 132, 0.2)",
            borderColor: "rgba(255, 99, 132, 1)",
            borderWidth: 1,
          },
        ],
      },
      options: {
        scales: {
          y: {
            beginAtZero: true,
          },
        },
      },
    });
  }
  async function exportAnalyticsToCSV() {
    setButtonLoading(elements.analyticsExport, true);
    const data = await apiRequest(
      `/analytics?range=${elements.analyticsTimeRange.value}`
    );
    if (!data || !data.dates || data.dates.length === 0) {
      showToast("Tidak ada data untuk diekspor.", "error");
      setButtonLoading(elements.analyticsExport, false);
      return;
    }
    let csvContent =
      "data:text/csv;charset=utf-8,Timestamp,Status,Profile Name\r\n";
    for (const [profileName, profileData] of Object.entries(data.profiles)) {
      for (const [timestamp, success] of Object.entries(
        profileData.timestamps
      )) {
        csvContent += `${timestamp},${
          success ? "Success" : "Failure"
        },${profileName}\r\n`;
      }
    }
    const link = document.createElement("a");
    link.href = encodeURI(csvContent);
    link.download = `analytics_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast(`Ekspor berhasil!`, "success");
    setButtonLoading(elements.analyticsExport, false);
  }
});
