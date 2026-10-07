const API = "/api/v1";
let token = localStorage.getItem("token");

function detailToText(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map(d => {
      const field = (d.loc || []).slice(1).join(".");
      return (field ? field + ": " : "") + d.msg;
    }).join("; ");
  }
  try { return JSON.stringify(detail); } catch { return "Неизвестная ошибка"; }
}

function forceLogout() {
  localStorage.removeItem("token");
  token = null;
  document.getElementById("app-screen").classList.add("hidden");
  document.getElementById("auth-screen").classList.remove("hidden");
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    ...opts,
    headers: {
      "Content-Type": opts.body ? "application/json" : undefined,
      ...(token ? { "Authorization": "Bearer " + token } : {}),
    },
  });
  if (res.status === 401 && token) {
    forceLogout();
    throw new Error("Сессия истекла. Войдите снова.");
  }
  if (res.status === 204) return null;
  let data;
  try {
    data = await res.json();
  } catch (e) {
    data = {};
  }
  if (!res.ok) {
    const msgText = detailToText(data.detail || res.statusText);
    throw new Error(msgText);
  }
  return data;
}

function msg(id, text, ok) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = "msg " + (ok ? "ok" : "err");
  if (text) setTimeout(() => { el.textContent = ""; }, 5000);
}

document.getElementById("btn-register").onclick = async () => {
  try {
    await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("reg-username").value,
        email: document.getElementById("reg-email").value,
        password: document.getElementById("reg-password").value,
      }),
    });
    msg("reg-msg", "Аккаунт создан — теперь войдите.", true);
  } catch (e) { msg("reg-msg", e.message); }
};

document.getElementById("btn-login").onclick = async () => {
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: document.getElementById("login-email").value,
        password: document.getElementById("login-password").value,
      }),
    });
    token = data.access_token;
    localStorage.setItem("token", token);
    document.getElementById("auth-screen").classList.add("hidden");
    document.getElementById("app-screen").classList.remove("hidden");
    loadLeagues().then(loadChars);
  } catch (e) { msg("login-msg", e.message); }
};

// ---- Приложение ----
function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function rowHtml(e, isCurrent) {
  const dead = e.dead ? '<span class="dead-tag">dead</span>' : "";
  return `<div class="row ${isCurrent ? "current" : ""} ${e.dead ? "dead" : ""}">
    <div class="rank">#${esc(e.rank)}</div>
    <div class="who">${esc(e.name)}<span class="cls">${esc(e.char_class)}</span>${dead}</div>
    <div class="lvl">ур. ${esc(e.level)}</div>
  </div>`;
}

async function loadLeagues() {
  const sel = document.getElementById("league");
  const prev = sel.value;

  const leagues = await api("/track/leagues");
  sel.innerHTML = leagues.map(l =>
    `<option value="${esc(l)}">${esc(l)}</option>`).join("");
  if (prev && leagues.includes(prev)) {
    sel.value = prev;
    localStorage.setItem('selectedLeague', prev);
  } else if (saved = localStorage.getItem('selectedLeague')) {
    if (leagues.includes(saved)) {
      sel.value = saved;
    }
  }
}

async function loadChars() {
  const chars = await api("/track");
  const box = document.getElementById("chars");
  if (!chars.length) {
    box.innerHTML = '<div class="spinner">Пока пусто — добавьте ник выше.</div>';
    return;
  }
  box.innerHTML = "";
  chars.forEach(c => {
    const row = document.createElement("div");
    row.className = "char-row";
    row.innerHTML =
      `<div class="char-name">${esc(c.name)}</div>
       <div class="char-league">${esc(c.league)}</div>
       <button class="small">Показать</button>
       <button class="small ghost">Удалить</button>`;
    const [btnShow, btnDel] = row.querySelectorAll("button");
    btnShow.onclick = () => showLadder(c);
    btnDel.onclick = async () => {
      try {
        await api("/track/" + c.id, { method: "DELETE" });
        loadChars();
      } catch (e) {
        msg("add-msg", e.message);
      }
    };
    box.appendChild(row);
  });
}

async function showLadder(c) {
  const panel = document.getElementById("ladder-panel");
  const box = document.getElementById("ladder");
  document.getElementById("ladder-title").textContent =
    `Позиция: ${c.name} — ${c.league}`;
  panel.classList.remove("hidden");
  box.innerHTML = '<div class="spinner">Первый запрос может занять до 20 секунд (парсинг лайдера)…</div>';
  try {
    const w = await api(`/track/${c.id}/ladder`);
    if (!w.current) throw new Error("Персонаж не найден в ладдере");
    box.innerHTML =
      (w.above ? rowHtml(w.above, false) : "") +
      rowHtml(w.current, true) +
      (w.below ? rowHtml(w.below, false) : "");
  } catch (e) {
    box.innerHTML = `<div class="msg err">${esc(e.message)}</div>`;
  }
}

document.getElementById("btn-add").onclick = async () => {
  const btn = document.getElementById("btn-add");
  const btnText = btn.querySelector(".btn-text");
  const spinner = btn.querySelector(".spinner");

  if (btn.disabled) return;

  const nameInput = document.getElementById("char-name");
  const name = nameInput.value.trim();
  const league = document.getElementById("league").value;

  if (!name) {
    msg("add-msg", "Введите имя персонажа", false);
    return;
  }
  if (!league) {
    msg("add-msg", "Выберите лигу", false);
    return;
  }

  btn.disabled = true;
  btnText.style.display = "none";
  spinner.style.display = "inline-block";

  try {
    await api("/track", {
      method: "POST",
      body: JSON.stringify({ name, league }),
    });
    msg("add-msg", "Персонаж добавлен!", true);
    nameInput.value = "";
    await loadChars();
  } catch (e) {
    msg("add-msg", e.message);
  } finally {
    btn.disabled = false;
    btnText.style.display = "block";
    spinner.style.display = "none";
  }
};

const logoutBtn = document.getElementById("btn-logout");
if (logoutBtn) {
  logoutBtn.onclick = () => {
    forceLogout();
    location.href = "/";
  };
}

document.addEventListener('DOMContentLoaded', () => {
  const sel = document.getElementById('league');
  if (!sel) return;
  sel.addEventListener('change', () => {
    localStorage.setItem('selectedLeague', sel.value);
  });
  const saved = localStorage.getItem('selectedLeague');
  if (saved) {
    sel.value = saved;
  }
});

if (token) {
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("app-screen").classList.remove("hidden");
  loadLeagues()
    .then(() => loadChars())
    .catch((e) => {
      if (e.message.includes("401") || e.message.includes("session") || e.message.includes("unauthorized")) {
          forceLogout();
      } else {
          msg("login-msg", "Ошибка загрузки данных: " + e.message, false);
      }
    });
} else {
  const authScreen = document.getElementById("auth-screen");
  const appScreen = document.getElementById("app-screen");
  if (authScreen) authScreen.classList.remove("hidden");
  if (appScreen) appScreen.classList.add("hidden");
}
