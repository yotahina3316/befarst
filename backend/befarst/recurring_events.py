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
    """当年の日付(過ぎていても)と、当年分がすでに過ぎている場合のみ翌年の日付も返す。

    「今後の直近1件」だけを返すと、すでに今年の誕生日を迎えたメンバーの分は
    来年の日付にしか存在しなくなり、カレンダーを開いても(半年〜1年先まで
    ページをめくらない限り)誕生日が一切表示されない状態になっていた
    (2026-09-23発覚)。一方で、当年・翌年を無条件に両方返すと、当年分がまだ
    来ていないメンバー(例: 11月生まれの場合、9月時点では当年の誕生日はまだ
    「今後の予定」)については当年・翌年の両方が同時に「未来の予定」として
    該当してしまい、MEMBERページの予定一覧やSCHEDULEカレンダーに同じ予定が
    2件(今年分・来年分)重複して表示される不具合が発生した(2026-09-23、
    デビュー記念日が2件表示される形で発覚)。翌年分は当年分がすでに過ぎて
    いる場合にのみ追加することで、「今後の予定」は常に1件だけになるようにする。
    """
    this_year = date(today.year, month, day)
    if this_year < today:
        return [this_year, date(today.year + 1, month, day)]
    return [this_year]


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
        # カード上に月日が出ないと「誕生日」とだけ表示されて本人の誕生日がいつなのか
        # 分からない、という指摘(2026-09-23)があったため、要約文に日付を明記する。
        "summary_ja": f"{occurrence.month}月{occurrence.day}日です。",
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
