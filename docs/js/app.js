// VAPID公開鍵(非秘密情報のためここに直接埋め込み。2026-09-19生成、CLAUDE.md参照)
const VAPID_PUBLIC_KEY =
  "BAvDkNGVDoA1iLGfn8SC6rSGcx_A4VygbgxS07MQV09qHJxCJJ9nUHJAS4uZiue2XY8SlwqP_cXkZCIp10eEMCY";

const CATEGORY_LABELS = { LIVE: "ライブ", GOODS: "グッズ", RELEASE: "DVD/Blu-ray", BIRTHDAY: "誕生日" };

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "Z"); // データはUTC naiveで保存されているためZ付与して解釈
  return d.toLocaleString("ja-JP", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderNewsItems(container, items) {
  if (!items.length) {
    container.innerHTML = '<p class="empty">まだ情報がありません</p>';
    return;
  }

  container.innerHTML = items
    .map((item) => {
      const title = item.title_ja || item.title_original;
      return `
        <a class="item-card" href="${item.url}" target="_blank" rel="noopener">
          <div class="meta">
            <span class="badge ${item.confidence}">${item.confidence}</span>
            <span class="item-date">${formatDate(item.published_at)}</span>
            ${item.source_category ? `<span class="item-date">${item.source_category}</span>` : ""}
          </div>
          <div class="item-title">${title}</div>
          ${item.summary_ja ? `<div class="item-summary">${item.summary_ja}</div>` : ""}
        </a>
      `;
    })
    .join("");
}

async function loadNews() {
  const container = document.getElementById("news-list");
  try {
    const res = await fetch("./data/news.json", { cache: "no-store" });
    const items = await res.json();
    renderNewsItems(container, items);
  } catch (e) {
    container.innerHTML = '<p class="empty">読み込みに失敗しました</p>';
  }
}

// ---------- SCHEDULE(カレンダー表示) ----------

function pad2(n) {
  return String(n).padStart(2, "0");
}

function toDayKey(year, monthIndex, day) {
  return `${year}-${pad2(monthIndex + 1)}-${pad2(day)}`;
}

function todayKey() {
  const t = new Date();
  return toDayKey(t.getFullYear(), t.getMonth(), t.getDate());
}

const calendarState = {
  currentMonth: (() => {
    const t = new Date();
    return new Date(t.getFullYear(), t.getMonth(), 1);
  })(),
  selectedDay: todayKey(),
  eventsByDay: new Map(),
};

function groupEventsByDay(items) {
  const map = new Map();
  for (const item of items) {
    const key = (item.event_date || "").slice(0, 10);
    if (!key) continue;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  }
  for (const list of map.values()) {
    list.sort((a, b) => (a.event_date || "").localeCompare(b.event_date || ""));
  }
  return map;
}

function renderCalendarGrid() {
  const grid = document.getElementById("calendar-grid");
  const label = document.getElementById("cal-month-label");
  const year = calendarState.currentMonth.getFullYear();
  const month = calendarState.currentMonth.getMonth(); // 0-indexed
  label.textContent = `${year}年${month + 1}月`;

  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const tKey = todayKey();

  let html = "";
  for (let i = 0; i < firstWeekday; i++) {
    html += '<div class="cal-cell cal-cell-empty"></div>';
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const key = toDayKey(year, month, d);
    const dayEvents = calendarState.eventsByDay.get(key) || [];
    const categories = [...new Set(dayEvents.map((e) => e.schedule_category))];
    const dots = categories.map((cat) => `<i class="dot dot-${cat}"></i>`).join("");

    const classes = ["cal-cell"];
    if (key === tKey) classes.push("cal-cell-today");
    if (key === calendarState.selectedDay) classes.push("cal-cell-selected");
    if (dayEvents.length) classes.push("cal-cell-has-events");

    html += `<button type="button" class="${classes.join(" ")}" data-day="${key}">
      <span class="cal-cell-num">${d}</span>
      <span class="cal-cell-dots">${dots}</span>
    </button>`;
  }

  grid.innerHTML = html;
  grid.querySelectorAll(".cal-cell[data-day]").forEach((cell) => {
    cell.addEventListener("click", () => selectDay(cell.dataset.day));
  });
}

function formatDayTitle(key) {
  const [y, m, d] = key.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const weekday = ["日", "月", "火", "水", "木", "金", "土"][date.getDay()];
  return `${m}月${d}日(${weekday})`;
}

function renderDayDetail(key) {
  document.getElementById("calendar-day-title").textContent = formatDayTitle(key);
  const container = document.getElementById("calendar-day-events");
  const events = calendarState.eventsByDay.get(key) || [];

  if (!events.length) {
    container.innerHTML = '<p class="empty">この日の予定はありません</p>';
    return;
  }

  container.innerHTML = events
    .map((item) => {
      const time = item.event_date && item.event_date.length > 10 ? item.event_date.slice(11, 16) : null;
      const title = item.title_ja || item.title_original;
      const catLabel = CATEGORY_LABELS[item.schedule_category] || item.schedule_category || "";
      return `
        <a class="item-card" href="${item.url}" target="_blank" rel="noopener">
          <div class="meta">
            <span class="badge cat-${item.schedule_category}">${catLabel}</span>
            ${time ? `<span class="item-date">${time}〜</span>` : ""}
          </div>
          <div class="item-title">${title}</div>
          ${item.summary_ja ? `<div class="item-summary">${item.summary_ja}</div>` : ""}
        </a>
      `;
    })
    .join("");
}

function selectDay(key) {
  calendarState.selectedDay = key;
  renderCalendarGrid();
  renderDayDetail(key);
}

function changeMonth(delta) {
  calendarState.currentMonth = new Date(
    calendarState.currentMonth.getFullYear(),
    calendarState.currentMonth.getMonth() + delta,
    1
  );
  renderCalendarGrid();
}

function setupCalendarNav() {
  document.getElementById("cal-prev").addEventListener("click", () => changeMonth(-1));
  document.getElementById("cal-next").addEventListener("click", () => changeMonth(1));
}

async function loadSchedule() {
  try {
    const res = await fetch("./data/schedule.json", { cache: "no-store" });
    const items = await res.json();
    calendarState.eventsByDay = groupEventsByDay(items);
    renderCalendarGrid();
    renderDayDetail(calendarState.selectedDay);
  } catch (e) {
    document.getElementById("calendar-day-events").innerHTML = '<p class="empty">読み込みに失敗しました</p>';
  }
}

// ---------- タブ切り替え ----------

function setupTabs() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document
        .querySelectorAll(".tab-panel")
        .forEach((panel) => panel.classList.remove("active"));
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
}

// ---------- Push通知 ----------

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

// バックエンドサーバーが無いため、購読情報を送信するAPIがない。
// 代わりに購読内容を画面に表示し、利用者が一度だけdata/subscriptions.jsonへ手動登録する運用とする。
async function setupPushNotifications() {
  const btn = document.getElementById("notify-btn");
  const box = document.getElementById("subscription-box");
  const output = document.getElementById("subscription-output");
  const closeBtn = document.getElementById("subscription-close-btn");
  closeBtn.addEventListener("click", () => {
    box.hidden = true;
  });

  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return; // このブラウザ/iOSバージョンはWeb Push未対応
  }

  const registration = await navigator.serviceWorker.register("./service-worker.js");

  const existingSubscription = await registration.pushManager.getSubscription();
  if (existingSubscription) {
    return; // すでに購読済み(このデバイス上では)
  }

  btn.hidden = false;
  btn.addEventListener("click", async () => {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") return;

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
    });

    output.value = JSON.stringify(subscription.toJSON(), null, 2);
    box.hidden = false;
    btn.hidden = true;
  });
}

setupTabs();
setupCalendarNav();
loadSchedule();
loadNews();
setupPushNotifications();
