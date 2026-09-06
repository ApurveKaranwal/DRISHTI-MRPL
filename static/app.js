/* ==============================================================================
   MRPL Sovereign AI Workbench - Client Controller (app.js)
   Clean, minimal, uncluttered controller matching the operations UI.
   ============================================================================== */

const TAB_TITLES = {
  "overview": { title: "Overview", subtitle: "Real-time overview of all plants and operations" },
  "main-refinery": { title: "Main Refinery", subtitle: "Crude Distillation (CDU) & Vacuum Distillation (VDU) status" },
  "petrochemicals": { title: "Petrochemicals", subtitle: "Polypropylene (PP) and FCC reactor status" },
  "aromatics": { title: "Aromatics Complex", subtitle: "Paraxylene, Benzene & continuous reforming status" },
  "utilities": { title: "Offsites & Utilities", subtitle: "Captive power plant & steam distribution" },
  "alerts": { title: "Operational Alerts", subtitle: "Process deviations & predictive risk indicators" },
  "reports": { title: "Reports", subtitle: "Generated notes, presentations and calculation workbooks" },
  "analytics": { title: "Analytics", subtitle: "Python execution runtime & hydrodynamic curves" },
  "documents": { title: "Documents", subtitle: "Indexed operational documents and statutory standards" },
  "settings": { title: "Settings", subtitle: "Local open-weight model registry" },
};

let activeAttachedFiles = [];

// -----------------------------------------------------------------------------
// Night / Day Theme Controller
// -----------------------------------------------------------------------------
function initTheme() {
  const saved = localStorage.getItem("mrpl_theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("mrpl_theme", next);
}

// Apply immediately on parse
initTheme();

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  setupNavigation();
  setupDropzone();
  fetchDeliverables();
});

// -----------------------------------------------------------------------------
// Navigation & Tab Switching
// -----------------------------------------------------------------------------
function setupNavigation() {
  const navItems = document.querySelectorAll(".nav-item");
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const tabId = item.getAttribute("data-tab");
      if (tabId) switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
  const targetNav = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
  if (targetNav) targetNav.classList.add("active");

  document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
  const targetContent = document.getElementById(`tab-${tabId}`);
  if (targetContent) targetContent.classList.add("active");

  const meta = TAB_TITLES[tabId] || { title: "Workbench", subtitle: "MRPL Operations" };
  const titleEl = document.getElementById("page-title");
  const subEl = document.getElementById("page-subtitle");
  if (titleEl) titleEl.textContent = meta.title;
  if (subEl) subEl.textContent = meta.subtitle;

  if (tabId === "reports") fetchDeliverables();
}

// -----------------------------------------------------------------------------
// AI Copilot Chat
// -----------------------------------------------------------------------------
async function sendMessage(overrideText = null, attachedFiles = []) {
  const inputEl = document.getElementById("chat-input");
  const text = (overrideText || inputEl.value).trim();
  if (!text) return;

  if (!overrideText) inputEl.value = "";

  const filesToSend = attachedFiles.length > 0 ? attachedFiles : activeAttachedFiles;
  activeAttachedFiles = [];

  appendUserMessage(text, filesToSend);

  const loadingId = "bot-loading-" + Date.now();
  appendBotLoading(loadingId);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        files: filesToSend,
      }),
    });

    const data = await response.json();
    removeLoading(loadingId);

    if (!data.success) {
      appendBotError(data.detail || "Execution failed.");
      return;
    }

    renderBotResponse(data);
    fetchDeliverables();

    if (data.results) {
      for (const r of data.results) {
        if (r.worker === "code_sandbox" && r.result) {
          const stdoutEl = document.getElementById("sandbox-stdout");
          if (stdoutEl && r.result.stdout) {
            stdoutEl.innerHTML = r.result.stdout.replace(/\n/g, "<br>");
          }
          const plotImg = document.getElementById("sandbox-plot-img");
          if (plotImg) {
            plotImg.src = "/api/download/pipeline_pressure_gradient.png?source=sandbox&t=" + Date.now();
          }
        }
      }
    }

  } catch (err) {
    removeLoading(loadingId);
    appendBotError("Network error: " + err);
  }
}

function appendUserMessage(text, files) {
  const container = document.getElementById("chat-container");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble chat-user";
  
  let content = `<div>${escapeHtml(text)}</div>`;
  if (files && files.length > 0) {
    content += `<div style="font-size: 10px; opacity: 0.85; margin-top: 4px;">Attached: ${files.join(", ")}</div>`;
  }
  bubble.innerHTML = content;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function appendBotLoading(id) {
  const container = document.getElementById("chat-container");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble chat-bot";
  bubble.id = id;
  bubble.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px;">
      <span class="status-dot dot-warning"></span>
      <span style="color: var(--text-muted); font-size: 11.5px;">Routing task &amp; executing...</span>
    </div>
  `;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function removeLoading(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function appendBotError(errorMsg) {
  const container = document.getElementById("chat-container");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble chat-bot";
  bubble.style.borderColor = "var(--color-danger)";
  bubble.innerHTML = `<span style="color: var(--color-danger); font-weight: 600;">Error:</span> ${escapeHtml(errorMsg)}`;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function renderBotResponse(data) {
  const container = document.getElementById("chat-container");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble chat-bot";

  const routing = data.routing || { profile: "general", model_id: "qwen2.5:7b" };
  const rawPlan = data.plan ? JSON.stringify(data.plan, null, 2) : "";

  let deliverablesHtml = "";
  if (data.deliverables && data.deliverables.length > 0) {
    deliverablesHtml = `<div style="margin-top: 10px; border-top: 1px solid var(--border-color); padding-top: 8px;">
      <div style="font-size: 10.5px; font-weight: 600; color: var(--color-success); margin-bottom: 5px;">Deliverables:</div>`;
    data.deliverables.forEach(d => {
      const ext = d.name.substring(d.name.lastIndexOf("."));
      deliverablesHtml += `
        <div class="result-card-item">
          <div class="result-file-info">
            ${getFileIcon(ext)}
            <span class="result-file-name" title="${d.name}">${d.name}</span>
          </div>
          <a class="download-link-btn" href="/api/download/${d.name}?source=reports" download>Download</a>
        </div>`;
    });
    deliverablesHtml += `</div>`;
  }

  bubble.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
      <span style="font-size: 10px; font-weight: 600; color: #A78BFA; text-transform: uppercase;">
        ${routing.profile} - ${routing.model_id}
      </span>
      <span style="font-size: 9.5px; color: var(--color-success);">Offline</span>
    </div>
    <div style="line-height: 1.5;">${formatMarkdown(data.answer || "")}</div>
    ${deliverablesHtml}
    <div class="thought-trace-box" onclick="this.classList.toggle('open')">
      <div class="thought-trace-title">
        <span>Action Plan (${(data.results || []).length} workers)</span>
        <span style="font-size: 9px; color: var(--text-dim);">Details</span>
      </div>
      <div class="thought-trace-content">${escapeHtml(rawPlan)}</div>
    </div>
  `;

  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

// -----------------------------------------------------------------------------
// Deliverables Fetcher & UI Drawer
// -----------------------------------------------------------------------------
async function fetchDeliverables() {
  try {
    const res = await fetch("/api/deliverables");
    const data = await res.json();
    const list = data.deliverables || [];

    // Right copilot drawer
    const drawerEl = document.getElementById("results-drawer-list");
    if (drawerEl) {
      if (list.length === 0) {
        drawerEl.innerHTML = `
          <div class="empty-results">
            <div style="font-size: 11px; color: var(--text-muted);">Your generated reports and charts will appear here.</div>
            <div style="font-size: 10px; color: var(--text-dim); margin-top: 2px;">Ask the AI to generate analysis, reports or charts.</div>
          </div>`;
      } else {
        drawerEl.innerHTML = list.slice(0, 5).map(f => `
          <div class="result-card-item">
            <div class="result-file-info">
              ${getFileIcon(f.extension)}
              <span class="result-file-name" title="${f.name}">${f.name}</span>
            </div>
            <a class="download-link-btn" href="${f.url}" download>Download</a>
          </div>
        `).join("");
      }
    }

    // Reports tab table
    const tbody = document.getElementById("deliverables-tbody");
    if (tbody) {
      if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 20px;">No reports generated yet.</td></tr>';
      } else {
        tbody.innerHTML = list.map(f => {
          const dateStr = new Date(f.modified * 1000).toLocaleDateString();
          return `
            <tr>
              <td><strong>${escapeHtml(f.name)}</strong></td>
              <td>${getFileIcon(f.extension)}</td>
              <td>${f.size_kb} KB</td>
              <td style="color: var(--text-muted);">${dateStr}</td>
              <td><a class="download-link-btn" href="${f.url}" download>Download</a></td>
            </tr>
          `;
        }).join("");
      }
    }

  } catch (err) {
    console.error("Error fetching deliverables:", err);
  }
}

function getFileIcon(ext) {
  const clean = (ext || "").toLowerCase().trim();
  if (clean === ".docx") return '<span style="font-weight: 700; color: #60A5FA; font-size: 10px;">DOCX</span>';
  if (clean === ".xlsx") return '<span style="font-weight: 700; color: #34D399; font-size: 10px;">XLSX</span>';
  if (clean === ".pptx") return '<span style="font-weight: 700; color: #FBBF24; font-size: 10px;">PPTX</span>';
  if (clean === ".png" || clean === ".jpg" || clean === ".jpeg") return '<span style="font-weight: 700; color: #C084FC; font-size: 10px;">PNG</span>';
  return '<span style="font-weight: 700; color: #94A3B8; font-size: 10px;">FILE</span>';
}

// -----------------------------------------------------------------------------
// Drag & Drop File Upload
// -----------------------------------------------------------------------------
function setupDropzone() {
  const dropzone = document.querySelector(".dropzone-box");
  if (!dropzone) return;

  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.style.borderColor = "#8B5CF6";
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.style.borderColor = "var(--border-highlight)";
    });
  });

  dropzone.addEventListener("drop", e => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFileUpload(files);
    }
  });
}

async function handleFileUpload(files) {
  if (!files || files.length === 0) return;
  const file = files[0];

  const formData = new FormData();
  formData.append("file", file);

  const container = document.getElementById("chat-container");
  const loadingBubble = document.createElement("div");
  loadingBubble.className = "chat-bubble chat-bot";
  loadingBubble.innerHTML = `Uploading <strong>${escapeHtml(file.name)}</strong>...`;
  container.appendChild(loadingBubble);
  container.scrollTop = container.scrollHeight;

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    loadingBubble.remove();

    if (data.success) {
      activeAttachedFiles.push(data.relative_path);
      appendBotResponse({
        answer: `File **${escapeHtml(data.filename)}** uploaded successfully. Ready for analysis.`,
        routing: { profile: "general", model_id: "system" }
      });
    } else {
      appendBotError("Failed to upload: " + (data.detail || "unknown error"));
    }
  } catch (err) {
    loadingBubble.remove();
    appendBotError("Upload error: " + err);
  }
}

// -----------------------------------------------------------------------------
// Utilities
// -----------------------------------------------------------------------------
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatMarkdown(md) {
  if (!md) return "";
  let text = escapeHtml(md);

  // Markdown tables: lines with pipes
  text = text.replace(/((?:\|[^\n]+\|\r?\n)+)/g, (match) => {
    const rows = match.trim().split(/\r?\n/).map(r => r.trim()).filter(Boolean);
    if (rows.length < 2) return match;
    
    const parseCells = row => row.replace(/^\|/, "").replace(/\|$/, "").split("|").map(c => c.trim());
    const headerCells = parseCells(rows[0]);
    let startIdx = 1;
    if (rows[1] && rows[1].includes("---")) {
      startIdx = 2;
    }
    
    let tableHtml = '<div class="chat-table-wrapper"><table class="data-table"><thead><tr>';
    headerCells.forEach(h => {
      tableHtml += `<th>${h}</th>`;
    });
    tableHtml += '</tr></thead><tbody>';
    
    for (let i = startIdx; i < rows.length; i++) {
      const cells = parseCells(rows[i]);
      tableHtml += '<tr>';
      cells.forEach(c => {
        tableHtml += `<td>${c}</td>`;
      });
      tableHtml += '</tr>';
    }
    tableHtml += '</tbody></table></div>';
    return tableHtml;
  });

  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/### (.*?)(?:\n|$)/g, '<h4 style="margin: 8px 0 4px 0; color: var(--text-heading); font-size: 13px;">$1</h4>');
  text = text.replace(/## (.*?)(?:\n|$)/g, '<h3 style="margin: 10px 0 6px 0; color: var(--text-heading); font-size: 14px;">$1</h3>');
  text = text.replace(/^- (.*?)(?:\n|$)/gm, '<li style="margin-left: 16px;">$1</li>');
  text = text.replace(/\n/g, "<br>");
  return text;
}
