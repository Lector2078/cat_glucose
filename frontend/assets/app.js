const authSection = document.getElementById("authSection");
const appSection = document.getElementById("appSection");
const previewOutput = document.getElementById("previewOutput");
const mappingSection = document.getElementById("mappingSection");
const metabaseSql = document.getElementById("metabaseSql");
const importStatus = document.getElementById("importStatus");

let cats = [];
let previewState = null;

function setImportStatus(message, isError = false) {
  if (!importStatus) return;
  importStatus.textContent = message;
  importStatus.classList.toggle("error", isError);
}

async function apiForm(path, formData) {
  const response = await fetch(path, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed (${response.status})`);
  }
  return response.json();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message);
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

async function checkAuth() {
  try {
    await api("/api/auth/me");
    authSection.classList.add("hidden");
    appSection.classList.remove("hidden");
    await loadCats();
    await loadReadings();
    await loadJobs();
  } catch {
    authSection.classList.remove("hidden");
    appSection.classList.add("hidden");
  }
}

function renderCatOptions() {
  const selects = ["readingCat", "filterCat", "importCat"];
  for (const id of selects) {
    const select = document.getElementById(id);
    const current = select.value;
    const withAll = id === "filterCat" ? '<option value="">All</option>' : '<option value="">Select Cat</option>';
    select.innerHTML =
      withAll + cats.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
    select.value = current;
  }
}

async function loadCats() {
  cats = await api("/api/cats");
  const list = document.getElementById("catList");
  list.innerHTML = "";
  cats.forEach((cat) => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${cat.name}</strong> ${cat.birth_date || ""} <button data-edit="${cat.id}">Edit</button> <button data-del="${cat.id}">Delete</button>`;
    list.appendChild(li);
  });
  renderCatOptions();
}

async function loadReadings() {
  const catId = document.getElementById("filterCat").value;
  const path = catId ? `/api/readings?cat_id=${encodeURIComponent(catId)}` : "/api/readings";
  const readings = await api(path);
  const tbody = document.getElementById("readingTableBody");
  const catMap = new Map(cats.map((c) => [String(c.id), c.name]));
  tbody.innerHTML = "";
  readings.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${catMap.get(String(r.cat_id)) || r.cat_id}</td>
      <td>${r.reading_at}</td>
      <td>${r.glucose_value} ${r.unit}</td>
      <td>${r.context || ""}</td>
      <td>${r.source}</td>
      <td><button data-reading-del="${r.id}">Delete</button></td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadJobs() {
  const jobs = await api("/api/import/jobs");
  const tbody = document.getElementById("jobsTableBody");
  tbody.innerHTML = "";
  jobs.forEach((j) => {
    const tr = document.createElement("tr");
    const errorCell = j.error_report_path
      ? `<a href="/api/import/jobs/${j.id}/errors">download</a>`
      : "";
    tr.innerHTML = `<td>${j.id}</td><td>${j.filename}</td><td>${j.status}</td><td>${j.rows_inserted}</td><td>${j.rows_rejected}</td><td>${errorCell}</td>`;
    tbody.appendChild(tr);
  });
}

document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;
  await api("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  await checkAuth();
});

document.getElementById("catForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const catId = document.getElementById("catId").value;
  const payload = {
    name: document.getElementById("catName").value.trim(),
    birth_date: document.getElementById("catBirthDate").value.trim() || null,
    notes: document.getElementById("catNotes").value.trim() || null,
  };
  if (!payload.name) {
    alert("Cat name is required");
    return;
  }
  if (catId) {
    await api(`/api/cats/${catId}`, { method: "PUT", body: JSON.stringify(payload) });
  } else {
    await api("/api/cats", { method: "POST", body: JSON.stringify(payload) });
  }
  document.getElementById("catForm").reset();
  document.getElementById("catId").value = "";
  await loadCats();
});

document.getElementById("catFormReset").addEventListener("click", () => {
  document.getElementById("catForm").reset();
  document.getElementById("catId").value = "";
});

document.getElementById("catList").addEventListener("click", async (e) => {
  const editId = e.target.getAttribute("data-edit");
  const delId = e.target.getAttribute("data-del");
  if (editId) {
    const cat = cats.find((c) => String(c.id) === editId);
    if (!cat) return;
    document.getElementById("catId").value = cat.id;
    document.getElementById("catName").value = cat.name;
    document.getElementById("catBirthDate").value = cat.birth_date || "";
    document.getElementById("catNotes").value = cat.notes || "";
  } else if (delId) {
    if (confirm("Delete this cat and all readings?")) {
      await api(`/api/cats/${delId}`, { method: "DELETE" });
      await loadCats();
      await loadReadings();
    }
  }
});

document.getElementById("readingForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    cat_id: Number(document.getElementById("readingCat").value),
    reading_at: document.getElementById("readingAt").value.trim(),
    glucose_value: Number(document.getElementById("readingValue").value),
    context: document.getElementById("readingContext").value.trim() || null,
    notes: document.getElementById("readingNotes").value.trim() || null,
    source: "manual",
  };
  if (!payload.cat_id || !payload.reading_at || Number.isNaN(payload.glucose_value)) {
    alert("Cat, timestamp, and glucose are required");
    return;
  }
  await api("/api/readings", { method: "POST", body: JSON.stringify(payload) });
  document.getElementById("readingForm").reset();
  await loadReadings();
});

document.getElementById("readingTableBody").addEventListener("click", async (e) => {
  const delId = e.target.getAttribute("data-reading-del");
  if (!delId) return;
  await api(`/api/readings/${delId}`, { method: "DELETE" });
  await loadReadings();
});

document.getElementById("refreshReadings").addEventListener("click", loadReadings);
document.getElementById("filterCat").addEventListener("change", loadReadings);
document.getElementById("refreshJobs").addEventListener("click", loadJobs);

function fillColumnSelects(columns, suggestions = {}) {
  const targets = ["datetimeColumn", "glucoseColumn", "contextColumn", "notesColumn"];
  targets.forEach((id) => {
    const select = document.getElementById(id);
    const startsWithNone = id === "contextColumn" || id === "notesColumn";
    const prefix = startsWithNone ? '<option value="">None</option>' : "";
    select.innerHTML = prefix + columns.map((c) => `<option value="${c}">${c}</option>`).join("");
  });
  if (suggestions.datetime_column) {
    document.getElementById("datetimeColumn").value = suggestions.datetime_column;
  }
  if (suggestions.glucose_column) {
    document.getElementById("glucoseColumn").value = suggestions.glucose_column;
  }
}

document.getElementById("importPreviewForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const previewBtn = document.getElementById("previewFileBtn");
  const file = document.getElementById("importFile").files[0];
  if (!file) {
    setImportStatus("Choose a .csv, .xlsx, or .txt file first.", true);
    return;
  }

  const formData = new FormData();
  formData.set("file", file);
  if (previewBtn) previewBtn.disabled = true;
  setImportStatus("Loading preview...");
  previewOutput.textContent = "";
  try {
    const data = await apiForm("/api/import/preview", formData);
    previewState = data;
    if (!data.columns || data.columns.length === 0) {
      throw new Error("File parsed but no columns were detected. Check the header row.");
    }
    previewOutput.textContent = JSON.stringify(data.preview, null, 2);
    fillColumnSelects(data.columns, data.suggested_columns || {});
    mappingSection.classList.remove("hidden");
    mappingSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
    if (cats.length === 0) {
      setImportStatus("Preview loaded. Create a cat above before committing import.", true);
    } else {
      setImportStatus(`Preview loaded: ${data.row_count} row(s), ${data.columns.length} column(s).`);
    }
  } catch (err) {
    console.error(err);
    previewState = null;
    mappingSection.classList.add("hidden");
    previewOutput.textContent = "";
    setImportStatus(err.message || "Preview failed.", true);
    alert(`Preview failed: ${err.message || "Unknown error"}`);
  } finally {
    if (previewBtn) previewBtn.disabled = false;
  }
});

document.getElementById("commitImport").addEventListener("click", async () => {
  const file = document.getElementById("importFile").files[0];
  const catId = document.getElementById("importCat").value;
  const datetimeColumn = document.getElementById("datetimeColumn").value;
  const glucoseColumn = document.getElementById("glucoseColumn").value;
  const contextColumn = document.getElementById("contextColumn").value;
  const notesColumn = document.getElementById("notesColumn").value;
  if (!previewState || !file || !catId || !datetimeColumn || !glucoseColumn) {
    const msg = !previewState
      ? "Run Preview File first."
      : !file
        ? "Re-select the same file before committing."
        : !catId
          ? "Select a cat for import."
          : "Map date/time and glucose columns.";
    setImportStatus(msg, true);
    alert(msg);
    return;
  }

  const formData = new FormData();
  formData.set("file", file);
  const params = new URLSearchParams({
    cat_id: catId,
    datetime_column: datetimeColumn,
    glucose_column: glucoseColumn,
  });
  if (contextColumn) params.set("context_column", contextColumn);
  if (notesColumn) params.set("notes_column", notesColumn);

  setImportStatus("Importing...");
  try {
    const result = await apiForm(`/api/import/commit?${params.toString()}`, formData);
    previewOutput.textContent = `Import complete:\n${JSON.stringify(result, null, 2)}`;
    setImportStatus(
      `Import finished: ${result.rows_inserted} inserted, ${result.rows_rejected} rejected.`,
    );
    await loadReadings();
    await loadJobs();
  } catch (err) {
    console.error(err);
    setImportStatus(err.message || "Import failed.", true);
    alert(`Import failed: ${err.message || "Unknown error"}`);
  }
});

document.getElementById("loadMetabaseSql").addEventListener("click", async () => {
  const data = await api("/api/metabase/bootstrap");
  metabaseSql.textContent = data.read_only_role_sql;
});

checkAuth().catch((err) => {
  console.error(err);
  alert(`Error loading app: ${err.message}`);
});
