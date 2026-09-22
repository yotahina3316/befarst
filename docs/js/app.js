// VAPID公開鍵(非秘密情報のためここに直接埋め込み。2026-09-19生成、CLAUDE.md参照)
const VAPID_PUBLIC_KEY =
  "BAvDkNGVDoA1iLGfn8SC6rSGcx_A4VygbgxS07MQV09qHJxCJJ9nUHJAS4uZiue2XY8SlwqP_cXkZCIp10eEMCY";

const CATEGORY_LABELS = {
  LIVE: "ライブ",
  GOODS: "グッズ",
  RELEASE: "DVD/Blu-ray",
  STREAM: "配信/生配信",
  DIGITAL: "配信リリース",
  DEADLINE: "申込締切",
  BIRTHDAY: "誕生日",
  ANNIVERSARY: "記念日",
};

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

// ---------- カード共通レイアウト(サムネイル画像対応) ----------

function itemCardHTML(item, metaHtml) {
  const title = item.title_ja || item.title_original;
  const thumb = item.image_url
    ? `<div class="item-thumb"><img src="${item.image_url}" alt="" loading="lazy" /></div>`
    : "";
  return `
    <a class="item-card" href="${item.url}" target="_blank" rel="noopener">
      ${thumb}
      <div class="item-body">
        <div class="meta">${metaHtml}</div>
        <div class="item-title">${title}</div>
        ${item.summary_ja ? `<div class="item-summary">${item.summary_ja}</div>` : ""}
      </div>
    </a>
  `;
}

function newsMetaHTML(item) {
  return `
    <span class="badge ${item.confidence}">${item.confidence}</span>
    <span class="item-date">${formatDate(item.published_at)}</span>
    ${item.source_category ? `<span class="item-date">${item.source_category}</span>` : ""}
  `;
}

function scheduleMetaHTML(item) {
  const time = item.event_date && item.event_date.length > 10 ? item.event_date.slice(11, 16) : null;
  const catLabel = CATEGORY_LABELS[item.schedule_category] || item.schedule_category || "";
  return `
    <span class="badge cat-${item.schedule_category}">${catLabel}</span>
    ${time ? `<span class="item-date">${time}〜</span>` : ""}
  `;
}

function renderNewsItems(container, items) {
  if (!items.length) {
    container.innerHTML = '<p class="empty">まだ情報がありません</p>';
    return;
  }
  container.innerHTML = items.map((item) => itemCardHTML(item, newsMetaHTML(item))).join("");
}

let allNewsItems = [];

// 最新ニュースのサムネイルをTOPページのヒーロー画像として使う(専用の画像素材を用意・保守する必要が無いようにするため)。
// サムネイルを持つ記事が無い場合は元のhero.webpのまま。
function updateHeroImage() {
  const heroImg = document.querySelector(".hero img");
  if (!heroImg) return;
  const withThumb = allNewsItems.find((item) => item.image_url);
  if (withThumb) {
    heroImg.src = withThumb.image_url;
  }
}

async function loadNews() {
  const container = document.getElementById("news-list");
  try {
    const res = await fetch("./data/news.json", { cache: "no-store" });
    allNewsItems = await res.json();
    renderNewsItems(container, allNewsItems);
    renderMemberTab();
    updateHeroImage();
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

  container.innerHTML = events.map((item) => itemCardHTML(item, scheduleMetaHTML(item))).join("");
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

let allScheduleItems = [];

async function loadSchedule() {
  try {
    const res = await fetch("./data/schedule.json", { cache: "no-store" });
    allScheduleItems = await res.json();
    calendarState.eventsByDay = groupEventsByDay(allScheduleItems);
    renderCalendarGrid();
    renderDayDetail(calendarState.selectedDay);
    renderMemberTab();
  } catch (e) {
    document.getElementById("calendar-day-events").innerHTML = '<p class="empty">読み込みに失敗しました</p>';
  }
}

// ---------- MEMBER ----------

const MEMBER_LIST = ["SOTA", "MANATO", "JUNON", "SHUNTO", "LEO", "RYUHEI"];
let selectedMember = MEMBER_LIST[0];

function setupMemberChips() {
  const container = document.getElementById("member-chips");
  container.innerHTML = MEMBER_LIST.map(
    (name) => `
      <button type="button" class="member-chip" data-member="${name}">
        <img class="member-chip-avatar" src="./images/members/${name.toLowerCase()}.webp" alt="" />
        <span>${name}</span>
      </button>
    `
  ).join("");
  container.querySelectorAll(".member-chip").forEach((btn) => {
    btn.addEventListener("click", () => selectMember(btn.dataset.member));
  });
  selectMember(selectedMember);
}

function selectMember(name) {
  selectedMember = name;
  document.querySelectorAll(".member-chip").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.member === name);
  });
  renderMemberTab();
}

function renderMemberTab() {
  const scheduleContainer = document.getElementById("member-schedule-list");
  const newsContainer = document.getElementById("member-news-list");
  if (!scheduleContainer || !newsContainer) return;

  const today = todayKey();
  const memberSchedule = allScheduleItems
    .filter(
      (item) => (item.members || []).includes(selectedMember) && (item.event_date || "").slice(0, 10) >= today
    )
    .sort((a, b) => (a.event_date || "").localeCompare(b.event_date || ""));

  const memberNews = allNewsItems.filter((item) => (item.members || []).includes(selectedMember));

  scheduleContainer.innerHTML = memberSchedule.length
    ? memberSchedule.map((item) => itemCardHTML(item, scheduleMetaHTML(item))).join("")
    : '<p class="empty">直近の予定はありません</p>';

  newsContainer.innerHTML = memberNews.length
    ? memberNews.map((item) => itemCardHTML(item, newsMetaHTML(item))).join("")
    : '<p class="empty">関連ニュースはありません</p>';
}

// ---------- 聖地巡礼 / BE:Fashion ----------
// どちらもAIが記事本文から自動抽出した「候補(candidate)」と、手動でdata/*.jsonを
// 編集してstatusを"confirmed"にした確認済み情報を同じ一覧に表示する。

function statusBadgeHTML(status) {
  return status === "confirmed"
    ? '<span class="badge confirmed">確認済み</span>'
    : '<span class="badge candidate">AI候補</span>';
}

function sourceLinkHTML(item) {
  return item.source_url
    ? `<a class="place-source-link" href="${item.source_url}" target="_blank" rel="noopener">元記事を見る</a>`
    : "";
}

function pilgrimageCardHTML(item) {
  const thumb = item.image_url
    ? `<div class="item-thumb"><img src="${item.image_url}" alt="" loading="lazy" /></div>`
    : "";
  return `
    <div class="item-card">
      ${thumb}
      <div class="item-body">
        <div class="meta">${statusBadgeHTML(item.status)}</div>
        <div class="item-title">${item.name_ja || ""}</div>
        ${item.address ? `<div class="item-summary">住所: ${item.address}</div>` : ""}
        ${item.description ? `<div class="item-summary">${item.description}</div>` : ""}
        ${sourceLinkHTML(item)}
      </div>
    </div>
  `;
}

async function loadPilgrimage() {
  const container = document.getElementById("pilgrimage-list");
  try {
    const res = await fetch("./data/pilgrimage.json", { cache: "no-store" });
    const items = await res.json();
    container.innerHTML = items.length
      ? items.map(pilgrimageCardHTML).join("")
      : '<p class="empty">まだ情報がありません</p>';
  } catch (e) {
    container.innerHTML = '<p class="empty">読み込みに失敗しました</p>';
  }
}

function fashionCardHTML(item) {
  const thumb = item.image_url
    ? `<div class="item-thumb"><img src="${item.image_url}" alt="" loading="lazy" /></div>`
    : "";
  const metaExtra = [item.member, item.brand].filter(Boolean).map((v) => `<span class="item-date">${v}</span>`).join("");
  return `
    <div class="item-card">
      ${thumb}
      <div class="item-body">
        <div class="meta">${statusBadgeHTML(item.status)}${metaExtra}</div>
        <div class="item-title">${item.item_name || ""}</div>
        ${item.description ? `<div class="item-summary">${item.description}</div>` : ""}
        ${sourceLinkHTML(item)}
      </div>
    </div>
  `;
}

async function loadFashion() {
  const container = document.getElementById("fashion-list");
  try {
    const res = await fetch("./data/fashion.json", { cache: "no-store" });
    const items = await res.json();
    container.innerHTML = items.length
      ? items.map(fashionCardHTML).join("")
      : '<p class="empty">まだ情報がありません</p>';
  } catch (e) {
    container.innerHTML = '<p class="empty">読み込みに失敗しました</p>';
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
setupMemberChips();
loadSchedule();
loadNews();
loadPilgrimage();
loadFashion();
setupPushNotifications();
