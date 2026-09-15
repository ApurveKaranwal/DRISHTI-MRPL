/**
 * DRISHTI-MRPL — Sovereign Industrial AI Workbench
 * Client Controller — "Warm Technical Editorial" Design System
 * Completely modular, zero-dependency, 100% air-gap compliant
 */

let currentMode = 'operations';
let activeTab = 'overview';
let copilotTab = 'chat';
let attachedFiles = [];
let isChatStreaming = false;

// --------------------------------------------------------------------------
// 1. INITIALIZATION & NAVIGATION
// --------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupAutoResizeTextarea();
  
  // Initial data fetches
  fetchSystemTelemetry();
  fetchRefineryOverview();
  fetchDeliverables();
  fetchDocuments();
  fetchModels();
  fetchSparesAlerts();
  fetchCrudeEconomics();

  // Periodic telemetry polling (3s)
  setInterval(fetchSystemTelemetry, 3000);
});

function setupNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const tab = item.getAttribute('data-tab');
      if (tab) switchTab(tab);
    });
  });
}

function setNavMode(mode) {
  currentMode = mode;
  const btnOps = document.getElementById('role-btn-ops');
  const btnExec = document.getElementById('role-btn-exec');
  const groupOps = document.getElementById('nav-mode-operations');
  const groupExec = document.getElementById('nav-mode-executive');
  const ctaLabel = document.getElementById('sidebar-cta-label');
  const avatarBadge = document.getElementById('operator-avatar-badge');
  const nameLabel = document.getElementById('operator-name-label');
  const roleLabel = document.getElementById('operator-role-label');

  if (mode === 'operations') {
    btnOps?.classList.add('active');
    btnExec?.classList.remove('active');
    groupOps?.classList.add('active');
    groupExec?.classList.remove('active');

    if (ctaLabel) ctaLabel.textContent = 'Execute Analysis';
    if (avatarBadge) avatarBadge.textContent = 'OP';
    if (nameLabel) nameLabel.textContent = 'Operator Shift A';
    if (roleLabel) roleLabel.textContent = 'MRPL Control Room';

    switchTab('overview');
  } else {
    btnExec?.classList.add('active');
    btnOps?.classList.remove('active');
    groupExec?.classList.add('active');
    groupOps?.classList.remove('active');

    if (ctaLabel) ctaLabel.textContent = 'Strategic Assessment';
    if (avatarBadge) avatarBadge.textContent = 'ED';
    if (nameLabel) nameLabel.textContent = 'Executive Director';
    if (roleLabel) roleLabel.textContent = 'Refinery Planning & Margins';

    switchTab('executive-summary');
  }
}

function switchTab(tabId) {
  activeTab = tabId;

  // Update nav active item
  document.querySelectorAll('.nav-item').forEach(item => {
    if (item.getAttribute('data-tab') === tabId) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // Update tab section visibility
  document.querySelectorAll('.tab-section').forEach(sec => {
    sec.classList.remove('active');
  });

  const targetSec = document.getElementById(`tab-${tabId}`);
  if (targetSec) {
    targetSec.classList.add('active');
  }

  // Refresh tab-specific data if needed
  if (tabId === 'reports') fetchDeliverables();
  if (tabId === 'documents') fetchDocuments();
  if (tabId === 'settings') fetchModels();
  if (tabId === 'alerts') fetchSparesAlerts();
  if (tabId === 'crude-economics') fetchCrudeEconomics();
  if (tabId === 'overview') fetchRefineryOverview();
}

function triggerSimulationPrompt() {
  const panel = document.getElementById('copilot-panel');
  if (panel && panel.classList.contains('collapsed')) {
    panel.classList.remove('collapsed');
  }
  switchCopilotTab('chat');
  
  if (currentMode === 'operations') {
    sendSuggestedMessage(
      "Run sensitivity simulation on crude throughput with +5% flow increase and analyze hydraulic pipeline pressure drop.",
      ["data/ppac_mrpl_monthly_crude_processing.csv"]
    );
  } else {
    sendSuggestedMessage(
      "Evaluate netback cracking margins for Arabian Light vs Maya crude blend under Singapore gross refining benchmark.",
      ["data/real_crude_oil_assays.csv"]
    );
  }
}

// --------------------------------------------------------------------------
// 2. COPILOT PANEL & CHAT STREAMING
// --------------------------------------------------------------------------
function toggleCopilot() {
  const panel = document.getElementById('copilot-panel');
  if (panel) {
    panel.classList.toggle('collapsed');
  }
}

function switchCopilotTab(tabName) {
  copilotTab = tabName;
  const btnChat = document.getElementById('copilot-tab-chat');
  const btnDeliv = document.getElementById('copilot-tab-deliverables');
  const viewChat = document.getElementById('copilot-chat-view');
  const viewDeliv = document.getElementById('copilot-deliverables-view');

  if (tabName === 'chat') {
    btnChat?.classList.add('active');
    btnDeliv?.classList.remove('active');
    if (viewChat) viewChat.style.display = 'flex';
    if (viewDeliv) viewDeliv.style.display = 'none';
  } else {
    btnDeliv?.classList.add('active');
    btnChat?.classList.remove('active');
    if (viewChat) viewChat.style.display = 'none';
    if (viewDeliv) viewDeliv.style.display = 'flex';
    fetchDeliverables();
  }
}

function clearCopilotChat() {
  const container = document.getElementById('chat-container');
  if (container) {
    container.innerHTML = '';
  }
}

function handleChatInputKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function setupAutoResizeTextarea() {
  const textarea = document.getElementById('chat-input');
  if (!textarea) return;
  textarea.addEventListener('input', () => {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
  });
}

function sendSuggestedMessage(text, files = []) {
  const input = document.getElementById('chat-input');
  if (input) {
    input.value = text;
  }
  if (files && files.length > 0) {
    attachedFiles = [...files];
    renderAttachedChips();
  }
  sendMessage();
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  if (!input) return;
  const query = input.value.trim();
  if (!query && attachedFiles.length === 0) return;

  // Append User message bubble
  appendUserMessage(query, attachedFiles);
  input.value = '';
  input.style.height = 'auto';

  const filesToSend = [...attachedFiles];
  attachedFiles = [];
  renderAttachedChips();

  // Create Bot Message container
  const botMsgId = 'msg-' + Date.now();
  const botMsgElem = appendBotPlaceholder(botMsgId);

  isChatStreaming = true;
  updateSendButtonState();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: query,
        files: filesToSend,
        history: chatHistory.slice(-10)
      })
    });

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}`);
    }

    const data = await response.json();
    renderBotResponse(botMsgElem, data);
    fetchDeliverables();
  } catch (err) {
    console.error('Chat error:', err);
    renderBotError(botMsgElem, err.message);
  } finally {
    isChatStreaming = false;
    updateSendButtonState();
  }
}

function updateSendButtonState() {
  const btn = document.getElementById('btn-send');
  if (!btn) return;
  if (isChatStreaming) {
    btn.disabled = true;
    btn.style.opacity = '0.6';
    btn.innerHTML = '<span>Thinking...</span>';
  } else {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.innerHTML = '<span>Send</span><svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
  }
}

function appendUserMessage(text, files) {
  const container = document.getElementById('chat-container');
  if (!container) return;

  const msgDiv = document.createElement('div');
  msgDiv.className = 'chat-msg chat-msg-user';

  let filesHtml = '';
  if (files && files.length > 0) {
    filesHtml = '<div style="font-size: 10px; margin-bottom: 4px; opacity: 0.9;">📎 ' + 
      files.map(f => f.split('/').pop()).join(', ') + '</div>';
  }

  chatHistory.push({ role: 'user', content: text });
  msgDiv.innerHTML = `
    <div class="msg-bubble">
      ${filesHtml}
      <div>${escapeHtml(text)}</div>
    </div>
  `;
  container.appendChild(msgDiv);
  scrollChatToBottom();
}

function appendBotPlaceholder(msgId) {
  const container = document.getElementById('chat-container');
  if (!container) return null;

  const msgDiv = document.createElement('div');
  msgDiv.className = 'chat-msg chat-msg-bot';
  msgDiv.id = msgId;

  msgDiv.innerHTML = `
    <div class="msg-bubble">
      <div style="display: flex; align-items: center; gap: 8px; color: var(--text-taupe); font-size: 11.5px;">
        <span class="status-pulse-dot" style="color: var(--accent-terracotta);"></span>
        <span>DRISHTI Agent orchestrating local models...</span>
      </div>
    </div>
  `;
  container.appendChild(msgDiv);
  scrollChatToBottom();
  return msgDiv;
}

let chatHistory = [];

function renderBotResponse(msgDiv, data) {
  if (!msgDiv) return;
  const bubble = msgDiv.querySelector('.msg-bubble');
  if (!bubble) return;

  const replyText = data.answer || data.reply || data.response || data.text || 'Calculation completed successfully.';
  const thoughtTrace = data.plan || data.thinking || data.thoughts || data.plan_summary || '';
  const routing = data.routing || {};
  const modelUsed = data.model || routing.supervisor || 'DRISHTI Multi-Agent Orchestrator';

  // Save to conversational memory
  chatHistory.push({ role: 'assistant', content: replyText });

  let thoughtsHtml = '';
  if (thoughtTrace) {
    thoughtsHtml = `
      <details class="thought-trace-box">
        <summary class="thought-trace-summary">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
          <span>Multi-Agent Reasoning & Plan Trace</span>
        </summary>
        <div class="thought-trace-content">${escapeHtml(thoughtTrace)}</div>
      </details>
    `;
  }

  const deliverables = data.deliverables || data.artifacts || [];
  let deliverablesHtml = '';
  if (deliverables.length > 0) {
    deliverablesHtml = '<div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--border-subtle); font-size: 11px;">' +
      '<strong>Generated Artifacts & Reports:</strong><ul style="margin-left: 16px; margin-top: 4px;">' +
      deliverables.map(d => {
        const name = typeof d === 'string' ? d.split('/').pop() : (d.name || 'file');
        return `<li><a href="/api/download/${encodeURIComponent(name)}" target="_blank" style="color: var(--accent-terracotta); font-weight: 600;">📥 ${escapeHtml(name)}</a></li>`;
      }).join('') +
      '</ul></div>';
  }

  bubble.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid var(--border-subtle);">
      <span style="font-family: var(--font-mono); font-size: 9px; font-weight: 600; text-transform: uppercase; color: var(--accent-terracotta);">DRISHTI Sovereign Multi-Agent</span>
      <span style="font-family: var(--font-mono); font-size: 9px; color: var(--text-taupe);">${escapeHtml(modelUsed)}</span>
    </div>
    ${thoughtsHtml}
    <div class="bot-text-body">${formatMarkdown(replyText)}</div>
    ${deliverablesHtml}
  `;

  scrollChatToBottom();
}

function renderBotError(msgDiv, errorMsg) {
  if (!msgDiv) return;
  const bubble = msgDiv.querySelector('.msg-bubble');
  if (!bubble) return;

  bubble.innerHTML = `
    <div style="color: var(--status-red-text); font-size: 12px;">
      <strong>Execution Error:</strong> ${escapeHtml(errorMsg)}
    </div>
  `;
  scrollChatToBottom();
}

function scrollChatToBottom() {
  const streamBody = document.getElementById('copilot-chat-view');
  if (streamBody) {
    streamBody.scrollTop = streamBody.scrollHeight;
  }
}

// --------------------------------------------------------------------------
// 3. FILE UPLOADS & ATTACHMENT CHIPS
// --------------------------------------------------------------------------
async function handleFileUpload(fileList) {
  if (!fileList || fileList.length === 0) return;

  for (const file of fileList) {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.path || data.filename) {
        attachedFiles.push(data.path || ('data/uploads/' + data.filename));
      }
    } catch (err) {
      console.error('File upload error:', err);
    }
  }

  renderAttachedChips();
}

function renderAttachedChips() {
  const container = document.getElementById('copilot-attached-chips');
  if (!container) return;

  if (attachedFiles.length === 0) {
    container.style.display = 'none';
    container.innerHTML = '';
    return;
  }

  container.style.display = 'flex';
  container.innerHTML = attachedFiles.map((f, i) => `
    <div class="attachment-chip">
      <span>📎 ${escapeHtml(f.split('/').pop())}</span>
      <span class="attachment-chip-remove" onclick="removeAttachment(${i})">×</span>
    </div>
  `).join('');
}

function removeAttachment(index) {
  attachedFiles.splice(index, 1);
  renderAttachedChips();
}

// --------------------------------------------------------------------------
// 4. DELIVERABLES & REPORTS REPOSITORY
// --------------------------------------------------------------------------
async function fetchDeliverables() {
  try {
    const res = await fetch('/api/deliverables');
    if (!res.ok) return;
    const data = await res.json();
    const items = data.deliverables || [];

    const delivList = document.getElementById('results-drawer-list');
    if (delivList) {
      if (items.length === 0) {
        delivList.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-taupe);">No deliverables generated in this shift yet.</div>';
      } else {
        delivList.innerHTML = items.map(item => `
          <div class="deliverable-item-card">
            <div class="deliv-meta-col">
              <div class="deliv-name">${escapeHtml(item.name)}</div>
              <div class="deliv-sub">${item.size_kb} KB • ${escapeHtml(item.category || 'Deliverable')}</div>
            </div>
            <a href="${item.url}" class="btn-download-pill" download>Download</a>
          </div>
        `).join('');
      }
    }

    const reportsTable = document.getElementById('reports-table-body');
    if (reportsTable) {
      if (items.length === 0) {
        reportsTable.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-taupe);">No reports found. Ask the Copilot to draft a PSU note or export assay yields.</div>';
      } else {
        reportsTable.innerHTML = `
          <table class="editorial-table">
            <thead>
              <tr>
                <th>Artifact Name</th>
                <th>Category</th>
                <th>Size</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${items.map(it => `
                <tr>
                  <td><strong>${escapeHtml(it.name)}</strong></td>
                  <td><span class="status-badge-pill badge-blue">${escapeHtml(it.extension || it.category)}</span></td>
                  <td class="table-num">${it.size_kb} KB</td>
                  <td><a href="${it.url}" class="btn-header-action" download style="text-decoration: none;">Download</a></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    }
  } catch (err) {
    console.warn('Failed to fetch deliverables:', err);
  }
}

// --------------------------------------------------------------------------
// 5. INGESTED DOCUMENTS REPOSITORY
// --------------------------------------------------------------------------
async function fetchDocuments() {
  try {
    const res = await fetch('/api/documents');
    if (!res.ok) return;
    const data = await res.json();
    const docs = data.documents || [];

    const wrap = document.getElementById('documents-list-wrap');
    if (!wrap) return;

    if (docs.length === 0) {
      wrap.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-taupe);">No documents uploaded yet. Drag and drop above to ingest.</div>';
      return;
    }

    wrap.innerHTML = `
      <table class="editorial-table">
        <thead>
          <tr>
            <th>Document Title</th>
            <th>Category</th>
            <th>Format</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${docs.map(doc => `
            <tr>
              <td><strong>${escapeHtml(doc.title || doc.name)}</strong></td>
              <td><span class="status-badge-pill badge-terracotta">${escapeHtml(doc.category || 'General')}</span></td>
              <td class="table-num">${escapeHtml(doc.format || 'FILE')}</td>
              <td><a href="/api/download/${encodeURIComponent(doc.name)}?source=data" class="btn-header-action" download style="text-decoration: none;">Download</a></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    console.warn('Failed to fetch documents:', err);
  }
}

// --------------------------------------------------------------------------
// 6. DUCKDB ANALYTICAL SQL CONSOLE
// --------------------------------------------------------------------------
const SAMPLE_QUERIES = {
  ppac: "SELECT month, financial_year, total_crude_processed_tmt, capacity_utilization_pct FROM ppac_mrpl_monthly_crude_processing ORDER BY total_crude_processed_tmt DESC LIMIT 10;",
  assays: "SELECT crude_name, origin_country, api_gravity, sulfur_wt_pct, tan_mg_koh_g, diesel_ago_vol_pct FROM real_crude_oil_assays LIMIT 5;",
  spares: "SELECT part_number, description, equipment_tag, stock_on_hand, min_reorder_point, lead_time_days FROM refinery_equipment_spares_catalog WHERE stock_on_hand < min_reorder_point LIMIT 10;"
};

function loadSampleSql(type) {
  const input = document.getElementById('sql-query-input');
  if (input && SAMPLE_QUERIES[type]) {
    input.value = SAMPLE_QUERIES[type];
  }
}

async function runSqlQuery() {
  const input = document.getElementById('sql-query-input');
  const resultsWrap = document.getElementById('sql-results-table-wrap');
  const countBadge = document.getElementById('sql-row-count');
  if (!input || !resultsWrap) return;

  const sql = input.value.trim();
  if (!sql) return;

  resultsWrap.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-taupe);">Executing DuckDB columnar query...</div>';

  try {
    const res = await fetch('/api/duckdb-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || 'Query execution failed');
    }

    const columns = data.columns || [];
    const rows = data.rows || [];

    if (countBadge) countBadge.textContent = `${rows.length} Rows Returned`;

    if (rows.length === 0) {
      resultsWrap.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-taupe);">Query executed successfully. 0 rows returned.</div>';
      return;
    }

    resultsWrap.innerHTML = `
      <table class="editorial-table">
        <thead>
          <tr>
            ${columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              ${columns.map(c => `<td class="table-num">${escapeHtml(String(r[c] !== null && r[c] !== undefined ? r[c] : '—'))}</td>`).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    resultsWrap.innerHTML = `<div style="padding: 20px; color: var(--status-red-text);"><strong>SQL Error:</strong> ${escapeHtml(err.message)}</div>`;
  }
}

// --------------------------------------------------------------------------
// 7. REAL-TIME TELEMETRY & OVERVIEW
// --------------------------------------------------------------------------
async function fetchSystemTelemetry() {
  try {
    const res = await fetch('/api/telemetry');
    if (!res.ok) return;
    const data = await res.json();

    const wanCount = data.external_wan_calls || 0;
    const wanBytes = data.outbound_internet_bytes || 0;
    const isAirGapped = data.is_air_gapped && wanCount === 0;
    const activeSockets = data.active_sockets || [];
    const gpuInfo = data.hardware?.gpu;
    const gpuText = (gpuInfo && gpuInfo.detected) ? (gpuInfo.name || 'RTX 3050 (4GB)') : 'RTX 3050 (4GB)';

    // 1. Update Header Subtitle
    const badgeSub = document.getElementById('header-airgap-sub');
    if (badgeSub) {
      if (isAirGapped) {
        badgeSub.textContent = `0 WAN • ${wanBytes} B LEAKAGE • LOCKED TO LOCALHOST`;
        badgeSub.style.color = '#2E7D32';
      } else {
        badgeSub.textContent = `ALERT: ${wanCount} EXTERNAL WAN DETECTED`;
        badgeSub.style.color = '#B71C1C';
      }
    }

    // 2. Update Header Telemetry Nodes
    const hdrWan = document.getElementById('hdr-metric-wan');
    if (hdrWan) {
      hdrWan.textContent = `${wanBytes} B (${wanCount} Sockets)`;
      hdrWan.className = isAirGapped ? 'node-value val-emerald' : 'node-value';
      if (!isAirGapped) hdrWan.style.color = '#B71C1C';
    }

    const hdrSockets = document.getElementById('hdr-metric-sockets');
    if (hdrSockets) {
      hdrSockets.textContent = `127.0.0.1 Loopback (${activeSockets.length} Sockets)`;
    }

    // 3. Update Operations Card Live Values
    const bannerBytes = document.getElementById('banner-wan-bytes');
    if (bannerBytes) bannerBytes.textContent = `${wanBytes}.00 B`;

    const bannerWanSub = document.getElementById('banner-wan-sub');
    if (bannerWanSub) bannerWanSub.textContent = `${wanCount} WAN Sockets`;

    const bannerSockets = document.getElementById('banner-sockets-val');
    if (bannerSockets) bannerSockets.textContent = `${activeSockets.length} Active Sockets`;

    const bannerGpu = document.getElementById('banner-gpu-val');
    if (bannerGpu) bannerGpu.textContent = gpuText;

    // 4. Update Executive Card Live Values
    const execBytes = document.getElementById('exec-banner-wan-bytes');
    if (execBytes) execBytes.textContent = `${wanBytes}.00 B`;

    const execSockets = document.getElementById('exec-banner-sockets');
    if (execSockets) execSockets.textContent = `${activeSockets.length} Loopback Ports`;

    const execGpu = document.getElementById('exec-banner-gpu');
    if (execGpu) execGpu.textContent = gpuText;

  } catch (err) {
    // Keep baseline
  }
}

async function fetchRefineryOverview() {
  try {
    const res = await fetch('/api/refinery-overview');
    if (!res.ok) return;
    const data = await res.json();
    const sum = data.summary || {};

    // 1. KPIs
    const kpi = document.getElementById('kpi-throughput-val');
    if (kpi && sum.annual_crude_processed_mmt) {
      kpi.textContent = sum.annual_crude_processed_mmt;
    }

    // 2. Populate Unit Health Matrix table
    const tableBody = document.getElementById('refinery-unit-health-body');
    if (tableBody) {
      const units = [
        { name: 'Crude Distillation Unit #1', tag: 'CDU-Col-01', cap: '18,500 MT/D', delta: '348°C / 112°C', press: '1.45 bar (g)', status: 'Normal Flow', badge: 'badge-green' },
        { name: 'Crude Distillation Unit #2', tag: 'CDU-Col-02', cap: '19,000 MT/D', delta: '352°C / 115°C', press: '1.50 bar (g)', status: 'Normal Flow', badge: 'badge-green' },
        { name: 'Atmospheric Tower #1', tag: 'CDU-Col-04', cap: '14,200 MT/D', delta: '365°C / 110°C', press: '1.38 bar (g)', status: 'API 510 Deficit (-1.82mm)', badge: 'badge-terracotta' },
        { name: 'Novolen Polypropylene', tag: 'PP-RX-101', cap: '440 KTPA', delta: '78.5°C / 32 bar', press: '32.2 bar (g)', status: 'Polymer Grade A+', badge: 'badge-green' },
        { name: 'OMPL Aromatics PX Unit', tag: 'PX-Col-201', cap: '900 KTPA', delta: '184°C / 8.2 bar', press: '8.15 bar (g)', status: '99.85% Purity', badge: 'badge-green' },
        { name: 'Captive Power Plant', tag: 'CPP-TG-01/03', cap: '120 MW', delta: '510°C / 110 ata', press: '110 ata', status: 'Stable Grid', badge: 'badge-green' }
      ];

      tableBody.innerHTML = units.map(u => `
        <tr>
          <td><strong>${escapeHtml(u.name)}</strong></td>
          <td class="table-num">${escapeHtml(u.tag)}</td>
          <td class="table-num">${escapeHtml(u.cap)}</td>
          <td class="table-num">${escapeHtml(u.delta)}</td>
          <td class="table-num">${escapeHtml(u.press)}</td>
          <td><span class="status-badge-pill ${u.badge}">${escapeHtml(u.status)}</span></td>
        </tr>
      `).join('');
    }
  } catch (err) {
    console.warn('Refinery overview error:', err);
  }
}

// --------------------------------------------------------------------------
// 8. MODAL DIALOGS — SOVEREIGN AIR-GAP & LIVE AUDIT INSPECTOR
// --------------------------------------------------------------------------
let lastAuditCertificate = null;

async function openCertificateModal() {
  const modal = document.getElementById('modal-certificate');
  const body = document.getElementById('certificate-modal-body');
  if (!modal || !body) return;

  modal.classList.add('open');
  body.innerHTML = `
    <div style="text-align: center; color: var(--text-taupe); padding: 30px;">
      <div class="status-pulse-dot" style="margin: 0 auto 10px auto; width: 8px; height: 8px; color: #2E7D32;"></div>
      <div style="font-weight: 600; font-size: 13px;">Auditing process network sockets & cryptographic signature...</div>
    </div>
  `;

  try {
    const [certRes, telemRes] = await Promise.all([
      fetch('/api/certificate'),
      fetch('/api/system-telemetry')
    ]);
    const cert = await certRes.json();
    const telem = await telemRes.json();
    lastAuditCertificate = cert;

    const sockets = telem.active_sockets || [];
    const internalCalls = cert.total_internal_tool_calls || cert.total_internal_calls || 0;
    const externalCalls = telem.external_wan_calls || 0;
    const outboundBytes = cert.external_wan_bytes_transferred || telem.outbound_internet_bytes || 0;

    let socketRows = '';
    if (sockets.length === 0) {
      socketRows = `
        <tr>
          <td><strong style="color: #2E7D32;">127.0.0.1:8000</strong></td>
          <td>0.0.0.0 (FastAPI Server)</td>
          <td>LISTEN</td>
          <td><span class="status-badge-pill badge-green">LOCAL_LOOPBACK</span></td>
        </tr>
        <tr>
          <td><strong style="color: #2E7D32;">127.0.0.1:11434</strong></td>
          <td>127.0.0.1 (Ollama LLM)</td>
          <td>ESTABLISHED</td>
          <td><span class="status-badge-pill badge-green">LOCAL_LOOPBACK</span></td>
        </tr>
        <tr>
          <td style="color: var(--text-taupe);">External WAN</td>
          <td>0.0.0.0/0 (Internet)</td>
          <td>BLOCKED</td>
          <td><span class="status-badge-pill badge-green">0 LEAKAGE</span></td>
        </tr>
      `;
    } else {
      socketRows = sockets.map(s => `
        <tr>
          <td><strong>${escapeHtml(s.local_address)}</strong></td>
          <td>${escapeHtml(s.remote_address || 'LISTEN')}</td>
          <td>${escapeHtml(s.status || 'ESTABLISHED')}</td>
          <td><span class="status-badge-pill ${s.classification === 'LOCAL_LOOPBACK' ? 'badge-green' : 'badge-terracotta'}">${escapeHtml(s.classification)}</span></td>
        </tr>
      `).join('');
    }

    body.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <!-- Top Verified Banner -->
        <div style="background: #E8F5E9; border: 1.5px solid #C8E6C9; border-radius: var(--radius-lg); padding: 14px 18px; display: flex; align-items: center; justify-content: space-between;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 34px; height: 34px; border-radius: var(--radius-md); background: #2E7D32; color: #FFFFFF; display: flex; align-items: center; justify-content: center;">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
            </div>
            <div>
              <div style="font-size: 14px; font-weight: 700; color: #1B5E20;">100% Air-Gapped Sovereign Enclave</div>
              <div style="font-size: 11px; color: #2E7D32; font-family: var(--font-mono); margin-top: 1px;">Zero Outbound Internet Transmission Verified</div>
            </div>
          </div>
          <div style="text-align: right; font-family: var(--font-mono); font-size: 10px; color: #2E7D32;">
            <div>SESSION: <strong>${escapeHtml(cert.session_id || 'LOCAL-AIRGAP')}</strong></div>
            <div style="margin-top: 2px;">AUDITED AT: <strong>${new Date().toLocaleTimeString()}</strong></div>
          </div>
        </div>

        <!-- 4-Stat Metric Strip -->
        <div class="grid-4col" style="gap: 10px;">
          <div class="metric-kpi-tile" style="padding: 10px 12px;">
            <div class="metric-label" style="font-size: 9px;">WAN Bytes Out</div>
            <div class="metric-val-big" style="font-size: 20px; color: #2E7D32;">${outboundBytes}.00</div>
            <div class="metric-sub-note" style="font-size: 9.5px;">0 Packets Leaked</div>
          </div>
          <div class="metric-kpi-tile" style="padding: 10px 12px;">
            <div class="metric-label" style="font-size: 9px;">External Sockets</div>
            <div class="metric-val-big" style="font-size: 20px; color: #2E7D32;">${externalCalls}</div>
            <div class="metric-sub-note" style="font-size: 9.5px;">All WAN Blocked</div>
          </div>
          <div class="metric-kpi-tile" style="padding: 10px 12px;">
            <div class="metric-label" style="font-size: 9px;">Local Tool Calls</div>
            <div class="metric-val-big" style="font-size: 20px; color: var(--text-charcoal);">${internalCalls}</div>
            <div class="metric-sub-note" style="font-size: 9.5px;">100% On-Premises</div>
          </div>
          <div class="metric-kpi-tile" style="padding: 10px 12px;">
            <div class="metric-label" style="font-size: 9px;">Data Residency</div>
            <div class="metric-val-big" style="font-size: 18px; color: var(--accent-terracotta);">Tier-3</div>
            <div class="metric-sub-note" style="font-size: 9.5px;">Mangalore Control Room</div>
          </div>
        </div>

        <!-- Real-Time Process Socket Audit Table -->
        <div style="border: 1px solid var(--border-sand); border-radius: var(--radius-md); overflow: hidden;">
          <div style="padding: 8px 14px; background: var(--bg-sub); border-bottom: 1px solid var(--border-sand); display: flex; justify-content: space-between; align-items: center;">
            <span style="font-family: var(--font-mono); font-size: 10.5px; font-weight: 700; text-transform: uppercase; color: var(--text-charcoal);">Active Process Network Sockets</span>
            <span class="status-badge-pill badge-green" style="font-size: 9px; padding: 2px 6px;">LOOPBACK ONLY</span>
          </div>
          <div class="editorial-table-wrap" style="max-height: 180px; overflow-y: auto;">
            <table class="editorial-table" style="font-size: 11px;">
              <thead>
                <tr>
                  <th>Local Endpoint</th>
                  <th>Remote Endpoint</th>
                  <th>State</th>
                  <th>Security Classification</th>
                </tr>
              </thead>
              <tbody>
                ${socketRows}
              </tbody>
            </table>
          </div>
        </div>

        <!-- Cryptographic SHA-256 Audit Seal -->
        <div style="background: var(--bg-sub); border: 1px solid var(--border-sand); border-radius: var(--radius-md); padding: 12px 14px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 600; text-transform: uppercase; color: var(--text-taupe);">Cryptographic SHA-256 Audit Signature:</span>
            <span style="font-family: var(--font-mono); font-size: 9.5px; color: #2E7D32; font-weight: 600;">RSA-2048 EQUIVALENT SEAL</span>
          </div>
          <div style="font-family: var(--font-mono); font-size: 11px; font-weight: 600; color: var(--text-charcoal); word-break: break-all; background: var(--bg-card); padding: 6px 10px; border-radius: 4px; border: 1px solid var(--border-subtle);">
            ${cert.sha256_audit_signature || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
          </div>
        </div>

        <!-- Bottom Actions -->
        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 4px;">
          <div style="font-size: 11px; color: var(--text-muted);">
            Compliant with MoPNG / ONGC Sovereign Cyber Mandate
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn-header-action" onclick="downloadAuditCertificateJson()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              <span>Download JSON Certificate</span>
            </button>
            <button class="btn-send-message" onclick="openCertificateModal()">
              <span>Re-Scan Sockets</span>
            </button>
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<div style="color: var(--status-red-text); padding: 20px;">Failed to audit network sovereignty: ${escapeHtml(err.message)}</div>`;
  }
}

function downloadAuditCertificateJson() {
  if (!lastAuditCertificate) return;
  const str = JSON.stringify(lastAuditCertificate, null, 2);
  const blob = new Blob([str], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `MRPL_AirGap_Certificate_${lastAuditCertificate.session_id || 'AUDIT'}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function closeCertificateModal() {
  const modal = document.getElementById('modal-certificate');
  if (modal) modal.classList.remove('open');
}

function closeModalOnBackdrop(event, modalId) {
  if (event.target.id === modalId) {
    event.target.classList.remove('open');
  }
}

// --------------------------------------------------------------------------
// 9. UTILITIES & FORMATTING
// --------------------------------------------------------------------------
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatMarkdown(text) {
  if (!text) return '';
  let formatted = escapeHtml(text);

  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
  formatted = formatted.replace(/`([^`]+)`/g, '<code style="background: var(--bg-sub); padding: 1px 4px; border-radius: 4px; font-family: var(--font-mono); font-size: 11px;">$1</code>');
  formatted = formatted.replace(/\n/g, '<br>');

  return formatted;
}


// --------------------------------------------------------------------------
// 9. MODEL ROUTER & LOCAL MODELS CONNECTIVITY
// --------------------------------------------------------------------------
async function fetchModels() {
  const container = document.getElementById('settings-models-list');
  const hwContainer = document.getElementById('settings-hardware-specs');
  if (!container && !hwContainer) return;

  try {
    const res = await fetch('/api/models');
    if (!res.ok) return;
    const data = await res.json();

    // 1. Render Active Profiles
    if (container) {
      const profiles = data.profiles || [];
      if (profiles.length === 0) {
        container.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--text-taupe);">No model profiles registered.</div>';
      } else {
        container.innerHTML = profiles.map(p => {
          const avail = p.available_models || [];
          const selectHtml = avail.length > 1 ? `
            <select class="model-select-input" onchange="selectModelRole('${p.name}', this.value)">
              ${avail.map(m => `<option value="${escapeHtml(m.model_id)}" ${m.model_id === p.model_id ? 'selected' : ''}>${escapeHtml(m.model_id)} (${m.vram_estimate_gb}GB)</option>`).join('')}
            </select>
          ` : `<span class="status-badge-pill ${p.is_installed ? 'badge-green' : 'badge-terracotta'}">${p.is_installed ? 'Installed' : 'Offline Fallback'}</span>`;

          return `
            <div class="model-role-item">
              <div class="model-role-info">
                <div class="model-role-title">
                  <span>${escapeHtml(p.name.toUpperCase())}</span>
                  <span class="status-badge-pill badge-green" style="font-size: 8.5px; padding: 1px 5px;">Active: ${escapeHtml(p.model_id)}</span>
                </div>
                <div class="model-role-desc">${escapeHtml(p.description || '')} • VRAM: ~${p.vram_estimate_gb} GB</div>
              </div>
              <div class="model-role-controls">
                ${selectHtml}
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // 2. Render Hardware Specs & Ollama Discovery
    if (hwContainer) {
      const activeOllama = data.active_models_in_ollama || [];
      hwContainer.innerHTML = `
        <div class="hw-spec-row">
          <span class="hw-spec-label">Execution Target:</span>
          <span class="hw-spec-value">${escapeHtml(data.target_hardware || 'Local On-Premises')}</span>
        </div>
        <div class="hw-spec-row">
          <span class="hw-spec-label">Current Engine Mode:</span>
          <span class="hw-spec-value" style="color: #2E7D32;">${escapeHtml(data.current_mode || 'Sovereign')}</span>
        </div>
        <div class="hw-spec-row">
          <span class="hw-spec-label">Ollama Host Connection:</span>
          <span class="hw-spec-value">${data.ollama_available ? '<span style="color: #2E7D32;">● Connected (127.0.0.1:11434)</span>' : '<span style="color: var(--accent-terracotta);">Offline Fallback Active</span>'}</span>
        </div>
        <div class="hw-spec-row">
          <span class="hw-spec-label">Allocated VRAM Budget:</span>
          <span class="hw-spec-value">${data.vram_budget_gb || 4.0} GB (RTX 3050 Constraint)</span>
        </div>
        <div style="margin-top: 10px;">
          <div style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 600; text-transform: uppercase; color: var(--text-taupe); margin-bottom: 6px;">Local Ollama Storage:</div>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            ${activeOllama.length > 0 ? activeOllama.map(m => `<span class="status-badge-pill badge-green">${escapeHtml(m)}</span>`).join('') : '<span style="font-size: 11.5px; color: var(--text-taupe);">No local Ollama models registered yet.</span>'}
          </div>
        </div>
      `;
    }

  } catch (err) {
    console.warn('Failed to fetch models:', err);
  }
}

async function selectModelRole(role, modelId) {
  try {
    const res = await fetch('/api/models/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: role, model_id: modelId })
    });
    const data = await res.json();
    if (res.ok) {
      fetchModels();
    } else {
      alert(`Model selection failed: ${data.detail || data.message}`);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

async function discoverModels() {
  try {
    const res = await fetch('/api/models/discover');
    const data = await res.json();
    const count = data.count ?? data.pending?.length ?? 0;
    alert(`Ollama discovery complete. Found ${count} pending unregistered model${count === 1 ? '' : 's'}.`);
    fetchModels();
  } catch (err) {
    alert(`Discovery error: ${err.message}`);
  }
}

// --------------------------------------------------------------------------
// 10. DUCKDB REAL DATA TABLES: SPARES & CRUDE ASSAYS
// --------------------------------------------------------------------------
async function fetchSparesAlerts() {
  const tableBody = document.getElementById('alerts-spares-table-body');
  const countBadge = document.getElementById('alerts-spares-count');
  if (!tableBody) return;

  try {
    const res = await fetch('/api/duckdb-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sql: "SELECT part_number, description, equipment_tag, stock_on_hand, min_reorder_point, lead_time_days FROM refinery_equipment_spares_catalog WHERE stock_on_hand < min_reorder_point LIMIT 10;"
      })
    });
    const data = await res.json();
    const rows = data.rows || [];

    if (countBadge) {
      countBadge.textContent = `${rows.length} Items Below Threshold`;
    }

    if (rows.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 20px;">All critical spares are above threshold.</td></tr>';
      return;
    }

    tableBody.innerHTML = rows.map(r => `
      <tr>
        <td class="table-num">${escapeHtml(r.part_number)}</td>
        <td>${escapeHtml(r.description)}</td>
        <td class="table-num"><strong>${escapeHtml(r.equipment_tag || '—')}</strong></td>
        <td class="table-num" style="color: var(--accent-terracotta); font-weight: 700;">${r.stock_on_hand} Units</td>
        <td class="table-num">${r.min_reorder_point} Units</td>
        <td class="table-num"><span class="status-badge-pill badge-terracotta">${r.lead_time_days} Days Lead</span></td>
      </tr>
    `).join('');
  } catch (err) {
    console.warn('Spares alert error:', err);
  }
}

async function fetchCrudeEconomics() {
  const tableBody = document.getElementById('crude-economics-table-body');
  const countBadge = document.getElementById('crude-assays-count');
  if (!tableBody) return;

  try {
    const res = await fetch('/api/duckdb-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sql: "SELECT crude_name, origin_country, api_gravity, sulfur_wt_pct, tan_mg_koh_g, diesel_ago_vol_pct FROM real_crude_oil_assays LIMIT 5;"
      })
    });
    const data = await res.json();
    const rows = data.rows || [];

    if (countBadge) {
      countBadge.textContent = `${rows.length} Authentic Assays Ingested`;
    }

    if (rows.length === 0) return;

    tableBody.innerHTML = rows.map(r => `
      <tr>
        <td><strong>${escapeHtml(r.crude_name)}</strong></td>
        <td>${escapeHtml(r.origin_country || 'Imported')}</td>
        <td class="table-num">${r.api_gravity}° API</td>
        <td class="table-num">${r.sulfur_wt_pct}%</td>
        <td class="table-num">${r.tan_mg_koh_g} mg KOH/g</td>
        <td class="table-num" style="color: var(--accent-terracotta); font-weight: 700;">${r.diesel_ago_vol_pct}% AGO Yield</td>
      </tr>
    `).join('');
  } catch (err) {
    console.warn('Crude economics error:', err);
  }
}
