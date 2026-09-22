"""毎年決まった日に繰り返すイベント(メンバー誕生日・グループの記念日)。

公式サイトのニュース記事として毎年出るとは限らないため、収集とは別に、
直近の該当日をスケジュールとして毎回生成する。メンバー構成や記念日が
変わった場合はここを更新すること。
"""

from datetime import date, datetime, timezone

from befarst.members import MEMBER_NAMES

# (表示名, 月, 日) — 2026年9月時点の現メンバー6名(RYOKIは2025年脱退のため含めない)
MEMBERS: list[tuple[str, int, int]] = [
    ("SOTA", 1, 18),
    ("MANATO", 4, 29),
    ("JUNON", 5, 23),
    ("SHUNTO", 9, 1),
    ("LEO", 9, 8),
    ("RYUHEI", 11, 7),
]

# (安定キー, タイトル, 月, 日) — グループの記念日。2021年11月3日にメジャーデビュー(デビュー曲「Gifted.」)
ANNIVERSARIES: list[tuple[str, str, int, int]] = [
    ("debut", "BE:FIRST デビュー記念日", 11, 3),
]


def _occurrences(month: int, day: int, today: date) -> list[date]:
    """当年と翌年、両方の日付を返す。

    「今後の直近1件」だけを返すと、すでに今年の誕生日を迎えたメンバーの分は
    来年の日付にしか存在しなくなり、カレンダーを開いても(半年〜1年先まで
    ページをめくらない限り)誕生日が一切表示されない状態になっていた
    (2026-09-23発覚)。当年分も常に生成しておくことで、今年すでに過ぎた日付
    も含めてカレンダー上のその月を開けば表示されるようにする。
    """
    return [date(today.year, month, day), date(today.year + 1, month, day)]


def _build_item(
    source_prefix: str,
    key: str,
    title: str,
    occurrence: date,
    schedule_category: str,
    members: list[str],
    image_url: str | None,
) -> dict:
    # source_idは表示文言(title)ではなく安定した`key`から生成する。過去にtitleの
    # 文言(英語"Birthday"→日本語"誕生日"など)を変えた際、source_idもtitleに連動して
    # 変わってしまい、同じ誕生日/記念日が毎回「新規」と誤判定され続ける不具合が発生した
    # (2026-09-21〜22)。以後、表示文言はいつでも変更できるが`key`は変えないこと。
    return {
        "source": source_prefix,
        "source_id": f"{key}-{occurrence.year}",
        "source_category": schedule_category,
        "schedule_category": schedule_category,
        "confidence": "OFFICIAL",
        "title_original": title,
        "title_ja": title,
        "summary_ja": f"{title}です。",
        "image_url": image_url,
        "members": members,
        "url": "https://befirst.tokyo/",
        "published_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "event_date": occurrence.isoformat(),
    }


def upcoming_recurring_events(existing_source_ids: set[str]) -> list[dict]:
    """直近のメンバー誕生日・グループ記念日をスケジュール候補として返す。"""
    today = datetime.now(timezone.utc).date()
    items: list[dict] = []

    for name, month, day in MEMBERS:
        image_url = f"./images/members/{name.lower()}.webp"
        for occurrence in _occurrences(month, day, today):
            item = _build_item("birthday", name, f"{name} 誕生日", occurrence, "BIRTHDAY", [name], image_url)
            if item["source_id"] not in existing_source_ids:
                items.append(item)

    for key, title, month, day in ANNIVERSARIES:
        for occurrence in _occurrences(month, day, today):
            # グループ全体の記念日なので、全メンバーのページに表示されるようタグ付けする
            item = _build_item("anniversary", key, title, occurrence, "ANNIVERSARY", list(MEMBER_NAMES), None)
            if item["source_id"] not in existing_source_ids:
                items.append(item)

    return items
