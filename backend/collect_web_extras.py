"""ロケ地(聖地巡礼)/BE:Fashionの候補を、公式サイト以外の情報源から拾う専用スクリプト。

collect.py(30分おき)とは別スケジュールで実行する想定(GitHub Actionsの
collect_web_extras.ymlを参照)。理由: ここで使うYouTube Data APIは無料枠のクエリ数に
上限があり、30分おきの実行には向かない。

公式サイト/YouTube公式チャンネルの記事本文にはロケ地・着用アイテムの言及がほとんど無く、
docs/data/pilgrimage.json・fashion.jsonが実質空のままになっていたため
(2026-09-23、ユーザー指摘)、YouTubeのファン投稿動画も対象に加えることにした。
公式情報ではないため、生成する候補には`origin`(表示ラベルは`origin_label`)を付与し、
フロント側で「YouTube検索」などの非公式ソースだと分かるバッジを表示する。

**Google Custom Search API(Web全体のファンブログ検索)は導入を試みたが、2026-09-23に
新規のGoogle Cloudプロジェクトでは提供終了済み(既存顧客も2027-01-01に全面終了予定)と
判明し、API有効化・課金設定・キー制限をすべて正しく行っても403エラーが解消しないことを
確認した。ユーザーとも相談の上、YouTube検索のみで運用する方針にした(CLAUDE.md参照)。"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from befarst.ai import extract_web_extras
from befarst.collectors import youtube_search
from befarst.storage import load_json, load_seen_ids, save_json, save_seen_ids, trim_candidates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("collect_web_extras")

REPO_ROOT = Path(__file__).resolve().parent.parent
PILGRIMAGE_PATH = REPO_ROOT / "docs" / "data" / "pilgrimage.json"
FASHION_PATH = REPO_ROOT / "docs" / "data" / "fashion.json"
SEEN_IDS_PATH = REPO_ROOT / "data" / "seen_ids.json"

# 無料枠(YouTube Data API: 1日1万ユニット=検索100回分)を大きく超えない範囲で絞っている。
# 増やす場合はAPIの無料枠を確認すること。
YOUTUBE_SEARCH_QUERIES = [
    "BE:FIRST ロケ地",
    "BE:FIRST 私服 ブランド 特定",
]

MAX_CANDIDATE_ITEMS = 100
RESULTS_PER_QUERY = 10


def main() -> None:
    pilgrimage_items = load_json(PILGRIMAGE_PATH)
    fashion_items = load_json(FASHION_PATH)
    seen_ids = load_seen_ids(SEEN_IDS_PATH)

    candidates = youtube_search.fetch_new_results(
        YOUTUBE_SEARCH_QUERIES, set(seen_ids.get("youtube_search", [])), RESULTS_PER_QUERY
    )

    new_pilgrimage_count = 0
    new_fashion_count = 0

    for candidate in candidates:
        seen_ids.setdefault(candidate["source"], []).append(candidate["source_id"])

        extras = extract_web_extras(
            query=candidate["query"], title=candidate["title"], content=candidate["snippet"]
        )
        now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        for idx, spot in enumerate(extras["pilgrimage_spots"]):
            pilgrimage_items.append(
                {
                    "id": f"{candidate['source']}-{candidate['source_id']}-pilgrimage-{idx}",
                    "status": "candidate",
                    "origin": candidate["source"],
                    "origin_label": candidate["origin_label"],
                    "name_ja": spot.get("name_ja"),
                    "description": spot.get("description") or "",
                    "address": spot.get("address"),
                    "image_url": None,
                    "source_url": candidate["url"],
                    "members": [],
                    "created_at": now_iso,
                }
            )
            new_pilgrimage_count += 1

        for idx, fashion_item in enumerate(extras["fashion_items"]):
            fashion_items.append(
                {
                    "id": f"{candidate['source']}-{candidate['source_id']}-fashion-{idx}",
                    "status": "candidate",
                    "origin": candidate["source"],
                    "origin_label": candidate["origin_label"],
                    "item_name": fashion_item.get("item_name"),
                    "brand": fashion_item.get("brand"),
                    "member": fashion_item.get("member"),
                    "category": fashion_item.get("category") or "clothing",
                    "description": fashion_item.get("description") or "",
                    "image_url": None,
                    "source_url": candidate["url"],
                    "created_at": now_iso,
                }
            )
            new_fashion_count += 1

    pilgrimage_items = trim_candidates(pilgrimage_items, MAX_CANDIDATE_ITEMS)
    fashion_items = trim_candidates(fashion_items, MAX_CANDIDATE_ITEMS)

    save_json(PILGRIMAGE_PATH, pilgrimage_items)
    save_json(FASHION_PATH, fashion_items)
    save_seen_ids(SEEN_IDS_PATH, seen_ids)

    logger.info(
        "YouTube検索収集完了: 検索候補=%s件, 新規pilgrimage=%s件, 新規fashion=%s件"
        "(保存件数 pilgrimage=%s, fashion=%s)",
        len(candidates),
        new_pilgrimage_count,
        new_fashion_count,
        len(pilgrimage_items),
        len(fashion_items),
    )


if __name__ == "__main__":
    main()
