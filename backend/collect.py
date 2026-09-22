"""GitHub Actionsから定期実行される、1回分の収集サイクル。

情報取得 → AI分類/日付抽出/翻訳/要約 → docs/data/*.json へ保存 → 新着スケジュールをPush通知、を1回実行する。
状態(重複除去)はJSONファイル自体に保存済みのsource_idで判定するため、別途DBは使わない。
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from befarst.ai import classify_and_summarize, extract_extras
from befarst.collectors import official_news, youtube
from befarst.members import detect_members
from befarst.notifications import notify_all
from befarst.recurring_events import upcoming_recurring_events
from befarst.storage import load_json, load_seen_ids, save_json, save_seen_ids, trim_candidates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("collect")

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWS_PATH = REPO_ROOT / "docs" / "data" / "news.json"
SCHEDULE_PATH = REPO_ROOT / "docs" / "data" / "schedule.json"
PILGRIMAGE_PATH = REPO_ROOT / "docs" / "data" / "pilgrimage.json"
FASHION_PATH = REPO_ROOT / "docs" / "data" / "fashion.json"
# news/scheduleの外に置く「一度処理した候補のsource_id」の記録(docsの外なのでPagesには出ない)。
# news/scheduleそのものだけをdedup判定に使うと、schedule判定された記事が
# SCHEDULE_PAST_DAYSの範囲外(=開催日がすでに数日以上前)ですぐ除外される場合に、
# その記事のsource_idがどこにも保存されず、次回実行時に「新着」として再取得→再度AI分類
# →再度Push通知、が実行のたびに永久に繰り返される不具合が発生した(2026-09-23発覚)。
SEEN_IDS_PATH = REPO_ROOT / "data" / "seen_ids.json"

MAX_NEWS_ITEMS = 200
SCHEDULE_PAST_DAYS = 3  # 直近の「見逃し確認」用に、開催済みでも数日は残す
RECURRING_SOURCES = {"birthday", "anniversary"}
RECURRING_PAST_DAYS = 400  # 誕生日/記念日は年1回のみのため、SCHEDULE_PAST_DAYSでは早く消えすぎる。翌年分が生成された後に古い方を消せる程度の猶予を持たせる
MAX_CANDIDATE_ITEMS = 100  # 聖地巡礼/BE:FashionのAI候補は増え続けるため上限を設ける(status="confirmed"は上限対象外)
MAX_SEEN_IDS_PER_SOURCE = 2000  # 無限に増え続けないよう、ソースごとに直近分のみ保持


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
    pilgrimage_items = load_json(PILGRIMAGE_PATH)
    fashion_items = load_json(FASHION_PATH)
    seen_ids = load_seen_ids(SEEN_IDS_PATH)

    candidates: list[dict] = []
    candidates += official_news.fetch_new_posts(
        existing_ids(news_items, schedule_items, source="official_news")
        | set(seen_ids.get("official_news", []))
    )
    candidates += youtube.fetch_new_videos(
        existing_ids(news_items, schedule_items, source="youtube") | set(seen_ids.get("youtube", []))
    )

    new_schedule_for_notify: list[dict] = []
    new_news_count = 0

    for candidate in candidates:
        # 分類結果がnews/scheduleどちらになるか、あるいは開催日が過去でschedule保存後すぐ
        # 除外されるかに関わらず、一度処理した候補は二度と取得・分類・通知しないようここで記録する。
        seen_ids.setdefault(candidate["source"], []).append(candidate["source_id"])

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
            "image_url": candidate.get("image_url"),
            "members": detect_members(candidate["title"], candidate["content"]),
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

        extras = extract_extras(title=candidate["title"], content=candidate["content"])
        now_iso = datetime.utcnow().isoformat()

        pilgrimage = extras["pilgrimage"]
        if pilgrimage:
            pilgrimage_items.append(
                {
                    "id": f"{candidate['source_id']}-pilgrimage",
                    "status": "candidate",
                    "origin": "official",
                    "origin_label": "公式サイト/YouTube",
                    "name_ja": pilgrimage.get("name_ja"),
                    "description": pilgrimage.get("description") or "",
                    "address": pilgrimage.get("address"),
                    "image_url": candidate.get("image_url"),
                    "source_url": candidate["url"],
                    "members": item["members"],
                    "created_at": now_iso,
                }
            )

        for idx, fashion_item in enumerate(extras["fashion_items"]):
            fashion_items.append(
                {
                    "id": f"{candidate['source_id']}-fashion-{idx}",
                    "status": "candidate",
                    "origin": "official",
                    "origin_label": "公式サイト/YouTube",
                    "item_name": fashion_item.get("item_name"),
                    "brand": fashion_item.get("brand"),
                    "member": fashion_item.get("member"),
                    "category": fashion_item.get("category") or "clothing",
                    "description": fashion_item.get("description") or "",
                    "image_url": candidate.get("image_url"),
                    "source_url": candidate["url"],
                    "created_at": now_iso,
                }
            )

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
    recurring_cutoff = (datetime.utcnow() - timedelta(days=RECURRING_PAST_DAYS)).isoformat()
    schedule_items = [
        i
        for i in schedule_items
        if i["event_date"] >= (recurring_cutoff if i["source"] in RECURRING_SOURCES else cutoff)
    ]
    schedule_items.sort(key=lambda x: x["event_date"])

    pilgrimage_items = trim_candidates(pilgrimage_items, MAX_CANDIDATE_ITEMS)
    fashion_items = trim_candidates(fashion_items, MAX_CANDIDATE_ITEMS)

    save_json(NEWS_PATH, news_items)
    save_json(SCHEDULE_PATH, schedule_items)
    save_json(PILGRIMAGE_PATH, pilgrimage_items)
    save_json(FASHION_PATH, fashion_items)
    save_seen_ids(SEEN_IDS_PATH, seen_ids, max_per_source=MAX_SEEN_IDS_PER_SOURCE)

    logger.info(
        "収集完了: 新規news=%s件, 新規schedule=%s件(誕生日/記念日%s件含む, 保存件数 news=%s, schedule=%s, "
        "pilgrimage=%s, fashion=%s)",
        new_news_count,
        len(new_schedule_for_notify),
        len(recurring_items),
        len(news_items),
        len(schedule_items),
        len(pilgrimage_items),
        len(fashion_items),
    )

    for item in new_schedule_for_notify:
        # 開催日がすでに数日以上前の場合は、今から知らせても意味のある新着ではない
        # ため通知しない(誕生日/記念日はカレンダー表示上は長期間保持するが、
        # 通知するかどうかの判断は他のカテゴリと同じ「直近かどうか」で揃える)。
        if item["event_date"] < cutoff:
            continue
        notify_all(
            title="BE:FIRST 新着スケジュール",
            body=item["title_ja"] or item["title_original"],
            url=item["url"],
        )


if __name__ == "__main__":
    main()
