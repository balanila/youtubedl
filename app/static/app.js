const form = document.querySelector("#info-form");
const urlInput = document.querySelector("#url");
const statusEl = document.querySelector("#status");
const resultEl = document.querySelector("#result");
const titleEl = document.querySelector("#title");
const metaEl = document.querySelector("#meta");
const thumbnailEl = document.querySelector("#thumbnail");
const optionsEl = document.querySelector("#options");
const tabs = [...document.querySelectorAll(".tab")];

let lastInfo = null;
let activeKind = "video";

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function durationText(seconds) {
  if (!seconds) return "";
  const mins = Math.floor(seconds / 60);
  const secs = String(seconds % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

function filenameFromDisposition(disposition, fallback) {
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encoded) {
    return decodeURIComponent(encoded[1]);
  }

  const quoted = disposition.match(/filename="([^"]+)"/i);
  if (quoted) {
    return quoted[1];
  }

  const plain = disposition.match(/filename=([^;]+)/i);
  if (plain) {
    return plain[1].trim();
  }

  return fallback;
}

function renderOptions() {
  optionsEl.innerHTML = "";
  const options = (lastInfo?.options || []).filter((item) => item.kind === activeKind);

  if (!options.length) {
    optionsEl.innerHTML = '<p class="meta">Для этого типа нет доступных вариантов.</p>';
    return;
  }

  for (const item of options) {
    const row = document.createElement("div");
    row.className = "option";

    const copy = document.createElement("div");
    const title = document.createElement("p");
    title.className = "option-title";
    title.textContent = item.label;

    const kind = document.createElement("p");
    kind.className = "option-kind";
    kind.textContent = item.kind === "audio" ? "Только аудио, MP3 после конвертации" : "Видео";

    copy.append(title, kind);

    const button = document.createElement("button");
    button.className = "download";
    button.type = "button";
    button.textContent = "Скачать";
    button.addEventListener("click", () => download(item, button));

    row.append(copy, button);
    optionsEl.append(row);
  }
}

async function download(item, button) {
  const body = new FormData();
  body.set("url", urlInput.value.trim());
  body.set("download_format", item.download_format);
  body.set("kind", item.kind);

  button.disabled = true;
  button.textContent = "...";
  setStatus("Готовлю файл. Для больших видео это может занять время.");

  try {
    const response = await fetch("/api/download", { method: "POST", body });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      setStatus(error.detail || "Не удалось скачать файл.", true);
      return;
    }

    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    let filename = filenameFromDisposition(disposition, "youtube-download");
    if (item.kind === "audio" && !filename.toLowerCase().endsWith(".mp3")) {
      filename = `${filename}.mp3`;
    }
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(href);
    setStatus("Файл готов.");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Скачать";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = new FormData(form);
  resultEl.hidden = true;
  setStatus("Читаю доступные форматы...");
  form.querySelector("button").disabled = true;

  try {
    const response = await fetch("/api/info", { method: "POST", body });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      setStatus(error.detail || "Не удалось получить список форматов.", true);
      return;
    }

    lastInfo = await response.json();
    titleEl.textContent = lastInfo.title;
    metaEl.textContent = durationText(lastInfo.duration);
    thumbnailEl.src = lastInfo.thumbnail || "";
    thumbnailEl.hidden = !lastInfo.thumbnail;
    activeKind = "video";
    tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.kind === activeKind));
    renderOptions();
    resultEl.hidden = false;
    setStatus("");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    form.querySelector("button").disabled = false;
  }
});

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    activeKind = tab.dataset.kind;
    tabs.forEach((item) => item.classList.toggle("active", item === tab));
    renderOptions();
  });
});
