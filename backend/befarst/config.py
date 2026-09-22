import os

from dotenv import load_dotenv

load_dotenv()


def _clean_env(name: str, default: str = "") -> str:
    """環境変数を読み込み、UTF-8 BOM(﻿)と前後の空白を除去する。

    GitHub Actions Secretsの値にBOMが混入しており、Anthropic APIのHTTPヘッダー構築
    (UnicodeEncodeError)やVAPID claimsの`sub`検証(mailto:で始まらないため不正判定)が
    失敗し、collect.pyが毎回クラッシュする不具合が発生した(2026-09-22)。
    原因(secret設定時にBOM付きファイルから値を読み込んだ等)を特定できなくても
    ここで無害化できるよう、環境変数読み込みは必ずこの関数を経由する。
    """
    return os.getenv(name, default).strip().lstrip("﻿").strip()


class Settings:
    anthropic_api_key: str = _clean_env("ANTHROPIC_API_KEY")
    official_site_base: str = _clean_env("OFFICIAL_SITE_BASE", "https://befirst.tokyo")
    youtube_channel_id: str = _clean_env("YOUTUBE_CHANNEL_ID", "UChNkqst-cjAoIbXb-ukn_tQ")
    vapid_private_key: str = _clean_env("VAPID_PRIVATE_KEY")
    vapid_claim_email: str = _clean_env("VAPID_CLAIM_EMAIL", "mailto:example@example.com")
    # ロケ地/BE:Fashionの候補をWeb検索(Google Custom Search)/YouTube検索(YouTube Data API)
    # から拾うための鍵(collect_web_extras.py専用、未設定ならその収集だけスキップされる)。
    # どちらもGoogle Cloud ConsoleのAPIキーで、有効化するAPIが違うだけなので同じキーの
    # 使い回しも可能(その場合はGOOGLE_SEARCH_API_KEYとYOUTUBE_DATA_API_KEYに同じ値を設定する)。
    google_search_api_key: str = _clean_env("GOOGLE_SEARCH_API_KEY")
    google_search_engine_id: str = _clean_env("GOOGLE_SEARCH_ENGINE_ID")
    youtube_data_api_key: str = _clean_env("YOUTUBE_DATA_API_KEY")


settings = Settings()
