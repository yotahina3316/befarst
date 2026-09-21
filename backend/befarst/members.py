"""メンバー名の定義と、記事本文からのメンバー言及検出。

MEMBERページ(Phase 2)向けに、news/scheduleの各アイテムがどのメンバーに
関する内容かをタグ付けするために使う。メンバー構成が変わった場合は
`MEMBER_ALIASES` を更新すること(誕生日は別途 `recurring_events.py` を参照)。
"""

# 表示名。フロント(docs/js/app.js)のメンバー選択チップの並び順もこれに合わせる。
MEMBER_NAMES = ["SOTA", "MANATO", "JUNON", "SHUNTO", "LEO", "RYUHEI"]

# 本文中の表記ゆれ(カタカナ含む)。ここに無いスペルは検出されない。
MEMBER_ALIASES: dict[str, list[str]] = {
    "SOTA": ["SOTA", "ソウタ"],
    "MANATO": ["MANATO", "マナト"],
    "JUNON": ["JUNON", "ジュノン"],
    "SHUNTO": ["SHUNTO", "シュント"],
    "LEO": ["LEO", "レオ"],
    "RYUHEI": ["RYUHEI", "リューヘイ"],
}


def detect_members(*texts: str) -> list[str]:
    """複数テキストを結合し、言及されているメンバー名の一覧を返す(登場順)。"""
    combined = " ".join(t or "" for t in texts)
    combined_upper = combined.upper()

    found = []
    for name in MEMBER_NAMES:
        for alias in MEMBER_ALIASES[name]:
            matched = alias.upper() in combined_upper if alias.isascii() else alias in combined
            if matched:
                found.append(name)
                break
    return found
