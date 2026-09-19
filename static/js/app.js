// AddressGuard AI - Frontend Controller
// Vanilla JS only, no frameworks. Talks to the Flask JSON API.

const PIPELINE_STEP_NAMES = [
  "Address Parsing", "Data Normalization", "Phone Validation", "PIN Validation",
  "City and State Validation", "Locality Validation", "Address Pattern Validation",
  "Geographic Consistency", "Anomaly Detection", "Correction Suggestions",
  "Confidence Calculation", "Final Decision",
];

const SAMPLE_ADDRESS =
  "Priya Sharma, 9876543210, 10-101/1/1, Sri Krishna Nagar Colony, Road No 1, Peerzadiguda, Hyderabad, Telangana, 500039";

let currentValidationId = null;
let pendingSuggestions = [];   // suggestions with their current chosen decision
let suggestionDecisions = {};  // field -> {decision, value}

// ---------- Navigation ----------
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.view).classList.add("active");
    if (btn.dataset.view === "history-view") loadHistory();
  });
});

document.getElementById("sample-btn").addEventListener("click", () => {
  document.getElementById("raw-address-input").value = SAMPLE_ADDRESS;
});

document.getElementById("validate-btn").addEventListener("click", runValidation);

// ---------- Pipeline rendering ----------
function renderPipelineSkeleton() {
  const list = document.getElementById("pipeline-steps");
  list.innerHTML = "";
  PIPELINE_STEP_NAMES.forEach(name => {
    const li = document.createElement("li");
    li.id = `step-${slug(name)}`;
    li.innerHTML = `<span>${name}</span><span class="pipeline-status status-WAITING">Waiting</span>`;
    list.appendChild(li);
  });
}

function slug(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, "-"); }

function setStepStatus(name, status) {
  const li = document.getElementById(`step-${slug(name)}`);
  if (!li) return;
  const badge = li.querySelector(".pipeline-status");
  badge.className = `pipeline-status status-${status}`;
  badge.textContent = status.charAt(0) + status.slice(1).toLowerCase();
}

async function animatePipeline(finalStepStatuses) {
  for (const name of PIPELINE_STEP_NAMES) {
    setStepStatus(name, "PROCESSING");
    await sleep(140);
    setStepStatus(name, finalStepStatuses[name] || "COMPLETED");
    await sleep(60);
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ---------- Run validation ----------
async function runValidation() {
  const rawText = document.getElementById("raw-address-input").value.trim();
  if (!rawText) { alert("Please enter an address to validate."); return; }

  renderPipelineSkeleton();
  document.getElementById("results-area").classList.add("hidden");
  document.getElementById("validate-btn").disabled = true;

  try {
    const res = await fetch("/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text: rawText }),
    });
    const data = await res.json();
    if (!res.ok) { alert(data.error || "Validation failed."); return; }

    const steps = data.validation.validation_details.pipeline_steps;
    await animatePipeline(steps);

    currentValidationId = data.validation.validation_id;
    pendingSuggestions = data.suggestions;
    suggestionDecisions = {};

    renderResults(data.validation, data.suggestions);
    document.getElementById("results-area").classList.remove("hidden");
  } catch (err) {
    console.error(err);
    alert("Something went wrong contacting the server.");
  } finally {
    document.getElementById("validate-btn").disabled = false;
  }
}

// ---------- Render results ----------
function renderResults(record, suggestions) {
  document.getElementById("current-validation-id").textContent = record.validation_id;

  // parsed address table
  const table = document.getElementById("parsed-address-table");
  table.innerHTML = "";
  Object.entries(record.working_address || {}).forEach(([k, v]) => {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${humanize(k)}</td><td>${v ? escapeHtml(v) : '<span class="muted">—</span>'}</td>`;
    table.appendChild(row);
  });

  // confidence & risk
  document.getElementById("confidence-score").textContent = `${record.confidence_score}%`;
  document.getElementById("risk-level").textContent = record.risk_level;

  const statusClass = record.final_status.replace(/\s+/g, "-");
  const banner = document.getElementById("status-banner");
  banner.className = `status-banner ${statusClass}`;
  document.getElementById("status-label").textContent = record.final_status;
  document.getElementById("recommendation-text").textContent = record.recommendation;

  // suggestions
  renderSuggestions(suggestions);

  // reasons / problems
  fillList("reasons-list", record.reasons);
  fillList("problems-list", record.problems);

  // validation details
  renderValidationDetails(record.validation_details);

  // report buttons
  renderReportButtons(record.validation_id);
}

function renderSuggestions(suggestions) {
  const container = document.getElementById("suggestions-list");
  container.innerHTML = "";
  const applyBtn = document.getElementById("apply-corrections-btn");

  if (!suggestions || suggestions.length === 0) {
    container.innerHTML = '<p class="muted">No corrections suggested — all recognizable fields matched known data.</p>';
    applyBtn.style.display = "none";
    return;
  }

  applyBtn.style.display = "inline-block";

  suggestions.forEach(s => {
    const item = document.createElement("div");
    item.className = "suggestion-item";
    item.innerHTML = `
      <div class="suggestion-info">
        <div class="field-name">${humanize(s.field)}</div>
        <div class="suggestion-values">${escapeHtml(s.original_value)}<span class="arrow">&rarr;</span><strong>${escapeHtml(s.suggested_value)}</strong></div>
        <div class="suggestion-reason">${escapeHtml(s.reason)} (${s.confidence}% match confidence)</div>
      </div>
      <div class="suggestion-actions" data-field="${s.field}">
        <button class="chip-btn accept" data-decision="ACCEPT">Accept</button>
        <button class="chip-btn reject" data-decision="REJECT">Reject</button>
        <button class="chip-btn edit" data-decision="MANUAL_EDIT">Edit</button>
      </div>
    `;
    container.appendChild(item);
  });

  container.querySelectorAll(".chip-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const actionsDiv = btn.closest(".suggestion-actions");
      const field = actionsDiv.dataset.field;
      actionsDiv.querySelectorAll(".chip-btn").forEach(b => b.classList.remove("selected"));

      if (btn.dataset.decision === "MANUAL_EDIT") {
        const value = prompt(`Enter the correct value for ${humanize(field)}:`);
        if (value === null) return;
        suggestionDecisions[field] = { decision: "MANUAL_EDIT", value };
      } else {
        suggestionDecisions[field] = { decision: btn.dataset.decision };
      }
      btn.classList.add("selected");
    });
  });
}

document.getElementById("apply-corrections-btn").addEventListener("click", async () => {
  if (!currentValidationId) return;
  const decisions = Object.entries(suggestionDecisions).map(([field, d]) => ({
    field, decision: d.decision, value: d.value,
  }));
  if (decisions.length === 0) { alert("Choose Accept, Reject, or Edit for at least one suggestion first."); return; }

  const btn = document.getElementById("apply-corrections-btn");
  btn.disabled = true;
  try {
    const res = await fetch(`/api/correction/${currentValidationId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decisions }),
    });
    const data = await res.json();
    if (!res.ok) { alert(data.error || "Could not apply corrections."); return; }

    renderPipelineSkeleton();
    await animatePipeline(data.new_result.validation_details.pipeline_steps);
    suggestionDecisions = {};
    renderResults(data.new_result, []); // corrections already applied; suggestions list reset
    document.getElementById("results-area").classList.remove("hidden");
  } finally {
    btn.disabled = false;
  }
});

function renderValidationDetails(details) {
  const container = document.getElementById("validation-details");
  container.innerHTML = "";

  const blocks = [
    { title: "Phone Validation", lines: [details.phone_result.status, details.phone_result.message, details.phone_result.ownership_note] },
    { title: "PIN Validation", lines: [details.pin_result.status, details.pin_result.message] },
    { title: "Geographic Consistency", lines: details.location_result.checks.map(c => `${c.check}: ${c.result} — ${c.message}`) },
    { title: "Anomaly Detection", lines: details.anomaly_result.anomalies.length ? details.anomaly_result.anomalies.map(a => a.message) : ["No anomalies detected."] },
    { title: "Parser Notes", lines: [...details.parser_warnings, ...(details.unrecognized_text.length ? [`Unrecognized text: ${details.unrecognized_text.join(", ")}`] : [])].filter(Boolean).length ? [...details.parser_warnings, ...(details.unrecognized_text.length ? [`Unrecognized text: ${details.unrecognized_text.join(", ")}`] : [])] : ["No parser warnings."] },
  ];

  blocks.forEach(b => {
    const div = document.createElement("div");
    div.className = "details-block";
    div.innerHTML = `<h4>${b.title}</h4>` + b.lines.map(l => `<p>${escapeHtml(String(l))}</p>`).join("");
    container.appendChild(div);
  });
}

function renderReportButtons(validationId) {
  const container = document.getElementById("report-buttons");
  container.innerHTML = `
    <a class="btn-secondary" href="/api/report/pdf/${validationId}" target="_blank">Download PDF Report</a>
    <a class="btn-secondary" href="/api/report/csv/${validationId}" target="_blank">Download CSV Export</a>
    <a class="btn-secondary" href="/api/report/qr/${validationId}" target="_blank">View QR Code</a>
    <a class="btn-secondary" href="/api/report/barcode/${validationId}" target="_blank">View Barcode</a>
  `;
}

// ---------- History ----------
async function loadHistory() {
  const q = document.getElementById("history-search").value.trim();
  const status = document.getElementById("history-status-filter").value;
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (status) params.set("status", status);

  const res = await fetch(`/api/history?${params.toString()}`);
  const data = await res.json();

  const tbody = document.querySelector("#history-table tbody");
  tbody.innerHTML = "";
  data.results.forEach(r => {
    const tr = document.createElement("tr");
    const statusClass = r.final_status.replace(/\s+/g, "-");
    tr.innerHTML = `
      <td>${r.validation_id}</td>
      <td>${escapeHtml(r.working_address.city || "—")} / ${escapeHtml(r.working_address.state || "—")}</td>
      <td>${r.confidence_score}%</td>
      <td>${r.risk_level}</td>
      <td><span class="status-pill ${statusClass}">${r.final_status}</span></td>
      <td>${new Date(r.created_at).toLocaleString()}</td>
    `;
    tr.addEventListener("click", () => showHistoryDetail(r.validation_id));
    tbody.appendChild(tr);
  });
}

async function showHistoryDetail(validationId) {
  const res = await fetch(`/api/history/${validationId}`);
  const record = await res.json();

  const card = document.getElementById("history-detail-card");
  card.classList.remove("hidden");
  const content = document.getElementById("history-detail-content");

  content.innerHTML = `
    <p><strong>${record.validation_id}</strong> &middot; ${new Date(record.created_at).toLocaleString()}</p>
    <p>Status: <span class="status-pill ${record.final_status.replace(/\s+/g, '-')}">${record.final_status}</span>
       &nbsp; Confidence: ${record.confidence_score}% &nbsp; Risk: ${record.risk_level}</p>
    <p class="muted">${escapeHtml(record.recommendation)}</p>
    <h4>Raw Input</h4>
    <p class="muted">${escapeHtml(record.raw_input)}</p>
    <div class="input-actions">
      <a class="btn-secondary" href="/api/report/pdf/${record.validation_id}" target="_blank">PDF</a>
      <a class="btn-secondary" href="/api/report/csv/${record.validation_id}" target="_blank">CSV</a>
      <a class="btn-secondary" href="/api/report/qr/${record.validation_id}" target="_blank">QR</a>
      <a class="btn-secondary" href="/api/report/barcode/${record.validation_id}" target="_blank">Barcode</a>
    </div>
  `;
  card.scrollIntoView({ behavior: "smooth" });
}

document.getElementById("history-refresh-btn").addEventListener("click", loadHistory);
document.getElementById("history-search").addEventListener("keydown", e => { if (e.key === "Enter") loadHistory(); });

// ---------- Helpers ----------
function fillList(id, items) {
  const ul = document.getElementById(id);
  ul.innerHTML = "";
  (items && items.length ? items : ["None"]).forEach(text => {
    const li = document.createElement("li");
    li.textContent = text;
    ul.appendChild(li);
  });
}

function humanize(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// ---------- Auth ----------
const logoutBtn = document.getElementById("logout-btn");
if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
  });
}
