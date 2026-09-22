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


EXTRAS_PROMPT_TEMPLATE = """あなたはBE:FIRSTのファン向け情報整理アシスタントです。
以下の記事本文から、次の2種類の情報を抽出してください。該当が無い場合はnull/空配列にしてください。
推測で断定せず、本文に明記されている場合のみ抽出してください。説明文は不要で、指定のJSON形式のみを出力してください。

# 記事情報
タイトル: {title}
本文(抜粋): {content}

# タスク
1. pilgrimage: BE:FIRSTのメンバーやグループに関連する具体的な「場所」(ロケ地、聖地巡礼スポットになりうる場所。例: 撮影が行われた店舗・施設、出演した会場、関連するカフェやショップ、出身地など)への言及が1件でもあれば、最も具体的なもの1件を抽出してください。「東京で」のような曖昧な地名のみの言及は対象外です。
2. fashion_items: メンバーが着用した服・アクセサリーへの具体的な言及(ブランド名やアイテム名が本文から分かるもの)があれば、複数抽出してください。

# 出力形式(このJSONのみを出力)
{{
  "pilgrimage": {{"name_ja": "場所の名称", "description": "説明(1〜2文)", "address": "住所が分かれば、無ければnull"}} または null,
  "fashion_items": [
    {{"item_name": "アイテム名", "brand": "ブランド名。分からなければnull", "member": "着用メンバー名。分からなければnull", "category": "clothing または accessory", "description": "説明(1文程度)"}}
  ]
}}
"""


WEB_EXTRAS_PROMPT_TEMPLATE = """あなたはBE:FIRSTのファン向け情報整理アシスタントです。
以下はWeb検索/YouTube検索で見つかったファン投稿のページ本文です(公式情報ではありません)。
ここから次の2種類の情報を抽出してください。該当が無い場合はどちらも空配列にしてください。
本文に明記されている場合のみ抽出し、推測や一般論での補完はしないでください。説明文は不要で、
指定のJSON形式のみを出力してください。

# 検索クエリ: {query}
# ページタイトル: {title}
# 本文(抜粋): {content}

# タスク
1. pilgrimage_spots: BE:FIRSTのメンバーやグループに関連する具体的な「場所」(ロケ地、聖地巡礼スポットになりうる場所。例: 撮影が行われた店舗・施設、出演した会場、関連するカフェやショップ、出身地など)への具体的な言及があれば、複数でもすべて抽出してください。「東京で」のような曖昧な地名のみの言及は対象外です。
2. fashion_items: メンバーが着用した服・アクセサリーへの具体的な言及(ブランド名やアイテム名が本文から分かるもの)があれば、複数抽出してください。

# 出力形式(このJSONのみを出力)
{{
  "pilgrimage_spots": [
    {{"name_ja": "場所の名称", "description": "説明(1〜2文)", "address": "住所が分かれば、無ければnull"}}
  ],
  "fashion_items": [
    {{"item_name": "アイテム名", "brand": "ブランド名。分からなければnull", "member": "着用メンバー名。分からなければnull", "category": "clothing または accessory", "description": "説明(1文程度)"}}
  ]
}}
"""


def extract_web_extras(query: str, title: str, content: str) -> dict:
    """Web検索/YouTube検索で見つかった非公式ページ1件から、聖地巡礼・BE:Fashionの候補を
    複数抽出する(ベストエフォート)。extract_extras()と異なり、まとめ記事等を想定して
    pilgrimageは複数抽出できる形にしている。失敗時や該当が無い場合は両方空で返す。
    """
    fallback = {"pilgrimage_spots": [], "fashion_items": []}

    if not settings.anthropic_api_key:
        return fallback

    prompt = WEB_EXTRAS_PROMPT_TEMPLATE.format(query=query, title=title, content=(content or "")[:3000])

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1536,
            messages=[{"role": "user", "content": prompt}],
        )
        text_block = next(block for block in response.content if block.type == "text")
        text = text_block.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.lower().startswith("json"):
                text = text[4:]
        result = json.loads(text)

        pilgrimage_spots = result.get("pilgrimage_spots")
        if not isinstance(pilgrimage_spots, list):
            pilgrimage_spots = []
        pilgrimage_spots = [p for p in pilgrimage_spots if isinstance(p, dict) and p.get("name_ja")]

        fashion_items = result.get("fashion_items")
        if not isinstance(fashion_items, list):
            fashion_items = []
        fashion_items = [f for f in fashion_items if isinstance(f, dict) and f.get("item_name")]

        return {"pilgrimage_spots": pilgrimage_spots, "fashion_items": fashion_items}
    except Exception:
        logger.exception("Web検索由来の聖地巡礼/BE:Fashion抽出に失敗しました。スキップします。")
        return fallback


def extract_extras(title: str, content: str) -> dict:
    """記事1件から聖地巡礼・BE:Fashionの候補情報をAIで抽出する(ベストエフォート)。

    失敗した場合や該当が無い場合はどちらも空扱いで返す。分類/翻訳(classify_and_summarize)
    とは別のAI呼び出しとして行い、失敗してもnews/schedule本体の処理には影響しない。
    """
    fallback = {"pilgrimage": None, "fashion_items": []}

    if not settings.anthropic_api_key:
        return fallback

    prompt = EXTRAS_PROMPT_TEMPLATE.format(title=title, content=(content or "")[:2000])

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text_block = next(block for block in response.content if block.type == "text")
        text = text_block.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.lower().startswith("json"):
                text = text[4:]
        result = json.loads(text)

        pilgrimage = result.get("pilgrimage")
        if not isinstance(pilgrimage, dict) or not pilgrimage.get("name_ja"):
            pilgrimage = None

        fashion_items = result.get("fashion_items")
        if not isinstance(fashion_items, list):
            fashion_items = []
        fashion_items = [f for f in fashion_items if isinstance(f, dict) and f.get("item_name")]

        return {"pilgrimage": pilgrimage, "fashion_items": fashion_items}
    except Exception:
        logger.exception("聖地巡礼/BE:Fashion抽出に失敗しました。スキップします。")
        return fallback
