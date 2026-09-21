import json
import logging
from datetime import datetime

import anthropic

from befarst.config import settings

logger = logging.getLogger(__name__)

_client = None

SCHEDULE_CATEGORIES = {"LIVE", "GOODS", "RELEASE", "STREAM", "DIGITAL"}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


PROMPT_TEMPLATE = """あなたはBE:FIRSTのファン向け情報整理アシスタントです。
以下の記事情報を分析し、指定のJSON形式のみで出力してください。説明文は不要です。

# 前提
本日の日付: {today}(記事本文に年の記載がなく月日のみの場合、この日付を基準に直近の該当日を採用してください。
例えば本日が2026-09-19で本文が「9/25(金)発売」なら2026-09-25と判断してください)

# 記事情報
タイトル: {title}
カテゴリ: {category}
本文(抜粋): {content}

# タスク
1. item_type: この記事が以下のいずれかに該当する場合のみ "schedule"、それ以外(TV/ラジオ/雑誌出演、キャンペーン告知など)は "news" と判定してください。
   - LIVE: ライブ・コンサート・ファンミーティング等の開催日、チケット先行/一般販売開始日
   - GOODS: グッズの発売日・受注開始日
   - RELEASE: DVD/Blu-rayの発売日
   - STREAM: YouTube生配信・オンラインイベント・リスニングパーティー等の開催日時
   - DIGITAL: 配信限定の楽曲・EP・アルバムのリリース日(サブスク/ダウンロード配信開始日)
2. schedule_category: item_typeが"schedule"の場合、上記のどれに該当するか "LIVE" / "GOODS" / "RELEASE" / "STREAM" / "DIGITAL" のいずれかを入れてください。newsの場合は null。
3. event_date: item_typeが"schedule"で、本文中に具体的な日付が明記されている場合はISO 8601形式(YYYY-MM-DD、時刻が分かればYYYY-MM-DDTHH:MM:SS)で抽出してください。
   日付が分からない/対象外の場合は null にしてください(その場合item_typeも"news"にしてください)。
4. deadline_date: 本文中に「チケット先行受付の締切」「応募締切」など、上記event_dateとは別の申込み締切日が明記されている場合、ISO 8601形式の日付で抽出してください。無ければ null。
5. title_ja: タイトルを自然な日本語にしてください(すでに日本語なら整形のみでそのまま可)。
6. summary_ja: 本文を2〜3文程度の日本語で要約してください。

# 出力形式(このJSONのみを出力)
{{
  "item_type": "news または schedule",
  "schedule_category": "LIVE / GOODS / RELEASE / STREAM / DIGITAL / null",
  "event_date": "ISO8601形式の日付、または null",
  "deadline_date": "ISO8601形式の日付、または null",
  "title_ja": "日本語タイトル",
  "summary_ja": "日本語要約"
}}
"""


def classify_and_summarize(title: str, category: str, content: str) -> dict:
    """記事1件をAIで分類・日付抽出・翻訳・要約する。

    失敗した場合は安全側(news扱い・元タイトルのまま)にフォールバックする。
    """
    fallback = {
        "item_type": "news",
        "schedule_category": None,
        "event_date": None,
        "deadline_date": None,
        "title_ja": title,
        "summary_ja": "",
    }

    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY が未設定のため、AI処理をスキップしました。")
        return fallback

    prompt = PROMPT_TEMPLATE.format(
        today=datetime.utcnow().strftime("%Y-%m-%d"),
        title=title,
        category=category or "不明",
        content=(content or "")[:2000],
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        # 拡張思考が有効だとcontent[0]がthinkingブロックになるため、text型のブロックを探す
        text_block = next(block for block in response.content if block.type == "text")
        text = text_block.text.strip()
        # モデルが```json ... ```で囲むことがあるため除去する
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.lower().startswith("json"):
                text = text[4:]
        result = json.loads(text)

        schedule_category = result.get("schedule_category")
        item_type = result.get("item_type", "news")
        if item_type == "schedule" and schedule_category not in SCHEDULE_CATEGORIES:
            # 分類が不正/対象外カテゴリならnews扱いにフォールバック
            item_type = "news"
            schedule_category = None

        return {
            "item_type": item_type,
            "schedule_category": schedule_category,
            "event_date": result.get("event_date"),
            "deadline_date": result.get("deadline_date"),
            "title_ja": result.get("title_ja") or title,
            "summary_ja": result.get("summary_ja") or "",
        }
    except Exception:
        logger.exception("AI分類処理に失敗しました。フォールバック値を使用します。")
        return fallback
