"use strict";

const MASK = "••••••••••••";
const toast = document.getElementById("toast");
let toastTimer;

function say(message) {
  toast.textContent = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.textContent = ""; }, 2000);
}

// ページの HTML にパスワードを含めないため、必要になった時点で毎回取得する
async function fetchPassword(siteId) {
  const response = await fetch(`/api/sites/${encodeURIComponent(siteId)}/password`, { cache: "no-store" });
  if (!response.ok) throw new Error(`${siteId} のパスワードを取得できませんでした`);
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

document.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;

  if (button.dataset.copyText !== undefined) {
    await copy(button.dataset.copyText, button.dataset.label);
    return;
  }

  const toggleId = button.dataset.toggle;
  if (toggleId) {
    const field = document.querySelector(`[data-password="${CSS.escape(toggleId)}"]`);
    if (button.getAttribute("aria-pressed") === "true") {
      field.textContent = MASK;
      button.setAttribute("aria-pressed", "false");
      button.setAttribute("aria-label", `${toggleId} のパスワードを表示`);
      return;
    }
    try {
      field.textContent = await fetchPassword(toggleId);
      button.setAttribute("aria-pressed", "true");
      button.setAttribute("aria-label", `${toggleId} のパスワードを隠す`);
    } catch (error) {
      say(error.message);
    }
    return;
  }

  const copyId = button.dataset.copyPassword;
  if (copyId) {
    try {
      await copy(await fetchPassword(copyId), `${copyId} のパスワード`);
    } catch (error) {
      say(error.message);
    }
  }
});

// 起動は完了まで数十秒かかるため、二重送信を防ぎつつ進行中であることを示す
document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-power]");
  if (!form) return;
  const button = form.querySelector("button");
  button.disabled = true;
  button.textContent = "処理中…";
});
