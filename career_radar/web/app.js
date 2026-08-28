"use strict";

const state = { opportunities: [], selectedId: null };
const elements = {
  list: document.querySelector("#opportunity-list"),
  loading: document.querySelector("#list-loading"),
  empty: document.querySelector("#empty-state"),
  detail: document.querySelector("#opportunity-detail"),
  detailPlaceholder: document.querySelector("#detail-placeholder"),
  recommendation: document.querySelector("#recommendation-filter"),
  status: document.querySelector("#status-filter"),
  dialog: document.querySelector("#import-dialog"),
  form: document.querySelector("#import-form"),
  formError: document.querySelector("#import-error"),
  submit: document.querySelector("#submit-import"),
  live: document.querySelector("#live-region"),
  scanProfile: document.querySelector("#scan-profile"),
  scanButton: document.querySelector("#scan-vacancies"),
  sourceStatus: document.querySelector("#source-status"),
};

const text = (tag, value, className) => {
  const node = document.createElement(tag);
  node.textContent = value;
  if (className) node.className = className;
  return node;
};

const api = async (path, options = {}) => {
  const response = await fetch(path, options);
  let payload;
  try { payload = await response.json(); } catch { payload = null; }
  if (!response.ok) {
    throw new Error(payload?.error?.message || "The local panel could not complete the request");
  }
  return payload;
};

const queryPath = () => {
  const params = new URLSearchParams();
  if (elements.recommendation.value) params.set("recommendation", elements.recommendation.value);
  if (elements.status.value) params.set("status", elements.status.value);
  const query = params.toString();
  return `/api/opportunities${query ? `?${query}` : ""}`;
};

const loadInbox = async ({ selectFirst = false } = {}) => {
  elements.loading.hidden = false;
  try {
    const payload = await api(queryPath());
    state.opportunities = payload.opportunities;
    const selectionIsVisible = state.opportunities.some((item) => item.id === state.selectedId);
    if (!selectionIsVisible) {
      state.selectedId = selectFirst && state.opportunities.length ? state.opportunities[0].id : null;
    }
    renderList();
    updateSummary();
    if (state.selectedId) {
      await loadDetail(state.selectedId);
    } else {
      showDetailPlaceholder();
    }
  } catch (error) {
    announce(error.message);
    elements.list.replaceChildren(text("li", "Inbox is unavailable. Use refresh to try again.", "loading-state"));
  } finally {
    elements.loading.hidden = true;
  }
};

const loadSources = async () => {
  try {
    const payload = await api("/api/sources");
    elements.scanProfile.replaceChildren();
    payload.profiles.forEach((profile) => {
      const option = document.createElement("option");
      option.value = profile.id;
      option.textContent = profile.name;
      elements.scanProfile.append(option);
    });
    const source = payload.sources[0];
    elements.sourceStatus.textContent = source.message;
    elements.sourceStatus.dataset.state = source.status;
    elements.scanButton.disabled = payload.profiles.length === 0;
  } catch (error) {
    elements.scanButton.disabled = true;
    elements.sourceStatus.textContent = error.message;
    elements.sourceStatus.dataset.state = "failed";
  }
};

const scanVacancies = async () => {
  elements.scanButton.disabled = true;
  elements.scanButton.textContent = "Scanning…";
  elements.sourceStatus.textContent = "Scanning HeadHunter. Vacancy details stay on this device…";
  elements.sourceStatus.dataset.state = "running";
  try {
    const payload = await api("/api/scans", {
      method: "POST",
      headers: mutationHeaders(),
      body: JSON.stringify({ profileId: elements.scanProfile.value }),
    });
    const source = payload.scan.sources[0];
    elements.sourceStatus.textContent = `${source.message}. ${source.importedCount} imported, ${source.skippedCount} skipped.`;
    elements.sourceStatus.dataset.state = source.status;
    await loadInbox({ selectFirst: source.importedCount > 0 });
    announce(elements.sourceStatus.textContent);
  } catch (error) {
    elements.sourceStatus.textContent = error.message;
    elements.sourceStatus.dataset.state = "failed";
    announce(error.message);
  } finally {
    elements.scanButton.disabled = false;
    elements.scanButton.textContent = "Scan vacancies";
  }
};

const renderList = () => {
  elements.list.replaceChildren();
  elements.empty.hidden = state.opportunities.length !== 0;
  if (!state.opportunities.length) {
    const isFiltered = elements.recommendation.value || elements.status.value;
    elements.empty.querySelector("h3").textContent = isFiltered ? "No matching opportunities" : "No opportunities yet";
    elements.empty.querySelector("p").textContent = isFiltered
      ? "Adjust the filters to return to your saved queue."
      : "Paste a vacancy to get an explained match and start your private queue.";
    elements.empty.querySelector("button").hidden = Boolean(isFiltered);
  }
  document.querySelector("#visible-count").textContent = `${state.opportunities.length} ${state.opportunities.length === 1 ? "role" : "roles"}`;
  state.opportunities.forEach((opportunity) => {
    const item = document.createElement("li");
    item.className = "opportunity-card";
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.id = opportunity.id;
    button.setAttribute("aria-current", String(opportunity.id === state.selectedId));
    button.setAttribute("aria-label", `${opportunity.title}, ${opportunity.recommendation}, score ${opportunity.overallScore} percent`);

    const top = text("div", "", "card-top");
    top.append(
      text("span", opportunity.recommendation, `recommendation recommendation-${opportunity.recommendation.toLowerCase()}`),
      text("span", `${opportunity.overallScore}%`, "score"),
    );
    const heading = text("h3", opportunity.title);
    const meta = text("div", "", "card-meta");
    meta.append(
      text("span", opportunity.status, "human-status"),
      text("span", `${opportunity.confidence}% confidence`),
    );
    button.append(top, heading, meta);
    button.addEventListener("click", () => selectOpportunity(opportunity.id));
    item.append(button);
    elements.list.append(item);
  });
};

const selectOpportunity = async (id) => {
  state.selectedId = id;
  renderList();
  await loadDetail(id);
  if (window.matchMedia("(max-width: 760px)").matches) {
    document.querySelector("#detail-pane").scrollIntoView({ behavior: "smooth", block: "start" });
  }
};

const loadDetail = async (id) => {
  try {
    const payload = await api(`/api/opportunities/${encodeURIComponent(id)}`);
    renderDetail(payload.opportunity);
  } catch (error) {
    announce(error.message);
  }
};

const renderDetail = (opportunity) => {
  elements.detailPlaceholder.hidden = true;
  elements.detail.hidden = false;
  elements.detail.replaceChildren();
  const root = text("div", "", "detail-content");
  const header = text("header", "", "detail-header");
  const titleBlock = document.createElement("div");
  titleBlock.append(
    text("span", opportunity.recommendation, `recommendation recommendation-${opportunity.recommendation.toLowerCase()}`),
    text("h2", opportunity.title),
    text("p", `${opportunity.confidence}% match confidence · seen ${opportunity.seenCount} ${opportunity.seenCount === 1 ? "time" : "times"}`),
  );
  const ring = text("div", "", "score-ring");
  ring.setAttribute("aria-label", `Opportunity score ${opportunity.overallScore} percent`);
  ring.append(text("strong", `${opportunity.overallScore}%`), text("span", "score"));
  header.append(titleBlock, ring);
  root.append(header, decisionStrip(opportunity), whySection(opportunity.matchReport), evidenceSection(opportunity.matchReport), provenanceSection(opportunity));
  elements.detail.append(root);
};

const decisionStrip = (opportunity) => {
  const strip = text("section", "", "decision-strip");
  const copy = document.createElement("div");
  copy.append(text("p", "My decision"), text("strong", opportunity.status));
  const actions = text("div", "", "status-actions");
  ["new", "shortlisted", "dismissed"].forEach((status) => {
    const button = text("button", status, "status-button");
    button.type = "button";
    button.setAttribute("aria-pressed", String(opportunity.status === status));
    button.addEventListener("click", () => updateStatus(opportunity.id, status));
    actions.append(button);
  });
  strip.append(copy, actions);
  return strip;
};

const whySection = (report) => {
  const section = text("section", "", "detail-section");
  section.append(text("h3", "Why this recommendation"));
  const reasons = Array.isArray(report?.reasons) ? report.reasons : [];
  const list = text("ul", "", "reason-list");
  (reasons.length ? reasons : ["No explanation recorded"]).forEach((reason) => list.append(text("li", reason)));
  section.append(list);
  const gaps = [
    ...(Array.isArray(report?.requiredGaps) ? report.requiredGaps : []),
    ...(Array.isArray(report?.unverifiedConstraints) ? report.unverifiedConstraints : []),
  ];
  if (gaps.length) {
    section.append(text("h3", "Gaps and unverified constraints"));
    const gapList = text("ul", "", "gap-list");
    gaps.forEach((gap) => gapList.append(text("li", gap)));
    section.append(gapList);
  }
  return section;
};

const evidenceSection = (report) => {
  const section = text("section", "", "detail-section");
  section.append(text("h3", "Requirement evidence"));
  const list = text("div", "", "evidence-list");
  const mappings = Array.isArray(report?.requirementMappings) ? report.requirementMappings : [];
  if (!mappings.length) list.append(text("p", "No catalogued requirements were recognized.", "reason-list"));
  mappings.forEach((mapping) => {
    const row = text("div", "", "evidence-row");
    const copy = document.createElement("div");
    const projects = Array.isArray(mapping.projects) && mapping.projects.length ? mapping.projects.join(", ") : "No project evidence";
    copy.append(text("strong", mapping.skillName || "Unknown requirement"), text("small", `${mapping.importance || "unknown"} · ${projects}`));
    const status = mapping.evidenceStatus || "gap";
    row.append(copy, text("span", status.replace("_", " "), `evidence-badge evidence-${status}`));
    list.append(row);
  });
  section.append(list);
  return section;
};

const provenanceSection = (opportunity) => {
  const section = text("section", "", "detail-section");
  section.append(text("h3", "Provenance"));
  const grid = text("dl", "", "provenance");
  const values = [
    ["Source", opportunity.source.name],
    ["Source ID", opportunity.source.vacancyId || "Not recorded"],
    ["Source URL", opportunity.source.url || "Not recorded"],
    ["Collection", opportunity.collectionMethod.replace("_", " ")],
    ["First seen", formatDate(opportunity.firstSeenAt)],
    ["Last seen", formatDate(opportunity.lastSeenAt)],
  ];
  values.forEach(([label, value]) => {
    const group = document.createElement("div");
    group.append(text("dt", label), text("dd", value));
    grid.append(group);
  });
  section.append(grid);
  return section;
};

const updateStatus = async (id, status) => {
  try {
    const payload = await api(`/api/opportunities/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: mutationHeaders(),
      body: JSON.stringify({ status }),
    });
    renderDetail(payload.opportunity);
    announce(`Status changed to ${status}`);
    await loadInbox();
  } catch (error) { announce(error.message); }
};

const submitImport = async (event) => {
  event.preventDefault();
  elements.formError.hidden = true;
  elements.submit.disabled = true;
  elements.submit.textContent = "Matching…";
  const data = new FormData(elements.form);
  const payload = { text: data.get("text"), source: "manual" };
  if (data.get("sourceUrl")) payload.sourceUrl = data.get("sourceUrl");
  if (data.get("sourceVacancyId")) payload.sourceVacancyId = data.get("sourceVacancyId");
  try {
    const result = await api("/api/opportunities", {
      method: "POST",
      headers: mutationHeaders(),
      body: JSON.stringify(payload),
    });
    state.selectedId = result.opportunity.id;
    elements.dialog.close();
    elements.form.reset();
    await loadInbox();
    announce(result.created ? "Opportunity added" : "Opportunity updated");
  } catch (error) {
    elements.formError.textContent = error.message;
    elements.formError.hidden = false;
  } finally {
    elements.submit.disabled = false;
    elements.submit.textContent = "Match and save";
  }
};

const mutationHeaders = () => ({ "Content-Type": "application/json", "X-Career-Radar-Request": "1" });
const formatDate = (value) => new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
const announce = (message) => { elements.live.textContent = ""; window.setTimeout(() => { elements.live.textContent = message; }, 20); };
const showDetailPlaceholder = () => { elements.detail.hidden = true; elements.detailPlaceholder.hidden = false; };
const updateSummary = () => {
  document.querySelector("#count-all").textContent = state.opportunities.length;
  document.querySelector("#count-apply").textContent = state.opportunities.filter((item) => item.recommendation === "APPLY").length;
  document.querySelector("#count-review").textContent = state.opportunities.filter((item) => item.recommendation === "REVIEW").length;
  document.querySelector("#count-shortlisted").textContent = state.opportunities.filter((item) => item.status === "shortlisted").length;
};

const openDialog = () => { elements.formError.hidden = true; elements.dialog.showModal(); document.querySelector("#vacancy-text").focus(); };
document.querySelector("#open-import").addEventListener("click", openDialog);
document.querySelector("#empty-import").addEventListener("click", openDialog);
document.querySelector("#close-import").addEventListener("click", () => elements.dialog.close());
document.querySelector("#cancel-import").addEventListener("click", () => elements.dialog.close());
document.querySelector("#refresh").addEventListener("click", () => loadInbox());
elements.scanButton.addEventListener("click", scanVacancies);
elements.recommendation.addEventListener("change", () => loadInbox({ selectFirst: true }));
elements.status.addEventListener("change", () => loadInbox({ selectFirst: true }));
elements.form.addEventListener("submit", submitImport);
elements.dialog.addEventListener("click", (event) => { if (event.target === elements.dialog) elements.dialog.close(); });

Promise.all([loadSources(), loadInbox({ selectFirst: true })]);
