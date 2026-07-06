const API =
  document.querySelector('meta[name="api-base"]')?.content?.replace(/\/$/, "") ||
  (window.location.port === "5500" ? "http://localhost:8000" : window.location.origin);

const TIMELINE_STEPS = [
  { id: "auth", label: "Authenticating manager" },
  { id: "understand", label: "Understanding requirements" },
  { id: "structure", label: "Creating structured request" },
  { id: "search", label: "Searching employee database" },
  { id: "skills", label: "Filtering by skills" },
  { id: "availability", label: "Checking availability" },
  { id: "certs", label: "Checking certifications" },
  { id: "projects", label: "Evaluating previous projects" },
  { id: "confidence", label: "Calculating confidence" },
  { id: "rank", label: "Ranking candidates" },
  { id: "explain", label: "Generating explanation" },
];

const APPROVAL_STEPS = [
  { id: "report", label: "Generating approval report" },
  { id: "notes", label: "Adding manager notes" },
  { id: "reasoning", label: "Including reasoning" },
  { id: "pdf", label: "Creating PDF" },
  { id: "download", label: "Preparing download" },
  { id: "done", label: "Completed" },
];

const WEIGHT_PRESETS = {
  "skills-first": {
    label: "Skills-first",
    skills: 45, availability: 20, experience: 15, location: 10, utilization: 10, language: 0,
  },
  "availability-first": {
    label: "Availability-first",
    skills: 25, availability: 40, experience: 15, location: 10, utilization: 10, language: 0,
  },
  "experience-first": {
    label: "Experience-first",
    skills: 20, availability: 20, experience: 40, location: 10, utilization: 10, language: 0,
  },
  balanced: {
    label: "Balanced",
    skills: 35, availability: 20, experience: 20, location: 10, utilization: 10, language: 5,
  },
};

const GERMAN_TO_BACKEND = { none: "none", basic: "A2", business: "B2", native: "native" };
const BACKEND_TO_GERMAN = {
  none: "none", basic: "basic", a1: "basic", a2: "basic", b1: "basic",
  b2: "business", business: "business", c1: "business", c2: "native", native: "native",
};

const EXTRACT_DEBOUNCE_MS = 900;
const EXTRACT_MIN_CHARS = 12;

let extractTimer = null;

const state = {
  token: sessionStorage.getItem("token"),
  username: sessionStorage.getItem("username") || "Manager",
  role: sessionStorage.getItem("role") || "manager",
  view: "request",
  clientMessage: "",
  criteria: null,
  searchConfig: null,
  searchOptions: null,
  modelProviders: null,
  savedCredentials: null,
  selectedSkills: new Set(),
  coreSkills: new Set(),
  candidates: [],
  summary: "",
  meta: null,
  selectedId: null,
  lastReport: null,
  stepStatus: {},
  weightPreset: "balanced",
  lastExtractedPrompt: "",
  extracting: false,
};

function $(id) { return document.getElementById(id); }

function authHeaders() {
  if (!state.token) throw new Error("Please sign in first.");
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${state.token}`,
  };
}

function initials(name) {
  return name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();
}

function matchPercent(candidate) {
  if (candidate.total_score != null) {
    return Math.min(99, Math.round(candidate.total_score));
  }
  if (candidate.skill_match?.match_percent != null) {
    return Math.round(candidate.skill_match.match_percent);
  }
  return 0;
}

const RULE_LABELS = {
  skills: "Skills",
  experience: "Experience",
  location: "Location",
  availability: "Availability",
  utilization: "Capacity",
  language: "Language",
};

function renderScoreBreakdownHtml(breakdown) {
  if (!breakdown?.length) return "";
  const rows = breakdown.map((row) => `
    <tr>
      <td>${escapeHtml(RULE_LABELS[row.rule] || row.rule)}</td>
      <td class="num">${row.raw_score ?? "—"}</td>
      <td class="num">${row.weight_percent ?? "—"}%</td>
      <td class="num weighted">${row.weighted_points ?? row.points ?? 0}</td>
    </tr>`).join("");
  return `
    <div class="score-breakdown">
      <div class="skill-match-header">
        <span class="skill-match-label">Weighted breakdown</span>
        <span class="skill-match-pct">raw × weight = pts</span>
      </div>
      <table class="breakdown-table">
        <thead><tr><th>Dimension</th><th>Raw</th><th>Weight</th><th>Pts</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function renderSkillMatchHtml(skillMatch) {
  if (!skillMatch) return "";
  const matched = (skillMatch.matched_skills || [])
    .map((s) => `<span class="skill-chip skill-matched" title="Direct match">${escapeHtml(s)}</span>`)
    .join("");
  const adjacent = (skillMatch.adjacent_credits || [])
    .map((a) => `<span class="skill-chip skill-adjacent" title="Partial credit: ${escapeHtml(a.required)} via ${escapeHtml(a.via)}">${escapeHtml(a.required)} ← ${escapeHtml(a.via)}</span>`)
    .join("");
  const missing = (skillMatch.missing_skills || [])
    .map((s) => `<span class="skill-chip skill-missing" title="Not matched">${escapeHtml(s)}</span>`)
    .join("");
  const pct = skillMatch.match_percent != null ? Math.round(skillMatch.match_percent) : "—";
  return `
    <div class="skill-match-block">
      <div class="skill-match-header">
        <span class="skill-match-label">Skill fit</span>
        <span class="skill-match-pct">${pct}% weighted</span>
      </div>
      <div class="skill-chips skill-match-chips">${matched}${adjacent}${missing}</div>
    </div>`;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatMarkdown(text) {
  if (!text) return "";
  let s = escapeHtml(text.trim());
  s = s.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>');
  s = s.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>');
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*(.+?)\*/g, "<em>$1</em>");
  const blocks = s.split(/\n{2,}/).map((block) => {
    const trimmed = block.trim();
    if (!trimmed) return "";
    if (/^<h[34]/.test(trimmed)) return trimmed;
    return `<p class="md-p">${trimmed.replace(/\n/g, "<br>")}</p>`;
  });
  return blocks.filter(Boolean).join("");
}

function renderResultsSummary() {
  const el = $("resultsSummary");
  const top = state.candidates[0];
  if (!top) {
    el.innerHTML = `<div class="summary-card"><p class="md-p">No candidates matched this request.</p></div>`;
    return;
  }
  const pct = matchPercent(top);
  el.innerHTML = `
    <div class="summary-card">
      <div class="summary-top">
        <div class="summary-pick">
          <span class="summary-badge">Top recommendation</span>
          <span class="summary-name">${escapeHtml(top.name)}</span>
        </div>
        <div class="summary-scores">
          <span class="summary-score-pill">${top.total_score} <small>pts</small></span>
          <span class="summary-score-pill muted">${pct}% match</span>
        </div>
      </div>
      <div class="summary-body formatted-text">${formatMarkdown(state.summary)}</div>
      ${renderMemoryHtml(top.staffing_memory)}
    </div>`;
}

function confidencePercent(candidate) {
  const skillRule = (candidate.score_breakdown || []).find((r) => r.rule === "skills" || r.rule === "skill_match");
  if (skillRule?.raw_score != null) return Math.round(skillRule.raw_score);
  return matchPercent(candidate);
}

function riskLabel(candidate) {
  const flags = candidate.judgment_flags || [];
  if (flags.some((f) => f.severity === "high")) return "High";
  if (flags.some((f) => f.severity === "medium")) return "Medium";
  if (candidate.status === "bench") return "Low";
  const util = candidate.current_utilization_pct ?? 80;
  if (util < 50) return "Low";
  if (util < 80) return "Medium";
  return "High";
}

function renderJudgmentHtml(flags) {
  if (!flags?.length) return "";
  const chips = flags.map((f) => {
    const cls = f.severity === "high" ? "judgment-high" : f.severity === "medium" ? "judgment-medium" : "judgment-low";
    return `<span class="judgment-chip ${cls}" title="${escapeHtml(f.detail)}">${escapeHtml(f.label)}</span>`;
  }).join("");
  return `<div class="judgment-chips">${chips}</div>`;
}

function renderMemoryHtml(memory) {
  if (!memory?.items?.length && !memory?.summary) return "";
  const items = (memory.items || []).slice(0, 2).map((item) =>
    `<li class="memory-item memory-${item.type}">${escapeHtml(item.label)}</li>`
  ).join("");
  const summary = memory.summary
    ? `<p class="memory-summary">${escapeHtml(memory.summary)}</p>`
    : "";
  return `<div class="staffing-memory">${summary}<ul class="memory-list">${items}</ul></div>`;
}

function managerRating(candidate) {
  const years = candidate.years_experience || 0;
  if (years >= 8) return "4.8";
  if (years >= 5) return "4.5";
  if (years >= 3) return "4.2";
  return "4.0";
}

function populateFieldsFromCriteria(criteria, prompt) {
  applyExtractedFields({
    required_skills: criteria.required_skills,
    core_skills: Object.entries(criteria.skill_weights || {})
      .filter(([, w]) => w >= 2)
      .map(([s]) => s),
    location: criteria.location,
    needed_by: criteria.needed_by,
    role_count: inferConsultants(prompt),
    required_german_level: criteria.required_german_level,
    client_facing: criteria.client_facing,
  }, { showHint: false });
  if (criteria.scoring_weights) applyScoringWeightsToUI(criteria.scoring_weights);
}

function weightPriorityLabel(value) {
  const v = Number(value);
  if (v <= 15) return "Nice to have";
  if (v <= 30) return "Somewhat important";
  if (v <= 50) return "Very important";
  return "Top priority";
}

function updateWeightDisplay(name) {
  const slider = $(`weight${name}`);
  if (!slider) return;
  const val = slider.value;
  const valEl = $(`weight${name}Val`);
  const priEl = $(`weight${name}Priority`);
  if (valEl) valEl.textContent = val;
  if (priEl) priEl.textContent = weightPriorityLabel(val);
}

function applyExtractedFields(data, { showHint = true } = {}) {
  if ($("fieldLocation")) $("fieldLocation").value = data.location || "";
  if ($("fieldStartDate")) $("fieldStartDate").value = data.needed_by || "";
  if (data.required_skills?.length) {
    state.selectedSkills = new Set(data.required_skills);
    const core = data.core_skills?.length ? data.core_skills : data.required_skills;
    state.coreSkills = new Set(core.filter((s) => data.required_skills.includes(s)));
    renderSkillPicker();
  }
  const roleCount = data.role_count ?? inferConsultants($("promptInput")?.value || "");
  set("fieldConsultants", String(roleCount));
  set("fieldRole", inferRole($("promptInput")?.value || ""));
  set("fieldIndustry", inferIndustry($("promptInput")?.value || ""));
  set("fieldWorkMode", inferWorkMode($("promptInput")?.value || ""));
  set("fieldDuration", inferDuration($("promptInput")?.value || ""));
  set("fieldPriority", inferPriority($("promptInput")?.value || ""));

  const germanUi = BACKEND_TO_GERMAN[data.required_german_level] || "none";
  if (data.client_facing && germanUi === "none") {
    $("fieldGermanFluency").value = "business";
  } else if ($("fieldGermanFluency")) {
    $("fieldGermanFluency").value = germanUi;
  }
  syncGermanWeightSlider();

  const hint = $("extractHint");
  const status = $("extractStatus");
  if (status) status.classList.add("hidden");
  if (hint) hint.classList.toggle("hidden", !showHint);
}

function set(id, val) {
  const el = $(id);
  if (el) el.value = val || "";
}

function syncGermanWeightSlider() {
  const level = $("fieldGermanFluency")?.value || "none";
  const on = level !== "none";
  const langSlider = $("weightLanguage");
  if (!langSlider) return;
  langSlider.disabled = !on;
  if (on && Number(langSlider.value) === 0) {
    langSlider.value = 15;
    updateWeightDisplay("Language");
  }
}

function scheduleExtractFromPrompt() {
  clearTimeout(extractTimer);
  const prompt = $("promptInput")?.value.trim() || "";
  const hint = $("extractHint");
  const status = $("extractStatus");

  if (prompt.length < EXTRACT_MIN_CHARS) {
    if (hint) hint.classList.add("hidden");
    if (status) status.classList.add("hidden");
    state.lastExtractedPrompt = "";
    return;
  }

  extractTimer = setTimeout(() => extractFromDescription(prompt), EXTRACT_DEBOUNCE_MS);
}

async function extractFromDescription(prompt) {
  const text = (prompt || $("promptInput")?.value || "").trim();
  if (text.length < EXTRACT_MIN_CHARS) return null;
  if (state.extracting) return null;

  const status = $("extractStatus");
  if (status) status.classList.remove("hidden");

  state.extracting = true;
  try {
    const res = await fetch(`${API}/api/extract-request`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ client_message: text }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (res.status === 428 || String(data.detail || "").includes("credentials")) {
        if (status) status.classList.add("hidden");
        return null;
      }
      throw new Error(data.detail || "Could not read your description");
    }
    state.lastExtractedPrompt = text;
    applyExtractedFields(data, { showHint: true });
    return data;
  } catch (e) {
    if (status) status.classList.add("hidden");
    console.warn("Extract failed:", e.message);
    return null;
  } finally {
    state.extracting = false;
  }
}

function applyWeightPreset(presetId) {
  const preset = WEIGHT_PRESETS[presetId];
  if (!preset) return;
  state.weightPreset = presetId;
  const weights = { ...preset };
  delete weights.label;
  applyScoringWeightsToUI(weights);
  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.preset === presetId);
  });
  const label = $("weightPresetLabel");
  if (label) label.textContent = preset.label;
}

function councilLabel(value) {
  return {
    yes: "Required",
    no: "Not applicable",
    unsure: "Unsure — follow up needed",
    already_notified: "Already notified",
  }[value] || value || "—";
}

async function loadModelProviders() {
  if (state.modelProviders) return state.modelProviders;
  const res = await fetch(`${API}/api/settings/providers`, { headers: authHeaders() });
  if (!res.ok) return null;
  state.modelProviders = await res.json();
  return state.modelProviders;
}

function providerLabel(id) {
  const p = (state.modelProviders?.providers || []).find((x) => x.id === id);
  return p?.label || id;
}

function modelLabel(providerId, modelId) {
  const p = (state.modelProviders?.providers || []).find((x) => x.id === providerId);
  const m = (p?.models || []).find((x) => x.id === modelId);
  return m?.label || modelId;
}

function renderSettingsProviderOptions() {
  const sel = $("settingsProvider");
  if (!sel || !state.modelProviders) return;
  sel.innerHTML = '<option value="">Select provider…</option>'
    + state.modelProviders.providers.map((p) =>
      `<option value="${escapeHtml(p.id)}">${escapeHtml(p.label)}</option>`
    ).join("");
}

function onSettingsProviderChange() {
  const providerId = $("settingsProvider")?.value;
  const modelSel = $("settingsModel");
  if (!modelSel) return;
  const provider = (state.modelProviders?.providers || []).find((p) => p.id === providerId);
  if (!provider) {
    modelSel.innerHTML = '<option value="">Select model…</option>';
    modelSel.disabled = true;
    updateSettingsSaveState();
    return;
  }
  modelSel.disabled = false;
  modelSel.innerHTML = '<option value="">Select model…</option>'
    + provider.models.map((m) =>
      `<option value="${escapeHtml(m.id)}">${escapeHtml(m.label)}</option>`
    ).join("");
  if (state.savedCredentials?.model_name && state.savedCredentials.provider === providerId) {
    modelSel.value = state.savedCredentials.model_name;
  }
  updateSettingsSaveState();
}

function updateSettingsSaveState() {
  const provider = $("settingsProvider")?.value;
  const model = $("settingsModel")?.value;
  const key = $("settingsApiKey")?.value.trim();
  const btn = $("settingsSaveBtn");
  if (btn) btn.disabled = !(provider && model && key.length >= 8);
}

function renderSavedCredentialsDisplay() {
  const el = $("settingsSaved");
  if (!el) return;
  const saved = state.savedCredentials;
  if (!saved?.configured) {
    el.innerHTML = `<p class="empty-state">No provider configured. Add your API key below before running AI searches.</p>`;
    return;
  }
  el.innerHTML = `
    <dl>
      <dt>Provider</dt><dd>${escapeHtml(providerLabel(saved.provider))}</dd>
      <dt>Model</dt><dd>${escapeHtml(modelLabel(saved.provider, saved.model_name))}</dd>
      <dt>API key</dt><dd>key ending in •••• ${escapeHtml(saved.key_last4)}</dd>
    </dl>`;
}

async function loadSettings() {
  showView("settings");
  $("settingsStatus").textContent = "";
  $("settingsStatus").className = "settings-status";
  await loadModelProviders();
  renderSettingsProviderOptions();

  try {
    const res = await fetch(`${API}/api/settings/credentials`, { headers: authHeaders() });
    if (res.ok) {
      state.savedCredentials = await res.json();
    }
  } catch {
    state.savedCredentials = { configured: false };
  }

  renderSavedCredentialsDisplay();
  if (state.savedCredentials?.configured) {
    $("settingsProvider").value = state.savedCredentials.provider;
    onSettingsProviderChange();
  }
  $("settingsApiKey").value = "";
  updateSettingsSaveState();
  await loadComplianceGuide();
}

function renderComplianceGuide(data) {
  const zdr = data?.zdr || {};
  const banner = $("zdrWarningBanner");
  if (banner) {
    banner.classList.toggle("hidden", Boolean(zdr.all_confirmed));
    const parts = [];
    if (!zdr.anthropic_zdr_confirmed) parts.push("Anthropic");
    if (!zdr.groq_zdr_confirmed) parts.push("Groq");
    const hint = $("zdrWarningText");
    if (hint && parts.length) {
      hint.textContent =
        `Server confirmation pending for: ${parts.join(" and ")}. ` +
        "These .env flags are a compliance checklist — the app cannot verify ZDR automatically.";
    }
    const instructions = $("zdrInstructions");
    if (instructions) {
      instructions.classList.remove("hidden");
      const blocks = [];
      if (!zdr.anthropic_zdr_confirmed && zdr.anthropic_zdr_how_to) {
        blocks.push(`<p><strong>Anthropic:</strong> ${escapeHtml(zdr.anthropic_zdr_how_to)}</p>`);
      }
      if (!zdr.groq_zdr_confirmed && zdr.groq_zdr_how_to) {
        blocks.push(`<p><strong>Groq:</strong> ${escapeHtml(zdr.groq_zdr_how_to)}</p>`);
      }
      if (zdr.verification_note) {
        blocks.push(`<p class="field-hint">${escapeHtml(zdr.verification_note)}</p>`);
      }
      blocks.push(
        "<p class=\"field-hint\">After your team confirms each arrangement, set " +
        "<code>ANTHROPIC_ZDR_CONFIRMED=true</code> and/or <code>GROQ_ZDR_CONFIRMED=true</code> in server <code>.env</code> and restart the API.</p>"
      );
      instructions.innerHTML = blocks.join("");
    }
  }

  const flow = data?.data_flow || {};
  const workflow = flow.workflow || [];
  $("llmWorkflowList").innerHTML = workflow
    .map((step) => `<li>${escapeHtml(step)}</li>`)
    .join("");

  const sent = flow.sent_to_llm || {};
  $("llmSentData").innerHTML = Object.entries(sent).map(([task, fields]) => `
    <h4 class="privacy-task">${escapeHtml(task.replace(/_/g, " "))}</h4>
    <ul class="guide-list">${fields.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>
  `).join("");

  const never = flow.never_sent_to_llm || [];
  $("llmNeverSent").innerHTML = never.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

async function loadComplianceGuide() {
  try {
    const res = await fetch(`${API}/api/settings/compliance`, { headers: authHeaders() });
    if (!res.ok) return;
    renderComplianceGuide(await res.json());
  } catch {
    /* settings page still usable without compliance block */
  }
}

async function saveModelSettings() {
  const provider = $("settingsProvider").value;
  const model_name = $("settingsModel").value;
  const api_key = $("settingsApiKey").value.trim();
  const status = $("settingsStatus");
  status.textContent = "Saving…";
  status.className = "settings-status";

  try {
    const res = await fetch(`${API}/api/settings/credentials`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ provider, model_name, api_key }),
    });
    const data = await res.json();
    if (!res.ok) {
      status.textContent = data.detail || "Save failed";
      status.className = "settings-status err";
      return;
    }
    state.savedCredentials = data;
    $("settingsApiKey").value = "";
    renderSavedCredentialsDisplay();
    updateSettingsSaveState();
    status.textContent = "Configuration saved.";
    status.className = "settings-status ok";
  } catch (e) {
    status.textContent = e.message;
    status.className = "settings-status err";
  }
}

async function loadSearchOptions() {
  try {
    const res = await fetch(`${API}/search-options`, { headers: authHeaders() });
    if (!res.ok) return;
    state.searchOptions = await res.json();
    const locSel = $("fieldLocation");
    if (locSel && state.searchOptions.locations) {
      locSel.innerHTML = '<option value="">Any location</option>'
        + state.searchOptions.locations.map((l) => `<option value="${escapeHtml(l)}">${escapeHtml(l)}</option>`).join("");
    }
    if (state.searchOptions.default_scoring_weights) {
      applyWeightPreset("balanced");
    }
    renderSkillPicker();
  } catch { /* login required */ }
}

function renderSkillPicker() {
  const el = $("skillPicker");
  if (!el || !state.searchOptions?.skills) return;
  el.innerHTML = state.searchOptions.skills.map((skill) => {
    const selected = state.selectedSkills.has(skill);
    const core = state.coreSkills.has(skill);
    return `
      <div class="skill-pick ${selected ? "selected" : ""}" data-skill="${escapeHtml(skill)}">
        <label class="skill-pick-label">
          <input type="checkbox" class="skill-check" data-skill="${escapeHtml(skill)}" ${selected ? "checked" : ""}>
          <span>${escapeHtml(skill)}</span>
        </label>
        <button type="button" class="core-toggle ${core ? "is-core" : ""}" data-skill="${escapeHtml(skill)}" title="Toggle core (2×) vs nice-to-have (1×)" ${selected ? "" : "disabled"}>★</button>
      </div>`;
  }).join("");

  el.querySelectorAll(".skill-check").forEach((cb) => {
    cb.addEventListener("change", () => {
      const skill = cb.dataset.skill;
      if (cb.checked) {
        state.selectedSkills.add(skill);
        state.coreSkills.add(skill);
      } else {
        state.selectedSkills.delete(skill);
        state.coreSkills.delete(skill);
      }
      renderSkillPicker();
    });
  });
  el.querySelectorAll(".core-toggle").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const skill = btn.dataset.skill;
      if (state.coreSkills.has(skill)) state.coreSkills.delete(skill);
      else state.coreSkills.add(skill);
      renderSkillPicker();
    });
  });
}

function applyScoringWeightsToUI(weights) {
  const map = {
    skills: "Skills",
    availability: "Availability",
    experience: "Experience",
    location: "Location",
    utilization: "Utilization",
    language: "Language",
  };
  Object.entries(map).forEach(([key, name]) => {
    const slider = $(`weight${name}`);
    if (slider && weights[key] != null) {
      slider.value = weights[key];
      updateWeightDisplay(name);
    }
  });
}

function collectScoringWeights() {
  return {
    skills: Number($("weightSkills")?.value || 40),
    availability: Number($("weightAvailability")?.value || 25),
    experience: Number($("weightExperience")?.value || 15),
    location: Number($("weightLocation")?.value || 10),
    utilization: Number($("weightUtilization")?.value || 10),
    language: Number($("weightLanguage")?.value || 0),
  };
}

function collectSearchConfig() {
  const required_skills = [...state.selectedSkills];
  const core_skills = [...state.coreSkills].filter((s) => state.selectedSkills.has(s));
  const location = $("fieldLocation")?.value || null;
  const needed_by = $("fieldStartDate")?.value || null;
  const germanUi = $("fieldGermanFluency")?.value || "none";
  const client_facing = germanUi !== "none";
  const required_german_level = client_facing ? (GERMAN_TO_BACKEND[germanUi] || "B2") : null;
  return {
    required_skills: required_skills.length ? required_skills : undefined,
    core_skills: core_skills.length ? core_skills : undefined,
    location: location || null,
    needed_by: needed_by || null,
    client_facing,
    required_german_level,
    scoring_weights: collectScoringWeights(),
    works_council_notification: $("fieldWorksCouncil")?.value || "no",
  };
}

function bindWeightSliders() {
  ["Skills", "Availability", "Experience", "Location", "Utilization", "Language"].forEach((name) => {
    const slider = $(`weight${name}`);
    if (!slider) return;
    slider.addEventListener("input", () => {
      updateWeightDisplay(name);
      state.weightPreset = "custom";
      const label = $("weightPresetLabel");
      if (label) label.textContent = "Custom";
      document.querySelectorAll(".preset-btn").forEach((btn) => btn.classList.remove("active"));
    });
  });
}

function bindWeightPresets() {
  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => applyWeightPreset(btn.dataset.preset));
  });
}

function bindPromptExtract() {
  const input = $("promptInput");
  if (!input) return;
  input.addEventListener("input", scheduleExtractFromPrompt);
  input.addEventListener("blur", () => {
    clearTimeout(extractTimer);
    const prompt = input.value.trim();
    if (prompt.length >= EXTRACT_MIN_CHARS && prompt !== state.lastExtractedPrompt) {
      extractFromDescription(prompt);
    }
  });
}

function inferRole(text) {
  const m = text.match(/\b(Senior|Junior|Lead|Principal)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Engineer)/i);
  return m ? m[0].trim() : "";
}
function inferExperience(text) {
  const m = text.match(/(\d+)\+?\s*years?/i);
  return m ? `${m[1]}+ years` : "";
}
function inferIndustry(text) {
  const industries = ["healthcare", "finance", "retail", "manufacturing", "automotive"];
  const found = industries.find((i) => text.toLowerCase().includes(i));
  return found ? found.charAt(0).toUpperCase() + found.slice(1) : "";
}
function inferWorkMode(text) {
  const t = text.toLowerCase();
  if (t.includes("remote")) return "Remote";
  if (t.includes("hybrid")) return "Hybrid";
  if (t.includes("onsite") || t.includes("on-site")) return "On-site";
  return "Hybrid";
}
function inferDuration(text) {
  const m = text.match(/(\d+)\s*(month|months|week|weeks)/i);
  return m ? m[0] : "";
}
function inferPriority(text) {
  const t = text.toLowerCase();
  if (t.includes("urgent") || t.includes("asap")) return "High";
  if (t.includes("low priority")) return "Low";
  return "Medium";
}
function inferCerts(text) {
  const certs = ["ISO 26262", "Azure", "AWS", "Kubernetes"];
  return certs.filter((c) => text.includes(c)).join(", ");
}
function inferConsultants(text) {
  const m = text.match(/(\d+)\s+(consultants?|engineers?|developers?)/i);
  return m ? m[1] : "1";
}

function renderTimelines() {
  renderTimeline(TIMELINE_STEPS, "agentTimeline");
  if ($("monitorTimeline")) renderTimeline(TIMELINE_STEPS, "monitorTimeline");
}

function renderTimeline(steps, containerId) {
  const el = $(containerId);
  if (!el) return;
  el.innerHTML = steps.map((step) => {
    const status = state.stepStatus[step.id] || "pending";
    const icon = status === "completed" ? "✓" : status === "running" ? "◌" : status === "failed" ? "!" : "·";
    const chip = status === "completed" ? "chip-green" : status === "running" ? "chip-blue" : status === "failed" ? "chip-orange" : "";
    const cls = status === "completed" ? "done" : status === "running" ? "active" : "";
    return `
      <div class="timeline-item ${cls}" data-step="${step.id}">
        <div class="timeline-icon">${icon}</div>
        <div class="timeline-label">${step.label}</div>
        ${chip ? `<span class="chip ${chip}">${status}</span>` : ""}
      </div>`;
  }).join("");
}

function updateAgentStats(meta) {
  if (!meta) return;
  $("statTime").textContent = `${(meta.execution_time_ms / 1000).toFixed(1)}s`;
  $("statConfidence").textContent = `${Math.round(meta.confidence * 100)}%`;
  $("statTools").textContent = (meta.tools_used || []).join(", ");
  $("statDocs").textContent = String(meta.documents_retrieved || 0);
  $("statReasoning").textContent = `${meta.reasoning_score || 0}%`;
}

function scoreRingSvg(percent, centerValue, centerLabel) {
  const r = 30;
  const c = 2 * Math.PI * r;
  const offset = c - (percent / 100) * c;
  return `
    <div class="score-ring">
      <svg width="72" height="72" viewBox="0 0 72 72">
        <circle cx="36" cy="36" r="${r}" fill="none" stroke="#e8eaed" stroke-width="5"/>
        <circle cx="36" cy="36" r="${r}" fill="none" stroke="#2563eb" stroke-width="5"
          stroke-dasharray="${c}" stroke-dashoffset="${offset}" stroke-linecap="round"/>
      </svg>
      <div class="score-ring-text">
        <span class="score-value">${centerValue}</span>
        <span class="score-label">${centerLabel}</span>
      </div>
    </div>`;
}

function renderCandidateCards() {
  const top3 = state.candidates.slice(0, 3);
  if (!top3.length) {
    $("candidateCards").innerHTML = `<p style="color:var(--text-secondary)">No candidates matched this request.</p>`;
    return;
  }

  if (!state.selectedId && top3[0]) state.selectedId = top3[0].employee_id;

  $("candidateCards").innerHTML = top3.map((c) => {
    const pct = matchPercent(c);
    const selected = c.employee_id === state.selectedId ? "selected" : "";
    const availClass = c.status === "bench" ? "status-bench" : "status-available";
    const availText = c.status === "bench" ? "On Bench" : `Available ${c.available_from}`;
    const reason = buildReason(c);
    const risk = riskLabel(c);
    const riskClass = risk === "Low" ? "risk-low" : risk === "Medium" ? "risk-medium" : "risk-high";
    return `
      <article class="candidate-card ${selected}" data-id="${c.employee_id}" onclick="selectCandidate(${c.employee_id})">
        ${scoreRingSvg(pct, c.total_score, "pts")}
        <div class="candidate-main">
          <div class="candidate-header">
            <div class="candidate-photo">${initials(c.name)}</div>
            <div>
              <div class="candidate-name">${escapeHtml(c.name)}</div>
              <div class="candidate-role">${escapeHtml(c.title || "Engineer")} · ${escapeHtml(c.department || "—")}</div>
            </div>
          </div>
          <dl class="meta-grid">
            <dt>Experience</dt><dd>${c.years_experience} years</dd>
            <dt>Location</dt><dd>${escapeHtml(c.location)}</dd>
            <dt>Confidence</dt><dd>${confidencePercent(c)}%</dd>
            <dt>Risk</dt><dd><span class="risk-chip ${riskClass}">${risk}</span></dd>
            <dt>Manager Rating</dt><dd>${managerRating(c)} / 5</dd>
            <dt>German</dt><dd><span class="fluency-chip">${escapeHtml(c.german_fluency || "none")}</span></dd>
            <dt>Match</dt><dd>${matchPercent(c)}% · ${c.total_score} pts</dd>
          </dl>
          ${renderSkillMatchHtml(c.skill_match)}
          ${renderScoreBreakdownHtml(c.score_breakdown)}
          ${renderJudgmentHtml(c.judgment_flags)}
          ${renderMemoryHtml(c.staffing_memory)}
          <div class="reason-box">${escapeHtml(reason)}</div>
          <span class="status-pill ${availClass}">${availText}</span>
        </div>
        <div class="candidate-action">
          <button class="btn btn-secondary" type="button" onclick="event.stopPropagation();viewEmployeeProfile(${c.employee_id})">View Full Profile</button>
        </div>
      </article>`;
  }).join("");

  renderComparisonTable(top3);
}

function buildReason(c) {
  const skillRule = (c.score_breakdown || []).find((r) => r.rule === "skills" || r.rule === "skill_match");
  if (skillRule?.detail) return skillRule.detail;
  const parts = (c.score_breakdown || []).map((r) => r.detail).filter(Boolean);
  if (parts.length) return parts.slice(0, 2).join(" ");
  return "Strong match based on skills, experience, and availability.";
}

function renderComparisonTable(candidates) {
  const rows = candidates.map((c) => {
    const sel = c.employee_id === state.selectedId ? "selected-row" : "";
    return `<tr class="${sel}">
      <td onclick="selectCandidate(${c.employee_id})"><strong>${c.name}</strong></td>
      <td onclick="selectCandidate(${c.employee_id})">${matchPercent(c)}%</td>
      <td onclick="selectCandidate(${c.employee_id})">${c.available_from}</td>
      <td onclick="selectCandidate(${c.employee_id})">${c.years_experience} yrs</td>
      <td onclick="selectCandidate(${c.employee_id})">${inferCerts((c.skills || []).join(" ")) || "—"}</td>
      <td onclick="selectCandidate(${c.employee_id})">${riskLabel(c)}</td>
      <td onclick="selectCandidate(${c.employee_id})">${managerRating(c)}</td>
      <td onclick="selectCandidate(${c.employee_id})">${confidencePercent(c)}%</td>
      <td class="report-actions-cell">
        <button class="btn btn-ghost btn-sm" type="button" onclick="viewEmployeeProfile(${c.employee_id})">Profile</button>
      </td>
    </tr>`;
  }).join("");

  $("comparisonBody").innerHTML = rows;
}

window.selectCandidate = function (id) {
  state.selectedId = id;
  renderCandidateCards();
};

async function downloadAuthenticatedFile(url, fallbackFilename) {
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${state.token}` },
  });
  if (!res.ok) {
    let detail = "Download failed.";
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  const blob = await res.blob();
  if (!blob.size) throw new Error("Downloaded file is empty.");

  let filename = fallbackFilename;
  const disposition = res.headers.get("Content-Disposition");
  if (disposition) {
    const match = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
    if (match) filename = decodeURIComponent(match[1].replace(/"/g, ""));
  }

  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  setTimeout(() => {
    document.body.removeChild(anchor);
    URL.revokeObjectURL(objectUrl);
  }, 250);
}

function renderEmployeeProfileModal(profile) {
  const statusLabel = profile.status === "bench" ? "On bench" : profile.status || "—";
  const benchHtml = profile.bench
    ? `<div class="profile-bench-alert"><strong>Bench status:</strong> ${escapeHtml(profile.bench.reason)}
        ${profile.bench.since ? `<br>Since: ${escapeHtml(profile.bench.since)}` : ""}</div>`
    : "";

  const skillsHtml = profile.skills?.length
    ? `<table class="profile-table"><thead><tr><th>Skill</th><th>Level</th><th>Years</th></tr></thead><tbody>
        ${profile.skills.map((s) => `<tr><td>${escapeHtml(s.skill_name)}</td><td>${escapeHtml(s.proficiency_level || "—")}</td><td>${s.years_used ?? "—"}</td></tr>`).join("")}
        </tbody></table>`
    : "<p class='empty-state'>No skills recorded.</p>";

  const certsHtml = profile.certifications?.length
    ? `<table class="profile-table"><thead><tr><th>Certification</th><th>Issuer</th><th>Issued</th></tr></thead><tbody>
        ${profile.certifications.map((c) => `<tr><td>${escapeHtml(c.cert_name)}</td><td>${escapeHtml(c.issuing_body || "—")}</td><td>${escapeHtml(c.issued_date || "—")}</td></tr>`).join("")}
        </tbody></table>`
    : "<p class='empty-state'>No certifications on file.</p>";

  const projects = [
    ...(profile.project_allocations || []).map((p) => ({
      name: p.project_name,
      client: p.client_name,
      role: p.role_on_project,
      dates: `${p.start_date || "—"} → ${p.end_date || "ongoing"}`,
      status: p.status,
    })),
    ...(profile.project_history || []).map((p) => ({
      name: p.role_title || "Project",
      client: p.client_name,
      role: p.domain,
      dates: `${p.start_date} → ${p.end_date}`,
      status: "completed",
    })),
  ];

  const projectsHtml = projects.length
    ? `<table class="profile-table"><thead><tr><th>Project</th><th>Client</th><th>Role</th><th>Period</th></tr></thead><tbody>
        ${projects.map((p) => `<tr><td>${escapeHtml(p.name || "—")}</td><td>${escapeHtml(p.client || "—")}</td><td>${escapeHtml(p.role || "—")}</td><td>${escapeHtml(p.dates)}</td></tr>`).join("")}
        </tbody></table>`
    : "<p class='empty-state'>No project history.</p>";

  $("profileModalTitle").textContent = `${profile.name} (#${profile.employee_id})`;
  $("profileModalBody").innerHTML = `
    ${benchHtml}
    <div class="profile-section">
      <h4>Personal &amp; employment</h4>
      <dl class="profile-grid">
        <dt>Employee ID</dt><dd>${profile.employee_id}</dd>
        <dt>Email</dt><dd>${escapeHtml(profile.email || "—")}</dd>
        <dt>Title</dt><dd>${escapeHtml(profile.title || "—")}</dd>
        <dt>Department</dt><dd>${escapeHtml(profile.department || "—")}</dd>
        <dt>Location</dt><dd>${escapeHtml(profile.location || "—")}${profile.country ? `, ${escapeHtml(profile.country)}` : ""}</dd>
        <dt>Employment</dt><dd>${escapeHtml(profile.employment_type || "—")}</dd>
        <dt>Seniority</dt><dd>${escapeHtml(profile.seniority_level || "—")}</dd>
        <dt>Hire date</dt><dd>${escapeHtml(profile.hire_date || "—")}</dd>
        <dt>Experience</dt><dd>${profile.years_experience ?? "—"} years</dd>
        <dt>Status</dt><dd>${escapeHtml(statusLabel)}</dd>
        <dt>Utilization</dt><dd>${profile.current_utilization_pct ?? "—"}%</dd>
        <dt>Available from</dt><dd>${escapeHtml(profile.available_from || "—")}</dd>
        <dt>German</dt><dd>${escapeHtml(profile.german_fluency || "none")}</dd>
        <dt>English</dt><dd>${escapeHtml(profile.english_fluency || "—")}</dd>
        <dt>Last rating</dt><dd>${escapeHtml(profile.last_performance_rating || "—")}</dd>
      </dl>
    </div>
    <div class="profile-section"><h4>Skills</h4>${skillsHtml}</div>
    <div class="profile-section"><h4>Certifications</h4>${certsHtml}</div>
    <div class="profile-section"><h4>Project history</h4>${projectsHtml}</div>`;
}

window.viewEmployeeProfile = async function (employeeId) {
  const modal = $("employeeProfileModal");
  if (!modal) return;
  modal.classList.remove("hidden");
  $("profileModalBody").innerHTML = "<p class='empty-state'>Loading profile…</p>";
  try {
    const res = await fetch(`${API}/api/employees/${employeeId}/profile`, {
      headers: authHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not load profile");
    renderEmployeeProfileModal(data);
  } catch (e) {
    $("profileModalBody").innerHTML = `<p class='empty-state'>${escapeHtml(e.message)}</p>`;
  }
};

function closeEmployeeProfileModal() {
  $("employeeProfileModal")?.classList.add("hidden");
}

function showView(view) {
  state.view = view;
  const views = ["request", "loading", "results", "approval-loading", "success", "history", "dashboard", "reports", "monitor", "settings"];
  views.forEach((v) => {
    const el = $(`view${v.charAt(0).toUpperCase()}${v.slice(1).replace(/-([a-z])/g, (_, c) => c.toUpperCase())}`);
    if (el) el.classList.toggle("hidden", view !== v);
  });

  document.querySelectorAll(".nav-item[data-view]").forEach((btn) => {
    const navView = btn.dataset.view;
    const active = navView === view
      || (view === "results" && navView === "request")
      || (view === "history" && navView === "reports");
    btn.classList.toggle("active", active);
  });

  document.querySelector(".agent-panel")?.classList.toggle("hidden-panel", ["dashboard", "history", "reports", "monitor", "settings"].includes(view));
  document.querySelector(".workspace")?.classList.toggle("full-width", ["dashboard", "history", "reports", "monitor", "settings"].includes(view));
}

async function login() {
  const username = $("loginUser").value.trim();
  const password = $("loginPass").value;
  const res = await fetch(`${API}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    $("loginError").textContent = "Invalid credentials.";
    return;
  }
  const data = await res.json();
  state.token = data.token;
  sessionStorage.setItem("token", data.token);
  sessionStorage.setItem("username", username);
  $("profileName").textContent = username;
  $("profileInitials").textContent = initials(username);
  $("loginOverlay").classList.add("hidden");
  loadSearchOptions();
}

function logout() {
  sessionStorage.clear();
  state.token = null;
  location.reload();
}

function animateProgress(target) {
  const bar = $("loadingProgress");
  let w = 0;
  const iv = setInterval(() => {
    w = Math.min(target, w + Math.random() * 12);
    bar.style.width = `${w}%`;
    if (w >= target) clearInterval(iv);
  }, 200);
}

async function findCandidates() {
  const prompt = $("promptInput").value.trim();
  if (!prompt) return alert("Describe your staffing requirement first.");
  if (prompt !== state.lastExtractedPrompt) {
    await extractFromDescription(prompt);
  }
  state.clientMessage = prompt;
  state.searchConfig = collectSearchConfig();
  state.stepStatus = {};
  TIMELINE_STEPS.forEach((s) => { state.stepStatus[s.id] = "pending"; });
  renderTimelines();
  showView("loading");
  $("loadingProgress").style.width = "0%";
  animateProgress(85);

  try {
    const res = await fetch(`${API}/agent-search`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        client_message: prompt,
        model: "claude-sonnet-4-6",
        search_config: state.searchConfig,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || "Search failed");
      showView("request");
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);

        if (event.type === "step") {
          state.stepStatus[event.id] = event.status === "completed" ? "completed" : event.status;
          renderTimelines();
        } else if (event.type === "criteria") {
          state.criteria = event.criteria;
          state.searchConfig = {
            required_skills: event.criteria.required_skills,
            core_skills: Object.entries(event.criteria.skill_weights || {})
              .filter(([, w]) => w >= 2).map(([s]) => s),
            location: event.criteria.location,
            needed_by: event.criteria.needed_by,
            scoring_weights: event.criteria.scoring_weights,
            client_facing: event.criteria.client_facing,
            required_german_level: event.criteria.required_german_level,
          };
          populateFieldsFromCriteria(event.criteria, prompt);
        } else if (event.type === "candidates") {
          state.candidates = event.candidates || [];
          state.summary = event.summary || "";
          state.meta = event.meta || state.meta;
          if (state.candidates[0]) state.selectedId = state.candidates[0].employee_id;
        } else if (event.type === "meta") {
          state.meta = event;
          updateAgentStats(event);
        } else if (event.type === "error") {
          const msg = event.message || "Search failed";
          if (msg.includes("credentials") || msg.includes("Model Settings")) {
            alert(msg + "\n\nOpen Settings to configure your AI provider.");
            showView("settings");
            loadSettings();
          } else {
            alert(msg);
            showView("request");
          }
          return;
        }
      }
    }

    $("loadingProgress").style.width = "100%";
    await new Promise((r) => setTimeout(r, 400));
    renderCandidateCards();
    renderResultsSummary();
    showView("results");
  } catch (e) {
    alert(e.message);
    showView("request");
  }
}

async function rejectRecommendation() {
  if (!state.selectedId) return alert("Select a candidate first.");
  const candidate = state.candidates.find((c) => c.employee_id === state.selectedId);
  if (!candidate) return alert("Candidate not found.");
  const notes = $("managerNotes")?.value.trim() || "";
  if (!confirm(`Reject ${candidate.name} for this staffing request?`)) return;

  try {
    const res = await fetch(`${API}/reject`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        employee_id: state.selectedId,
        client_message: state.clientMessage,
        manager_notes: notes,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || "Rejection failed");
      return;
    }
    state.candidates = state.candidates.filter((c) => c.employee_id !== state.selectedId);
    state.selectedId = state.candidates[0]?.employee_id || null;
    if (state.candidates.length) {
      renderCandidateCards();
      renderResultsSummary();
    } else {
      showView("request");
    }
  } catch (e) {
    alert(e.message);
  }
}

async function approveRecommendation() {
  if (!state.selectedId) return alert("Select a candidate first.");
  const council = $("fieldWorksCouncil")?.value || "no";
  if (council === "unsure") {
    showBetriebsratModal((answer) => submitApproval(answer));
    return;
  }
  submitApproval(council);
}

function showBetriebsratModal(onAnswer) {
  const modal = $("betriebsratModal");
  if (!modal) return onAnswer("unsure");
  modal.classList.remove("hidden");
  modal.querySelectorAll("[data-council]").forEach((btn) => {
    btn.onclick = () => {
      modal.classList.add("hidden");
      onAnswer(btn.dataset.council);
    };
  });
}

async function submitApproval(worksCouncilNotification) {
  state.stepStatus = {};
  APPROVAL_STEPS.forEach((s) => { state.stepStatus[s.id] = "pending"; });
  showView("approval-loading");
  renderTimeline(APPROVAL_STEPS, "approvalTimeline");

  const advance = async (id) => {
    state.stepStatus[id] = "running";
    renderTimeline(APPROVAL_STEPS, "approvalTimeline");
    await new Promise((r) => setTimeout(r, 350));
    state.stepStatus[id] = "completed";
    renderTimeline(APPROVAL_STEPS, "approvalTimeline");
  };

  try {
    await advance("report");
    await advance("notes");

    const res = await fetch(`${API}/approve`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        employee_id: state.selectedId,
        client_message: state.clientMessage,
        manager_notes: $("managerNotes").value.trim(),
        search_config: state.searchConfig,
        works_council_notification: worksCouncilNotification,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      const detail = err.detail || "Approval failed";
      if (res.status === 428 || String(detail).includes("credentials")) {
        alert(detail + "\n\nOpen Settings to configure your AI provider.");
        loadSettings();
      } else {
        alert(detail);
        showView("results");
      }
      return;
    }

    await advance("reasoning");
    await advance("pdf");
    await advance("download");

    const report = await res.json();
    state.lastReport = report;
    await advance("done");

    renderSuccessReport(report);
    showView("success");
  } catch (e) {
    alert(e.message);
    showView("results");
  }
}

function renderSuccessReport(report) {
  $("successEmployee").textContent = report.employee_name;
  $("successApprover").textContent = report.approved_by;
  $("successTime").textContent = new Date(report.approved_at).toLocaleString();
  $("successConfidence").textContent = `${matchPercent({ total_score: report.total_score })}%`;
  $("successSummary").innerHTML = formatMarkdown(report.fit_summary || "");
  const breakdown = report.score_breakdown || [];
  $("successReasoning").innerHTML = breakdown.length
    ? breakdown.map((r) => `
        <div class="reasoning-row">
          <span class="reasoning-points">+${r.weighted_points ?? r.points ?? 0}</span>
          <div>
            <div class="reasoning-rule">${escapeHtml(RULE_LABELS[r.rule] || r.rule.replace(/_/g, " "))}</div>
            <div class="reasoning-detail">${escapeHtml(r.detail)}${r.raw_score != null ? ` (raw ${r.raw_score} × ${r.weight_percent}%)` : ""}</div>
          </div>
        </div>`).join("")
    : "<p class='md-p'>No breakdown available.</p>";
  $("successNotes").textContent = report.manager_notes || "No additional notes.";
  $("successCouncil").textContent = councilLabel(report.works_council_notification);
}

async function downloadPdf() {
  if (!state.lastReport?.report_id) {
    alert("No report available to download.");
    return;
  }
  try {
    await downloadAuthenticatedFile(
      `${API}/reports/${state.lastReport.report_id}/pdf`,
      `staffing-report-${state.lastReport.report_id}.pdf`,
    );
  } catch (e) {
    alert(e.message);
  }
}

function exportJson() {
  if (!state.lastReport) return;
  const blob = new Blob([JSON.stringify(state.lastReport, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `staffing-report-${state.lastReport.report_id}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function shareInternally() {
  if (!state.lastReport) return;
  const text = `Staffing approval #${state.lastReport.report_id}: ${state.lastReport.employee_name} approved by ${state.lastReport.approved_by}`;
  navigator.clipboard.writeText(text).then(() => alert("Summary copied to clipboard."));
}

async function loadHistory() {
  showView("history");
  try {
    const res = await fetch(`${API}/reports`, { headers: authHeaders() });
    const data = await res.json();
    const reports = data.reports || [];
    $("historyList").innerHTML = reports.length
      ? reports.map((r) => historyItemHtml(r)).join("")
      : "<p class='empty-state'>No approvals yet.</p>";
  } catch {
    $("historyList").innerHTML = "<p class='empty-state'>Could not load history.</p>";
  }
}

function historyItemHtml(r) {
  return `
    <div class="history-item" onclick="openReport(${r.report_id})">
      <div>
        <strong>#${r.report_id} · ${escapeHtml(r.employee_name)}</strong>
        <div class="history-meta">${escapeHtml(r.approved_by)} · ${new Date(r.approved_at).toLocaleString()}</div>
      </div>
      <span class="chip chip-green">${r.total_score} pts</span>
    </div>`;
}

async function loadDashboard() {
  showView("dashboard");
  try {
    const res = await fetch(`${API}/reports`, { headers: authHeaders() });
    const data = await res.json();
    const reports = data.reports || [];
    const avgScore = reports.length
      ? Math.round(reports.reduce((s, r) => s + (r.total_score || 0), 0) / reports.length)
      : 0;
    $("dashboardStats").innerHTML = `
      <div class="stat-card"><span class="stat-label">Total Approvals</span><span class="stat-value">${reports.length}</span></div>
      <div class="stat-card"><span class="stat-label">Avg Match Score</span><span class="stat-value">${avgScore || "—"}</span></div>
      <div class="stat-card"><span class="stat-label">Last Search</span><span class="stat-value">${state.candidates.length ? state.candidates.length + " candidates" : "—"}</span></div>
      <div class="stat-card"><span class="stat-label">Agent Confidence</span><span class="stat-value">${state.meta ? Math.round(state.meta.confidence * 100) + "%" : "—"}</span></div>`;
    $("dashboardRecent").innerHTML = reports.slice(0, 5).length
      ? reports.slice(0, 5).map((r) => historyItemHtml(r)).join("")
      : "<p class='empty-state'>No recent approvals. Create a staffing request to get started.</p>";
  } catch {
    $("dashboardStats").innerHTML = "<p class='empty-state'>Could not load dashboard.</p>";
  }
}

async function loadReports() {
  showView("reports");
  try {
    const res = await fetch(`${API}/reports`, { headers: authHeaders() });
    const data = await res.json();
    const reports = data.reports || [];
    $("reportsBody").innerHTML = reports.length
      ? reports.map((r) => `
          <tr>
            <td>#${r.report_id}</td>
            <td><strong>${escapeHtml(r.employee_name)}</strong></td>
            <td>${escapeHtml(r.approved_by)}</td>
            <td>${new Date(r.approved_at).toLocaleDateString()}</td>
            <td>${r.total_score} pts</td>
            <td class="report-actions-cell">
              <button class="btn btn-secondary btn-sm" type="button" onclick="openReport(${r.report_id})">View</button>
              <button class="btn btn-ghost btn-sm" type="button" onclick="downloadReportPdf(${r.report_id})">PDF</button>
            </td>
          </tr>`).join("")
      : `<tr><td colspan="6" class="empty-state">No reports generated yet.</td></tr>`;
  } catch {
    $("reportsBody").innerHTML = `<tr><td colspan="6" class="empty-state">Could not load reports.</td></tr>`;
  }
}

function loadMonitor() {
  showView("monitor");
  renderTimelines();
  const meta = state.meta;
  $("monitorMetrics").innerHTML = meta ? `
    <div class="metric-card"><span>Execution Time</span><strong>${(meta.execution_time_ms / 1000).toFixed(1)}s</strong></div>
    <div class="metric-card"><span>Confidence</span><strong>${Math.round(meta.confidence * 100)}%</strong></div>
    <div class="metric-card"><span>Documents</span><strong>${meta.documents_retrieved || 0}</strong></div>
    <div class="metric-card"><span>Reasoning</span><strong>${meta.reasoning_score || 0}%</strong></div>`
    : `<p class="empty-state">Run a staffing search to populate agent metrics.</p>`;
  const tools = meta?.tools_used || ["extract_criteria", "search_people", "rank_scorer", "generate_summary"];
  $("monitorTools").innerHTML = tools.map((t) => `<span class="tool-pill">${escapeHtml(t)}</span>`).join("");
}

window.downloadReportPdf = async function (reportId) {
  try {
    await downloadAuthenticatedFile(
      `${API}/reports/${reportId}/pdf`,
      `staffing-report-${reportId}.pdf`,
    );
  } catch (e) {
    alert(e.message);
  }
};

window.openReport = async function (id) {
  const res = await fetch(`${API}/reports/${id}`, { headers: authHeaders() });
  if (!res.ok) return;
  state.lastReport = await res.json();
  renderSuccessReport(state.lastReport);
  showView("success");
};

function bindNav() {
  document.querySelectorAll(".nav-item[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.view;
      if (view === "history") loadHistory();
      else if (view === "reports") loadReports();
      else if (view === "dashboard") loadDashboard();
      else if (view === "monitor") loadMonitor();
      else if (view === "settings") loadSettings();
      else if (view === "request") showView("request");
      else if (view === "employees") {
        showView("request");
      }
    });
  });
  $("loginBtn").addEventListener("click", login);
  $("logoutBtn").addEventListener("click", logout);
  $("findBtn").addEventListener("click", findCandidates);
  $("approveBtn").addEventListener("click", approveRecommendation);
  $("reevalBtn").addEventListener("click", () => showView("request"));
  $("rejectBtn").addEventListener("click", rejectRecommendation);
  $("downloadPdfBtn").addEventListener("click", downloadPdf);
  $("exportJsonBtn").addEventListener("click", exportJson);
  $("shareBtn").addEventListener("click", shareInternally);
  $("newRequestBtn").addEventListener("click", () => showView("request"));
  $("settingsProvider")?.addEventListener("change", onSettingsProviderChange);
  $("settingsModel")?.addEventListener("change", updateSettingsSaveState);
  $("settingsApiKey")?.addEventListener("input", updateSettingsSaveState);
  $("settingsSaveBtn")?.addEventListener("click", saveModelSettings);
  $("profileModalClose")?.addEventListener("click", closeEmployeeProfileModal);
  $("employeeProfileModal")?.addEventListener("click", (e) => {
    if (e.target.id === "employeeProfileModal") closeEmployeeProfileModal();
  });
}

function init() {
  renderTimelines();
  updateAgentStats(null);
  bindNav();
  bindWeightSliders();
  bindWeightPresets();
  bindPromptExtract();
  $("fieldGermanFluency")?.addEventListener("change", syncGermanWeightSlider);
  applyWeightPreset("balanced");
  if (state.token) {
    $("loginOverlay").classList.add("hidden");
    $("profileName").textContent = state.username;
    $("profileInitials").textContent = initials(state.username);
    loadSearchOptions();
  }
  showView("request");
}

init();
