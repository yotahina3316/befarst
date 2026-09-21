import html
import logging
import re
from datetime import datetime

import httpx

from befarst.config import settings

logger = logging.getLogger(__name__)

# https://befirst.tokyo/wp-json/wp/v2/categories で確認済みのカテゴリID対応表(2026年9月時点)
CATEGORY_MAP = {
    1: "NEWS",
    9: "MEDIA",
    10: "TV",
    11: "RADIO",
    12: "WEB",
    13: "MAGAZINE",
    14: "LIVE",
    15: "MUSIC",
    16: "DVD_BD",
    17: "GOODS",
    18: "CM",
}

_TAG_RE = re.compile(r"<[^>]+>")
_IMG_SRC_RE = re.compile(r'<img[^>]+src="([^"]+)"')


def _strip_html(raw_html: str) -> str:
    text = _TAG_RE.sub(" ", raw_html or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _first_image_url(raw_html: str) -> str | None:
    """本文HTML中の最初の<img src>を記事のサムネイルとして使う。

    公式サイトはWordPressの「アイキャッチ画像」機能を使っておらず(featured_media
    は常に0)、画像は本文中に直接埋め込まれているため、この方式で抽出する。
    """
    match = _IMG_SRC_RE.search(raw_html or "")
    return html.unescape(match.group(1)) if match else None


def _category_label(category_ids: list[int]) -> str:
    labels = [CATEGORY_MAP.get(cid) for cid in category_ids]
    labels = [label for label in labels if label]
    return "/".join(labels) if labels else "NEWS"


def fetch_new_posts(existing_source_ids: set[str], max_pages: int = 5) -> list[dict]:
    """BE:FIRST公式サイト(WordPress)のニュース投稿を新しい順に取得する。

    既知のsource_idに到達した時点で収集を打ち切る(全件を毎回取得しない)。
    """
    base = f"{settings.official_site_base}/wp-json/wp/v2/posts"
    new_posts: list[dict] = []

    with httpx.Client(timeout=15.0, headers={"User-Agent": "BefarstPersonalApp/1.0"}) as client:
        for page in range(1, max_pages + 1):
            try:
                resp = client.get(
                    base,
                    params={
                        "per_page": 20,
                        "page": page,
                        "_fields": "id,date_gmt,link,title,content,categories",
                    },
                )
            except httpx.HTTPError:
                logger.exception("公式サイトのニュース取得に失敗しました(page=%s)", page)
                break

            if resp.status_code != 200:
                break

            posts = resp.json()
            if not posts:
                break

            reached_known_item = False
            for post in posts:
                source_id = str(post["id"])
                if source_id in existing_source_ids:
                    reached_known_item = True
                    break

                new_posts.append(
                    {
                        "source": "official_news",
                        "source_id": source_id,
                        "source_category": _category_label(post.get("categories", [])),
                        "title": _strip_html(post["title"]["rendered"]),
                        "content": _strip_html(post["content"]["rendered"]),
                        "image_url": _first_image_url(post["content"]["rendered"]),
                        "url": post["link"],
                        # date_gmtはUTCだがオフセット表記を含まないnaive文字列のため、そのままnaive UTCとして扱う
                        "published_at": datetime.fromisoformat(post["date_gmt"]),
                    }
                )

            if reached_known_item:
                break

    return new_posts
