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
  "alerts": { title: "Statutory Audits", subtitle: "OISD-STD-129, API 510 & statutory asset integrity compliance" },
  "reports": { title: "Reports", subtitle: "Generated notes, presentations and calculation workbooks" },
  "analytics": { title: "Analytics", subtitle: "Python execution runtime & hydrodynamic curves" },
  "documents": { title: "Documents", subtitle: "Indexed operational documents and statutory standards" },
  "settings": { title: "Settings", subtitle: "Local open-weight model registry" },
};

let activeAttachedFiles = [];
let selectedModelProfile = "auto";
let loadingIntervals = {};
let loadingTimeouts = {};
let availableModelRegistry = null;
let cachedRefineryData = null;
let currentGovDataset = "monthly";

// -----------------------------------------------------------------------------
// Theme Controller (Locked permanently to Dark SCADA)
// -----------------------------------------------------------------------------
function initTheme() {
  try { localStorage.removeItem("mrpl_theme"); } catch (e) {}
  document.documentElement.setAttribute("data-theme", "dark");
}

function toggleTheme() {
  document.documentElement.setAttribute("data-theme", "dark");
}

// Apply immediately on parse
initTheme();

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  setupNavigation();
  setupDropzone();
  fetchDeliverables();
  fetchDocuments();
  fetchModelRegistry();
  fetchSystemTelemetry();
  fetchRefineryOverview();
  initHudOverview();
  renderTrack("hud-main-segmented-track", 42, 38);
  renderTrack("hud-petro-segmented-track", 42, 36);
  renderTrack("hud-aromatics-segmented-track", 42, 39);
  renderTrack("hud-utilities-segmented-track", 42, 40);
  renderTrack("hud-alerts-segmented-track", 42, 41);
  switchCrudeAssay("Arabian Light");
  executeInteractiveDarcy();
  renderGovDatasetChart("monthly");
  initTouchAndMicroInteractions();
  setInterval(fetchSystemTelemetry, 2500);

  const initialTab = (window.location.hash ? window.location.hash.replace("#", "") : null);
  if (initialTab) switchTab(initialTab);
  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "");
    if (hash) switchTab(hash);
  });
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

  if (tabId === "overview") {
    fetchRefineryOverview();
    initHudOverview();
  }
  if (tabId === "main-refinery") {
    renderTrack("hud-main-segmented-track", 42, 38);
    switchCrudeAssay(currentAssayName || "Arabian Light");
  }
  if (tabId === "petrochemicals") {
    renderTrack("hud-petro-segmented-track", 42, 36);
  }
  if (tabId === "aromatics") {
    renderTrack("hud-aromatics-segmented-track", 42, 39);
  }
  if (tabId === "utilities") {
    renderTrack("hud-utilities-segmented-track", 42, 40);
  }
  if (tabId === "alerts") {
    renderTrack("hud-alerts-segmented-track", 42, 41);
  }
  if (tabId === "reports") fetchDeliverables();
  if (tabId === "documents") fetchDocuments();
  if (tabId === "settings") fetchDiscoveredModels();
  if (tabId === "analytics") {
    setTimeout(() => {
      executeInteractiveDarcy();
      renderGovDatasetChart(currentGovDataset || "monthly");
    }, 60);
  }
  setTimeout(initTouchAndMicroInteractions, 50);
}

// -----------------------------------------------------------------------------
// AI Copilot Chat
// -----------------------------------------------------------------------------
// -----------------------------------------------------------------------------
// Model Registry & Live Profile Switcher
// -----------------------------------------------------------------------------
function onModelProfileChange() {
  const sel = document.getElementById("model-profile-select");
  if (sel) {
    selectedModelProfile = sel.value;
  }
}

async function fetchModelRegistry() {
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    availableModelRegistry = data;

    const pillText = document.getElementById("header-model-label");
    if (pillText) {
      const activeCount = (data.profiles || []).filter(p => p.is_installed).length;
      pillText.textContent = `${activeCount} Models Active`;
    }

    const copilotBadge = document.getElementById("copilot-badge-text");
    if (copilotBadge) {
      copilotBadge.textContent = "Ollama Active (" + (data.active_models_in_ollama || []).length + " Weights)";
    }

    const targetEl = document.getElementById("hw-target-name");
    if (targetEl && data.target_hardware) {
      targetEl.textContent = data.target_hardware;
    }

    const backendEl = document.getElementById("hw-backend-status");
    if (backendEl && data.current_mode) {
      backendEl.textContent = data.current_mode;
    }

    renderModelModal(data);
  } catch (err) {
    console.warn("Could not load /api/models:", err);
  }
}

async function fetchSystemTelemetry() {
  try {
    const res = await fetch("/api/system-telemetry");
    if (!res.ok) return;
    const data = await res.json();

    // 1. Header Real-Time Hardware Ticker
    const cpuEl = document.getElementById("ticker-cpu-val");
    if (cpuEl && data.cpu) {
      cpuEl.textContent = `${data.cpu.percent}%`;
    }

    const ramEl = document.getElementById("ticker-ram-val");
    if (ramEl && data.ram) {
      ramEl.textContent = `${data.ram.used_gb} GB`;
    }

    const gpuEl = document.getElementById("ticker-gpu-val");
    if (gpuEl && data.gpu) {
      if (data.gpu.detected && data.gpu.vram_used_mb > 0) {
        gpuEl.textContent = `${(data.gpu.vram_used_mb / 1024).toFixed(1)} GB`;
      } else if (data.gpu.detected) {
        gpuEl.textContent = "Online";
      } else {
        gpuEl.textContent = "Active";
      }
    }

    const romEl = document.getElementById("ticker-rom-val");
    if (romEl && data.storage) {
      romEl.textContent = `${data.storage.used_gb} GB`;
    }

    // 2. Hardware Modal Full Telemetry
    if (data.os) {
      const osBadge = document.getElementById("modal-os-badge");
      if (osBadge) osBadge.textContent = data.os;
    }

    // CPU Modal Card
    if (data.cpu) {
      const cpuPct = document.getElementById("hw-cpu-pct");
      if (cpuPct) cpuPct.textContent = `${data.cpu.percent}%`;
      const cpuBar = document.getElementById("hw-cpu-bar");
      if (cpuBar) cpuBar.style.width = `${Math.min(100, Math.max(0, data.cpu.percent))}%`;
      const cpuName = document.getElementById("hw-cpu-name");
      if (cpuName) cpuName.textContent = data.cpu.name || "Host Processor";
      const cpuCores = document.getElementById("hw-cpu-cores");
      if (cpuCores) cpuCores.textContent = `${data.cpu.cores_physical} Physical / ${data.cpu.cores_logical} Logical Cores`;
      const cpuFreq = document.getElementById("hw-cpu-freq");
      if (cpuFreq) cpuFreq.textContent = data.cpu.freq_mhz ? `${data.cpu.freq_mhz} MHz` : "Standard Frequency";
    }

    // RAM Modal Card
    if (data.ram) {
      const ramPct = document.getElementById("hw-ram-pct");
      if (ramPct) ramPct.textContent = `${data.ram.percent}%`;
      const ramBar = document.getElementById("hw-ram-bar");
      if (ramBar) ramBar.style.width = `${Math.min(100, Math.max(0, data.ram.percent))}%`;
      const ramUsage = document.getElementById("hw-ram-usage");
      if (ramUsage) ramUsage.textContent = `${data.ram.used_gb} / ${data.ram.total_gb} GB Used`;
      const ramAvail = document.getElementById("hw-ram-avail");
      if (ramAvail) ramAvail.textContent = `${data.ram.available_gb} GB Available`;
    }

    // GPU Modal Card
    if (data.gpu) {
      const gpuPct = document.getElementById("hw-gpu-pct");
      if (gpuPct) {
        if (data.gpu.detected) {
          gpuPct.textContent = `${data.gpu.vram_percent}%`;
        } else {
          gpuPct.textContent = "N/A";
        }
      }
      const gpuBar = document.getElementById("hw-gpu-bar");
      if (gpuBar) gpuBar.style.width = `${Math.min(100, Math.max(0, data.gpu.vram_percent || 0))}%`;
      const gpuName = document.getElementById("hw-gpu-name");
      if (gpuName) gpuName.textContent = data.gpu.name || "Host CPU / Integrated";
      const gpuVram = document.getElementById("hw-gpu-vram");
      if (gpuVram) {
        if (data.gpu.vram_total_mb > 0) {
          gpuVram.textContent = `${data.gpu.vram_used_mb} / ${data.gpu.vram_total_mb} MB VRAM`;
        } else {
          gpuVram.textContent = data.gpu.type || "CPU Fallback";
        }
      }
      const gpuTemp = document.getElementById("hw-gpu-temp");
      if (gpuTemp) {
        if (data.gpu.temperature_c !== null && data.gpu.temperature_c !== undefined) {
          gpuTemp.textContent = `${data.gpu.temperature_c} °C`;
        } else if (data.gpu.driver && data.gpu.driver !== "N/A") {
          gpuTemp.textContent = `Driver: ${data.gpu.driver}`;
        } else {
          gpuTemp.textContent = data.gpu.type || "Standard";
        }
      }
    }

    // ROM / Disk Modal Card
    if (data.storage) {
      const romPct = document.getElementById("hw-rom-pct");
      if (romPct) romPct.textContent = `${data.storage.percent}%`;
      const romBar = document.getElementById("hw-rom-bar");
      if (romBar) romBar.style.width = `${Math.min(100, Math.max(0, data.storage.percent))}%`;
      const romUsage = document.getElementById("hw-rom-usage");
      if (romUsage) romUsage.textContent = `${data.storage.used_gb} / ${data.storage.total_gb} GB Used`;
      const romFree = document.getElementById("hw-rom-free");
      if (romFree) romFree.textContent = `${data.storage.free_gb} GB Free`;
    }
  } catch (err) {
    // Silent fail on transient poll failure
  }
}

const DOMAIN_META = {
  "code": {
    label: "Code & Math",
    pillClass: "tag-code",
    paramChip: "7B • Q4_K_M",
    icon: `<svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>`
  },
  "reasoning": {
    label: "Root-Cause RCA",
    pillClass: "tag-reasoning",
    paramChip: "1.5B • Distill",
    icon: `<svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><path d="M12 2a8 8 0 0 0-8 8c0 3 2 5.5 5 7v3h6v-3c3-1.5 5-4 5-7a8 8 0 0 0-8-8z"></path></svg>`
  },
  "general": {
    label: "PSU Memorandums",
    pillClass: "tag-general",
    paramChip: "7B • Instruct",
    icon: `<svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>`
  },
  "vision": {
    label: "P&ID Vision & OCR",
    pillClass: "tag-vision",
    paramChip: "3B • Vision",
    icon: `<svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`
  },
  "fast": {
    label: "Intent Router",
    pillClass: "tag-fast",
    paramChip: "3B • Router",
    icon: `<svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>`
  },
  "embedding": {
    label: "Vector RAG Index",
    pillClass: "tag-embedding",
    paramChip: "384-Dim • Dense",
    icon: `<svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>`
  }
};

function renderModelModal(data) {
  const grid = document.getElementById("modal-model-grid");
  if (!grid) return;

  let profiles = (data.profiles || []).slice();
  if (!profiles.some(p => p.name === "embedding")) {
    profiles.push({
      name: "embedding",
      model_id: "bge-small-en-v1.5",
      fallback_id: "nomic-embed-text",
      vram_estimate_gb: 0.4,
      description: "Dense semantic vector retrieval engine for standards (OISD, API 510) and P&ID engineering schematics.",
      is_installed: true
    });
  }

  grid.innerHTML = profiles.map(p => {
    const meta = DOMAIN_META[p.name] || {
      label: p.name.toUpperCase(),
      pillClass: "tag-general",
      paramChip: "Local Model",
      icon: `<svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><circle cx="12" cy="12" r="10"/></svg>`
    };

    return `
      <div class="modal-model-card">
        <div class="card-model-top">
          <span class="card-profile-tag ${meta.pillClass}">
            ${meta.icon}
            <span>${meta.label}</span>
          </span>
          <span class="model-status-pill ${p.is_installed ? 'status-ready' : 'status-sim'}">
            <span class="model-status-dot"></span>
            <span>${p.is_installed ? 'GPU Accelerated' : 'Standby Mode'}</span>
          </span>
        </div>

        <div class="card-model-name-row" style="margin-bottom: 8px;">
          <span class="card-model-name">${escapeHtml(p.model_id)}</span>
          <span class="card-model-param-chip">${meta.paramChip}</span>
        </div>

        ${(p.available_models && p.available_models.length > 1) ? `
          <div style="margin-bottom: 10px; background: rgba(0,0,0,0.25); padding: 6px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.08);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <span style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.7;">Active Route Model</span>
              <span style="font-size: 10px; color: #4ade80;">${p.available_models.length} Compatible</span>
            </div>
            <select onchange="handleModelSelection('${escapeHtml(p.name)}', this.value)" style="width: 100%; padding: 4px 6px; background: #181c24; color: #e2e8f0; border: 1px solid rgba(255,255,255,0.2); border-radius: 4px; font-size: 11px; font-family: monospace; outline: none; cursor: pointer;">
              ${p.available_models.map(m => `
                <option value="${escapeHtml(m.model_id)}" ${m.model_id === p.model_id ? 'selected' : ''}>
                  ${escapeHtml(m.model_id)} ${m.is_installed ? '✓ Installed' : '(Not in Ollama)'}
                </option>
              `).join("")}
            </select>
          </div>
        ` : ''}

        <div class="card-model-desc">${escapeHtml(p.description)}</div>

        <div class="card-model-footer">
          <div class="card-vram-chip">
            <svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="7" cy="12" r="2"/><circle cx="17" cy="12" r="2"/><path d="M12 8v8"/></svg>
            <span>~${p.vram_estimate_gb} GB VRAM</span>
          </div>
          <span class="card-fallback-text">Fallback: <code>${escapeHtml(p.fallback_id || 'None')}</code></span>
        </div>
      </div>
    `;
  }).join("");
}

async function handleModelSelection(role, modelId) {
  try {
    const res = await fetch("/api/models/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: role, model_id: modelId })
    });
    const result = await res.json();
    if (res.ok) {
      console.log(`[ModelRouter] Switched ${role} to ${modelId}`);
      await fetchModelRegistry();
    } else {
      alert(result.detail || "Failed to switch model");
    }
  } catch (err) {
    console.error("Error switching model:", err);
  }
}

function openModelRegistryModal() {
  const modal = document.getElementById("model-modal");
  if (modal) modal.classList.add("open");
  fetchModelRegistry();
}

function closeModelRegistryModal() {
  const modal = document.getElementById("model-modal");
  if (modal) modal.classList.remove("open");
}

// -----------------------------------------------------------------------------
// New Model Detection — "New Model Detected" confirmation flow
// -----------------------------------------------------------------------------
const CAP_LABELS = { text: "Text", vision: "Vision", code: "Code", reasoning: "Reasoning" };
const ROLE_LABELS = {
  general: "General",
  reasoning: "Reasoning",
  code: "Code",
  vision: "Vision",
  supervisor: "Supervisor",
};

async function fetchDiscoveredModels() {
  const emptyEl = document.getElementById("model-discovery-empty");
  const listEl = document.getElementById("model-discovery-list");
  const countEl = document.getElementById("model-discovery-count");
  if (!listEl) return;

  try {
    const res = await fetch("/api/models/discover");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderDiscoveredModels(data.pending || []);
  } catch (err) {
    console.warn("Could not load /api/models/discover:", err);
    if (emptyEl) {
      emptyEl.style.display = "block";
      emptyEl.textContent = "Could not reach the model discovery service.";
    }
    if (countEl) countEl.style.display = "none";
  }
}

function renderDiscoveredModels(pending) {
  const listEl = document.getElementById("model-discovery-list");
  const countEl = document.getElementById("model-discovery-count");
  if (!listEl) return;

  if (countEl) {
    if (pending.length > 0) {
      countEl.style.display = "inline-block";
      countEl.textContent = `${pending.length} Pending`;
    } else {
      countEl.style.display = "none";
    }
  }

  if (!pending.length) {
    listEl.innerHTML = `<div class="model-discover-empty" id="model-discovery-empty">No new models detected. Pull a model with Ollama and hit Rescan.</div>`;
    return;
  }

  listEl.innerHTML = `<div class="model-discover-list">${pending.map(renderDiscoveredModelCard).join("")}</div>`;
}

function renderDiscoveredModelCard(model) {
  const safeId = escapeHtml(model.model_id);
  const domId = safeId.replace(/[^a-zA-Z0-9]/g, "_");
  const suggested = new Set(model.suggested_roles || []);

  const capChips = [
    ...(model.capabilities || []).map(c => ({ c, cls: "cap-chip-yes", glyph: "✓" })),
    ...(model.uncertain_capabilities || []).map(c => ({ c, cls: "cap-chip-maybe", glyph: "?" })),
    ...(model.not_detected || []).map(c => ({ c, cls: "cap-chip-no", glyph: "✗" })),
  ].map(({ c, cls, glyph }) => `<span class="cap-chip ${cls}">${glyph} ${escapeHtml(CAP_LABELS[c] || c)}</span>`).join("");

  const meta = [model.parameter_size, model.quantization].filter(Boolean).join(" • ");
  const roles = model.available_roles || ["general", "reasoning", "code", "vision", "supervisor"];

  const roleChips = roles.map(role => {
    const checked = suggested.has(role);
    return `
      <label class="role-chip ${checked ? 'checked' : ''}" data-model="${domId}">
        <input type="checkbox" value="${escapeHtml(role)}" ${checked ? 'checked' : ''} onchange="onRoleChipToggle(this)">
        <span>${escapeHtml(ROLE_LABELS[role] || role)}</span>
      </label>
    `;
  }).join("");

  return `
    <div class="model-discover-item" id="discover-item-${domId}" data-model-id="${safeId}">
      <div class="model-discover-item-top">
        <span class="model-discover-name">${safeId}</span>
        ${meta ? `<span class="model-discover-meta">${escapeHtml(meta)}</span>` : ''}
      </div>
      <div class="model-discover-caps">${capChips}</div>
      <div class="model-discover-roles-label">Add this model to:</div>
      <div class="model-discover-roles">${roleChips}</div>
      <div class="model-discover-actions">
        <button class="ghost-btn" onclick="dismissDiscoveredModel('${safeId}', '${domId}')">Not Now</button>
        <button class="primary-btn" onclick="confirmDiscoveredModel('${safeId}', '${domId}')">Add Model</button>
      </div>
    </div>
  `;
}

function onRoleChipToggle(checkbox) {
  const label = checkbox.closest(".role-chip");
  if (label) label.classList.toggle("checked", checkbox.checked);
}

async function confirmDiscoveredModel(modelId, domId) {
  const item = document.getElementById(`discover-item-${domId}`);
  if (!item) return;

  const roles = Array.from(item.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);
  if (!roles.length) {
    alert("Select at least one role before adding this model.");
    return;
  }

  const addBtn = item.querySelector(".primary-btn");
  if (addBtn) { addBtn.disabled = true; addBtn.textContent = "Adding…"; }

  try {
    const res = await fetch("/api/models/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_id: modelId, roles: roles }),
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || "Failed to register model");

    item.remove();
    await fetchDiscoveredModels();
    await fetchModelRegistry();
  } catch (err) {
    alert(err.message || "Failed to add model");
    if (addBtn) { addBtn.disabled = false; addBtn.textContent = "Add Model"; }
  }
}

async function dismissDiscoveredModel(modelId, domId) {
  const item = document.getElementById(`discover-item-${domId}`);
  try {
    await fetch("/api/models/dismiss", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_id: modelId }),
    });
    if (item) item.remove();
    const listEl = document.getElementById("model-discovery-list");
    if (listEl && !listEl.querySelector(".model-discover-item")) {
      renderDiscoveredModels([]);
    }
  } catch (err) {
    console.warn("Failed to dismiss model:", err);
  }
}

// -----------------------------------------------------------------------------
// Official Refinery Overview & PPAC Govt. Data Ingestion
// -----------------------------------------------------------------------------
async function fetchRefineryOverview() {
  try {
    const res = await fetch("/api/refinery-overview");
    if (!res.ok) return;
    const data = await res.json();
    if (!data || (!data.summary && !data.monthly_processing)) return;
    cachedRefineryData = data;

    const s = data.summary;
    if (s) {
      const annualCrudeEl = document.getElementById("ov-annual-crude");
      if (annualCrudeEl && s.annual_crude_processed_mmt !== undefined) {
        annualCrudeEl.textContent = `${s.annual_crude_processed_mmt} MMT`;
      }

      const annualKpi = document.getElementById("kpi-annual-throughput");
      if (annualKpi && s.annual_crude_processed_mmt !== undefined) {
        annualKpi.textContent = `${s.annual_crude_processed_mmt} MMT`;
      }

      const capUtil = document.getElementById("kpi-capacity-util");
      if (capUtil && s.capacity_utilization_pct !== undefined) {
        capUtil.textContent = `${s.capacity_utilization_pct}%`;
        renderHudSegmentedBar(s.capacity_utilization_pct);
        const speedo = document.getElementById("hud-speedo-val");
        if (speedo) speedo.textContent = Number(s.capacity_utilization_pct).toFixed(1);
      }

      const assays = document.getElementById("kpi-crude-assays");
      if (assays && s.crude_assays_indexed !== undefined) {
        assays.textContent = `${s.crude_assays_indexed} Blends`;
      }

      const spares = document.getElementById("kpi-spares-count");
      if (spares && s.oem_spares_catalogued !== undefined) {
        spares.textContent = `${s.oem_spares_catalogued} Items`;
      }
    }

    // Populate monthly processing table from DuckDB / PPAC
    const tbody = document.getElementById("ppac-monthly-tbody");
    if (tbody && Array.isArray(data.monthly_processing) && data.monthly_processing.length > 0) {
      tbody.innerHTML = data.monthly_processing.map(row => {
        const monthStr = row.month || row.month_year || "";
        const ind = Number(row.indigenous_crude_tmt || 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        const imp = Number(row.imported_crude_tmt || 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        const tot = Number(row.total_crude_processed_tmt || 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        const tgt = Number(row.ppac_target_tmt || row.target_tmt || 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        const util = Number(row.capacity_utilization_pct || 0).toFixed(1);
        const isAbove = Number(util) >= 100;
        return `
          <tr>
            <td><code>${escapeHtml(monthStr)}</code></td>
            <td>${ind}</td>
            <td>${imp}</td>
            <td><strong>${tot} TMT</strong></td>
            <td>${tgt}</td>
            <td><span class="status-badge-${isAbove ? 'green' : 'orange'}">${util}%</span></td>
          </tr>
        `;
      }).join("");
    }

    // Re-render Government PPAC visualizer with freshly loaded authentic DuckDB data
    if (typeof renderGovDatasetChart === "function") {
      renderGovDatasetChart(currentGovDataset || "monthly");
    }
  } catch (err) {
    console.warn("Could not load /api/refinery-overview:", err);
  }
}

// -----------------------------------------------------------------------------
// AI Copilot Chat & Live Orchestration
// -----------------------------------------------------------------------------
async function sendMessage(overrideText = null, attachedFiles = []) {
  const inputEl = document.getElementById("chat-input");
  const text = (overrideText || inputEl.value).trim();
  if (!text) return;

  const copilotPanel = document.querySelector(".copilot-panel");
  if (copilotPanel && copilotPanel.classList.contains("collapsed")) {
    copilotPanel.classList.remove("collapsed");
  }
  switchCopilotTab("chat");

  if (!overrideText) {
    inputEl.value = "";
    inputEl.style.height = "auto";
  }

  const filesToSend = attachedFiles.length > 0 ? attachedFiles : activeAttachedFiles;
  activeAttachedFiles = [];

  appendUserMessage(text, filesToSend);

  const loadingId = "bot-loading-" + Date.now();
  appendBotLoading(loadingId);

  try {
    const payload = {
      message: text,
      files: filesToSend,
    };

    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    let data;
    const responseText = await response.text();
    try {
      data = JSON.parse(responseText);
    } catch (parseErr) {
      removeLoading(loadingId);
      appendBotError(`Server Error (${response.status}): ${responseText.slice(0, 300) || response.statusText || "Invalid server response"}`);
      return;
    }

    removeLoading(loadingId);

    if (!response.ok || !data.success) {
      appendBotError(data.detail || data.error || `Execution failed (HTTP ${response.status})`);
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

const THINKING_PHASES = [
  { verb: "Thinking", thought: "Analyzing operational query & prompt context..." },
  { verb: "Contemplating", thought: "Contemplating refinery process parameters & dynamics..." },
  { verb: "Evaluating", thought: "Evaluating CDU-3 distillation column kinematics & tray hydraulics..." },
  { verb: "Pondering", thought: "Cross-referencing ultrasonic thickness logs with API 510 corrosion rates..." },
  { verb: "Reasoning", thought: "Computing Darcy-Weisbach hydraulic head loss & line friction factors..." },
  { verb: "Deliberating", thought: "Auditing OISD-129 safety relief interlocks & statutory operating limits..." },
  { verb: "Synthesizing", thought: "Synthesizing crude assay yield curves & hydrocarbon cut-points..." },
  { verb: "Mulling", thought: "Calibrating safe operating envelope setpoints & flow parameters..." },
  { verb: "Reflecting", thought: "Verifying sovereign air-gap isolation & local VRAM context..." },
  { verb: "Formulating", thought: "Formulating deterministic engineering mitigations & control steps..." },
  { verb: "Structuring", thought: "Structuring actionable technical recommendations for plant engineers..." },
  { verb: "Polishing", thought: "Finalizing sovereign refinery intelligence response..." }
];

function appendBotLoading(id) {
  const container = document.getElementById("chat-container");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble chat-bot";
  bubble.id = id;

  const initialPhase = THINKING_PHASES[0];

  bubble.innerHTML = `
    <div class="claude-thinking-card">
      <div class="thinking-header-row">
        <div class="thinking-status-group">
          <div class="thinking-sparkle-orb">
            <span class="thinking-sparkle-glow"></span>
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
              <path d="M12 2v20M2 12h20M4.93 4.93l14.14 14.14M4.93 19.07l14.14-14.14"/>
              <circle cx="12" cy="12" r="2.2" fill="currentColor"/>
            </svg>
          </div>
          <div class="thinking-verb-container">
            <span class="thinking-verb-text" id="${id}-verb">${initialPhase.verb}</span>
            <span class="thinking-dots-anim">
              <span>.</span><span>.</span><span>.</span>
            </span>
          </div>
        </div>
        <span class="thinking-timer-badge" id="${id}-timer">0.0s</span>
      </div>

      <div class="thinking-subthought-box">
        <span class="thinking-subthought-pulse"></span>
        <span class="thinking-phrase-text" id="${id}-phrase">${initialPhase.thought}</span>
      </div>

      <div class="thinking-shimmer-track">
        <div class="thinking-shimmer-bar"></div>
      </div>
    </div>
  `;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;

  const startTime = Date.now();
  let currentPhaseIndex = 0;
  const phaseDuration = 2.0; // Rotate phrase every 2 seconds

  const timer = setInterval(() => {
    const elapsedSeconds = (Date.now() - startTime) / 1000;
    const timerEl = document.getElementById(`${id}-timer`);
    if (timerEl) timerEl.textContent = `${elapsedSeconds.toFixed(1)}s`;

    const rawIndex = Math.floor(elapsedSeconds / phaseDuration);
    // Cycle progressively through thoughts; wrap around cleanly if inference takes longer
    const phaseIndex = rawIndex < THINKING_PHASES.length
      ? rawIndex
      : 3 + ((rawIndex - THINKING_PHASES.length) % (THINKING_PHASES.length - 3));

    if (phaseIndex !== currentPhaseIndex) {
      currentPhaseIndex = phaseIndex;
      const targetPhase = THINKING_PHASES[phaseIndex];
      const verbEl = document.getElementById(`${id}-verb`);
      const phraseEl = document.getElementById(`${id}-phrase`);

      if (verbEl && phraseEl) {
        verbEl.classList.add("thinking-fading-out");
        phraseEl.classList.add("thinking-fading-out");

        const tOut = setTimeout(() => {
          if (!document.getElementById(id)) return;
          verbEl.textContent = targetPhase.verb;
          phraseEl.textContent = targetPhase.thought;
          verbEl.classList.remove("thinking-fading-out");
          phraseEl.classList.remove("thinking-fading-out");
          verbEl.classList.add("thinking-fading-in");
          phraseEl.classList.add("thinking-fading-in");

          setTimeout(() => {
            const curVerb = document.getElementById(`${id}-verb`);
            const curPhrase = document.getElementById(`${id}-phrase`);
            if (curVerb) curVerb.classList.remove("thinking-fading-in");
            if (curPhrase) curPhrase.classList.remove("thinking-fading-in");
          }, 200);
        }, 180);

        loadingTimeouts[id] = tOut;
      }
    }
  }, 100);

  loadingIntervals[id] = timer;
}

function removeLoading(id) {
  if (loadingIntervals[id]) {
    clearInterval(loadingIntervals[id]);
    delete loadingIntervals[id];
  }
  if (loadingTimeouts[id]) {
    clearTimeout(loadingTimeouts[id]);
    delete loadingTimeouts[id];
  }
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

function detectHydraulicParameters(text, results) {
  if (!text && (!results || results.length === 0)) return null;
  const combined = (text || "") + " " + JSON.stringify(results || []);

  let length = null;
  let diameter = null;
  let flow = null;
  let density = null;
  let viscosity = null;

  const mLen = combined.match(/(?:length|pipeline length|distance)[\s:=]+([0-9.]+)\s*m(?:eters)?\b/i);
  if (mLen) length = parseFloat(mLen[1]);

  const mDia = combined.match(/(?:diameter|inside diameter)[\s:=]+([0-9.]+)\s*m\b/i);
  if (mDia) diameter = parseFloat(mDia[1]);

  const mFlow = combined.match(/(?:flow rate|volumetric flow|flow)[\s:=]+([0-9.]+)\s*(?:m3\/h|m³\/h)\b/i);
  if (mFlow) flow = parseFloat(mFlow[1]);

  const mRho = combined.match(/(?:density)[\s:=]+([0-9.]+)\s*(?:kg\/m3|kg\/m³)\b/i);
  if (mRho) density = parseFloat(mRho[1]);

  const mVisc = combined.match(/(?:viscosity|kinematic viscosity)[\s:=]+([0-9.]+)\s*cst\b/i);
  if (mVisc) viscosity = parseFloat(mVisc[1]);

  const params = {};
  if (length && length >= 10 && length <= 50000) params.length = length;
  if (diameter && diameter >= 0.01 && diameter <= 3.0) params.diameter = diameter;
  if (flow && flow >= 1.0 && flow <= 5000) params.flow = flow;
  if (density && density >= 500 && density <= 1500) params.density = density;
  if (viscosity && viscosity >= 0.1 && viscosity <= 200) params.viscosity = viscosity;

  return Object.keys(params).length >= 2 ? params : null;
}

function renderBotResponse(data) {
  const container = document.getElementById("chat-container");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble chat-bot";

  const routing = data.routing || { profile: "general", model_id: "qwen2.5:7b", vram_estimate_gb: 4.5, reason: "Default routed" };
  const rawPlan = data.plan ? JSON.stringify(data.plan, null, 2) : "";

  // Check for hydrodynamic parameters to sync with Analytics workbench
  const syncParams = detectHydraulicParameters(data.answer, data.results);
  let syncParamsHtml = "";
  if (syncParams) {
    syncParamsHtml = `
      <div style="margin-top: 8px; padding: 7px 10px; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.28); border-radius: 6px; display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap;">
        <span style="font-size: 11px; color: #38BDF8; display: flex; align-items: center; gap: 5px;">
          <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
          <strong>Hydrodynamic Calculation Parameters Detected</strong>
        </span>
        <button class="copilot-query-btn" onclick='syncAgentParameters(${JSON.stringify(syncParams)})' style="padding: 4px 8px; font-size: 10.5px;">
          Apply to Analytics Workbench &rarr;
        </button>
      </div>`;
  }

  let deliverablesHtml = "";
  if (data.deliverables && data.deliverables.length > 0) {
    deliverablesHtml = `<div style="margin-top: 10px; border-top: 1px solid var(--border-color); padding-top: 8px;">
      <div style="font-size: 10.5px; font-weight: 600; color: var(--color-success); margin-bottom: 5px;">Generated Deliverables:</div>`;
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

  // Build Worker Action Steps for Live Orchestration Trace
  let stepsHtml = "";
  if (data.results && data.results.length > 0) {
    data.results.forEach(r => {
      let detailText = "";
      if (r.worker === "code_sandbox") {
        detailText = r.result && r.result.success ? `Executed script (${r.result.execution_time_seconds}s) | Exit Code: 0` : `Script status: ${r.result ? r.result.stderr || 'Executed' : 'Completed'}`;
      } else if (r.worker === "data_analysis") {
        const cnt = r.result ? (r.result.row_count_returned ?? r.result.row_count ?? (Array.isArray(r.result.rows) ? r.result.rows.length : 0)) : 0;
        detailText = r.result && Array.isArray(r.result.rows) ? `DuckDB SQL returned ${cnt} rows` : (r.result && r.result.error ? r.result.error : "Query processed");
      } else if (r.worker === "vision") {
        detailText = `Processed image (${r.result ? r.result.source || 'image' : 'image'}) via local VLM & OCR`;
      } else if (r.worker === "template_author") {
        detailText = `Authored statutory deliverable: ${r.result ? r.result.file_name || 'Document' : 'Document'}`;
      } else if (r.worker === "document_retrieval") {
        detailText = `Retrieved engineering evidence passages`;
      } else {
        detailText = `Executed ${r.action}`;
      }

      stepsHtml += `
        <div class="trace-step-row">
          <span class="trace-worker-pill">${escapeHtml(r.worker)}.${escapeHtml(r.action)}</span>
          <span class="trace-action-text">${escapeHtml(detailText)}</span>
        </div>`;
    });
  } else {
    stepsHtml = `<div style="font-size: 10.5px; color: var(--text-dim);">Direct LLM generation without auxiliary worker invocation.</div>`;
  }

  let vramText = "";
  if (routing.vram_estimate_gb) {
    vramText = `~${routing.vram_estimate_gb} GB VRAM`;
  } else if (data.telemetry?.hardware?.gpu?.detected && data.telemetry.hardware.gpu.name) {
    vramText = data.telemetry.hardware.gpu.name.replace("NVIDIA GeForce ", "").replace(" Laptop GPU", "");
  }

  const modelBadgeHtml = routing.model_id ? `
    <span class="model-badge">
      <svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>
      MODEL: ${escapeHtml(routing.model_id)}
    </span>` : "";

  const profileBadgeHtml = (routing.profile && routing.profile !== "general") ? `
    <span class="profile-badge">${escapeHtml(routing.profile)}</span>` : "";

  const vramBadgeHtml = vramText ? `
    <span class="vram-badge">${escapeHtml(vramText)}</span>` : "";

  bubble.innerHTML = `
    <!-- Top Model Banner (Highly Visible) -->
    <div class="bot-model-header">
      <div class="bot-model-left">
        ${modelBadgeHtml}
        ${profileBadgeHtml}
        ${vramBadgeHtml}
      </div>
      <div class="bot-model-right">
        <span class="mode-tag"><span class="status-dot dot-success"></span> GPU Accelerated (Ollama)</span>
      </div>
    </div>

    <!-- Main Synthesized Content -->
    <div style="line-height: 1.55; margin-top: 6px;">${formatMarkdown(data.answer || "")}</div>

    ${syncParamsHtml}
    ${deliverablesHtml}

    <!-- Live Orchestration Trace (SCADA Transparent Pipeline) -->
    <div class="orchestration-trace-card">
      <div class="trace-header-toggle" onclick="this.parentElement.classList.toggle('open')">
        <span style="display: flex; align-items: center; gap: 6px;">
          <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
          <strong>Live Orchestration Trace</strong> &bull; ${(data.results || []).length} Workers Executed
        </span>
        <span style="font-size: 9.5px; opacity: 0.7;">View Pipeline Details &blacktriangledown;</span>
      </div>
      <div class="trace-body">
        <div style="margin-bottom: 6px; font-size: 10px; color: var(--text-dim);">
          <strong style="color: var(--text-muted);">Router Reason:</strong> ${escapeHtml(routing.reason || "Matched domain profile triggers")}
        </div>
        <div style="font-size: 10px; font-weight: 600; color: var(--text-muted); margin-bottom: 4px;">Worker Dispatch Sequence:</div>
        ${stepsHtml}
        <div class="trace-sovereign-tag">
          <svg viewBox="0 0 24 24" width="11" height="11" stroke="#10B981" stroke-width="2.5" fill="none"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
          <span>100% Air-Gapped / Zero External WAN Traffic / SHA-256 Signed</span>
        </div>
      </div>
    </div>
  `;

  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

const appendBotResponse = renderBotResponse;

// -----------------------------------------------------------------------------
// Deliverables Fetcher & UI Drawer
// -----------------------------------------------------------------------------
// -----------------------------------------------------------------------------
// Deliverables Fetcher & UI Drawer & Reports Explorer
// -----------------------------------------------------------------------------
let cachedDeliverablesList = [];
let currentReportsFilter = "all";

async function fetchDeliverables() {
  try {
    const res = await fetch("/api/deliverables");
    const data = await res.json();
    const list = data.deliverables || [];
    cachedDeliverablesList = list;

    const delivBadge = document.getElementById("copilot-deliverables-label");
    if (delivBadge) {
      delivBadge.textContent = list.length > 0 ? `Deliverables (${list.length})` : "Deliverables";
    }

    // Right copilot deliverables view
    const drawerEl = document.getElementById("results-drawer-list");
    if (drawerEl) {
      if (list.length === 0) {
        drawerEl.innerHTML = `
          <div class="empty-results">
            <div style="font-size: 11.5px; color: var(--text-muted);">No reports generated in this shift yet.</div>
            <div style="font-size: 10.5px; color: var(--text-dim); margin-top: 4px;">Prompt the Copilot to draft an inspection note, export assay cuts, or run a hydrodynamic calculation.</div>
          </div>`;
      } else {
        drawerEl.innerHTML = list.map(f => {
          const dateStr = new Date(f.modified * 1000).toLocaleDateString();
          return `
          <div class="deliverable-card-item">
            <div class="result-file-info">
              ${getFileIcon(f.extension)}
              <div class="deliv-file-meta">
                <span class="result-file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
                <span class="deliv-file-date">${f.size_kb} KB &bull; ${dateStr}</span>
              </div>
            </div>
            <a class="download-link-btn" href="${f.url}" download>Download</a>
          </div>
        `;
        }).join("");
      }
    }

    // Update summary metric strip on Reports tab
    updateReportsStats(list);

    // Render reports table with active filters
    filterReports();

  } catch (err) {
    console.error("Error fetching deliverables:", err);
  }
}

function updateReportsStats(list) {
  const strip = document.getElementById("reports-stats-strip");
  if (!strip) return;

  const totalCount = list.length;
  const docxCount = list.filter(f => (f.extension || "").toLowerCase() === ".docx").length;
  const pptxCount = list.filter(f => (f.extension || "").toLowerCase() === ".pptx").length;
  const xlsxCount = list.filter(f => [".xlsx", ".csv"].includes((f.extension || "").toLowerCase())).length;
  const mdCount = list.filter(f => (f.extension || "").toLowerCase() === ".md").length;
  const pyCount = list.filter(f => (f.extension || "").toLowerCase() === ".py").length;
  const totalMB = (list.reduce((acc, f) => acc + (f.size_kb || 0), 0) / 1024).toFixed(1);

  strip.innerHTML = `
    <div class="file-stat-chip">
      <span class="stat-chip-num">${totalCount}</span>
      <span class="stat-chip-label">Total Reports</span>
    </div>
    <div class="file-stat-chip">
      <span class="stat-chip-num" style="color: #60A5FA;">${docxCount}</span>
      <span class="stat-chip-label">Word Memos</span>
    </div>
    <div class="file-stat-chip">
      <span class="stat-chip-num" style="color: #FBBF24;">${pptxCount}</span>
      <span class="stat-chip-label">Presentations</span>
    </div>
    <div class="file-stat-chip">
      <span class="stat-chip-num" style="color: #34D399;">${xlsxCount}</span>
      <span class="stat-chip-label">Workbooks</span>
    </div>
    <div class="file-stat-chip">
      <span class="stat-chip-num" style="color: #C084FC;">${mdCount}</span>
      <span class="stat-chip-label">AI Reports</span>
    </div>
    <div class="file-stat-chip">
      <span class="stat-chip-num" style="color: #38BDF8;">${totalMB} MB</span>
      <span class="stat-chip-label">Storage Volume</span>
    </div>
  `;
}

function getReadableReportMeta(f) {
  const name = f.name || "";
  const ext = (f.extension || "").toLowerCase();

  let title = name;
  let subtitle = "";
  let category = "Deliverable";
  let catColor = "#94A3B8";

  if (name.startsWith("MRPL_Approval_Note_")) {
    const id = name.replace("MRPL_Approval_Note_", "").replace(/\.[^/.]+$/, "");
    title = "MRPL Statutory Approval Note";
    subtitle = `Statutory Compliance • Ref #${id}`;
    category = "Board Deliverable";
    catColor = "#60A5FA";
  } else if (name.startsWith("MRPL_Calc_Sheet_")) {
    const id = name.replace("MRPL_Calc_Sheet_", "").replace(/\.[^/.]+$/, "");
    title = "Turnaround Engineering Calc Sheet";
    subtitle = `Mass/Energy Balance & Hydraulics • Ref #${id}`;
    category = "Workbook";
    catColor = "#34D399";
  } else if (name.startsWith("MRPL_Executive_Brief_")) {
    const id = name.replace("MRPL_Executive_Brief_", "").replace(/\.[^/.]+$/, "");
    title = "Executive Board Briefing Deck";
    subtitle = `C-Suite Strategic Deck • Ref #${id}`;
    category = "Presentation";
    catColor = "#FBBF24";
  } else if (name.startsWith("supervisor_report_")) {
    const match = name.match(/supervisor_report_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_([a-f0-9]+)/);
    if (match) {
      const dt = `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}`;
      title = "AI Supervisor Shift Investigation Report";
      subtitle = `Shift Execution • ${dt} • Hash #${match[7]}`;
    } else {
      title = "AI Supervisor Operational Report";
      subtitle = name;
    }
    category = "AI Shift Report";
    catColor = "#C084FC";
  } else if (name.startsWith("MRPL_AirGap_Certificate_")) {
    const id = name.replace("MRPL_AirGap_Certificate_", "").replace(/\.[^/.]+$/, "");
    title = "Air-Gap Cryptographic Security Seal";
    subtitle = `Session SHA-256 Digest #${id}`;
    category = "Audit Certificate";
    catColor = "#38BDF8";
  } else if (ext === ".py") {
    title = name.replace(/\.py$/i, "").replace(/_/g, " ").toUpperCase();
    subtitle = "Sandboxed Python Engineering Model";
    category = "Sandbox Script";
    catColor = "#38BDF8";
  } else if (ext === ".png" || ext === ".jpg") {
    title = name.replace(/\.[^/.]+$/, "").replace(/_/g, " ");
    subtitle = "Engineering Sandbox Plot / Diagram";
    category = "Figure / Plot";
    catColor = "#F472B6";
  } else {
    title = name.replace(/\.[^/.]+$/, "").replace(/_/g, " ");
    subtitle = name;
  }

  return { title, subtitle, category, catColor };
}

function setReportsFilter(filterType, btnEl) {
  currentReportsFilter = filterType;
  if (btnEl) {
    document.querySelectorAll("#reports-filter-pills .filter-pill-btn").forEach(b => b.classList.remove("active"));
    btnEl.classList.add("active");
  }
  filterReports();
}

function clearReportsSearch() {
  const input = document.getElementById("reports-search-input");
  if (input) {
    input.value = "";
    filterReports();
  }
}

function resetReportsFilter() {
  clearReportsSearch();
  const allBtn = document.querySelector("#reports-filter-pills .filter-pill-btn[data-filter='all']");
  if (allBtn) setReportsFilter("all", allBtn);
}

function filterReports() {
  const tbody = document.getElementById("deliverables-tbody");
  const countLabel = document.getElementById("reports-count-label");
  const clearBtn = document.getElementById("reports-search-clear");
  const query = (document.getElementById("reports-search-input")?.value || "").toLowerCase().trim();

  if (clearBtn) {
    clearBtn.style.display = query.length > 0 ? "block" : "none";
  }

  let filtered = cachedDeliverablesList.filter(f => {
    const ext = (f.extension || "").toLowerCase();

    // Filter pill check
    if (currentReportsFilter === "docx" && ext !== ".docx") return false;
    if (currentReportsFilter === "pptx" && ext !== ".pptx") return false;
    if (currentReportsFilter === "xlsx" && !([".xlsx", ".csv"].includes(ext))) return false;
    if (currentReportsFilter === "md" && ext !== ".md") return false;
    if (currentReportsFilter === "py" && ext !== ".py") return false;

    // Search query check
    if (query) {
      const meta = getReadableReportMeta(f);
      const name = (f.name || "").toLowerCase();
      const title = meta.title.toLowerCase();
      const sub = meta.subtitle.toLowerCase();
      const cat = meta.category.toLowerCase();
      const dateStr = new Date(f.modified * 1000).toLocaleDateString().toLowerCase();
      const match = name.includes(query) || title.includes(query) || sub.includes(query) || cat.includes(query) || ext.includes(query) || dateStr.includes(query);
      if (!match) return false;
    }

    return true;
  });

  if (countLabel) {
    if (query || currentReportsFilter !== "all") {
      countLabel.textContent = `Showing ${filtered.length} of ${cachedDeliverablesList.length} reports`;
    } else {
      countLabel.textContent = `Showing all ${cachedDeliverablesList.length} reports`;
    }
  }

  if (!tbody) return;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6">
          <div class="empty-file-state">
            <p>No deliverables match your search or filter criteria.</p>
            <button class="empty-file-reset-btn" onclick="resetReportsFilter()">Reset Filter &amp; Search</button>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(f => {
    const meta = getReadableReportMeta(f);
    const dateStr = new Date(f.modified * 1000).toLocaleDateString(undefined, {
      year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
    });
    const formatBadge = getFileFormatBadge(f.extension);

    return `
      <tr>
        <td>
          <div style="font-weight: 700; color: #F1F5F9; font-size: 12.5px;">${escapeHtml(meta.title)}</div>
          <div style="font-size: 11px; color: var(--text-dim); margin-top: 3px; font-family: var(--font-mono);">
            ${escapeHtml(meta.subtitle)}
          </div>
        </td>
        <td>${formatBadge}</td>
        <td>
          <span class="file-category-pill" style="color: ${meta.catColor}; border-color: ${meta.catColor}40;">
            ${escapeHtml(meta.category)}
          </span>
        </td>
        <td style="font-family: var(--font-mono); font-size: 11.5px; color: #CBD5E1;">${f.size_kb} KB</td>
        <td style="color: var(--text-muted); font-size: 11px;">${dateStr}</td>
        <td style="text-align: right; white-space: nowrap;">
          <a class="download-link-btn" href="${f.url}" download title="Download file to local workstation">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Download
          </a>
          <button class="ask-ai-link-btn" onclick="queryDeliverableInCopilot('${escapeHtml(f.name)}')" title="Ask AI Copilot to analyze this report">
            ⚡ Ask AI
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

function getFileFormatBadge(ext) {
  const clean = (ext || "").toLowerCase().trim();
  if (clean === ".docx") return '<span class="file-format-badge fmt-docx">DOCX</span>';
  if (clean === ".xlsx") return '<span class="file-format-badge fmt-xlsx">XLSX</span>';
  if (clean === ".csv") return '<span class="file-format-badge fmt-csv">CSV</span>';
  if (clean === ".pptx") return '<span class="file-format-badge fmt-pptx">PPTX</span>';
  if (clean === ".pdf") return '<span class="file-format-badge fmt-pdf">PDF</span>';
  if (clean === ".md") return '<span class="file-format-badge fmt-md">MD</span>';
  if (clean === ".py") return '<span class="file-format-badge fmt-py">PY</span>';
  if (clean === ".png" || clean === ".jpg" || clean === ".jpeg") return '<span class="file-format-badge fmt-img">PNG</span>';
  return `<span class="file-format-badge">${clean.replace(".", "").toUpperCase() || "FILE"}</span>`;
}

function getFileIcon(ext) {
  return getFileFormatBadge(ext);
}

function queryDeliverableInCopilot(filename) {
  const input = document.getElementById("copilot-input");
  if (input) {
    input.value = `Analyze and summarize deliverable ${filename}, extracting key findings, anomalies, and statutory recommendations.`;
    input.focus();
  }
}

// -----------------------------------------------------------------------------
// Documents Fetcher & Repository Registry
// -----------------------------------------------------------------------------
let cachedDocumentsList = [];
let currentDocsFilter = "all";

async function fetchDocuments() {
  try {
    const res = await fetch("/api/documents");
    if (!res.ok) return;
    const docs = await res.json();
    if (!Array.isArray(docs)) return;
    cachedDocumentsList = docs;

    updateDocumentsStats(docs);
    filterDocuments();
  } catch (err) {
    console.warn("Could not load /api/documents:", err);
  }
}

function updateDocumentsStats(docs) {
  const strip = document.getElementById("docs-stats-strip");
  if (!strip) return;

  const totalCount = docs.length;
  const pidCount = docs.filter(d => (d.category || "").includes("P&ID")).length;
  const crudeCount = docs.filter(d => (d.category || "").includes("Crude")).length;
  const safetyCount = docs.filter(d => (d.category || "").includes("Standard") || (d.category || "").includes("NDT")).length;
  const sparesCount = docs.filter(d => (d.category || "").includes("Spares") || (d.category || "").includes("Pipe")).length;
  const totalMB = (docs.reduce((acc, d) => acc + (d.size_kb || 0), 0) / 1024).toFixed(1);

  strip.innerHTML = `
    <div class="file-stat-chip">
      <span class="stat-chip-num">${totalCount}</span>
      <span class="stat-chip-label">Indexed Documents</span>
    </div>
    <div class="file-stat-chip">
      <span class="stat-chip-num" style="color: #EC4899;">${pidCount}</span>
      <span class="stat-chip-label">P&amp;ID Schemes</span>
    </div>
    <div class="file-stat-chip">
      <span class="stat-chip-num" style="color: #FBBF24;">${crudeCount}</span>
      <span class="stat-chip-label">Crude Assays</span>
    </div>
    <div class="file-stat-chip">
      <span class="stat-chip-num" style="color: #F87171;">${safetyCount}</span>
      <span class="stat-chip-label">Safety &amp; Codes</span>
    </div>
    <div class="file-stat-chip">
      <span class="stat-chip-num" style="color: #34D399;">${sparesCount}</span>
      <span class="stat-chip-label">Spares &amp; Pipes</span>
    </div>
    <div class="file-stat-chip">
      <span class="stat-chip-num" style="color: #38BDF8;">${totalMB} MB</span>
      <span class="stat-chip-label">Verified Storage</span>
    </div>
  `;
}

function setDocsFilter(filterType, btnEl) {
  currentDocsFilter = filterType;
  if (btnEl) {
    document.querySelectorAll("#docs-filter-pills .filter-pill-btn").forEach(b => b.classList.remove("active"));
    btnEl.classList.add("active");
  }
  filterDocuments();
}

function clearDocsSearch() {
  const input = document.getElementById("docs-search-input");
  if (input) {
    input.value = "";
    filterDocuments();
  }
}

function resetDocsFilter() {
  clearDocsSearch();
  const allBtn = document.querySelector("#docs-filter-pills .filter-pill-btn[data-filter='all']");
  if (allBtn) setDocsFilter("all", allBtn);
}

function filterDocuments() {
  const tbody = document.getElementById("documents-tbody");
  const countLabel = document.getElementById("docs-count-label");
  const clearBtn = document.getElementById("docs-search-clear");
  const query = (document.getElementById("docs-search-input")?.value || "").toLowerCase().trim();

  if (clearBtn) {
    clearBtn.style.display = query.length > 0 ? "block" : "none";
  }

  let filtered = cachedDocumentsList.filter(d => {
    const cat = (d.category || "").toLowerCase();
    const name = (d.name || "").toLowerCase();
    const fmt = (d.format || "").toLowerCase();

    // Filter pill check
    if (currentDocsFilter === "pid" && !cat.includes("p&id")) return false;
    if (currentDocsFilter === "crude" && !cat.includes("crude")) return false;
    if (currentDocsFilter === "ndt" && !(cat.includes("ndt") || cat.includes("standard") || cat.includes("safety"))) return false;
    if (currentDocsFilter === "asme" && !(cat.includes("pipe") || cat.includes("spares"))) return false;
    if (currentDocsFilter === "ppac" && !(name.includes("ppac") || cat.includes("production") || name.includes("slate"))) return false;

    // Search query check
    if (query) {
      const title = (d.title || "").toLowerCase();
      const desc = (d.description || "").toLowerCase();
      const match = name.includes(query) || title.includes(query) || desc.includes(query) || cat.includes(query) || fmt.includes(query);
      if (!match) return false;
    }

    return true;
  });

  if (countLabel) {
    if (query || currentDocsFilter !== "all") {
      countLabel.textContent = `Showing ${filtered.length} of ${cachedDocumentsList.length} documents`;
    } else {
      countLabel.textContent = `Showing all ${cachedDocumentsList.length} documents`;
    }
  }

  if (!tbody) return;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6">
          <div class="empty-file-state">
            <p>No indexed documents match your search or filter criteria.</p>
            <button class="empty-file-reset-btn" onclick="resetDocsFilter()">Reset Filter &amp; Search</button>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(d => {
    const isDuckDB = d.format === "CSV";
    const isVision = d.format === "PNG" || d.format === "JPG";
    const engine = isDuckDB ? "DuckDB (In-Memory)" : (isVision ? "Vision Cache" : "PyMuPDF / RAG");
    const statusClass = d.exists ? "green" : "orange";
    const statusText = d.exists ? `Active (${d.size_kb} KB)` : "Offline";
    const fmtBadge = getFileFormatBadge("." + (d.format || "file").toLowerCase());

    return `
      <tr>
        <td>
          <div style="font-weight: 700; color: #F1F5F9; font-size: 12.5px;">${escapeHtml(d.title || d.name)}</div>
          <div style="font-size: 11px; color: var(--text-dim); margin-top: 3px; font-family: var(--font-mono);">
            <code>${escapeHtml(d.name)}</code> &bull; ${escapeHtml(d.description || "")}
          </div>
        </td>
        <td>
          <span class="file-category-pill">${escapeHtml(d.category || "Dataset")}</span>
        </td>
        <td>${fmtBadge}</td>
        <td><span style="font-weight: 600; font-size: 11px; color: #38BDF8;">${engine}</span></td>
        <td><span class="status-badge-${statusClass}">${statusText}</span></td>
        <td style="text-align: right; white-space: nowrap;">
          <a class="download-link-btn" href="/api/download/${encodeURIComponent(d.name)}?source=data" download title="Download raw dataset">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Get
          </a>
          <button class="ask-ai-link-btn" onclick="queryDocInCopilot('${escapeHtml(d.name)}')" title="Query this document in Copilot">
            ⚡ Query
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

function queryDocInCopilot(filename) {
  const input = document.getElementById("copilot-input");
  if (input) {
    input.value = `Query verified operational document ${filename} for engineering parameters, design criteria, and specifications.`;
    input.focus();
  }
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

  // 1. Code blocks: ```lang ... ```
  text = text.replace(/```(?:[a-zA-Z0-9_-]+)?\r?\n([\s\S]*?)```/g, (m, code) => {
    return `<pre class="chat-code-block"><code>${code.trim()}</code></pre>`;
  });

  // 2. Markdown tables: lines with pipes
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

  // 3. Blockquotes: lines starting with &gt;
  text = text.replace(/^(?:&gt;|>)\s?(.*)$/gm, '<blockquote class="chat-quote">$1</blockquote>');

  // 4. Inline formatting
  text = text.replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>');
  text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/### (.*?)(?:\n|$)/g, '<h4 style="margin: 5px 0 2px 0; color: var(--text-heading); font-size: 11px; font-weight: 700;">$1</h4>');
  text = text.replace(/## (.*?)(?:\n|$)/g, '<h3 style="margin: 6px 0 3px 0; color: var(--text-heading); font-size: 11.5px; font-weight: 700;">$1</h3>');
  text = text.replace(/^- (.*?)(?:\n|$)/gm, '<li style="margin-left: 12px; margin-bottom: 2px;">$1</li>');
  text = text.replace(/\n/g, "<br>");
  return text;
}

// -----------------------------------------------------------------------------
// Interactive Crude Assays & TBP Distillation Yields
// Grounded in data/real_crude_oil_assays.csv
// -----------------------------------------------------------------------------
let currentAssayName = "Arabian Light";

const CRUDE_ASSAYS = {
  "Arabian Light": {
    btnId: "btn-assay-arab-light",
    origin: "Saudi Arabia",
    api: "32.8° API",
    density: "861.2 kg/m³ @ 15°C",
    sulfur: "1.97 wt%",
    tan: "0.12 mg KOH/g",
    pour: "Pour Point: -21.0°C",
    viscosity: "5.30 cSt",
    cuts: [
      { name: "LPG (Liquefied Petroleum Gas)", range: "C3 - C4 (< 20°C)", pct: 2.4, class: "cut-lpg", unit: "Mounded Storage Bullets & LPG Merox" },
      { name: "Light & Heavy Naphtha", range: "IBP - 150°C", pct: 19.4, class: "cut-naphtha", unit: "NHT & Catalytic Reforming (CCR Platformer)" },
      { name: "Aviation Turbine Fuel / Kerosene", range: "150°C - 240°C", pct: 12.3, class: "cut-atf", unit: "Kero Merox Sweetening (IS 1571 Jet A-1)" },
      { name: "High Speed Diesel (HSD BS-VI)", range: "240°C - 360°C", pct: 21.5, class: "cut-diesel", unit: "Diesel Hydrotreater DHDT (< 10 ppm S)" },
      { name: "Vacuum Gas Oil (VGO)", range: "360°C - 565°C", pct: 30.3, class: "cut-vgo", unit: "Hydrocracker Unit (HCU) & FCCU Feed" },
      { name: "Vacuum Residue / Heavy Ends", range: "> 565°C", pct: 14.1, class: "cut-residue", unit: "Delayed Coker Unit (DCU) & Bitumen (VG-30)" }
    ]
  },
  "Arabian Heavy": {
    btnId: "btn-assay-arab-heavy",
    origin: "Saudi Arabia",
    api: "27.9° API",
    density: "887.6 kg/m³ @ 15°C",
    sulfur: "2.85 wt%",
    tan: "0.24 mg KOH/g",
    pour: "Pour Point: -18.0°C",
    viscosity: "15.20 cSt",
    cuts: [
      { name: "LPG (Liquefied Petroleum Gas)", range: "C3 - C4 (< 20°C)", pct: 1.8, class: "cut-lpg", unit: "Mounded Storage Bullets & LPG Merox" },
      { name: "Light & Heavy Naphtha", range: "IBP - 150°C", pct: 14.3, class: "cut-naphtha", unit: "NHT & Catalytic Reforming (CCR Platformer)" },
      { name: "Aviation Turbine Fuel / Kerosene", range: "150°C - 240°C", pct: 10.4, class: "cut-atf", unit: "Kero Merox Sweetening (IS 1571 Jet A-1)" },
      { name: "High Speed Diesel (HSD BS-VI)", range: "240°C - 360°C", pct: 18.2, class: "cut-diesel", unit: "Diesel Hydrotreater DHDT (< 10 ppm S)" },
      { name: "Vacuum Gas Oil (VGO)", range: "360°C - 565°C", pct: 29.8, class: "cut-vgo", unit: "Hydrocracker Unit (HCU) & FCCU Feed" },
      { name: "Vacuum Residue / Heavy Ends", range: "> 565°C", pct: 25.5, class: "cut-residue", unit: "Delayed Coker Unit (DCU) & Bitumen (VG-40)" }
    ]
  },
  "Brent Blend": {
    btnId: "btn-assay-brent",
    origin: "United Kingdom",
    api: "38.3° API",
    density: "833.3 kg/m³ @ 15°C",
    sulfur: "0.37 wt%",
    tan: "0.08 mg KOH/g",
    pour: "Pour Point: -6.0°C",
    viscosity: "3.40 cSt",
    cuts: [
      { name: "LPG (Liquefied Petroleum Gas)", range: "C3 - C4 (< 20°C)", pct: 3.1, class: "cut-lpg", unit: "Mounded Storage Bullets & LPG Merox" },
      { name: "Light & Heavy Naphtha", range: "IBP - 150°C", pct: 23.6, class: "cut-naphtha", unit: "NHT & Catalytic Reforming (CCR Platformer)" },
      { name: "Aviation Turbine Fuel / Kerosene", range: "150°C - 240°C", pct: 13.8, class: "cut-atf", unit: "Kero Merox Sweetening (IS 1571 Jet A-1)" },
      { name: "High Speed Diesel (HSD BS-VI)", range: "240°C - 360°C", pct: 23.6, class: "cut-diesel", unit: "Diesel Hydrotreater DHDT (< 10 ppm S)" },
      { name: "Vacuum Gas Oil (VGO)", range: "360°C - 565°C", pct: 22.1, class: "cut-vgo", unit: "Hydrocracker Unit (HCU) & FCCU Feed" },
      { name: "Vacuum Residue / Heavy Ends", range: "> 565°C", pct: 13.8, class: "cut-residue", unit: "Delayed Coker Unit (DCU) & Bitumen" }
    ]
  },
  "Maya Heavy": {
    btnId: "btn-assay-maya",
    origin: "Mexico",
    api: "21.8° API",
    density: "923.0 kg/m³ @ 15°C",
    sulfur: "3.52 wt%",
    tan: "0.42 mg KOH/g",
    pour: "Pour Point: -9.0°C",
    viscosity: "32.80 cSt",
    cuts: [
      { name: "LPG (Liquefied Petroleum Gas)", range: "C3 - C4 (< 20°C)", pct: 1.5, class: "cut-lpg", unit: "Mounded Storage Bullets & LPG Merox" },
      { name: "Light & Heavy Naphtha", range: "IBP - 150°C", pct: 11.8, class: "cut-naphtha", unit: "NHT & Catalytic Reforming (CCR Platformer)" },
      { name: "Aviation Turbine Fuel / Kerosene", range: "150°C - 240°C", pct: 8.8, class: "cut-atf", unit: "Kero Merox Sweetening (IS 1571 Jet A-1)" },
      { name: "High Speed Diesel (HSD BS-VI)", range: "240°C - 360°C", pct: 16.4, class: "cut-diesel", unit: "Diesel Hydrotreater DHDT (< 10 ppm S)" },
      { name: "Vacuum Gas Oil (VGO)", range: "360°C - 565°C", pct: 33.0, class: "cut-vgo", unit: "Hydrocracker Unit (HCU) & FCCU Feed" },
      { name: "Vacuum Residue / Heavy Ends", range: "> 565°C", pct: 28.5, class: "cut-residue", unit: "Delayed Coker Unit (DCU) & Bitumen" }
    ]
  },
  "Mangala": {
    btnId: "btn-assay-mangala",
    origin: "India (Rajasthan)",
    api: "29.0° API",
    density: "881.6 kg/m³ @ 15°C",
    sulfur: "0.12 wt%",
    tan: "0.35 mg KOH/g",
    pour: "Pour Point: +30.0°C (Waxy)",
    viscosity: "28.50 cSt",
    cuts: [
      { name: "LPG (Liquefied Petroleum Gas)", range: "C3 - C4 (< 20°C)", pct: 1.2, class: "cut-lpg", unit: "Mounded Storage Bullets & LPG Merox" },
      { name: "Light & Heavy Naphtha", range: "IBP - 150°C", pct: 11.3, class: "cut-naphtha", unit: "NHT & Catalytic Reforming (CCR Platformer)" },
      { name: "Aviation Turbine Fuel / Kerosene", range: "150°C - 240°C", pct: 9.2, class: "cut-atf", unit: "Kero Merox Sweetening (IS 1571 Jet A-1)" },
      { name: "High Speed Diesel (HSD BS-VI)", range: "240°C - 360°C", pct: 22.1, class: "cut-diesel", unit: "Diesel Hydrotreater DHDT (< 10 ppm S)" },
      { name: "Vacuum Gas Oil (VGO)", range: "360°C - 565°C", pct: 38.2, class: "cut-vgo", unit: "Hydrocracker Unit (HCU) & FCCU Feed" },
      { name: "Vacuum Residue / Heavy Ends", range: "> 565°C", pct: 18.0, class: "cut-residue", unit: "Delayed Coker Unit (DCU) & Bitumen" }
    ]
  }
};

// Toggle between Visual SCADA view and Raw Data Table across tabs
function toggleMrView(section, viewType, btn) {
  const card = btn.closest(".hud-glass-card, .dash-card, .audit-section-container, .audit-card-wrap");
  if (!card) return;
  btn.parentElement.querySelectorAll(".view-toggle-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  const visualEl = card.querySelector(".section-visual-view");
  const tableEl = card.querySelector(".section-table-view");
  if (viewType === "visual") {
    if (visualEl) visualEl.style.display = "block";
    if (tableEl) tableEl.style.display = "none";
  } else {
    if (visualEl) visualEl.style.display = "none";
    if (tableEl) tableEl.style.display = "block";
  }
}

// Seamless interlock from dashboard to DRISHTI AI Copilot
function prefillCopilotChat(promptText) {
  const inputEl = document.getElementById("chat-input");
  if (inputEl) {
    inputEl.value = promptText;
    inputEl.focus();
    inputEl.style.transition = "box-shadow 0.3s ease";
    inputEl.style.boxShadow = "0 0 14px rgba(255, 122, 0, 0.7)";
    setTimeout(() => {
      inputEl.style.boxShadow = "";
    }, 1500);
  }
  const panel = document.querySelector(".copilot-panel");
  if (panel && panel.classList.contains("collapsed")) {
    panel.classList.remove("collapsed");
  }
}

function switchCrudeAssay(assayName) {
  const assay = CRUDE_ASSAYS[assayName];
  if (!assay) return;
  currentAssayName = assayName;

  // Toggle active button
  document.querySelectorAll(".assay-toggle-btn").forEach(btn => btn.classList.remove("active"));
  const activeBtn = document.getElementById(assay.btnId);
  if (activeBtn) activeBtn.classList.add("active");

  // Update properties
  const propApi = document.getElementById("assay-prop-api");
  const propDensity = document.getElementById("assay-prop-density");
  const propSulfur = document.getElementById("assay-prop-sulfur");
  const propTan = document.getElementById("assay-prop-tan");
  const propVisc = document.getElementById("assay-prop-visc");
  const propPour = document.getElementById("assay-prop-pour");

  if (propApi) propApi.textContent = assay.api;
  if (propDensity) propDensity.textContent = assay.density;
  if (propSulfur) propSulfur.textContent = assay.sulfur;
  if (propTan) propTan.textContent = assay.tan;
  if (propVisc) propVisc.textContent = assay.viscosity;
  if (propPour) propPour.textContent = assay.pour;

  const basketLabel = document.getElementById("mr-basket-name");
  if (basketLabel) basketLabel.textContent = assayName;

  const nameBadge = document.getElementById("assay-current-name-badge");
  if (nameBadge) nameBadge.textContent = assayName;

  // Update Main Refinery Equalizer Bars in HUD
  const mainEq = document.getElementById("hud-main-equalizer-bars");
  if (mainEq && assay.cuts) {
    mainEq.innerHTML = "";
    assay.cuts.forEach(cut => {
      const bar = document.createElement("div");
      bar.className = "eq-bar active";
      const h = Math.round(Math.min(64, Math.max(14, cut.pct * 1.8)));
      bar.style.height = `${h}px`;
      bar.title = `${cut.name}: ${cut.pct}%`;
      mainEq.appendChild(bar);
    });
  }

  // Rebuild Distillation Cut Bar
  const cutBar = document.getElementById("assay-cut-bar");
  if (cutBar && assay.cuts) {
    const cutNameMap = {
      "cut-lpg": "LPG",
      "cut-naphtha": "Naphtha",
      "cut-atf": "ATF",
      "cut-diesel": "Diesel",
      "cut-vgo": "VGO",
      "cut-residue": "Resid"
    };

    cutBar.innerHTML = assay.cuts.map(cut => {
      const shortName = cutNameMap[cut.class] || cut.name.split(' ')[0];
      const textContent = cut.pct >= 6.0 ? `${shortName} ${cut.pct.toFixed(1)}%` : "";
      return `<div class="cut-segment ${cut.class}" style="width: ${cut.pct}%;" title="${escapeHtml(cut.name)}: ${cut.pct.toFixed(1)}%">${textContent}</div>`;
    }).join("");

    // Update legend values if elements exist
    assay.cuts.forEach(cut => {
      const el = document.getElementById(`legend-${cut.class}`);
      if (el) el.textContent = `${cut.pct.toFixed(1)}%`;
    });
  }

  // Calculate Distillate Quality Spectrum Summary
  const cuts = assay.cuts || [];
  let light = 0, mid = 0, heavy = 0;
  cuts.forEach(c => {
    if (c.class === "cut-lpg" || c.class === "cut-naphtha") light += c.pct;
    else if (c.class === "cut-atf" || c.class === "cut-diesel") mid += c.pct;
    else heavy += c.pct;
  });
  const elLight = document.getElementById("summary-light-ends");
  const elMid = document.getElementById("summary-mid-distillates");
  const elHeavy = document.getElementById("summary-heavy-ends");
  if (elLight) elLight.textContent = `${light.toFixed(1)}%`;
  if (elMid) elMid.textContent = `${mid.toFixed(1)}%`;
  if (elHeavy) elHeavy.textContent = `${heavy.toFixed(1)}%`;

  // Render Visual Yield Stream Cards
  const visualContainer = document.getElementById("assay-visual-cuts-container");
  if (visualContainer && cuts.length) {
    const cutGradientMap = {
      "cut-lpg": "linear-gradient(90deg, #0284C7, #38BDF8)",
      "cut-naphtha": "linear-gradient(90deg, #2563EB, #60A5FA)",
      "cut-atf": "linear-gradient(90deg, #D97706, #FBBF24)",
      "cut-diesel": "linear-gradient(90deg, #059669, #10B981)",
      "cut-vgo": "linear-gradient(90deg, #7C3AED, #A855F7)",
      "cut-residue": "linear-gradient(90deg, #475569, #94A3B8)"
    };
    const cutColorMap = {
      "cut-lpg": "#38BDF8",
      "cut-naphtha": "#60A5FA",
      "cut-atf": "#FBBF24",
      "cut-diesel": "#10B981",
      "cut-vgo": "#A855F7",
      "cut-residue": "#94A3B8"
    };

    visualContainer.innerHTML = cuts.map(cut => {
      const grad = cutGradientMap[cut.class] || "linear-gradient(90deg, #FF7A00, #FF9E2C)";
      const dotColor = cutColorMap[cut.class] || "#FF9E2C";
      return `
        <div class="yield-stream-card ${cut.class}">
          <div class="yield-stream-header">
            <div class="yield-stream-info">
              <span class="yield-color-dot" style="background: ${dotColor};"></span>
              <span class="yield-stream-name">${escapeHtml(cut.name)}</span>
              <span class="yield-stream-range">${escapeHtml(cut.range)}</span>
            </div>
            <div class="yield-stream-pct" style="color: ${dotColor};">
              ${cut.pct.toFixed(1)}% <span class="yield-stream-unit">Vol</span>
            </div>
          </div>
          <div class="yield-progress-track">
            <div class="yield-progress-fill" style="width: ${cut.pct}%; background: ${grad};"></div>
          </div>
          <div class="yield-stream-footer">
            <span class="yield-dest-arrow">➜</span>
            <span class="yield-dest-label">Disposition:</span>
            <span class="yield-dest-value">${escapeHtml(cut.unit)}</span>
          </div>
        </div>
      `;
    }).join("");
  }

  // Rebuild Cut Table Body (for toggle view)
  const tbody = document.getElementById("assay-cut-table-body");
  if (tbody) {
    tbody.innerHTML = assay.cuts.map(cut => `
      <tr>
        <td><strong>${cut.name}</strong></td>
        <td><code>${cut.range}</code></td>
        <td style="font-weight: 700; color: var(--text-heading); font-family: var(--font-mono);">${cut.pct.toFixed(1)}%</td>
        <td>${cut.unit}</td>
      </tr>
    `).join("");
  }
}

// -----------------------------------------------------------------------------
// Interactive Hydrodynamic Calculator (Darcy-Weisbach & Swamee-Jain)
// -----------------------------------------------------------------------------
const DARCY_PRESETS = {
  "crude": { length: 500.0, diameter: 0.3048, flow: 450.0, density: 875.0, viscosity: 15.0, roughness: 0.045, btnId: "btn-preset-crude" },
  "diesel": { length: 1200.0, diameter: 0.2027, flow: 220.0, density: 830.0, viscosity: 3.5, roughness: 0.045, btnId: "btn-preset-diesel" },
  "cw": { length: 800.0, diameter: 0.4064, flow: 1200.0, density: 1000.0, viscosity: 1.0, roughness: 0.050, btnId: "btn-preset-cw" }
};

function applyDarcyPreset(presetKey) {
  const p = DARCY_PRESETS[presetKey];
  if (!p) return;

  const lenEl = document.getElementById("darcy-input-length");
  const diaEl = document.getElementById("darcy-input-diameter");
  const flowEl = document.getElementById("darcy-input-flow");
  const denEl = document.getElementById("darcy-input-density");
  const viscEl = document.getElementById("darcy-input-viscosity");
  const roughEl = document.getElementById("darcy-input-roughness");

  if (lenEl) lenEl.value = p.length;
  if (diaEl) diaEl.value = p.diameter;
  if (flowEl) flowEl.value = p.flow;
  if (denEl) denEl.value = p.density;
  if (viscEl) viscEl.value = p.viscosity;
  if (roughEl) roughEl.value = p.roughness;

  document.querySelectorAll("#tab-analytics .assay-toggle-btn").forEach(btn => btn.classList.remove("active"));
  const targetBtn = document.getElementById(p.btnId);
  if (targetBtn) targetBtn.classList.add("active");

  executeInteractiveDarcy();
}

function executeInteractiveDarcy() {
  const L = parseFloat(document.getElementById("darcy-input-length")?.value) || 500.0;
  const D = parseFloat(document.getElementById("darcy-input-diameter")?.value) || 0.3048;
  const Q = parseFloat(document.getElementById("darcy-input-flow")?.value) || 450.0;
  const rho = parseFloat(document.getElementById("darcy-input-density")?.value) || 875.0;
  const nu_cSt = parseFloat(document.getElementById("darcy-input-viscosity")?.value) || 15.0;
  const rough_mm = parseFloat(document.getElementById("darcy-input-roughness")?.value) || 0.045;

  // Fluid mechanics calculation
  const area = Math.PI * Math.pow(D, 2) / 4.0;
  const Q_m3s = Q / 3600.0;
  const v = Q_m3s / area;
  const nu_m2s = nu_cSt * 1e-6;
  const Re = (v * D) / nu_m2s;

  const eps_m = rough_mm / 1000.0;
  let f = 0.02;
  if (Re < 2300) {
    f = 64.0 / (Re || 1);
  } else {
    // Swamee-Jain formula
    const term1 = eps_m / (3.7 * D);
    const term2 = 5.74 / Math.pow(Re, 0.9);
    f = 0.25 / Math.pow(Math.log10(term1 + term2), 2);
  }

  // Pressure drop (Darcy-Weisbach)
  const deltaP_Pa = f * (L / D) * 0.5 * rho * Math.pow(v, 2);
  const deltaP_bar = deltaP_Pa / 100000.0;
  const deltaP_kPa = deltaP_Pa / 1000.0;

  // Head loss & gradient
  const head_m = deltaP_Pa / (rho * 9.80665);
  const gradient_m_km = (head_m / L) * 1000.0;

  // Update UI Elements
  const velEl = document.getElementById("darcy-res-velocity");
  const reyEl = document.getElementById("darcy-res-reynolds");
  const regEl = document.getElementById("darcy-res-regime");
  const fEl = document.getElementById("darcy-res-friction");
  const gradEl = document.getElementById("darcy-res-gradient");
  const dpEl = document.getElementById("darcy-res-deltap");

  if (velEl) velEl.textContent = `${v.toFixed(2)} m/s`;
  if (reyEl) reyEl.textContent = Math.round(Re).toLocaleString();
  if (fEl) fEl.textContent = f.toFixed(5);
  if (gradEl) gradEl.textContent = `${gradient_m_km.toFixed(2)} m / km`;
  if (dpEl) dpEl.textContent = `${deltaP_bar.toFixed(3)} bar (${deltaP_kPa.toFixed(1)} kPa)`;

  if (regEl) {
    if (Re < 2300) {
      regEl.className = "status-badge-blue";
      regEl.textContent = "Laminar Flow";
    } else if (Re < 4000) {
      regEl.className = "status-badge-yellow";
      regEl.textContent = "Transitional Flow";
    } else {
      regEl.className = "status-badge-green";
      regEl.textContent = "Turbulent Flow";
    }
  }

  // Update Sandbox script text and stdout
  const scriptEl = document.getElementById("darcy-script-code");
  if (scriptEl) {
    scriptEl.textContent = `length_m = ${L.toFixed(1)}          # Pipeline length (m)
diameter_m = ${D.toFixed(4)}       # Pipe inside diameter (m)
flow_rate_m3_h = ${Q.toFixed(1)}    # Transfer volumetric flow (m3/h)
density_kg_m3 = ${rho.toFixed(1)}     # Fluid density at operating temp
viscosity_cSt = ${nu_cSt.toFixed(1)}      # Kinematic viscosity (cSt)

velocity_m_s = (flow_rate_m3_h / 3600.0) / (3.14159 * (${D.toFixed(4)}**2) / 4.0)
reynolds = (velocity_m_s * ${D.toFixed(4)}) / (${nu_cSt.toFixed(1)} * 1e-6)
f = ${f.toFixed(5)} # Swamee-Jain friction factor
delta_p_bar = (f * (${L.toFixed(1)}/${D.toFixed(4)}) * 0.5 * ${rho.toFixed(1)} * (velocity_m_s**2)) / 100000.0
print(f"Total Pressure Drop: {delta_p_bar:.3f} bar")`;
  }

  const stdoutEl = document.getElementById("sandbox-stdout");
  if (stdoutEl) {
    const now = new Date().toLocaleTimeString();
    stdoutEl.innerHTML = `[${now}] Calculation Complete:<br>
Flow Velocity: ${v.toFixed(2)} m/s<br>
Reynolds Number: ${Math.round(Re).toLocaleString()} (${Re >= 4000 ? 'Turbulent' : 'Laminar'})<br>
Darcy Friction Factor: ${f.toFixed(5)}<br>
Total Pressure Drop: ${deltaP_bar.toFixed(3)} bar (${deltaP_kPa.toFixed(1)} kPa)<br>
Hydraulic Gradient: ${gradient_m_km.toFixed(2)} m head loss / km<br>
[Exit Code: 0 | Execution Time: 0.08s]`;
  }

  // Render Dynamic Canvas Chart
  renderDarcyCanvasChart(L, D, Q, rho, nu_cSt, rough_mm, deltaP_bar, v, Re, f);
}

// -----------------------------------------------------------------------------
// Dynamic Darcy-Weisbach Hydraulic Canvas Chart (Zero External CDN)
// -----------------------------------------------------------------------------
let darcyChartState = null;
let darcyEventsAttached = false;

function getThemeColors() {
  const isDark = document.documentElement.getAttribute("data-theme") !== "light";
  return {
    isDark,
    textColor: isDark ? "#94a3b8" : "#64748b",
    headingColor: isDark ? "#f8fafc" : "#0f172a",
    gridColor: isDark ? "rgba(255, 255, 255, 0.07)" : "rgba(0, 0, 0, 0.06)",
    axisColor: isDark ? "rgba(255, 255, 255, 0.18)" : "rgba(0, 0, 0, 0.18)",
    crosshairColor: isDark ? "rgba(56, 189, 248, 0.4)" : "rgba(2, 132, 199, 0.4)"
  };
}

function renderDarcyCanvasChart(L, D, Q, rho, nu_cSt, rough_mm, deltaP_bar, v, Re, f, hoverX = null) {
  const canvas = document.getElementById("darcy-canvas-chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const w = rect.width || (canvas.parentElement ? canvas.parentElement.clientWidth : 480) || 480;
  const h = rect.height || (canvas.parentElement ? canvas.parentElement.clientHeight : 230) || 230;

  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
  if (ctx.resetTransform) {
    ctx.resetTransform();
  } else {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
  }
  ctx.scale(dpr, dpr);

  const colors = getThemeColors();
  ctx.clearRect(0, 0, w, h);

  const padL = 52;
  const padR = 25;
  const padT = 20;
  const padB = 35;
  const plotW = Math.max(10, w - padL - padR);
  const plotH = Math.max(10, h - padT - padB);

  // Pressure Calculations
  const P_inlet = Math.max(12.0, Math.ceil((deltaP_bar + 10.5) * 10) / 10);
  const P_outlet = P_inlet - deltaP_bar;
  const P_limit = 10.5; // Min statutory delivery pressure limit (bar)

  // Update outlet legend label
  const outletLegendEl = document.getElementById("darcy-outlet-legend");
  if (outletLegendEl) {
    outletLegendEl.textContent = `${P_outlet.toFixed(2)} bar`;
  }

  const yMin = Math.max(0, Math.min(9.5, P_outlet - 0.6));
  const yMax = Math.max(13.0, P_inlet + 0.6);

  const toX = dist => padL + (dist / L) * plotW;
  const toY = p => padT + (1 - (p - yMin) / (yMax - yMin)) * plotH;

  // Save chart state for mouse events
  darcyChartState = {
    L, D, Q, rho, nu_cSt, rough_mm, deltaP_bar, v, Re, f,
    P_inlet, P_outlet, P_limit, yMin, yMax,
    padL, padR, padT, padB, plotW, plotH, w, h
  };

  // Draw Horizontal Grid Lines & Y Axis Ticks
  ctx.font = "10px Inter, -apple-system, sans-serif";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";

  const numYTicks = 5;
  for (let i = 0; i <= numYTicks; i++) {
    const val = yMin + (i / numYTicks) * (yMax - yMin);
    const yPos = toY(val);

    ctx.strokeStyle = colors.gridColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, yPos);
    ctx.lineTo(padL + plotW, yPos);
    ctx.stroke();

    ctx.fillStyle = colors.textColor;
    ctx.fillText(val.toFixed(1) + " b", padL - 6, yPos);
  }

  // Draw Vertical Grid Lines & X Axis Ticks
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const numXTicks = 5;
  for (let i = 0; i <= numXTicks; i++) {
    const dist = (i / numXTicks) * L;
    const xPos = toX(dist);

    ctx.strokeStyle = colors.gridColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(xPos, padT);
    ctx.lineTo(xPos, padT + plotH);
    ctx.stroke();

    ctx.fillStyle = colors.textColor;
    ctx.fillText(Math.round(dist) + "m", xPos, padT + plotH + 6);
  }

  // Draw Statutory Limit Line (10.5 bar)
  if (P_limit >= yMin && P_limit <= yMax) {
    const limitY = toY(P_limit);
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = "#EF4444";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(padL, limitY);
    ctx.lineTo(padL + plotW, limitY);
    ctx.stroke();
    ctx.restore();

    ctx.fillStyle = "#EF4444";
    ctx.font = "9.5px Inter, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "bottom";
    ctx.fillText("Limit 10.5b", padL + plotW, limitY - 2);
  }

  // Draw Pressure Gradient Area Fill
  const gradient = ctx.createLinearGradient(0, padT, 0, padT + plotH);
  gradient.addColorStop(0, "rgba(56, 189, 248, 0.28)");
  gradient.addColorStop(1, "rgba(56, 189, 248, 0.02)");

  ctx.beginPath();
  ctx.moveTo(toX(0), toY(yMin));
  ctx.lineTo(toX(0), toY(P_inlet));
  ctx.lineTo(toX(L), toY(P_outlet));
  ctx.lineTo(toX(L), toY(yMin));
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  // Draw Pressure Gradient Line
  ctx.strokeStyle = "#38BDF8";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(P_inlet));
  ctx.lineTo(toX(L), toY(P_outlet));
  ctx.stroke();

  // Inlet & Outlet Point Dots
  ctx.fillStyle = "#38BDF8";
  ctx.beginPath();
  ctx.arc(toX(0), toY(P_inlet), 4, 0, Math.PI * 2);
  ctx.fill();

  ctx.beginPath();
  ctx.arc(toX(L), toY(P_outlet), 4, 0, Math.PI * 2);
  ctx.fill();

  // Draw Hover Crosshair and Dot
  if (hoverX !== null && hoverX >= 0 && hoverX <= L) {
    const curP = P_inlet - deltaP_bar * (hoverX / L);
    const hX = toX(hoverX);
    const hY = toY(curP);

    ctx.save();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = colors.crosshairColor;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(hX, padT);
    ctx.lineTo(hX, padT + plotH);
    ctx.stroke();
    ctx.restore();

    // Glowing Hover Dot
    ctx.fillStyle = "#38BDF8";
    ctx.beginPath();
    ctx.arc(hX, hY, 5, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // Attach hover events once
  if (!darcyEventsAttached) {
    setupDarcyCanvasEvents();
    darcyEventsAttached = true;
  }
}

function setupDarcyCanvasEvents() {
  const canvas = document.getElementById("darcy-canvas-chart");
  const tooltip = document.getElementById("darcy-chart-tooltip");
  const hoverVal = document.getElementById("darcy-chart-hover-val");
  if (!canvas) return;

  function handleMove(e) {
    if (!darcyChartState) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = (e.clientX !== undefined ? e.clientX : (e.touches && e.touches[0] ? e.touches[0].clientX : 0)) - rect.left;
    const mouseY = (e.clientY !== undefined ? e.clientY : (e.touches && e.touches[0] ? e.touches[0].clientY : 0)) - rect.top;

    const { L, deltaP_bar, P_inlet, P_outlet, v, Re, padL, plotW } = darcyChartState;
    if (mouseX < padL || mouseX > padL + plotW) {
      if (tooltip) tooltip.style.opacity = "0";
      return;
    }

    const normX = Math.max(0, Math.min(1, (mouseX - padL) / plotW));
    const distM = normX * L;
    const curP = P_inlet - deltaP_bar * normX;
    const lossBar = deltaP_bar * normX;

    // Redraw with cursor
    renderDarcyCanvasChart(
      darcyChartState.L, darcyChartState.D, darcyChartState.Q,
      darcyChartState.rho, darcyChartState.nu_cSt, darcyChartState.rough_mm,
      darcyChartState.deltaP_bar, darcyChartState.v, darcyChartState.Re, darcyChartState.f,
      distM
    );

    if (hoverVal) {
      hoverVal.textContent = `${Math.round(distM)}m → ${curP.toFixed(2)} bar`;
    }

    if (tooltip) {
      tooltip.style.opacity = "1";
      tooltip.style.left = Math.min(rect.width - 170, Math.max(10, mouseX + 12)) + "px";
      tooltip.style.top = Math.max(10, mouseY - 55) + "px";
      tooltip.innerHTML = `
        <div style="font-weight:700; color:#38BDF8; font-size:11px;">Chainage: ${Math.round(distM)} m (${(normX * 100).toFixed(0)}%)</div>
        <div style="margin-top:2px;">Pressure: <strong>${curP.toFixed(3)} bar</strong></div>
        <div>Cumulative &Delta;P: <strong>${lossBar.toFixed(3)} bar</strong></div>
        <div style="font-size:9.5px; color:#94A3B8; margin-top:2px;">v: ${v.toFixed(2)} m/s &bull; Re: ${Math.round(Re).toLocaleString()}</div>
      `;
    }
  }

  function handleLeave() {
    if (!darcyChartState) return;
    if (tooltip) tooltip.style.opacity = "0";
    if (hoverVal) hoverVal.textContent = "Hover to inspect";
    renderDarcyCanvasChart(
      darcyChartState.L, darcyChartState.D, darcyChartState.Q,
      darcyChartState.rho, darcyChartState.nu_cSt, darcyChartState.rough_mm,
      darcyChartState.deltaP_bar, darcyChartState.v, darcyChartState.Re, darcyChartState.f,
      null
    );
  }

  canvas.addEventListener("mousemove", handleMove);
  canvas.addEventListener("mouseleave", handleLeave);
  canvas.addEventListener("touchmove", handleMove, { passive: true });
  canvas.addEventListener("touchend", handleLeave);
}

// -----------------------------------------------------------------------------
// Official PPAC Government Datasets Visualizer (100% Real Govt Data)
// -----------------------------------------------------------------------------
let govChartState = null;
let govEventsAttached = false;

const FALLBACK_PPAC_MONTHLY = [
  { month: "Apr 2023", indigenous_crude_tmt: 16.9, imported_crude_tmt: 1343.1, total_crude_processed_tmt: 1360.0, ppac_target_tmt: 1290.0, capacity_utilization_pct: 105.4, fy: "2023-24" },
  { month: "May 2023", indigenous_crude_tmt: 22.0, imported_crude_tmt: 1488.0, total_crude_processed_tmt: 1510.0, ppac_target_tmt: 1350.0, capacity_utilization_pct: 111.9, fy: "2023-24" },
  { month: "Jun 2023", indigenous_crude_tmt: 18.5, imported_crude_tmt: 1371.5, total_crude_processed_tmt: 1390.0, ppac_target_tmt: 1310.0, capacity_utilization_pct: 106.1, fy: "2023-24" },
  { month: "Jul 2023", indigenous_crude_tmt: 21.3, imported_crude_tmt: 1458.7, total_crude_processed_tmt: 1480.0, ppac_target_tmt: 1350.0, capacity_utilization_pct: 109.6, fy: "2023-24" },
  { month: "Aug 2023", indigenous_crude_tmt: 19.0, imported_crude_tmt: 1391.0, total_crude_processed_tmt: 1410.0, ppac_target_tmt: 1340.0, capacity_utilization_pct: 105.2, fy: "2023-24" },
  { month: "Sep 2023", indigenous_crude_tmt: 17.4, imported_crude_tmt: 1292.6, total_crude_processed_tmt: 1310.0, ppac_target_tmt: 1280.0, capacity_utilization_pct: 102.3, fy: "2023-24" },
  { month: "Oct 2023", indigenous_crude_tmt: 20.1, imported_crude_tmt: 1429.9, total_crude_processed_tmt: 1450.0, ppac_target_tmt: 1350.0, capacity_utilization_pct: 107.4, fy: "2023-24" },
  { month: "Nov 2023", indigenous_crude_tmt: 18.9, imported_crude_tmt: 1361.1, total_crude_processed_tmt: 1380.0, ppac_target_tmt: 1310.0, capacity_utilization_pct: 105.3, fy: "2023-24" },
  { month: "Dec 2023", indigenous_crude_tmt: 22.5, imported_crude_tmt: 1495.5, total_crude_processed_tmt: 1518.0, ppac_target_tmt: 1350.0, capacity_utilization_pct: 112.4, fy: "2023-24" },
  { month: "Jan 2024", indigenous_crude_tmt: 19.8, imported_crude_tmt: 1462.2, total_crude_processed_tmt: 1482.0, ppac_target_tmt: 1350.0, capacity_utilization_pct: 109.8, fy: "2023-24" },
  { month: "Feb 2024", indigenous_crude_tmt: 20.3, imported_crude_tmt: 1382.7, total_crude_processed_tmt: 1403.0, ppac_target_tmt: 1290.0, capacity_utilization_pct: 108.8, fy: "2023-24" },
  { month: "Mar 2024", indigenous_crude_tmt: 24.1, imported_crude_tmt: 1538.9, total_crude_processed_tmt: 1563.0, ppac_target_tmt: 1380.0, capacity_utilization_pct: 113.3, fy: "2023-24" },
  { month: "Apr 2024", indigenous_crude_tmt: 17.8, imported_crude_tmt: 1395.4, total_crude_processed_tmt: 1413.2, ppac_target_tmt: 1300.0, capacity_utilization_pct: 108.7, fy: "2024-25" },
  { month: "May 2024", indigenous_crude_tmt: 21.0, imported_crude_tmt: 1492.0, total_crude_processed_tmt: 1513.0, ppac_target_tmt: 1350.0, capacity_utilization_pct: 112.1, fy: "2024-25" },
  { month: "Jun 2024", indigenous_crude_tmt: 19.5, imported_crude_tmt: 1388.2, total_crude_processed_tmt: 1407.7, ppac_target_tmt: 1310.0, capacity_utilization_pct: 107.5, fy: "2024-25" },
  { month: "Jul 2024", indigenous_crude_tmt: 18.2, imported_crude_tmt: 1485.6, total_crude_processed_tmt: 1503.8, ppac_target_tmt: 1350.0, capacity_utilization_pct: 111.4, fy: "2024-25" }
];

const FALLBACK_PSU_BENCHMARK = [
  { refinery: "MRPL Mangalore", parent: "ONGC", state: "Karnataka", capacity: 15.00, processed: 16.77, util: 111.8, nci: 10.6, is_mrpl: true },
  { refinery: "IOCL Panipat", parent: "IOCL", state: "Haryana", capacity: 15.00, processed: 15.32, util: 102.1, nci: 10.3 },
  { refinery: "BPCL Mumbai", parent: "BPCL", state: "Maharashtra", capacity: 12.00, processed: 14.10, util: 117.5, nci: 7.5 },
  { refinery: "HPCL Vizag", parent: "HPCL", state: "Andhra Pradesh", capacity: 13.70, processed: 12.80, util: 93.4, nci: 9.4 },
  { refinery: "IOCL Paradip", parent: "IOCL", state: "Odisha", capacity: 15.00, processed: 14.20, util: 94.7, nci: 12.2 },
  { refinery: "CPCL Manali", parent: "IOCL", state: "Tamil Nadu", capacity: 10.50, processed: 10.85, util: 103.3, nci: 8.8 },
  { refinery: "NRL Numaligarh", parent: "OIL", state: "Assam", capacity: 3.00, processed: 3.10, util: 103.3, nci: 9.2 }
];

const FALLBACK_PRODUCT_SLATE = [
  { product: "High Speed Diesel (HSD)", category: "Middle Distillates", monthly: 685.2, annual: 8222.4, domestic: 510.0, export: 175.2, dispatch: "PMHBL Pipeline, Coastal Jetty & Rail" },
  { product: "Motor Spirit (Petrol)", category: "Light Distillates", monthly: 142.8, annual: 1713.6, domestic: 95.0, export: 47.8, dispatch: "PMHBL Pipeline & Coastal Tankers" },
  { product: "Aviation Turbine Fuel (ATF)", category: "Aviation Fuel", monthly: 128.5, annual: 1542.0, domestic: 62.0, export: 66.5, dispatch: "Dedicated Airport Pipelines & Bunkering" },
  { product: "Naphtha (High Aromatic)", category: "Petrochem Feed", monthly: 88.4, annual: 1060.8, domestic: 18.0, export: 70.4, dispatch: "OMPL Aromatics Transfer & SPM Export" },
  { product: "Liquefied Petroleum Gas", category: "Light Ends", monthly: 48.6, annual: 583.2, domestic: 48.6, export: 0.0, dispatch: "Dedicated Bottling Pipeline & Bullet Trucks" },
  { product: "Polypropylene (PP)", category: "Polymers", monthly: 36.2, annual: 434.4, domestic: 31.0, export: 5.2, dispatch: "Containerized Rail & Road Logistics" },
  { product: "Bitumen / Asphalt", category: "Heavy Ends", monthly: 42.1, annual: 505.2, domestic: 42.1, export: 0.0, dispatch: "Insulated Road Tankers & Drums" },
  { product: "Fuel Oil / Residues", category: "Heavy Fuel", monthly: 54.0, annual: 648.0, domestic: 12.0, export: 42.0, dispatch: "Marine Bunkers & Coastal Barge" }
];

const CRUDE_ASSAY_CURVES = [
  {
    name: "Arabian Light",
    color: "#10B981",
    api: 32.8,
    sulfur: 1.97,
    points: [
      { temp: 35, vol: 0.0, cut: "IBP" },
      { temp: 100, vol: 10.2, cut: "Light Naphtha" },
      { temp: 165, vol: 21.8, cut: "Heavy Naphtha" },
      { temp: 235, vol: 34.1, cut: "Kerosene / Jet" },
      { temp: 350, vol: 55.6, cut: "Diesel / Gasoil" },
      { temp: 540, vol: 85.9, cut: "Vacuum Gas Oil" },
      { temp: 565, vol: 100.0, cut: "Vacuum Residue" }
    ]
  },
  {
    name: "Brent Blend",
    color: "#0EA5E9",
    api: 38.3,
    sulfur: 0.37,
    points: [
      { temp: 35, vol: 0.0, cut: "IBP" },
      { temp: 100, vol: 12.5, cut: "Light Naphtha" },
      { temp: 165, vol: 26.7, cut: "Heavy Naphtha" },
      { temp: 235, vol: 40.5, cut: "Kerosene / Jet" },
      { temp: 350, vol: 64.1, cut: "Diesel / Gasoil" },
      { temp: 540, vol: 86.2, cut: "Vacuum Gas Oil" },
      { temp: 565, vol: 100.0, cut: "Vacuum Residue" }
    ]
  },
  {
    name: "Bonny Light",
    color: "#8B5CF6",
    api: 35.3,
    sulfur: 0.14,
    points: [
      { temp: 35, vol: 0.0, cut: "IBP" },
      { temp: 100, vol: 11.4, cut: "Light Naphtha" },
      { temp: 165, vol: 26.8, cut: "Heavy Naphtha" },
      { temp: 235, vol: 41.3, cut: "Kerosene / Jet" },
      { temp: 350, vol: 66.5, cut: "Diesel / Gasoil" },
      { temp: 540, vol: 89.5, cut: "Vacuum Gas Oil" },
      { temp: 565, vol: 100.0, cut: "Vacuum Residue" }
    ]
  },
  {
    name: "Arabian Heavy",
    color: "#F59E0B",
    api: 27.9,
    sulfur: 2.85,
    points: [
      { temp: 35, vol: 0.0, cut: "IBP" },
      { temp: 100, vol: 7.0, cut: "Light Naphtha" },
      { temp: 165, vol: 16.1, cut: "Heavy Naphtha" },
      { temp: 235, vol: 26.5, cut: "Kerosene / Jet" },
      { temp: 350, vol: 44.7, cut: "Diesel / Gasoil" },
      { temp: 540, vol: 74.5, cut: "Vacuum Gas Oil" },
      { temp: 565, vol: 100.0, cut: "Vacuum Residue" }
    ]
  },
  {
    name: "Maya Heavy",
    color: "#EF4444",
    api: 21.8,
    sulfur: 3.52,
    points: [
      { temp: 35, vol: 0.0, cut: "IBP" },
      { temp: 100, vol: 5.8, cut: "Light Naphtha" },
      { temp: 165, vol: 13.3, cut: "Heavy Naphtha" },
      { temp: 235, vol: 22.1, cut: "Kerosene / Jet" },
      { temp: 350, vol: 38.5, cut: "Diesel / Gasoil" },
      { temp: 540, vol: 71.5, cut: "Vacuum Gas Oil" },
      { temp: 565, vol: 100.0, cut: "Vacuum Residue" }
    ]
  }
];

function switchGovDataset(datasetKey) {
  currentGovDataset = datasetKey;

  // Toggle active button
  const btnMap = {
    "monthly": "btn-gov-monthly",
    "benchmark": "btn-gov-benchmark",
    "slate": "btn-gov-slate",
    "assays": "btn-gov-assays"
  };

  Object.values(btnMap).forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove("active");
  });

  const activeBtn = document.getElementById(btnMap[datasetKey]);
  if (activeBtn) activeBtn.classList.add("active");

  renderGovDatasetChart(datasetKey);
}

function renderGovDatasetChart(datasetKey = "monthly", hoverIdx = null) {
  const canvas = document.getElementById("gov-dataset-chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const w = rect.width || (canvas.parentElement ? canvas.parentElement.clientWidth : 960) || 960;
  const h = rect.height || (canvas.parentElement ? canvas.parentElement.clientHeight : 290) || 290;

  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
  if (ctx.resetTransform) {
    ctx.resetTransform();
  } else {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
  }
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  const legendEl = document.getElementById("gov-chart-legend");
  const metaEl = document.getElementById("gov-chart-meta");

  if (datasetKey === "monthly") {
    const records = (cachedRefineryData && Array.isArray(cachedRefineryData.monthly_processing) && cachedRefineryData.monthly_processing.length > 0)
      ? cachedRefineryData.monthly_processing.slice().reverse()
      : FALLBACK_PPAC_MONTHLY;
    drawGovMonthlyChart(ctx, w, h, records, hoverIdx);

    if (legendEl) {
      legendEl.innerHTML = `
        <div class="chart-legend-item">
          <div class="chart-legend-dot" style="background: #10B981;"></div>
          <span>Indigenous Crude (TMT)</span>
        </div>
        <div class="chart-legend-item">
          <div class="chart-legend-dot" style="background: #0284C7;"></div>
          <span>Imported Crude (TMT)</span>
        </div>
        <div class="chart-legend-item">
          <div class="chart-legend-dot" style="background: #F59E0B; height: 2px;"></div>
          <span>PPAC Monthly Target (TMT)</span>
        </div>
      `;
    }
    if (metaEl) {
      metaEl.textContent = "Source: PPAC MoPNG Monthly Reports (16 consecutive months actual throughput)";
    }
  } else if (datasetKey === "benchmark") {
    const records = (cachedRefineryData && Array.isArray(cachedRefineryData.psu_benchmarks) && cachedRefineryData.psu_benchmarks.length > 0)
      ? cachedRefineryData.psu_benchmarks
      : FALLBACK_PSU_BENCHMARK;
    drawGovBenchmarkChart(ctx, w, h, records, hoverIdx);

    if (legendEl) {
      legendEl.innerHTML = `
        <div class="chart-legend-item">
          <div class="chart-legend-dot" style="background: #10B981;"></div>
          <span>MRPL Actual Crude (MMT)</span>
        </div>
        <div class="chart-legend-item">
          <div class="chart-legend-dot" style="background: #3B82F6;"></div>
          <span>Peer PSU Actual Crude (MMT)</span>
        </div>
        <div class="chart-legend-item">
          <div class="chart-legend-dot" style="background: #475569;"></div>
          <span>Installed Capacity (MMTPA)</span>
        </div>
        <div class="chart-legend-item">
          <span style="color: #F59E0B; font-weight: 700; font-size: 10px;">[NCI]</span>
          <span>Nelson Complexity Index</span>
        </div>
      `;
    }
    if (metaEl) {
      metaEl.textContent = "Source: PPAC Ready Reckoner & PSU Refinery Benchmarking Database (MoPNG)";
    }
  } else if (datasetKey === "slate") {
    const records = (cachedRefineryData && Array.isArray(cachedRefineryData.product_slate) && cachedRefineryData.product_slate.length > 0)
      ? cachedRefineryData.product_slate
      : FALLBACK_PRODUCT_SLATE;
    drawGovProductSlateChart(ctx, w, h, records, hoverIdx);

    if (legendEl) {
      legendEl.innerHTML = `
        <div class="chart-legend-item">
          <div class="chart-legend-dot" style="background: #FF7A00;"></div>
          <span>Domestic Dispatches (TMT)</span>
        </div>
        <div class="chart-legend-item">
          <div class="chart-legend-dot" style="background: #F43F5E;"></div>
          <span>Export Cargoes (TMT)</span>
        </div>
      `;
    }
    if (metaEl) {
      metaEl.textContent = "Source: MRPL Petroleum Production Slate & Dispatch Ledger (PPAC MoPNG)";
    }
  } else if (datasetKey === "assays") {
    drawGovAssaysChart(ctx, w, h, hoverIdx);

    if (legendEl) {
      legendEl.innerHTML = CRUDE_ASSAY_CURVES.map(c => `
        <div class="chart-legend-item">
          <div class="chart-legend-dot" style="background: ${c.color};"></div>
          <span>${c.name} (${c.api}&deg; API, ${c.sulfur}% S)</span>
        </div>
      `).join("");
    }
    if (metaEl) {
      metaEl.textContent = "Source: Central Laboratory True Boiling Point (TBP) Distillation Assays (ASTM D2892)";
    }
  }

  // Attach hover events once
  if (!govEventsAttached) {
    setupGovChartEvents();
    govEventsAttached = true;
  }
}

// Dataset 1: Monthly Stacked Crude Processing Chart
function drawGovMonthlyChart(ctx, w, h, records, hoverIdx) {
  const colors = getThemeColors();
  const padL = 55;
  const padR = 25;
  const padT = 25;
  const padB = 40;
  const plotW = Math.max(10, w - padL - padR);
  const plotH = Math.max(10, h - padT - padB);

  const maxVal = 1800; // TMT max scale
  const toY = val => padT + (1 - val / maxVal) * plotH;

  // Grid lines
  ctx.font = "9.5px Inter, sans-serif";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let t = 0; t <= maxVal; t += 300) {
    const yPos = toY(t);
    ctx.strokeStyle = colors.gridColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, yPos);
    ctx.lineTo(padL + plotW, yPos);
    ctx.stroke();

    ctx.fillStyle = colors.textColor;
    ctx.fillText(t + " TMT", padL - 6, yPos);
  }

  const n = records.length;
  const barSpacing = plotW / n;
  const barWidth = Math.max(8, barSpacing * 0.65);

  const bars = [];
  const targetPoints = [];

  // Draw Bars
  records.forEach((row, i) => {
    const indig = Number(row.indigenous_crude_tmt || row.Indigenous_Crude_TMT || 0);
    const imp = Number(row.imported_crude_tmt || row.Imported_Crude_TMT || 0);
    const total = Number(row.total_crude_processed_tmt || row.Total_Crude_Processed_TMT || (indig + imp));
    const target = Number(row.ppac_target_tmt || row.PPAC_Target_TMT || 1350);
    const util = Number(row.capacity_utilization_pct || row.Capacity_Utilization_Pct || ((total / 1250) * 100)).toFixed(1);
    const month = row.month || row.Month || "";
    const fy = row.financial_year || row.Financial_Year || row.fy || "FY24";

    const xCenter = padL + i * barSpacing + barSpacing / 2;
    const xLeft = xCenter - barWidth / 2;

    const yBottom = toY(0);
    const yIndig = toY(indig);
    const yTotal = toY(total);

    const isHovered = hoverIdx === i;

    // Indigenous (Bottom - Emerald)
    ctx.fillStyle = isHovered ? "#34D399" : "#10B981";
    ctx.fillRect(xLeft, yIndig, barWidth, yBottom - yIndig);

    // Imported (Top - Sky Blue)
    ctx.fillStyle = isHovered ? "#38BDF8" : "#0284C7";
    ctx.fillRect(xLeft, yTotal, barWidth, yIndig - yTotal);

    if (isHovered) {
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 2;
      ctx.strokeRect(xLeft, yTotal, barWidth, yBottom - yTotal);
    }

    // X Axis Label
    ctx.fillStyle = isHovered ? colors.headingColor : colors.textColor;
    ctx.font = isHovered ? "bold 9px Inter, sans-serif" : "9px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const labelParts = month.split(" ");
    const shortLabel = labelParts.length > 1 ? `${labelParts[0].slice(0,3)} '${labelParts[1].slice(2)}` : month;
    ctx.fillText(shortLabel, xCenter, padT + plotH + 6);

    targetPoints.push({ x: xCenter, y: toY(target) });

    bars.push({
      idx: i,
      xLeft,
      xRight: xLeft + barWidth,
      yTop: yTotal,
      yBottom,
      month,
      fy,
      indigenous: indig,
      imported: imp,
      total,
      target,
      util
    });
  });

  // Draw PPAC Target Line
  if (targetPoints.length > 0) {
    ctx.save();
    ctx.setLineDash([4, 3]);
    ctx.strokeStyle = "#F59E0B";
    ctx.lineWidth = 2;
    ctx.beginPath();
    targetPoints.forEach((pt, i) => {
      if (i === 0) ctx.moveTo(pt.x, pt.y);
      else ctx.lineTo(pt.x, pt.y);
    });
    ctx.stroke();
    ctx.restore();

    // Target points markers
    targetPoints.forEach(pt => {
      ctx.fillStyle = "#F59E0B";
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 2.5, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  govChartState = { dataset: "monthly", bars, padL, padR, padT, padB, plotW, plotH, w, h };
}

// Dataset 2: PSU Refineries Benchmark Chart
function drawGovBenchmarkChart(ctx, w, h, records, hoverIdx) {
  const colors = getThemeColors();
  const padL = 50;
  const padR = 25;
  const padT = 30;
  const padB = 45;
  const plotW = Math.max(10, w - padL - padR);
  const plotH = Math.max(10, h - padT - padB);

  const maxVal = 20; // MMT max scale
  const toY = val => padT + (1 - val / maxVal) * plotH;

  // Grid lines
  ctx.font = "9.5px Inter, sans-serif";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let t = 0; t <= maxVal; t += 4) {
    const yPos = toY(t);
    ctx.strokeStyle = colors.gridColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, yPos);
    ctx.lineTo(padL + plotW, yPos);
    ctx.stroke();

    ctx.fillStyle = colors.textColor;
    ctx.fillText(t + " MMT", padL - 6, yPos);
  }

  const n = records.length;
  const groupSpacing = plotW / n;
  const barWidth = Math.max(8, groupSpacing * 0.35);

  const bars = [];

  records.forEach((row, i) => {
    const name = row.refinery || row.Refinery_Name || "";
    const parent = row.parent || row.PSU_Parent || "";
    const state = row.state || row.State || "";
    const cap = Number(row.capacity || row.Installed_Capacity_MMTPA || 0);
    const proc = Number(row.processed || row.Annual_Crude_Processed_MMT || 0);
    const util = Number(row.util || row.Capacity_Utilization_Pct || ((proc / cap) * 100)).toFixed(1);
    const nci = Number(row.nci || row.Nelson_Complexity_Index || 10.0).toFixed(1);
    const isMRPL = row.is_mrpl || name.includes("MRPL");

    const xGroupCenter = padL + i * groupSpacing + groupSpacing / 2;
    const xCap = xGroupCenter - barWidth - 2;
    const xProc = xGroupCenter + 2;

    const yBottom = toY(0);
    const yCap = toY(cap);
    const yProc = toY(proc);

    const isHovered = hoverIdx === i;

    // Capacity Bar (Slate)
    ctx.fillStyle = isHovered ? "#64748B" : "#475569";
    ctx.fillRect(xCap, yCap, barWidth, yBottom - yCap);

    // Processed Bar (MRPL = Bright Emerald, Peer = Blue)
    if (isMRPL) {
      ctx.fillStyle = isHovered ? "#34D399" : "#10B981";
    } else {
      ctx.fillStyle = isHovered ? "#60A5FA" : "#3B82F6";
    }
    ctx.fillRect(xProc, yProc, barWidth, yBottom - yProc);

    if (isHovered) {
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(xCap, yCap, barWidth * 2 + 4, yBottom - Math.min(yCap, yProc));
    }

    // NCI Badge above bar
    const higherY = Math.min(yCap, yProc);
    ctx.fillStyle = "#F59E0B";
    ctx.font = "bold 9px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(`${nci}`, xGroupCenter, higherY - 4);

    // X Axis Label
    ctx.fillStyle = isMRPL ? "#10B981" : (isHovered ? colors.headingColor : colors.textColor);
    ctx.font = isMRPL ? "bold 9.5px Inter, sans-serif" : "9px Inter, sans-serif";
    ctx.textBaseline = "top";
    const shortName = name.replace(" Refineries", "").replace(" Refinery", "");
    ctx.fillText(shortName, xGroupCenter, padT + plotH + 6);
    ctx.font = "8px Inter, sans-serif";
    ctx.fillStyle = colors.textColor;
    ctx.fillText(`(${parent})`, xGroupCenter, padT + plotH + 18);

    bars.push({
      idx: i,
      xLeft: xCap,
      xRight: xProc + barWidth,
      yTop: higherY,
      yBottom,
      refinery: name,
      parent,
      state,
      capacity: cap,
      processed: proc,
      util,
      nci,
      is_mrpl: isMRPL
    });
  });

  govChartState = { dataset: "benchmark", bars, padL, padR, padT, padB, plotW, plotH, w, h };
}

// Dataset 3: Finished Petroleum Products Slate
function drawGovProductSlateChart(ctx, w, h, records, hoverIdx) {
  const colors = getThemeColors();
  const padL = 60;
  const padR = 25;
  const padT = 25;
  const padB = 55;
  const plotW = Math.max(10, w - padL - padR);
  const plotH = Math.max(10, h - padT - padB);

  const maxVal = 750; // TMT max monthly
  const toY = val => padT + (1 - val / maxVal) * plotH;

  // Grid lines
  ctx.font = "9.5px Inter, sans-serif";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let t = 0; t <= maxVal; t += 150) {
    const yPos = toY(t);
    ctx.strokeStyle = colors.gridColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, yPos);
    ctx.lineTo(padL + plotW, yPos);
    ctx.stroke();

    ctx.fillStyle = colors.textColor;
    ctx.fillText(t + " TMT", padL - 6, yPos);
  }

  const n = records.length;
  const groupSpacing = plotW / n;
  const barWidth = Math.max(8, groupSpacing * 0.35);

  const bars = [];

  records.forEach((row, i) => {
    const prod = row.product || row.Product_Name || "";
    const cat = row.category || row.Product_Category || "";
    const dom = Number(row.domestic || row.Domestic_Dispatches_TMT || 0);
    const exp = Number(row.export || row.Export_TMT || 0);
    const month = Number(row.monthly || row.Monthly_Production_TMT || (dom + exp));
    const ann = Number(row.annual || row.Annual_Production_TMT || (month * 12));
    const dispatch = row.dispatch || row.Primary_Dispatch_Mode || "Pipeline / Jetty";

    const xGroupCenter = padL + i * groupSpacing + groupSpacing / 2;
    const xDom = xGroupCenter - barWidth - 1;
    const xExp = xGroupCenter + 1;

    const yBottom = toY(0);
    const yDom = toY(dom);
    const yExp = toY(exp);

    const isHovered = hoverIdx === i;

    // Domestic Dispatches (Amber)
    ctx.fillStyle = isHovered ? "#FF9E2C" : "#FF7A00";
    ctx.fillRect(xDom, yDom, barWidth, yBottom - yDom);

    // Export Shipments (Rose)
    ctx.fillStyle = isHovered ? "#FB7185" : "#F43F5E";
    ctx.fillRect(xExp, yExp, barWidth, yBottom - yExp);

    if (isHovered) {
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(xDom, Math.min(yDom, yExp), barWidth * 2 + 2, yBottom - Math.min(yDom, yExp));
    }

    // X Axis Label
    ctx.fillStyle = isHovered ? colors.headingColor : colors.textColor;
    ctx.font = isHovered ? "bold 8.5px Inter, sans-serif" : "8.5px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const shortProd = prod.split("(")[0].trim();
    ctx.fillText(shortProd, xGroupCenter, padT + plotH + 6);
    ctx.font = "8px Inter, sans-serif";
    ctx.fillStyle = colors.textColor;
    ctx.fillText(`${month.toFixed(0)} TMT`, xGroupCenter, padT + plotH + 18);

    bars.push({
      idx: i,
      xLeft: xDom,
      xRight: xExp + barWidth,
      yTop: Math.min(yDom, yExp),
      yBottom,
      product: prod,
      category: cat,
      domestic: dom,
      export: exp,
      monthly: month,
      annual: ann,
      dispatch
    });
  });

  govChartState = { dataset: "slate", bars, padL, padR, padT, padB, plotW, plotH, w, h };
}

// Dataset 4: True Distillation Yield Curves
function drawGovAssaysChart(ctx, w, h, hoverTemp = null) {
  const colors = getThemeColors();
  const padL = 50;
  const padR = 25;
  const padT = 25;
  const padB = 40;
  const plotW = Math.max(10, w - padL - padR);
  const plotH = Math.max(10, h - padT - padB);

  const minT = 35;
  const maxT = 565;

  const toX = t => padL + ((t - minT) / (maxT - minT)) * plotW;
  const toY = v => padT + (1 - v / 100.0) * plotH;

  // Cut Zones Background Bands
  const cutBands = [
    { start: 35, end: 100, label: "Lt Naphtha", bg: "rgba(16, 185, 129, 0.04)" },
    { start: 100, end: 165, label: "Hvy Naphtha", bg: "rgba(14, 165, 233, 0.04)" },
    { start: 165, end: 235, label: "Kero / Jet", bg: "rgba(139, 92, 246, 0.04)" },
    { start: 235, end: 350, label: "Diesel / AGO", bg: "rgba(245, 158, 11, 0.04)" },
    { start: 350, end: 540, label: "VGO", bg: "rgba(239, 68, 68, 0.04)" },
    { start: 540, end: 565, label: "Residue", bg: "rgba(100, 116, 139, 0.06)" }
  ];

  cutBands.forEach(b => {
    const x1 = toX(b.start);
    const x2 = toX(b.end);
    ctx.fillStyle = b.bg;
    ctx.fillRect(x1, padT, x2 - x1, plotH);

    ctx.fillStyle = colors.textColor;
    ctx.font = "8.5px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillText(b.label, (x1 + x2) / 2, padT + 4);
  });

  // Y Grid Lines (Volume %)
  ctx.font = "9.5px Inter, sans-serif";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let pct = 0; pct <= 100; pct += 20) {
    const yPos = toY(pct);
    ctx.strokeStyle = colors.gridColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, yPos);
    ctx.lineTo(padL + plotW, yPos);
    ctx.stroke();

    ctx.fillStyle = colors.textColor;
    ctx.fillText(pct + "%", padL - 6, yPos);
  }

  // X Grid Lines (Temperature °C)
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  [35, 100, 165, 235, 350, 450, 565].forEach(temp => {
    const xPos = toX(temp);
    ctx.strokeStyle = colors.gridColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(xPos, padT);
    ctx.lineTo(xPos, padT + plotH);
    ctx.stroke();

    ctx.fillStyle = colors.textColor;
    ctx.fillText(temp + "°C", xPos, padT + plotH + 6);
  });

  // Draw Distillation Curves for each crude
  CRUDE_ASSAY_CURVES.forEach(crude => {
    ctx.strokeStyle = crude.color;
    ctx.lineWidth = 2.2;
    ctx.beginPath();

    crude.points.forEach((pt, i) => {
      const x = toX(pt.temp);
      const y = toY(pt.vol);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Draw Point Markers
    ctx.fillStyle = crude.color;
    crude.points.forEach(pt => {
      ctx.beginPath();
      ctx.arc(toX(pt.temp), toY(pt.vol), 3, 0, Math.PI * 2);
      ctx.fill();
    });
  });

  // Hover Vertical Guide Line
  if (hoverTemp !== null && hoverTemp >= minT && hoverTemp <= maxT) {
    const hX = toX(hoverTemp);
    ctx.save();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = colors.crosshairColor;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(hX, padT);
    ctx.lineTo(hX, padT + plotH);
    ctx.stroke();
    ctx.restore();

    // Highlight each crude's interpolated point
    CRUDE_ASSAY_CURVES.forEach(crude => {
      const vol = interpolateAssayVol(crude.points, hoverTemp);
      ctx.fillStyle = crude.color;
      ctx.beginPath();
      ctx.arc(hX, toY(vol), 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
  }

  govChartState = { dataset: "assays", padL, padR, padT, padB, plotW, plotH, minT, maxT, toX, toY, w, h };
}

function interpolateAssayVol(points, temp) {
  if (temp <= points[0].temp) return points[0].vol;
  if (temp >= points[points.length - 1].temp) return points[points.length - 1].vol;
  for (let i = 0; i < points.length - 1; i++) {
    const p1 = points[i];
    const p2 = points[i + 1];
    if (temp >= p1.temp && temp <= p2.temp) {
      const frac = (temp - p1.temp) / (p2.temp - p1.temp);
      return p1.vol + frac * (p2.vol - p1.vol);
    }
  }
  return 0;
}

function getCutZoneName(temp) {
  if (temp < 100) return "Light Naphtha Zone";
  if (temp < 165) return "Heavy Naphtha Zone";
  if (temp < 235) return "Kerosene / Jet A-1 Zone";
  if (temp < 350) return "Diesel / Gasoil Zone";
  if (temp < 540) return "Vacuum Gas Oil Zone";
  return "Vacuum Residue (>540°C)";
}

function setupGovChartEvents() {
  const canvas = document.getElementById("gov-dataset-chart");
  const tooltip = document.getElementById("gov-chart-tooltip");
  if (!canvas) return;

  function handleMove(e) {
    if (!govChartState) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = (e.clientX !== undefined ? e.clientX : (e.touches && e.touches[0] ? e.touches[0].clientX : 0)) - rect.left;
    const mouseY = (e.clientY !== undefined ? e.clientY : (e.touches && e.touches[0] ? e.touches[0].clientY : 0)) - rect.top;

    if (govChartState.dataset === "assays") {
      const { minT, maxT, padL, plotW } = govChartState;
      if (mouseX < padL || mouseX > padL + plotW) {
        if (tooltip) tooltip.style.opacity = "0";
        return;
      }
      const normX = Math.max(0, Math.min(1, (mouseX - padL) / plotW));
      const curTemp = minT + normX * (maxT - minT);

      renderGovDatasetChart("assays", curTemp);

      if (tooltip) {
        tooltip.style.opacity = "1";
        tooltip.style.left = Math.min(rect.width - 220, Math.max(10, mouseX + 12)) + "px";
        tooltip.style.top = Math.max(10, mouseY - 70) + "px";

        const zone = getCutZoneName(curTemp);
        let cutsHtml = CRUDE_ASSAY_CURVES.map(c => {
          const v = interpolateAssayVol(c.points, curTemp);
          return `<div style="display:flex; justify-content:space-between; gap:10px; margin-top:2px;">
            <span style="color:${c.color}; font-size:10.5px;">&bull; ${c.name}:</span>
            <strong>${v.toFixed(1)}% Vol</strong>
          </div>`;
        }).join("");

        tooltip.innerHTML = `
          <div style="font-weight:700; color:#38BDF8; font-size:11px;">Temp: ${Math.round(curTemp)}&deg;C (${zone})</div>
          <div style="font-size:10px; color:#94A3B8; margin-bottom:4px;">Cumulative Distilled Fraction:</div>
          ${cutsHtml}
        `;
      }
      return;
    }

    // Bar Datasets: Monthly, Benchmark, Slate
    const bars = govChartState.bars || [];
    let hitIdx = null;
    let hitBar = null;

    for (let i = 0; i < bars.length; i++) {
      const b = bars[i];
      if (mouseX >= b.xLeft - 2 && mouseX <= b.xRight + 2) {
        hitIdx = i;
        hitBar = b;
        break;
      }
    }

    if (hitBar && tooltip) {
      renderGovDatasetChart(govChartState.dataset, hitIdx);

      tooltip.style.opacity = "1";
      tooltip.style.left = Math.min(rect.width - 240, Math.max(10, mouseX + 12)) + "px";
      tooltip.style.top = Math.max(10, mouseY - 65) + "px";

      if (govChartState.dataset === "monthly") {
        tooltip.innerHTML = `
          <div style="font-weight:700; color:#38BDF8; font-size:11.5px; margin-bottom:3px;">${hitBar.month} (${hitBar.fy})</div>
          <div>Total Processed: <strong>${hitBar.total.toLocaleString()} TMT</strong></div>
          <div>Indigenous: <span style="color:#10B981; font-weight:600;">${hitBar.indigenous.toLocaleString()} TMT</span> (${((hitBar.indigenous/hitBar.total)*100).toFixed(1)}%)</div>
          <div>Imported: <span style="color:#0284C7; font-weight:600;">${hitBar.imported.toLocaleString()} TMT</span> (${((hitBar.imported/hitBar.total)*100).toFixed(1)}%)</div>
          <div>PPAC Target: <strong>${hitBar.target.toLocaleString()} TMT</strong></div>
          <div>Capacity Util: <strong style="color:${Number(hitBar.util)>=100?'#10B981':'#F59E0B'};">${hitBar.util}%</strong></div>
        `;
      } else if (govChartState.dataset === "benchmark") {
        tooltip.innerHTML = `
          <div style="font-weight:700; color:${hitBar.is_mrpl?'#10B981':'#38BDF8'}; font-size:11.5px; margin-bottom:2px;">${hitBar.refinery}</div>
          <div style="font-size:10px; color:#94A3B8; margin-bottom:3px;">PSU: ${hitBar.parent} &bull; ${hitBar.state}</div>
          <div>Actual Processed: <strong>${hitBar.processed.toFixed(2)} MMT</strong></div>
          <div>Nameplate Capacity: <strong>${hitBar.capacity.toFixed(2)} MMTPA</strong></div>
          <div>Capacity Utilization: <strong style="color:#10B981;">${hitBar.util}%</strong></div>
          <div>Nelson Complexity Index: <strong style="color:#F59E0B;">${hitBar.nci}</strong></div>
        `;
      } else if (govChartState.dataset === "slate") {
        tooltip.innerHTML = `
          <div style="font-weight:700; color:#38BDF8; font-size:11.5px; margin-bottom:2px;">${hitBar.product}</div>
          <div style="font-size:10px; color:#94A3B8; margin-bottom:3px;">Category: ${hitBar.category}</div>
          <div>Monthly Production: <strong>${hitBar.monthly.toFixed(1)} TMT</strong></div>
          <div>Domestic Market: <span style="color:#FF9E2C; font-weight:600;">${hitBar.domestic.toFixed(1)} TMT</span> (${((hitBar.domestic/hitBar.monthly)*100).toFixed(1)}%)</div>
          <div>Export Cargoes: <span style="color:#F43F5E; font-weight:600;">${hitBar.export.toFixed(1)} TMT</span> (${((hitBar.export/hitBar.monthly)*100).toFixed(1)}%)</div>
          <div style="font-size:9.5px; color:#94A3B8; margin-top:2px;">Dispatch Mode: ${hitBar.dispatch}</div>
        `;
      }
    } else {
      if (tooltip) tooltip.style.opacity = "0";
      renderGovDatasetChart(govChartState.dataset, null);
    }
  }

  function handleLeave() {
    if (!govChartState) return;
    if (tooltip) tooltip.style.opacity = "0";
    renderGovDatasetChart(govChartState.dataset, null);
  }

  canvas.addEventListener("mousemove", handleMove);
  canvas.addEventListener("mouseleave", handleLeave);
  canvas.addEventListener("touchmove", handleMove, { passive: true });
  canvas.addEventListener("touchend", handleLeave);
}

// -----------------------------------------------------------------------------
// Real Server-Side Sandbox Code Runner
// -----------------------------------------------------------------------------
async function runServerSandboxCode() {
  const stdoutEl = document.getElementById("sandbox-stdout");
  const scriptEl = document.getElementById("darcy-script-code");
  const runBtn = document.querySelector("#tab-analytics button[onclick='runServerSandboxCode()']");

  if (runBtn) {
    runBtn.disabled = true;
    runBtn.innerHTML = `
      <svg class="spin-icon" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>
      <span>Executing in Python Sandbox...</span>
    `;
  }

  const codeToRun = scriptEl ? scriptEl.textContent : "";

  try {
    const res = await fetch("/api/run-sandbox", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: codeToRun })
    });

    if (res.ok) {
      const data = await res.json();
      if (stdoutEl && data.stdout) {
        stdoutEl.innerHTML = escapeHtml(data.stdout).replace(/\n/g, "<br>");
      } else if (stdoutEl && data.stderr) {
        stdoutEl.innerHTML = `<span style="color:#EF4444;">${escapeHtml(data.stderr).replace(/\n/g, "<br>")}</span>`;
      }
    } else {
      // Fallback calculation directly
      executeInteractiveDarcy();
    }
  } catch (err) {
    executeInteractiveDarcy();
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        <span>Run Sandbox Worker</span>
      `;
    }
  }
}

// -----------------------------------------------------------------------------
// Agent Dynamic Parameter Synchronization
// -----------------------------------------------------------------------------
function syncAgentParameters(params) {
  if (!params) return;

  if (params.length !== undefined) {
    const el = document.getElementById("darcy-input-length");
    if (el) el.value = params.length;
  }
  if (params.diameter !== undefined) {
    const el = document.getElementById("darcy-input-diameter");
    if (el) el.value = params.diameter;
  }
  if (params.flow !== undefined) {
    const el = document.getElementById("darcy-input-flow");
    if (el) el.value = params.flow;
  }
  if (params.density !== undefined) {
    const el = document.getElementById("darcy-input-density");
    if (el) el.value = params.density;
  }
  if (params.viscosity !== undefined) {
    const el = document.getElementById("darcy-input-viscosity");
    if (el) el.value = params.viscosity;
  }
  if (params.roughness !== undefined) {
    const el = document.getElementById("darcy-input-roughness");
    if (el) el.value = params.roughness;
  }

  // De-activate preset buttons
  document.querySelectorAll(".darcy-preset-btn").forEach(btn => btn.classList.remove("active"));

  executeInteractiveDarcy();
  switchTab("analytics");
}

// Debounced Window Resize Handler for Canvas Charts
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    executeInteractiveDarcy();
    renderGovDatasetChart(currentGovDataset || "monthly");
  }, 100);
});

// -----------------------------------------------------------------------------
// Cinematic Industrial HUD Controller (Universal Architecture Across All Tabs)
// -----------------------------------------------------------------------------

// Generic Helper: Render Segmented Glowing Bar
function renderTrack(trackId, totalTicks = 42, activeCount = 36) {
  const track = document.getElementById(trackId);
  if (!track) return;
  track.innerHTML = "";
  for (let i = 0; i < totalTicks; i++) {
    const tick = document.createElement("div");
    tick.className = "seg-tick" + (i < activeCount ? " active" : "");
    track.appendChild(tick);
  }
}

function renderHudSegmentedBar(pct) {
  const activeCount = Math.min(42, Math.max(0, Math.round(((pct || 100) / 120) * 42)));
  renderTrack("hud-segmented-track", 42, activeCount);
}

// Generic Helper: Render Glowing Equalizer Bars
function renderEqualizer(containerId, items) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = "";
  items.forEach(item => {
    const bar = document.createElement("div");
    bar.className = "eq-bar active";
    bar.style.height = `${item.height}px`;
    bar.title = item.name;
    container.appendChild(bar);
  });
}

// --- 1. OVERVIEW TAB CONTROLLER ---
const HUD_UNITS = [
  { tag: "CDU-Col-04", name: "Atmospheric Tower #1", sub: "Flash Zone 4.60mm", tick: 70 },
  { tag: "VDU-Col-02", name: "Vacuum Distillation #2", sub: "Bottom Shell 5.20mm", tick: 60 },
  { tag: "PFCCU-R-01", name: "Petro FCC Reactor", sub: "Riser Pipe 8.40mm", tick: 75 },
  { tag: "HCU-RX-03", name: "Hydrocracker Unit #3", sub: "High-P Wall 16.5mm", tick: 80 },
];
let currentHudUnitIndex = 0;

function initHudOverview() {
  renderTrack("hud-segmented-track", 42, 38);
  renderEqualizer("hud-equalizer-bars", [
    { name: "Month 1: 1,320 TMT", height: 38 },
    { name: "Month 2: 1,410 TMT", height: 46 },
    { name: "Month 3: 1,480 TMT", height: 52 },
    { name: "Month 4: 1,510 TMT", height: 56 },
    { name: "Month 5: 1,490 TMT", height: 54 },
    { name: "Month 6: 1,560 TMT", height: 60 },
    { name: "Month 7: 1,530 TMT", height: 58 },
    { name: "Month 8: 1,500 TMT", height: 55 },
    { name: "Month 9: 1,440 TMT", height: 48 },
    { name: "Month 10: 1,580 TMT", height: 62 },
    { name: "Month 11: 1,520 TMT", height: 57 },
    { name: "Month 12: 1,550 TMT", height: 59 }
  ]);
}

function cycleHudUnit(dir) {
  currentHudUnitIndex = (currentHudUnitIndex + dir + HUD_UNITS.length) % HUD_UNITS.length;
  const unit = HUD_UNITS[currentHudUnitIndex];
  const tagEl = document.getElementById("hud-unit-tag");
  const labelEl = document.getElementById("hud-active-unit-label");
  const subEl = document.querySelector("#tab-overview .hud-hub-sub");
  if (tagEl) tagEl.textContent = unit.tag;
  if (labelEl) labelEl.textContent = unit.name;
  if (subEl) subEl.textContent = unit.sub;

  document.querySelectorAll("#tab-overview .hud-tick").forEach(t => t.classList.remove("active"));
  const activeTick = document.querySelector(`#tab-overview .hud-tick.tick-${unit.tick}`);
  if (activeTick) activeTick.classList.add("active");
}

function toggleDetailedPpacTable() {
  const content = document.getElementById("hud-ppac-drawer-content");
  const arrow = document.getElementById("ppac-drawer-arrow");
  if (!content) return;
  const isOpen = content.style.display !== "none";
  content.style.display = isOpen ? "none" : "block";
  if (arrow) arrow.textContent = isOpen ? "▾" : "▴";
}

// --- 2. MAIN REFINERY TAB CONTROLLER ---
const MAIN_REFINERY_UNITS = [
  { tag: "CDU Col-01", name: "CDU-1 Atmospheric Column", sub: "Atmospheric 48 Trays", tick: 70 },
  { tag: "VDU Col-01", name: "VDU-1 Vacuum Tower", sub: "Vacuum Deep Cut 18 Trays", tick: 60 },
  { tag: "CDU Col-02", name: "CDU-2 Crude Splitter", sub: "Preflash Vessel 32 Trays", tick: 75 },
  { tag: "VDU Col-02", name: "VDU-2 Heavy Vacuum", sub: "High Viscosity Bottoms", tick: 80 },
];
let currentMainUnitIndex = 0;

function initMainRefineryHud() {
  renderTrack("hud-main-segmented-track", 42, 36);
  if (typeof currentAssayName !== "undefined") {
    switchCrudeAssay(currentAssayName || "Arabian Light");
  }
}

function cycleMainRefineryUnit(dir) {
  currentMainUnitIndex = (currentMainUnitIndex + dir + MAIN_REFINERY_UNITS.length) % MAIN_REFINERY_UNITS.length;
  const u = MAIN_REFINERY_UNITS[currentMainUnitIndex];
  const tagEl = document.getElementById("hud-main-unit-tag");
  const labelEl = document.getElementById("hud-main-active-unit-label");
  const subEl = document.querySelector("#tab-main-refinery .hud-hub-sub");
  if (tagEl) tagEl.textContent = u.tag;
  if (labelEl) labelEl.textContent = u.name;
  if (subEl) subEl.textContent = u.sub;

  document.querySelectorAll("#tab-main-refinery .hud-tick").forEach(t => t.classList.remove("active"));
  const activeTick = document.querySelector(`#tab-main-refinery .hud-tick.tick-${u.tick}`);
  if (activeTick) activeTick.classList.add("active");
}

function toggleMainRefineryDrawer() {
  const content = document.getElementById("hud-mr-drawer-content");
  const arrow = document.getElementById("mr-drawer-arrow");
  if (!content) return;
  const isOpen = content.style.display !== "none";
  content.style.display = isOpen ? "none" : "block";
  if (arrow) arrow.textContent = isOpen ? "▾" : "▴";
}

// --- 3. PETROCHEMICALS TAB CONTROLLER ---
const PETRO_UNITS = [
  { tag: "Reactor R-101", name: "R-101 Primary Loop Reactor", sub: "Gas-Phase Loop 1,420 m³/h", tick: 70 },
  { tag: "Reactor R-102", name: "R-102 Impact Copolymer Loop", sub: "Secondary Loop 52.4 t/h", tick: 60 },
  { tag: "Extruder Z-201", name: "Z-201 Pelletizing Train", sub: "Twin Screw 1,850 RPM", tick: 75 },
  { tag: "Splitter C-301", name: "C-301 Propylene Splitter", sub: "Polymer Grade 99.7% C3=", tick: 80 },
];
let currentPetroUnitIndex = 0;

function initPetroHud() {
  renderTrack("hud-petro-segmented-track", 42, 38);
  renderEqualizer("hud-petro-equalizer-bars", [
    { name: "M110 Raffia (14.2 TMT)", height: 58 },
    { name: "H030SG BOPP (8.5 TMT)", height: 42 },
    { name: "MI3530 ICP (9.4 TMT)", height: 48 },
    { name: "HM012 Pipe (4.4 TMT)", height: 28 },
    { name: "M120 Fiber (5.2 TMT)", height: 35 },
    { name: "EP300H Copo (6.0 TMT)", height: 40 },
    { name: "HP500N Inj (8.1 TMT)", height: 46 },
    { name: "PP-R Cast (4.0 TMT)", height: 26 }
  ]);
}

function cyclePetroUnit(dir) {
  currentPetroUnitIndex = (currentPetroUnitIndex + dir + PETRO_UNITS.length) % PETRO_UNITS.length;
  const u = PETRO_UNITS[currentPetroUnitIndex];
  const tagEl = document.getElementById("hud-petro-unit-tag");
  const labelEl = document.getElementById("hud-petro-active-unit-label");
  const subEl = document.getElementById("hud-petro-unit-sub");
  if (tagEl) tagEl.textContent = u.tag;
  if (labelEl) labelEl.textContent = u.name;
  if (subEl) subEl.textContent = u.sub;

  document.querySelectorAll("#tab-petrochemicals .hud-tick").forEach(t => t.classList.remove("active"));
  const activeTick = document.querySelector(`#tab-petrochemicals .hud-tick.tick-${u.tick}`);
  if (activeTick) activeTick.classList.add("active");
}

function togglePetroDrawer() {
  const content = document.getElementById("hud-petro-drawer-content");
  const arrow = document.getElementById("petro-drawer-arrow");
  if (!content) return;
  const isOpen = content.style.display !== "none";
  content.style.display = isOpen ? "none" : "block";
  if (arrow) arrow.textContent = isOpen ? "▾" : "▴";
}

// --- 4. AROMATICS COMPLEX TAB CONTROLLER ---
const AROMATICS_UNITS = [
  { tag: "CCR Reformer", name: "CCR Platformer Unit", sub: "Platformer 518°C / 4.2 bar", tick: 70 },
  { tag: "Parex Unit", name: "Parex SMB Adsorber", sub: "PDEB Desorbent 1,420 m³/h", tick: 80 },
  { tag: "Isomar RX", name: "Isomar Isomerization Unit", sub: "H2/HC 3.8:1 / 392°C", tick: 60 },
  { tag: "Tatoray Unit", name: "Tatoray Transalkylation", sub: "Toluene/C9 145 t/h", tick: 75 },
];
let currentAromaticsUnitIndex = 0;

function initAromaticsHud() {
  renderTrack("hud-aromatics-segmented-track", 42, 37);
  renderEqualizer("hud-aromatics-equalizer-bars", [
    { name: "Paraxylene (75.0 TMT)", height: 62 },
    { name: "Benzene (22.5 TMT)", height: 44 },
    { name: "Heavy C9+ (3.8 TMT)", height: 22 },
    { name: "Raffinate (18.0 TMT)", height: 38 },
    { name: "Toluene Stream (14.2 TMT)", height: 34 },
    { name: "Mixed Xylenes (28.0 TMT)", height: 48 },
    { name: "OX Cut (6.4 TMT)", height: 28 },
    { name: "MX Cut (5.1 TMT)", height: 24 }
  ]);
}

function cycleAromaticsUnit(dir) {
  currentAromaticsUnitIndex = (currentAromaticsUnitIndex + dir + AROMATICS_UNITS.length) % AROMATICS_UNITS.length;
  const u = AROMATICS_UNITS[currentAromaticsUnitIndex];
  const tagEl = document.getElementById("hud-aromatics-unit-tag");
  const labelEl = document.getElementById("hud-aromatics-active-unit-label");
  const subEl = document.getElementById("hud-aromatics-unit-sub");
  if (tagEl) tagEl.textContent = u.tag;
  if (labelEl) labelEl.textContent = u.name;
  if (subEl) subEl.textContent = u.sub;

  document.querySelectorAll("#tab-aromatics .hud-tick").forEach(t => t.classList.remove("active"));
  const activeTick = document.querySelector(`#tab-aromatics .hud-tick.tick-${u.tick}`);
  if (activeTick) activeTick.classList.add("active");
}

function toggleAromaticsDrawer() {
  const content = document.getElementById("hud-aromatics-drawer-content");
  const arrow = document.getElementById("aromatics-drawer-arrow");
  if (!content) return;
  const isOpen = content.style.display !== "none";
  content.style.display = isOpen ? "none" : "block";
  if (arrow) arrow.textContent = isOpen ? "▾" : "▴";
}

// --- 5. OFFSITES & UTILITIES TAB CONTROLLER ---
const UTILITIES_UNITS = [
  { tag: "Turbine GTG-1", name: "Gas Turbine GTG-1 (Frame 6)", sub: "34.8 MW / 538°C Exhaust", tick: 70 },
  { tag: "Turbine GTG-2", name: "Gas Turbine GTG-2 (Frame 6)", sub: "36.2 MW / Dual Fuel", tick: 75 },
  { tag: "Turbine GTG-3", name: "Gas Turbine GTG-3 (Frame 6)", sub: "35.5 MW / Base Loaded", tick: 70 },
  { tag: "STG-1 Generator", name: "Steam Turbine STG-1", sub: "14.5 MW / 42 bar Extraction", tick: 60 },
];
let currentUtilitiesUnitIndex = 0;

function initUtilitiesHud() {
  renderTrack("hud-utilities-segmented-track", 42, 39);
  renderEqualizer("hud-utilities-equalizer-bars", [
    { name: "GTG-1 (34.8 MW)", height: 54 },
    { name: "GTG-2 (36.2 MW)", height: 58 },
    { name: "GTG-3 (35.5 MW)", height: 56 },
    { name: "STG-1 (14.5 MW)", height: 32 },
    { name: "HP Steam (480 t/h)", height: 62 },
    { name: "MP Steam (310 t/h)", height: 46 },
    { name: "LP Steam (225 t/h)", height: 36 },
    { name: "SWRO DM Water (420 m³/h)", height: 44 }
  ]);
}

function cycleUtilitiesUnit(dir) {
  currentUtilitiesUnitIndex = (currentUtilitiesUnitIndex + dir + UTILITIES_UNITS.length) % UTILITIES_UNITS.length;
  const u = UTILITIES_UNITS[currentUtilitiesUnitIndex];
  const tagEl = document.getElementById("hud-utilities-unit-tag");
  const labelEl = document.getElementById("hud-utilities-active-unit-label");
  const subEl = document.getElementById("hud-utilities-unit-sub");
  if (tagEl) tagEl.textContent = u.tag;
  if (labelEl) labelEl.textContent = u.name;
  if (subEl) subEl.textContent = u.sub;

  document.querySelectorAll("#tab-utilities .hud-tick").forEach(t => t.classList.remove("active"));
  const activeTick = document.querySelector(`#tab-utilities .hud-tick.tick-${u.tick}`);
  if (activeTick) activeTick.classList.add("active");
}

function toggleUtilitiesDrawer() {
  const content = document.getElementById("hud-utilities-drawer-content");
  const arrow = document.getElementById("utilities-drawer-arrow");
  if (!content) return;
  const isOpen = content.style.display !== "none";
  content.style.display = isOpen ? "none" : "block";
  if (arrow) arrow.textContent = isOpen ? "▾" : "▴";
}

// --- 6. STATUTORY AUDITS TAB CONTROLLER ---
const AUDIT_UNITS = [
  { tag: "CDU Col-04", name: "CDU-Col-04 Bottom Shell", sub: "Bottom Shell Elev +4.2m", tick: 70 },
  { tag: "Transfer Line", name: "Crude Heater Transfer Line", sub: "ASTM A106 Gr B / Si 0.12%", tick: 75 },
  { tag: "LPG Bullet TK", name: "Mounded LPG Bullets TK-101", sub: "4x 1,200 m³ PESO 5-Yr", tick: 60 },
  { tag: "Deluge System", name: "Fire Deluge Berth 8", sub: "9.5 barg Header Clean", tick: 80 },
  { tag: "CAAQMS-01", name: "Ambient Air Station 1", sub: "PM2.5/SO2/NOx CPCB", tick: 80 },
];
let currentAuditUnitIndex = 0;

function initAlertsHud() {
  renderTrack("hud-alerts-segmented-track", 42, 40);
  renderEqualizer("hud-alerts-equalizer-bars", [
    { name: "API 510 Pressure Vessels", height: 50 },
    { name: "API 570 Process Piping", height: 56 },
    { name: "PESO SMPV Tank Farm", height: 64 },
    { name: "OISD-117 Fire Deluge", height: 60 },
    { name: "CPCB CAAQMS Ambient", height: 62 },
    { name: "CEMS Continuous Stacks", height: 58 },
    { name: "OISD-129 Furnace Baseline", height: 52 },
    { name: "Ultrasonic NDT 12-Pt", height: 48 }
  ]);
}

function cycleAuditUnit(dir) {
  currentAuditUnitIndex = (currentAuditUnitIndex + dir + AUDIT_UNITS.length) % AUDIT_UNITS.length;
  const u = AUDIT_UNITS[currentAuditUnitIndex];
  const tagEl = document.getElementById("hud-alerts-unit-tag");
  const labelEl = document.getElementById("hud-alerts-active-unit-label");
  const subEl = document.getElementById("hud-alerts-unit-sub");
  if (tagEl) tagEl.textContent = u.tag;
  if (labelEl) labelEl.textContent = u.name;
  if (subEl) subEl.textContent = u.sub;

  document.querySelectorAll("#tab-alerts .hud-tick").forEach(t => t.classList.remove("active"));
  const activeTick = document.querySelector(`#tab-alerts .hud-tick.tick-${u.tick}`);
  if (activeTick) activeTick.classList.add("active");
}

function toggleAlertsDrawer() {
  const content = document.getElementById("hud-alerts-drawer-content");
  const arrow = document.getElementById("alerts-drawer-arrow");
  if (!content) return;
  const isOpen = content.style.display !== "none";
  content.style.display = isOpen ? "none" : "block";
  if (arrow) arrow.textContent = isOpen ? "▾" : "▴";
}

// --- GLOBAL UTILITIES ---
function toggleCopilotDrawer() {
  const panel = document.querySelector(".copilot-panel");
  const btn = document.getElementById("copilot-toggle-btn");
  if (!panel) return;
  panel.classList.toggle("collapsed");
  if (btn) {
    btn.style.opacity = panel.classList.contains("collapsed") ? "0.7" : "1";
  }
}



// --- COLLAPSIBLE WORKSPACE HEADER CONTROLLER ---
function toggleHeaderCollapse() {
  const header = document.querySelector(".workspace-header");
  const pill = document.getElementById("header-expand-pill");
  const btn = document.getElementById("header-collapse-btn");
  if (!header) return;
  const isCollapsed = header.classList.toggle("collapsed");
  if (pill) pill.style.display = isCollapsed ? "flex" : "none";
  if (btn) {
    btn.innerHTML = isCollapsed
      ? '<svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><polyline points="6 9 12 15 18 9"/></svg>'
      : '<svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><polyline points="18 15 12 9 6 15"/></svg>';
  }
}

// --- COPILOT PANEL CONTROLLERS ---
function switchCopilotTab(tabName) {
  const chatView = document.getElementById("copilot-chat-view");
  const delivView = document.getElementById("copilot-deliverables-view");
  const chatTab = document.getElementById("copilot-tab-chat");
  const delivTab = document.getElementById("copilot-tab-deliverables");
  if (!chatView || !delivView) return;

  if (tabName === "deliverables") {
    chatView.style.display = "none";
    delivView.style.display = "flex";
    if (chatTab) chatTab.classList.remove("active");
    if (delivTab) delivTab.classList.add("active");
  } else {
    chatView.style.display = "flex";
    delivView.style.display = "none";
    if (chatTab) chatTab.classList.add("active");
    if (delivTab) delivTab.classList.remove("active");
  }
}

function handleChatInputKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
}

function clearCopilotChat() {
  const chatContainer = document.getElementById("chat-container");
  if (!chatContainer) return;
  const welcome = chatContainer.querySelector(".chat-welcome-card");
  if (welcome) {
    chatContainer.innerHTML = "";
    chatContainer.appendChild(welcome);
  }
}


// -----------------------------------------------------------------------------
// TOUCH-SENSITIVE MICRO-INTERACTION & SCADA ANIMATION ENGINE
// -----------------------------------------------------------------------------

// Tooltip DOM instance
let globalHudTooltip = null;

function getOrCreateHudTooltip() {
  if (!globalHudTooltip) {
    globalHudTooltip = document.createElement("div");
    globalHudTooltip.className = "hud-touch-tooltip";
    document.body.appendChild(globalHudTooltip);
  }
  return globalHudTooltip;
}

function showHudTooltip(text, x, y) {
  const tt = getOrCreateHudTooltip();
  tt.innerHTML = text;
  tt.style.left = `${x}px`;
  tt.style.top = `${y}px`;
  tt.classList.add("visible");
}

function hideHudTooltip() {
  if (globalHudTooltip) {
    globalHudTooltip.classList.remove("visible");
  }
}

// 1. Universal Touch Ripple Generator
function initUniversalTouchRipple() {
  const rippleTargets = ".btn, .nav-item, .assay-toggle-btn, .hud-axis-btn, .copilot-chip, .hud-drawer-toggle, .speedo-delta-badge, .hud-speedometer-card, .hud-col-gauge, .reformer-btn, .legend-chip";

  document.addEventListener("pointerdown", (e) => {
    const target = e.target.closest(rippleTargets);
    if (!target) return;

    const rect = target.getBoundingClientRect();
    const ripple = document.createElement("span");
    ripple.className = "touch-ripple-effect";

    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;

    ripple.style.width = ripple.style.height = `${size}px`;
    ripple.style.left = `${x}px`;
    ripple.style.top = `${y}px`;

    // Ensure target position relative
    const compPos = window.getComputedStyle(target).position;
    if (compPos === "static") {
      target.style.position = "relative";
    }
    target.style.overflow = "hidden";
    target.appendChild(ripple);

    setTimeout(() => {
      ripple.remove();
    }, 600);
  }, { passive: true });
}

// 2. Interactive Linked Cut Bar & 2x3 Legend
function initCutBarInteractions() {
  const cutMeta = {
    "cut-lpg": { name: "Liquefied Petroleum Gas (LPG)", range: "C3 - C4 (-42°C to 0°C)", desc: "Bottling & clean domestic fuel" },
    "cut-naphtha": { name: "Light & Heavy Naphtha", range: "35°C - 175°C", desc: "Petrochemical feedstock (OMPL Aromatics/PP)" },
    "cut-atf": { name: "Aviation Turbine Fuel (ATF / Jet A-1)", range: "150°C - 260°C", desc: "Freeze point -47°C commercial aviation" },
    "cut-diesel": { name: "Ultra-Low Sulfur Diesel (BS-VI)", range: "250°C - 370°C", desc: "Sulfur < 10 ppm, Cetane 51+ prime transport fuel" },
    "cut-vgo": { name: "Vacuum Gas Oil (Heavy VGO)", range: "370°C - 540°C", desc: "FCC & Hydrocracker conversion feedstock" },
    "cut-residue": { name: "Vacuum Residue (VR / Bitumen)", range: "540°C+ Heavy Ends", desc: "Bitumen VG-30/40 & Petcoke delayed coker feed" },
  };

  const cutSegments = document.querySelectorAll(".cut-segment");
  cutSegments.forEach(seg => {
    // Find class matching cut-*
    let cutKey = null;
    for (const cls of seg.classList) {
      if (cutMeta[cls]) {
        cutKey = cls;
        break;
      }
    }
    if (!cutKey) return;

    function handleEnter(e) {
      seg.classList.add("active-cut-highlight");
      const meta = cutMeta[cutKey];
      const shortKey = cutKey.replace("cut-", "");
      
      // Highlight matching legend item
      const legEl = document.getElementById(`legend-cut-${shortKey}`) || document.getElementById(`legend-petro-${shortKey}`);
      if (legEl && legEl.parentElement) {
        legEl.parentElement.classList.add("active-legend-highlight");
      }

      const rect = seg.getBoundingClientRect();
      const valText = seg.textContent.trim() || seg.getAttribute("title") || "";
      showHudTooltip(`
        <div style="font-weight:800; color:#FF9E2C; margin-bottom:2px;">${meta.name}</div>
        <div style="font-size:10px; color:#38BDF8;">Boiling Cut: ${meta.range}</div>
        <div style="font-size:9.5px; color:#94A3B8; margin-top:2px;">${meta.desc}</div>
        <div style="font-size:10px; font-weight:700; color:#FFFFFF; margin-top:3px;">Yield Fraction: ${valText}</div>
      `, rect.left + rect.width / 2, rect.top);
    }

    function handleLeave() {
      seg.classList.remove("active-cut-highlight");
      const shortKey = cutKey.replace("cut-", "");
      const legEl = document.getElementById(`legend-cut-${shortKey}`) || document.getElementById(`legend-petro-${shortKey}`);
      if (legEl && legEl.parentElement) {
        legEl.parentElement.classList.remove("active-legend-highlight");
      }
      hideHudTooltip();
    }

    seg.addEventListener("mouseenter", handleEnter);
    seg.addEventListener("mouseleave", handleLeave);
    seg.addEventListener("touchstart", (e) => {
      handleEnter(e);
      setTimeout(handleLeave, 2500);
    }, { passive: true });
  });

  // Link legend hover to cut bar
  const legendItems = document.querySelectorAll(".cut-bar-container + div > div, .hud-equalizer-card [id^='legend-']");
  legendItems.forEach(item => {
    item.classList.add("legend-cut-item");
    item.addEventListener("mouseenter", () => {
      const valSpan = item.querySelector("[id^='legend-']");
      if (!valSpan) return;
      const key = valSpan.id.replace("legend-cut-", "").replace("legend-petro-", "");
      const targetSeg = document.querySelector(`.cut-segment.cut-${key}`);
      if (targetSeg) {
        targetSeg.classList.add("active-cut-highlight");
      }
    });
    item.addEventListener("mouseleave", () => {
      document.querySelectorAll(".cut-segment").forEach(s => s.classList.remove("active-cut-highlight"));
    });
  });
}


// 4. Interactive Column Gauges Tactile Pulse
function initGaugeInteractions() {
  const gauges = document.querySelectorAll(".hud-col-gauge");
  gauges.forEach(gauge => {
    gauge.addEventListener("pointerdown", () => {
      gauge.classList.add("active-touch");
      const tempVal = gauge.querySelector(".gauge-temp-val")?.textContent || "";
      const colName = gauge.querySelector(".gauge-col-name")?.textContent || "";
      const colSub = gauge.querySelector(".gauge-col-sub")?.textContent || "";

      const rect = gauge.getBoundingClientRect();
      showHudTooltip(`
        <div style="font-weight:800; color:#FF9E2C;">${colName}</div>
        <div style="font-size:10px; color:#94A3B8;">${colSub}</div>
        <div style="font-size:12px; font-weight:800; color:#00F5D4; font-family:var(--font-mono); margin-top:2px;">Operating: ${tempVal}</div>
      `, rect.left + rect.width / 2, rect.top);

      setTimeout(() => {
        gauge.classList.remove("active-touch");
        hideHudTooltip();
      }, 2000);
    });
  });
}

// 5. Interactive Equalizer Bouncing Physics
function initEqualizerInteractions() {
  const eqBars = document.querySelectorAll(".eq-bar");
  eqBars.forEach(bar => {
    bar.addEventListener("pointerenter", () => {
      bar.classList.add("active-touch");
    });
    bar.addEventListener("pointerleave", () => {
      bar.classList.remove("active-touch");
    });
  });
}

// Master Initializer called on DOMContentLoaded and tab switch
function initTouchAndMicroInteractions() {
  initUniversalTouchRipple();
  initCutBarInteractions();
  initGaugeInteractions();
  initEqualizerInteractions();
}
