"""毎年決まった日に繰り返すイベント(メンバー誕生日・グループの記念日)。

公式サイトのニュース記事として毎年出るとは限らないため、収集とは別に、
直近の該当日をスケジュールとして毎回生成する。メンバー構成や記念日が
変わった場合はここを更新すること。
"""

from datetime import date, datetime, timezone

# (表示名, 月, 日) — 2026年9月時点の現メンバー6名(RYOKIは2025年脱退のため含めない)
MEMBERS: list[tuple[str, int, int]] = [
    ("SOTA", 1, 18),
    ("MANATO", 4, 29),
    ("JUNON", 5, 23),
    ("SHUNTO", 9, 1),
    ("LEO", 9, 8),
    ("RYUHEI", 11, 7),
]

# (タイトル, 月, 日) — グループの記念日。2021年11月3日にメジャーデビュー(デビュー曲「Gifted.」)
ANNIVERSARIES: list[tuple[str, int, int]] = [
    ("BE:FIRST デビュー記念日", 11, 3),
]


def _next_occurrence(month: int, day: int, today: date) -> date:
    occurrence = date(today.year, month, day)
    if occurrence < today:
        occurrence = date(today.year + 1, month, day)
    return occurrence


def _build_item(source_prefix: str, title: str, occurrence: date, schedule_category: str) -> dict:
    return {
        "source": source_prefix,
        "source_id": f"{title}-{occurrence.year}",
        "source_category": schedule_category,
        "schedule_category": schedule_category,
        "confidence": "OFFICIAL",
        "title_original": title,
        "title_ja": title,
        "summary_ja": f"{title}です。",
        "url": "https://befirst.tokyo/",
        "published_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "event_date": occurrence.isoformat(),
    }


def upcoming_recurring_events(existing_source_ids: set[str]) -> list[dict]:
    """直近のメンバー誕生日・グループ記念日をスケジュール候補として返す。"""
    today = datetime.now(timezone.utc).date()
    items: list[dict] = []

    for name, month, day in MEMBERS:
        occurrence = _next_occurrence(month, day, today)
        item = _build_item("birthday", f"{name} 誕生日", occurrence, "BIRTHDAY")
        if item["source_id"] not in existing_source_ids:
            items.append(item)

    for title, month, day in ANNIVERSARIES:
        occurrence = _next_occurrence(month, day, today)
        item = _build_item("anniversary", title, occurrence, "ANNIVERSARY")
        if item["source_id"] not in existing_source_ids:
            items.append(item)

    return items
