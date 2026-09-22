"""Google Custom Search APIでWeb全体を検索し、ロケ地/BE:Fashionの手がかりになりそうな
ファンブログ等のページを拾う(collect_web_extras.py専用、collect.pyの30分毎の収集とは無関係)。

無料枠(1日100クエリ)を大きく超えないよう、呼び出し元は1日1回程度の低頻度で実行し、
クエリ数も絞ること。
"""

import html
import logging
import re

import httpx

from befarst.config import settings

logger = logging.getLogger(__name__)

SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw_html: str) -> str:
    text = _TAG_RE.sub(" ", raw_html or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_page_text(url: str, max_chars: int = 4000) -> str | None:
    """検索結果のページ本文をベストエフォートで取得する。

    ファンブログは構成が多様でアクセス自体に失敗することもあるため、失敗時は例外を
    握りNoneを返す(呼び出し元はその場合、検索結果のsnippetだけで抽出を試みる)。
    """
    try:
        with httpx.Client(
            timeout=10.0, headers={"User-Agent": "BefarstPersonalApp/1.0"}, follow_redirects=True
        ) as client:
            resp = client.get(url)
        if resp.status_code != 200 or "html" not in resp.headers.get("content-type", ""):
            return None
        return _strip_html(resp.text)[:max_chars]
    except httpx.HTTPError:
        logger.info("Web検索結果ページの取得に失敗しました(url=%s)。snippetのみ使用します。", url)
        return None


def fetch_new_results(
    queries: list[str], existing_source_ids: set[str], results_per_query: int = 10
) -> list[dict]:
    """クエリごとにGoogle Custom Search APIを呼び出し、未処理のURLを候補として返す。"""
    if not settings.google_search_api_key or not settings.google_search_engine_id:
        logger.info("Google Custom Search未設定のため、Web検索収集をスキップしました。")
        return []

    candidates: list[dict] = []
    with httpx.Client(timeout=15.0) as client:
        for query in queries:
            try:
                resp = client.get(
                    SEARCH_ENDPOINT,
                    params={
                        "key": settings.google_search_api_key,
                        "cx": settings.google_search_engine_id,
                        "q": query,
                        "num": results_per_query,
                        "lr": "lang_ja",
                    },
                )
            except httpx.HTTPError:
                logger.exception("Google Custom Search呼び出しに失敗しました(query=%s)", query)
                continue

            if resp.status_code != 200:
                logger.warning(
                    "Google Custom Searchがエラーを返しました(query=%s, status=%s, body=%s)",
                    query,
                    resp.status_code,
                    resp.text[:300],
                )
                continue

            for item in resp.json().get("items", []):
                link = item.get("link")
                if not link or link in existing_source_ids:
                    continue
                candidates.append(
                    {
                        "source": "web_search",
                        "source_id": link,
                        "origin_label": "Web検索",
                        "query": query,
                        "title": item.get("title", ""),
                        "snippet": _strip_html(item.get("snippet", "")),
                        "url": link,
                    }
                )

    return candidates
