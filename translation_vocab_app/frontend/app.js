const inputText = document.getElementById("inputText");
const translateBtn = document.getElementById("translateBtn");
const pasteBtn = document.getElementById("pasteBtn");
const saveToggle = document.getElementById("saveToggle");
const noteSelect = document.getElementById("noteSelect");
const newNoteInput = document.getElementById("newNoteInput");
const addNoteBtn = document.getElementById("addNoteBtn");
const noteFilter = document.getElementById("noteFilter");
const refreshBtn = document.getElementById("refreshBtn");
const resultCard = document.getElementById("resultCard");
const resultLanguages = document.getElementById("resultLanguages");
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
const translateView = document.getElementById("translateView");
const notebookView = document.getElementById("notebookView");
const pageIndicator = document.getElementById("pageIndicator");
const prevPage = document.getElementById("prevPage");
const nextPage = document.getElementById("nextPage");
const pageContent = document.getElementById("pageContent");
const pageCard = document.getElementById("pageCard");
const detailsOverlay = document.getElementById("detailsOverlay");
const closeDetails = document.getElementById("closeDetails");
const detailsContent = document.getElementById("detailsContent");

let pendingInstallEvent = null;
let activeRowId = null;
let vocabItems = [];
let currentIndex = 0;
let debounceTimer = null;
const AUTO_TRANSLATE_DELAY = 600;

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Request failed");
  }
  return res.json();
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
  };
  const data = await fetchJSON("/api/translate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  renderResult(data);
  if (data.saved) {
    await loadNotes();
    await loadVocab(noteFilter.value || note);
  }
}

function renderResult(data) {
  resultCard.hidden = false;
  resultLanguages.textContent = `${data.src_lang} → ${data.dest_lang}`;
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
  const targets = [noteSelect, noteFilter];
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

async function loadVocab(note = null) {
  const params = note ? `?note=${encodeURIComponent(note)}` : "";
  const { items } = await fetchJSON(`/api/vocab${params}`);
  vocabItems = items;
  currentIndex = 0;
  renderPage();
}

function colorForWrong(count) {
  if (count === 0) return "gray";
  if (count === 1) return "#ef4444";
  if (count === 2) return "#f97316";
  if (count === 3) return "#eab308";
  return "#22c55e";
}

async function incrementWrong(id, button) {
  const data = await fetchJSON(`/api/vocab/${id}/wrong/increment`, { method: "POST" });
  button.textContent = data.wrong_count;
  button.style.background = colorForWrong(data.wrong_count);
  const idx = vocabItems.findIndex((v) => v.id === id);
  if (idx >= 0) {
    vocabItems[idx].wrong_count = data.wrong_count;
  }
}

async function handleActionClick(event, item) {
  const action = event.target.dataset.action;
  if (!action) return;
  if (action === "delete") {
    await fetchJSON(`/api/vocab/${item.id}`, { method: "DELETE" });
    await loadVocab(noteFilter.value);
  }
  if (action === "details") {
    showDetailsModal(item);
  }
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
    const data = await fetchJSON(`/api/vocab/${activeRowId}/attempt`, {
      method: "POST",
      body: JSON.stringify({ result }),
    });
    overlay.classList.add("hidden");
    activeRowId = null;
    await loadVocab(noteFilter.value);
  });
});

pasteBtn.addEventListener("click", async () => {
  if (!navigator.clipboard) return;
  const text = await navigator.clipboard.readText();
  inputText.value = text;
  translate();
});

inputText.addEventListener("input", () => {
  // auto-translate on input changes with small debounce
  clearTimeout(inputText._timer);
  inputText._timer = setTimeout(translate, 400);
});

translateBtn.addEventListener("click", translate);

addNoteBtn.addEventListener("click", async () => {
  const newNote = newNoteInput.value.trim();
  if (!newNote) return;
  const { notes } = await fetchJSON("/api/notes");
  if (!notes.includes(newNote)) {
    noteSelect.appendChild(new Option(newNote, newNote));
    noteFilter.appendChild(new Option(newNote, newNote));
  }
  noteSelect.value = newNote;
  noteFilter.value = newNote;
});

noteFilter.addEventListener("change", () => loadVocab(noteFilter.value));
refreshBtn.addEventListener("click", () => loadVocab(noteFilter.value));

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

async function init() {
  try {
    await loadNotes();
    noteFilter.value = "daily";
    await loadVocab("daily");
  } catch (err) {
    console.error(err);
  }
}

init();

function renderPage(direction = null) {
  pageIndicator.textContent = vocabItems.length
    ? `${currentIndex + 1}/${vocabItems.length}`
    : "0/0";
  pageContent.innerHTML = "";
  if (!vocabItems.length) {
    pageContent.innerHTML = "<p class='detail'>No items yet.</p>";
    return;
  }
  const item = vocabItems[currentIndex];
  const wrongBtn = document.createElement("button");
  wrongBtn.textContent = item.wrong_count;
  wrongBtn.className = "wrong-btn";
  wrongBtn.style.background = colorForWrong(item.wrong_count);
  wrongBtn.addEventListener("click", () => incrementWrong(item.id, wrongBtn));

  const cover = document.createElement("div");
  cover.className = "cover";
  const meaning = document.createElement("div");
  meaning.className = "meaning page-meaning";
  meaning.textContent = item.korean;

  cover.addEventListener("click", () => {
    cover.style.display = "none";
    meaning.style.display = "block";
    activeRowId = item.id;
    overlay.classList.remove("hidden");
  });

  const header = document.createElement("div");
  header.className = "page-content-header";
  header.innerHTML = `<h3>${item.english}</h3>`;
  header.appendChild(wrongBtn);

  const meta = document.createElement("div");
  meta.className = "page-meta";
  const success = document.createElement("span");
  success.className = "chip";
  success.textContent = `Success: ${item.success_rate}%`;
  const noteTag = document.createElement("span");
  noteTag.className = "chip";
  noteTag.textContent = `Note: ${item.note}`;
  meta.appendChild(success);
  meta.appendChild(noteTag);

  const actions = document.createElement("div");
  actions.className = "btn-row";
  const detailsBtn = document.createElement("button");
  detailsBtn.className = "ghost-btn";
  detailsBtn.textContent = "Details";
  detailsBtn.dataset.action = "details";
  detailsBtn.addEventListener("click", (e) => handleActionClick(e, item));
  const deleteBtn = document.createElement("button");
  deleteBtn.className = "ghost-btn";
  deleteBtn.textContent = "Delete";
  deleteBtn.dataset.action = "delete";
  deleteBtn.addEventListener("click", (e) => handleActionClick(e, item));
  actions.appendChild(detailsBtn);
  actions.appendChild(deleteBtn);

  pageContent.appendChild(header);
  pageContent.appendChild(meta);
  pageContent.appendChild(cover);
  pageContent.appendChild(meaning);
  pageContent.appendChild(actions);

  if (direction === "left") {
    pageCard.classList.add("slide-left");
    requestAnimationFrame(() => {
      pageCard.classList.remove("slide-left");
    });
  } else if (direction === "right") {
    pageCard.classList.add("slide-right");
    requestAnimationFrame(() => {
      pageCard.classList.remove("slide-right");
    });
  }
}

prevPage.addEventListener("click", () => {
  if (!vocabItems.length) return;
  currentIndex = (currentIndex - 1 + vocabItems.length) % vocabItems.length;
  renderPage("left");
});

nextPage.addEventListener("click", () => {
  if (!vocabItems.length) return;
  currentIndex = (currentIndex + 1) % vocabItems.length;
  renderPage("right");
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

function debounceTranslate() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    translate({ save: false });
  }, AUTO_TRANSLATE_DELAY);
}

inputText.addEventListener("input", debounceTranslate);
