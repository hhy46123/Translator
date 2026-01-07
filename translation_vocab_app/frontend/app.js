const inputText = document.getElementById("inputText");
const translateBtn = document.getElementById("translateBtn");
const pasteBtn = document.getElementById("pasteBtn");
const saveToggle = document.getElementById("saveToggle");
const noteSelect = document.getElementById("noteSelect");
const newNoteInput = document.getElementById("newNoteInput");
const addNoteBtn = document.getElementById("addNoteBtn");
const providerSelect = document.getElementById("providerSelect");
const directionSelect = document.getElementById("directionSelect");
const searchInput = document.getElementById("searchInput");
const directionFilter = document.getElementById("directionFilter");
const refreshBtn = document.getElementById("refreshBtn");
const resultCard = document.getElementById("resultCard");
const resultLanguages = document.getElementById("resultLanguages");
const providerMeta = document.getElementById("providerMeta");
const originalTextEl = document.getElementById("originalText");
const translatedTextEl = document.getElementById("translatedText");
const ipaTextEl = document.getElementById("ipaText");
const nounFormsEl = document.getElementById("nounForms");
const verbFormsEl = document.getElementById("verbForms");
const adjFormsEl = document.getElementById("adjForms");
const phrasesEl = document.getElementById("phrases");
const examplesEl = document.getElementById("examples");
const overlay = document.getElementById("overlay");
const closeModalBtn = document.getElementById("closeModal");
const installBtn = document.getElementById("installBtn");
const navButtons = document.querySelectorAll(".nav-btn");
const notebookView = document.getElementById("notebookView");
const pageIndicator = document.getElementById("pageIndicator");
const prevPage = document.getElementById("prevPage");
const nextPage = document.getElementById("nextPage");
const leftPageContent = document.getElementById("leftPageContent");
const rightPageContent = document.getElementById("rightPageContent");
const leftPageNumber = document.getElementById("leftPageNumber");
const rightPageNumber = document.getElementById("rightPageNumber");
const detailsOverlay = document.getElementById("detailsOverlay");
const closeDetails = document.getElementById("closeDetails");
const detailsContent = document.getElementById("detailsContent");
const apiStatus = document.getElementById("apiStatus");
const errorBox = document.getElementById("errorBox");

let pendingInstallEvent = null;
let activeRowId = null;
let notebookItems = [];
let totalCount = 0;
let currentPage = 0;
let debounceTimer = null;
const SPREAD_SIZE = 40;
const PAGE_SIZE = 20;
const AUTO_TRANSLATE_DELAY = 600;

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await res.text();
  let data = text;
  try {
    data = text ? JSON.parse(text) : {};
  } catch (err) {
    // non-JSON response; keep raw text
  }
  if (!res.ok) {
    const message = (data && data.detail) || data || "Request failed";
    throw new Error(message);
  }
  return data;
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

function showError(message) {
  errorBox.hidden = false;
  errorBox.textContent = message;
}

function populateList(element, items) {
  element.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    element.appendChild(li);
  });
}

async function translate(options = {}) {
  const text = inputText.value.trim();
  if (!text) return;
  const note = newNoteInput.value.trim() || noteSelect.value;
  const payload = {
    text,
    note,
    save: options.save === undefined ? saveToggle.checked : options.save,
    provider: providerSelect.value || "auto",
    direction: directionSelect.value || "auto",
  };
  clearError();
  try {
    const data = await fetchJSON("/api/translate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderResult(data);
    if (data.translation_success) {
      await loadNotebook(0);
    }
  } catch (err) {
    showError(err.message || "Translation failed");
  }
}

function renderResult(data) {
  resultCard.hidden = false;
  resultLanguages.textContent = `${data.src_lang} → ${data.dest_lang}`;
  providerMeta.textContent = `Provider: ${data.provider_used || "n/a"} · Latency: ${
    data.latency_ms ?? "—"
  } ms`;
  if (data.error_chain && data.error_chain.length) {
    providerMeta.textContent += ` · Fallbacks: ${data.error_chain.join(" | ")}`;
  }
  originalTextEl.textContent = data.original;
  translatedTextEl.textContent = data.translated;
  ipaTextEl.textContent = data.ipa;
  populateList(nounFormsEl, data.related.noun_forms || []);
  populateList(verbFormsEl, data.related.verb_forms || []);
  populateList(adjFormsEl, data.related.adj_forms || []);
  populateList(phrasesEl, data.related.phrases || []);
  populateList(examplesEl, data.related.examples || []);
}

async function loadNotes() {
  const { notes } = await fetchJSON("/api/notes");
  const targets = [noteSelect];
  targets.forEach((select) => {
    select.innerHTML = "";
    notes.forEach((n) => {
      const opt = document.createElement("option");
      opt.value = n;
      opt.textContent = n;
      select.appendChild(opt);
    });
  });
  if (!notes.includes("daily")) {
    const opt = document.createElement("option");
    opt.value = "daily";
    opt.textContent = "daily";
    targets.forEach((select) => select.appendChild(opt.cloneNode(true)));
  }
}

async function loadNotebook(page = 0, direction = null) {
  const params = new URLSearchParams();
  params.append("page", String(page + 1));
  params.append("page_size", String(SPREAD_SIZE));
  if (searchInput.value.trim()) {
    params.append("query", searchInput.value.trim());
  }
  if (directionFilter.value) {
    params.append("direction", directionFilter.value);
  }
  const data = await fetchJSON(`/api/notebook?${params.toString()}`);
  notebookItems = data.items || [];
  totalCount = data.total_count || 0;
  currentPage = page;
  renderSpread(direction);
}

function colorForWrong(count) {
  if (count === 0) return "gray";
  if (count === 1) return "#ef4444";
  if (count === 2) return "#f97316";
  if (count === 3) return "#eab308";
  return "#22c55e";
}

async function handleNotebookDelete(item) {
  await fetchJSON(`/api/notebook/${item.id}`, { method: "DELETE" });
  const totalPages = Math.max(1, Math.ceil(Math.max(totalCount - 1, 0) / SPREAD_SIZE));
  const nextPage = Math.min(currentPage, totalPages - 1);
  await loadNotebook(nextPage);
}

overlay.addEventListener("click", (e) => {
  if (e.target === overlay) {
    overlay.classList.add("hidden");
  }
});

closeModalBtn.addEventListener("click", () => overlay.classList.add("hidden"));

overlay.querySelectorAll("button[data-result]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!activeRowId) return;
    const result = btn.dataset.result;
    await fetchJSON(`/api/vocab/${activeRowId}/attempt`, {
      method: "POST",
      body: JSON.stringify({ result }),
    });
    overlay.classList.add("hidden");
    activeRowId = null;
    await loadNotebook(currentPage);
  });
});

pasteBtn.addEventListener("click", async () => {
  if (!navigator.clipboard) return;
  const text = await navigator.clipboard.readText();
  inputText.value = text;
  translate({ save: false });
});

function debounceTranslate() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => translate({ save: false }), AUTO_TRANSLATE_DELAY);
}

inputText.addEventListener("input", debounceTranslate);

translateBtn.addEventListener("click", () => translate());

addNoteBtn.addEventListener("click", async () => {
  const newNote = newNoteInput.value.trim();
  if (!newNote) return;
  const { notes } = await fetchJSON("/api/notes");
  if (!notes.includes(newNote)) {
    noteSelect.appendChild(new Option(newNote, newNote));
  }
  noteSelect.value = newNote;
});

refreshBtn.addEventListener("click", () => loadNotebook(currentPage));
searchInput.addEventListener("input", () => loadNotebook(0));
directionFilter.addEventListener("change", () => loadNotebook(0));

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  pendingInstallEvent = e;
  installBtn.style.display = "inline-flex";
});

installBtn.addEventListener("click", async () => {
  if (!pendingInstallEvent) return;
  pendingInstallEvent.prompt();
  await pendingInstallEvent.userChoice;
  pendingInstallEvent = null;
});

function renderSpread(direction = null) {
  const book = document.querySelector(".book");
  if (direction === "next") {
    book.classList.add("page-turn-next");
    setTimeout(() => book.classList.remove("page-turn-next"), 400);
  } else if (direction === "prev") {
    book.classList.add("page-turn-prev");
    setTimeout(() => book.classList.remove("page-turn-prev"), 400);
  }

  const totalPages = Math.max(1, Math.ceil(totalCount / SPREAD_SIZE));
  const currentPageNumber = Math.min(currentPage + 1, totalPages);
  pageIndicator.textContent = `Page ${currentPageNumber} / ${totalPages}`;

  const leftItems = notebookItems.slice(0, PAGE_SIZE);
  const rightItems = notebookItems.slice(PAGE_SIZE, SPREAD_SIZE);

  renderPageContent(leftPageContent, leftItems, leftPageNumber, currentPage * SPREAD_SIZE + 1);
  renderPageContent(
    rightPageContent,
    rightItems,
    rightPageNumber,
    currentPage * SPREAD_SIZE + PAGE_SIZE + 1
  );
}

function renderPageContent(container, items, pageNumberEl, startIndex) {
  container.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "detail";
    empty.textContent = "No items on this page yet.";
    container.appendChild(empty);
    pageNumberEl.textContent = "";
    return;
  }
  items.forEach((item) => {
    const row = buildPageItem(item);
    container.appendChild(row);
  });
  pageNumberEl.textContent = startIndex;
}

function buildPageItem(item) {
  const wrapper = document.createElement("div");
  wrapper.className = "page-item";

  const header = document.createElement("div");
  header.className = "page-item-header";
  const title = document.createElement("span");
  title.textContent = `${item.original} → ${item.translated}`;

  header.appendChild(title);

  const body = document.createElement("div");
  body.className = "page-item-body";

  const direction = document.createElement("div");
  direction.className = "detail";
  direction.textContent = `Direction: ${item.src_lang} → ${item.dest_lang}`;

  const timestamp = document.createElement("div");
  timestamp.className = "detail";
  timestamp.textContent = `Last seen: ${item.last_seen_at}`;

  const count = document.createElement("div");
  count.className = "detail";
  if (item.count && item.count > 1) {
    count.textContent = `Count: ${item.count}`;
  }

  const actions = document.createElement("div");
  actions.className = "btn-row";
  const deleteBtn = document.createElement("button");
  deleteBtn.className = "ghost-btn";
  deleteBtn.textContent = "Delete";
  deleteBtn.addEventListener("click", () => handleNotebookDelete(item));
  actions.appendChild(deleteBtn);

  body.appendChild(direction);
  body.appendChild(timestamp);
  if (count.textContent) {
    body.appendChild(count);
  }
  body.appendChild(actions);

  wrapper.appendChild(header);
  wrapper.appendChild(body);
  return wrapper;
}

prevPage.addEventListener("click", () => {
  const totalPages = Math.max(1, Math.ceil(totalCount / SPREAD_SIZE));
  currentPage = (currentPage - 1 + totalPages) % totalPages;
  loadNotebook(currentPage, "prev");
});

nextPage.addEventListener("click", () => {
  const totalPages = Math.max(1, Math.ceil(totalCount / SPREAD_SIZE));
  currentPage = (currentPage + 1) % totalPages;
  loadNotebook(currentPage, "next");
});

document.addEventListener("keydown", (e) => {
  if (notebookView.classList.contains("active")) {
    if (e.key === "ArrowLeft") prevPage.click();
    if (e.key === "ArrowRight") nextPage.click();
  }
});

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    navButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const target = btn.dataset.target;
    document.querySelectorAll(".view").forEach((view) => {
      view.classList.toggle("active", view.id === target);
    });
  });
});

function showDetailsModal(item) {
  const phrases = item.phrases && item.phrases.length ? item.phrases : ["No phrases"];
  const examples = item.examples && item.examples.length ? item.examples : ["No examples"];
  const nounForms = item.noun_forms && item.noun_forms.length ? item.noun_forms : [];
  const verbForms = item.verb_forms && item.verb_forms.length ? item.verb_forms : [];
  const adjForms = item.adj_forms && item.adj_forms.length ? item.adj_forms : [];
  const ipa = item.ipa || "N/A";

  detailsContent.innerHTML = `
    <p><strong>IPA:</strong> ${ipa}</p>
    <div class="detail-list">
      <h4>Noun forms</h4>
      <ul>${(nounForms.length ? nounForms : ["None"]).map((x) => `<li>${x}</li>`).join("")}</ul>
      <h4>Verb forms</h4>
      <ul>${(verbForms.length ? verbForms : ["None"]).map((x) => `<li>${x}</li>`).join("")}</ul>
      <h4>Adjective forms</h4>
      <ul>${(adjForms.length ? adjForms : ["None"]).map((x) => `<li>${x}</li>`).join("")}</ul>
      <h4>Phrases / Idioms</h4>
      <ul>${phrases.map((x) => `<li>${x}</li>`).join("")}</ul>
      <h4>Examples</h4>
      <ul>${examples.map((x) => `<li>${x}</li>`).join("")}</ul>
    </div>
  `;
  detailsOverlay.classList.remove("hidden");
}

closeDetails.addEventListener("click", () => detailsOverlay.classList.add("hidden"));
detailsOverlay.addEventListener("click", (e) => {
  if (e.target === detailsOverlay) detailsOverlay.classList.add("hidden");
});

async function loadHealth() {
  try {
    const data = await fetchJSON("/api/health");
    const providerStatuses = data.providers || {};
    const allOk = Object.values(providerStatuses).every((p) => p.ok);
    apiStatus.textContent = allOk ? "API OK" : "API Degraded";
    apiStatus.style.background = allOk ? "#dcfce7" : "#fef3c7";
    apiStatus.style.color = allOk ? "#166534" : "#92400e";
  } catch (err) {
    apiStatus.textContent = "API FAIL";
    apiStatus.style.background = "#fee2e2";
    apiStatus.style.color = "#7f1d1d";
  }
}

async function init() {
  try {
    await loadNotes();
    await loadNotebook(0);
    await loadHealth();
  } catch (err) {
    console.error(err);
  }
}

init();
