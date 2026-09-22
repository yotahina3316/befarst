"""YouTube Data API v3でファン投稿動画を検索し、ロケ地/BE:Fashionの手がかりを拾う
(collect_web_extras.py専用)。

`befarst/collectors/youtube.py`が公式チャンネルのRSSから新着動画を取得するのに対し、
こちらはキーワード検索(search.list)でチャンネルを問わず関連動画を横断的に探す。
無料枠は1日1万ユニットで、search.list呼び出し1回が100ユニットのため、1日1回・
数クエリ程度の実行であれば十分収まる。
"""

import logging

import httpx

from befarst.config import settings

logger = logging.getLogger(__name__)

SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"


def fetch_new_results(queries: list[str], existing_source_ids: set[str], results_per_query: int = 10) -> list[dict]:
    """クエリごとにYouTube動画を検索し、未処理のvideoIdを候補として返す(タイトル+概要欄付き)。"""
    if not settings.youtube_data_api_key:
        logger.info("YouTube Data API未設定のため、YouTube検索収集をスキップしました。")
        return []

    video_ids: list[str] = []
    meta_by_id: dict[str, dict] = {}

    with httpx.Client(timeout=15.0) as client:
        for query in queries:
            try:
                resp = client.get(
                    SEARCH_ENDPOINT,
                    params={
                        "key": settings.youtube_data_api_key,
                        "q": query,
                        "part": "snippet",
                        "type": "video",
                        "maxResults": results_per_query,
                        "relevanceLanguage": "ja",
                    },
                )
            except httpx.HTTPError:
                logger.exception("YouTube検索呼び出しに失敗しました(query=%s)", query)
                continue

            if resp.status_code != 200:
                logger.warning(
                    "YouTube検索がエラーを返しました(query=%s, status=%s, body=%s)",
                    query,
                    resp.status_code,
                    resp.text[:300],
                )
                continue

            for item in resp.json().get("items", []):
                video_id = item.get("id", {}).get("videoId")
                if not video_id or video_id in existing_source_ids or video_id in meta_by_id:
                    continue
                video_ids.append(video_id)
                meta_by_id[video_id] = {"query": query, "snippet": item.get("snippet", {})}

        candidates: list[dict] = []
        # search.listのsnippet.descriptionは概要欄が切り詰められているため、videos.listで
        # フルの概要欄を取り直す(50件までまとめて1回のリクエストで取得できる)。
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            try:
                resp = client.get(
                    VIDEOS_ENDPOINT,
                    params={
                        "key": settings.youtube_data_api_key,
                        "id": ",".join(batch),
                        "part": "snippet",
                    },
                )
                resp.raise_for_status()
                full_snippets = {v["id"]: v["snippet"] for v in resp.json().get("items", [])}
            except httpx.HTTPError:
                logger.exception("YouTube動画詳細の取得に失敗しました。search結果のsnippetで代用します。")
                full_snippets = {}

            for video_id in batch:
                snippet = full_snippets.get(video_id, meta_by_id[video_id]["snippet"])
                candidates.append(
                    {
                        "source": "youtube_search",
                        "source_id": video_id,
                        "origin_label": "YouTube検索",
                        "query": meta_by_id[video_id]["query"],
                        "title": snippet.get("title", ""),
                        "snippet": snippet.get("description", ""),
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                    }
                )

    return candidates
