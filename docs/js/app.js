// VAPID公開鍵(非秘密情報のためここに直接埋め込み。2026-09-19生成、CLAUDE.md参照)
const VAPID_PUBLIC_KEY =
  "BAvDkNGVDoA1iLGfn8SC6rSGcx_A4VygbgxS07MQV09qHJxCJJ9nUHJAS4uZiue2XY8SlwqP_cXkZCIp10eEMCY";

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

function renderItems(container, items, { showEventDate }) {
  if (!items.length) {
    container.innerHTML = '<p class="empty">まだ情報がありません</p>';
    return;
  }

  container.innerHTML = items
    .map((item) => {
      const dateLabel = showEventDate
        ? formatDate(item.event_date)
        : formatDate(item.published_at);
      const title = item.title_ja || item.title_original;
      return `
        <a class="item-card" href="${item.url}" target="_blank" rel="noopener">
          <div class="meta">
            <span class="badge ${item.confidence}">${item.confidence}</span>
            <span class="item-date">${dateLabel}</span>
            ${item.source_category ? `<span class="item-date">${item.source_category}</span>` : ""}
          </div>
          <div class="item-title">${title}</div>
          ${item.summary_ja ? `<div class="item-summary">${item.summary_ja}</div>` : ""}
        </a>
      `;
    })
    .join("");
}

async function loadSchedule() {
  const container = document.getElementById("schedule-list");
  try {
    const res = await fetch("./data/schedule.json", { cache: "no-store" });
    const items = await res.json();
    renderItems(container, items, { showEventDate: true });
  } catch (e) {
    container.innerHTML = '<p class="empty">読み込みに失敗しました</p>';
  }
}

async function loadNews() {
  const container = document.getElementById("news-list");
  try {
    const res = await fetch("./data/news.json", { cache: "no-store" });
    const items = await res.json();
    renderItems(container, items, { showEventDate: false });
  } catch (e) {
    container.innerHTML = '<p class="empty">読み込みに失敗しました</p>';
  }
}

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
  const output = document.getElementById("subscription-output");
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
    output.hidden = false;
    btn.hidden = true;
  });
}

setupTabs();
loadSchedule();
loadNews();
setupPushNotifications();
