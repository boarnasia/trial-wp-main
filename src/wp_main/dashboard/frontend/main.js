import "./main.css";

const MASK = "••••••••••";
const toast = document.getElementById("toast");
let toastTimer;

function say(message) {
  toast.textContent = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.textContent = ""; }, 2000);
}

// ページの HTML にパスワードを含めないため、必要になった時点で毎回取得する
async function fetchSecret(button) {
  const response = await fetch(button.dataset.secretUrl, { cache: "no-store" });
  if (!response.ok) throw new Error(`${button.dataset.label}を取得できませんでした`);
  return (await response.json()).password;
}

async function copy(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    say(`${label}をコピーしました`);
  } catch {
    say(`${label}をコピーできませんでした`);
  }
}

async function toggleSecret(button) {
  const field = document.querySelector(`[data-secret="${CSS.escape(button.dataset.secretToggle)}"]`);
  if (button.getAttribute("aria-pressed") === "true") {
    field.textContent = MASK;
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", `${button.dataset.label}を表示`);
    return;
  }
  field.textContent = await fetchSecret(button);
  button.setAttribute("aria-pressed", "true");
  button.setAttribute("aria-label", `${button.dataset.label}を隠す`);
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;
  try {
    if (button.dataset.copyText !== undefined) {
      await copy(button.dataset.copyText, button.dataset.label);
    } else if (button.dataset.secretToggle) {
      await toggleSecret(button);
    } else if (button.dataset.secretCopy !== undefined) {
      await copy(await fetchSecret(button), button.dataset.label);
    }
  } catch (error) {
    say(error.message);
  }
});

// 起動や再取得は完了まで数十秒かかるため、二重送信を防ぎつつ進行中であることを示す
document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-power], form[data-refresh]");
  if (!form) return;
  const button = form.querySelector("button");
  button.disabled = true;
  button.textContent = form.dataset.refresh === undefined ? "処理中…" : "取得中…";
});

function keepInUrl(params) {
  const url = new URL(location.href);
  for (const [key, value] of Object.entries(params)) {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  }
  history.replaceState(null, "", url);
}

function setupSiteFilter() {
  const input = document.getElementById("site-filter");
  if (!input) return;
  const rows = [...document.querySelectorAll("[data-site-id]")];
  const empty = document.querySelector("[data-site-empty]");
  const count = document.querySelector("[data-site-count]");

  function apply() {
    const query = input.value.trim().toLowerCase();
    let shown = 0;
    for (const row of rows) {
      const hit = !query || row.dataset.siteId.toLowerCase().includes(query);
      row.hidden = !hit;
      if (hit) shown += 1;
    }
    empty.hidden = shown > 0;
    count.textContent = query ? `${shown} / ${rows.length} 件` : `${rows.length} 件`;
    // 再読み込みしても絞り込みを保つ
    keepInUrl({ site: input.value.trim() });
  }

  input.value = new URL(location.href).searchParams.get("site") ?? "";
  input.addEventListener("input", apply);
  apply();
}

function setupShutdown() {
  const dialog = document.getElementById("shutdown-dialog");
  if (!dialog) return;
  document.getElementById("shutdown-open").addEventListener("click", () => dialog.showModal());
  document.getElementById("shutdown-cancel").addEventListener("click", () => dialog.close());
  document.getElementById("shutdown-confirm").addEventListener("click", async (event) => {
    event.target.disabled = true;
    try {
      const response = await fetch("/session/shutdown", {
        method: "POST",
        headers: { "X-CSRFToken": dialog.dataset.csrf },
      });
      if (response.status !== 202) throw new Error(`開発セッションを終了できませんでした（HTTP ${response.status}）`);
      dialog.close();
      document.getElementById("session-ended").hidden = false;
    } catch (error) {
      event.target.disabled = false;
      dialog.close();
      say(error.message);
    }
  });
}

function setupPluginFilter() {
  const nameInput = document.getElementById("plugin-filter");
  const siteInput = document.getElementById("plugin-site-filter");
  if (!nameInput) return;
  const rows = [...document.querySelectorAll("tr[data-plugin]")];
  const siteCells = [...document.querySelectorAll("[data-col-site]")];
  const majorCells = [...document.querySelectorAll("[data-col-major]")];
  const siteHeaders = [...document.querySelectorAll("th[data-col-site]")];
  const empty = document.querySelector("[data-plugin-empty]");
  const count = document.querySelector("[data-plugin-count]");

  function apply() {
    const name = nameInput.value.trim().toLowerCase();
    const site = siteInput.value.trim().toLowerCase();
    const visibleSites = new Set(
      siteHeaders.map((th) => th.dataset.colSite).filter((id) => !site || id.toLowerCase().includes(site)),
    );
    // 残ったサイトが使っている WordPress のメジャーの列だけを残す
    const majors = new Set(
      siteHeaders.filter((th) => visibleSites.has(th.dataset.colSite)).map((th) => th.dataset.major),
    );
    for (const cell of siteCells) cell.hidden = !visibleSites.has(cell.dataset.colSite);
    for (const cell of majorCells) cell.hidden = !majors.has(cell.dataset.colMajor);
    let shown = 0;
    for (const row of rows) {
      const installed = row.dataset.sites.split(" ").some((id) => visibleSites.has(id));
      const hit = (!name || row.dataset.plugin.includes(name)) && (!site || installed);
      row.hidden = !hit;
      if (hit) shown += 1;
    }
    empty.hidden = shown > 0;
    count.textContent = name || site ? `(${shown} / ${rows.length})` : "";
    keepInUrl({ q: nameInput.value.trim(), site: siteInput.value.trim() });
  }

  const params = new URL(location.href).searchParams;
  nameInput.value = params.get("q") ?? "";
  siteInput.value = params.get("site") ?? "";
  nameInput.addEventListener("input", apply);
  siteInput.addEventListener("input", apply);
  apply();
}

setupSiteFilter();
setupPluginFilter();
setupShutdown();
