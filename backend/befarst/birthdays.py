"""BE:FIRSTメンバーの誕生日(固定データ)。

公式サイトには「誕生日お知らせ」記事が毎年出るとは限らないため、
ニュース収集とは別に、直近の誕生日をスケジュールとして毎回生成する。
脱退・加入等でメンバー構成が変わった場合はここを更新すること。
"""

from datetime import date, datetime, timezone

# (表示名, 誕生月, 誕生日) — 2026年9月時点の現メンバー6名(RYOKIは2025年脱退のため含めない)
MEMBERS: list[tuple[str, int, int]] = [
    ("SOTA", 1, 18),
    ("MANATO", 4, 29),
    ("JUNON", 5, 23),
    ("SHUNTO", 9, 1),
    ("LEO", 9, 8),
    ("RYUHEI", 11, 7),
]


def upcoming_birthdays(existing_source_ids: set[str]) -> list[dict]:
    """各メンバーの直近の誕生日(今年まだなら今年、過ぎていれば来年)をスケジュール候補として返す。"""
    today = datetime.now(timezone.utc).date()
    items: list[dict] = []

    for name, month, day in MEMBERS:
        birthday = date(today.year, month, day)
        if birthday < today:
            birthday = date(today.year + 1, month, day)

        source_id = f"{name}-{birthday.year}"
        if source_id in existing_source_ids:
            continue

        items.append(
            {
                "source": "birthday",
                "source_id": source_id,
                "source_category": "BIRTHDAY",
                "schedule_category": "BIRTHDAY",
                "confidence": "OFFICIAL",
                "title_original": f"{name} Birthday",
                "title_ja": f"{name} 誕生日",
                "summary_ja": f"{name}の誕生日です。",
                "url": "https://befirst.tokyo/",
                "published_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                "event_date": birthday.isoformat(),
            }
        )

    return items
