"""collect.py・collect_web_extras.pyで共通して使う、JSONファイルの読み書きヘルパー。

DBを持たない方針(CLAUDE.md参照)のため、news/schedule/pilgrimage/fashionの本体データも
「一度処理した候補のID」の記録も、すべて素朴なJSONファイルの読み書きで済ませている。
"""

import json
from pathlib import Path

MAX_CANDIDATE_ITEMS = 100  # 聖地巡礼/BE:FashionのAI候補は増え続けるため上限を設ける(status="confirmed"は上限対象外)


def load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_seen_ids(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_seen_ids(path: Path, seen_ids: dict[str, list[str]], max_per_source: int = 2000) -> None:
    for source in seen_ids:
        seen_ids[source] = seen_ids[source][-max_per_source:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seen_ids, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def trim_candidates(items: list[dict], max_candidates: int = MAX_CANDIDATE_ITEMS) -> list[dict]:
    """confirmed(手動確認済み)は全件保持し、candidate(AI抽出候補)は新しい順に上限まで残す。"""
    confirmed = [i for i in items if i.get("status") == "confirmed"]
    candidates = [i for i in items if i.get("status") != "confirmed"]
    candidates.sort(key=lambda x: x["created_at"], reverse=True)
    return confirmed + candidates[:max_candidates]
