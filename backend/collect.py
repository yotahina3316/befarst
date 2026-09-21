"""GitHub Actionsから定期実行される、1回分の収集サイクル。

情報取得 → AI分類/日付抽出/翻訳/要約 → docs/data/*.json へ保存 → 新着スケジュールをPush通知、を1回実行する。
状態(重複除去)はJSONファイル自体に保存済みのsource_idで判定するため、別途DBは使わない。
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from befarst.ai import classify_and_summarize
from befarst.collectors import official_news, youtube
from befarst.notifications import notify_all
from befarst.recurring_events import upcoming_recurring_events

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("collect")

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWS_PATH = REPO_ROOT / "docs" / "data" / "news.json"
SCHEDULE_PATH = REPO_ROOT / "docs" / "data" / "schedule.json"

MAX_NEWS_ITEMS = 200
SCHEDULE_PAST_DAYS = 3  # 直近の「見逃し確認」用に、開催済みでも数日は残す


def load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def existing_ids(*item_lists: list[dict], source: str) -> set[str]:
    ids: set[str] = set()
    for items in item_lists:
        ids |= {item["source_id"] for item in items if item["source"] == source}
    return ids


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        cleaned = raw.rstrip("Z")
        datetime.fromisoformat(cleaned)  # 妥当性チェック
        return cleaned
    except (ValueError, AttributeError):
        return None


def main() -> None:
    news_items = load_json(NEWS_PATH)
    schedule_items = load_json(SCHEDULE_PATH)

    candidates: list[dict] = []
    candidates += official_news.fetch_new_posts(
        existing_ids(news_items, schedule_items, source="official_news")
    )
    candidates += youtube.fetch_new_videos(
        existing_ids(news_items, schedule_items, source="youtube")
    )

    new_schedule_for_notify: list[dict] = []
    new_news_count = 0

    for candidate in candidates:
        ai_result = classify_and_summarize(
            title=candidate["title"],
            category=candidate["source_category"],
            content=candidate["content"],
        )

        event_date = _parse_date(ai_result.get("event_date"))
        deadline_date = _parse_date(ai_result.get("deadline_date"))

        item = {
            "source": candidate["source"],
            "source_id": candidate["source_id"],
            "source_category": candidate["source_category"],
            "confidence": "OFFICIAL",
            "title_original": candidate["title"],
            "title_ja": ai_result["title_ja"],
            "summary_ja": ai_result["summary_ja"],
            "url": candidate["url"],
            "published_at": candidate["published_at"].isoformat(),
        }

        if ai_result["item_type"] == "schedule" and event_date:
            item["event_date"] = event_date
            item["schedule_category"] = ai_result["schedule_category"]
            schedule_items.append(item)
            new_schedule_for_notify.append(item)

            if deadline_date:
                deadline_item = dict(item)
                deadline_item["source_id"] = f"{candidate['source_id']}-deadline"
                deadline_item["schedule_category"] = "DEADLINE"
                deadline_item["event_date"] = deadline_date
                deadline_item["title_ja"] = f"{item['title_ja']}(申込締切)"
                schedule_items.append(deadline_item)
                new_schedule_for_notify.append(deadline_item)
        else:
            news_items.append(item)
            new_news_count += 1

    # メンバー誕生日・グループ記念日(公式サイトのニュースとは別枠で、直近の日付を毎回補充する)
    recurring_existing = existing_ids(schedule_items, source="birthday") | existing_ids(
        schedule_items, source="anniversary"
    )
    recurring_items = upcoming_recurring_events(recurring_existing)
    for item in recurring_items:
        schedule_items.append(item)
        new_schedule_for_notify.append(item)

    news_items.sort(key=lambda x: x["published_at"], reverse=True)
    news_items = news_items[:MAX_NEWS_ITEMS]

    cutoff = (datetime.utcnow() - timedelta(days=SCHEDULE_PAST_DAYS)).isoformat()
    schedule_items = [i for i in schedule_items if i["event_date"] >= cutoff]
    schedule_items.sort(key=lambda x: x["event_date"])

    save_json(NEWS_PATH, news_items)
    save_json(SCHEDULE_PATH, schedule_items)

    logger.info(
        "収集完了: 新規news=%s件, 新規schedule=%s件(誕生日/記念日%s件含む, 保存件数 news=%s, schedule=%s)",
        new_news_count,
        len(new_schedule_for_notify),
        len(recurring_items),
        len(news_items),
        len(schedule_items),
    )

    for item in new_schedule_for_notify:
        notify_all(
            title="BE:FIRST 新着スケジュール",
            body=item["title_ja"] or item["title_original"],
            url=item["url"],
        )


if __name__ == "__main__":
    main()
