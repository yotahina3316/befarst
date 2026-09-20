import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    official_site_base: str = os.getenv("OFFICIAL_SITE_BASE", "https://befirst.tokyo")
    youtube_channel_id: str = os.getenv("YOUTUBE_CHANNEL_ID", "UChNkqst-cjAoIbXb-ukn_tQ")
    vapid_private_key: str = os.getenv("VAPID_PRIVATE_KEY", "")
    vapid_claim_email: str = os.getenv("VAPID_CLAIM_EMAIL", "mailto:example@example.com")


settings = Settings()
