import logging
from datetime import datetime

import feedparser

from befarst.config import settings

logger = logging.getLogger(__name__)


def fetch_new_videos(existing_source_ids: set[str]) -> list[dict]:
    """BE:FIRST公式YouTubeチャンネルのRSSフィードから新着動画を取得する。

    YouTubeのチャンネルRSSはAPIキー不要で取得できる想定だが、
    ネットワーク環境によっては到達できない場合があるため、失敗時は空リストを返す
    (収集パイプライン全体を止めないため)。
    """
    if not settings.youtube_channel_id:
        return []

    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={settings.youtube_channel_id}"

    try:
        feed = feedparser.parse(url)
    except Exception:
        logger.exception("YouTube RSSの取得に失敗しました。")
        return []

    if feed.bozo and not feed.entries:
        logger.warning("YouTube RSSの取得結果が空、または不正な形式でした: %s", url)
        return []

    new_videos: list[dict] = []
    for entry in feed.entries:
        video_id = entry.get("yt_videoid") or entry.get("id", "").rsplit(":", 1)[-1]
        if not video_id or video_id in existing_source_ids:
            continue

        published = entry.get("published_parsed")  # UTCのtime.struct_time(feedparser仕様)
        published_at = datetime(*published[:6]) if published else datetime.utcnow()

        new_videos.append(
            {
                "source": "youtube",
                "source_id": video_id,
                "source_category": "VIDEO",
                "title": entry.get("title", ""),
                "content": entry.get("summary", ""),
                "url": entry.get("link", ""),
                "published_at": published_at,
            }
        )

    return new_videos
