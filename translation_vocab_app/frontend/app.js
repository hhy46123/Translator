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
const vocabBody = document.getElementById("vocabBody");
const overlay = document.getElementById("overlay");
const closeModalBtn = document.getElementById("closeModal");
const installBtn = document.getElementById("installBtn");

let pendingInstallEvent = null;
let activeRowId = null;

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

async function translate() {
  const text = inputText.value.trim();
  if (!text) return;
  const note = newNoteInput.value.trim() || noteSelect.value;
  const payload = {
    text,
    note,
    save: saveToggle.checked,
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
  vocabBody.innerHTML = "";
  items.forEach((item) => vocabBody.appendChild(buildRow(item)));
}

function buildRow(item) {
  const tr = document.createElement("tr");
  tr.dataset.id = item.id;

  const wrongBtn = document.createElement("button");
  wrongBtn.textContent = item.wrong_count;
  wrongBtn.className = "wrong-btn";
  wrongBtn.style.background = colorForWrong(item.wrong_count);
  wrongBtn.addEventListener("click", () => incrementWrong(item.id, wrongBtn));

  const wrongTd = document.createElement("td");
  wrongTd.appendChild(wrongBtn);

  const enTd = document.createElement("td");
  enTd.textContent = item.english;

  const koTd = document.createElement("td");
  const cover = document.createElement("div");
  cover.className = "cover";
  const meaning = document.createElement("div");
  meaning.className = "meaning";
  meaning.textContent = item.korean;
  koTd.appendChild(cover);
  koTd.appendChild(meaning);

  cover.addEventListener("click", () => {
    cover.style.display = "none";
    meaning.style.display = "block";
    activeRowId = item.id;
    overlay.classList.remove("hidden");
  });

  const successTd = document.createElement("td");
  successTd.className = "success-rate";
  successTd.textContent = `${item.success_rate}%`;

  const actionsTd = document.createElement("td");
  actionsTd.innerHTML = `
    <button class="ghost-btn" data-action="details">Details</button>
    <button class="ghost-btn" data-action="delete">Delete</button>
  `;
  actionsTd.addEventListener("click", (e) => handleActionClick(e, item));

  tr.appendChild(wrongTd);
  tr.appendChild(enTd);
  tr.appendChild(koTd);
  tr.appendChild(successTd);
  tr.appendChild(actionsTd);

  return tr;
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
}

async function handleActionClick(event, item) {
  const action = event.target.dataset.action;
  if (!action) return;
  if (action === "delete") {
    await fetchJSON(`/api/vocab/${item.id}`, { method: "DELETE" });
    await loadVocab(noteFilter.value);
  }
  if (action === "details") {
    const details = [
      `Phrases: ${(item.phrases || []).join(", ")}`,
      `Examples: ${(item.examples || []).join(" | ")}`,
    ].join("\n");
    alert(details || "No extra details");
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
