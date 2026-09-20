import json
import logging
from pathlib import Path

from pywebpush import WebPushException, webpush

from befarst.config import settings

logger = logging.getLogger(__name__)

# リポジトリルート/data/subscriptions.json(Pagesで公開されないディレクトリ)に購読情報を保管する
SUBSCRIPTIONS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "subscriptions.json"


def _load_subscriptions() -> list[dict]:
    if not SUBSCRIPTIONS_PATH.exists():
        return []
    return json.loads(SUBSCRIPTIONS_PATH.read_text(encoding="utf-8"))


def notify_all(title: str, body: str, url: str = "/") -> None:
    if not settings.vapid_private_key:
        logger.info("VAPIDキー未設定のため通知をスキップしました: %s", title)
        return

    subscriptions = _load_subscriptions()
    if not subscriptions:
        logger.info("登録済みのPush購読がないため通知をスキップしました: %s", title)
        return

    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_claim_email},
            )
        except WebPushException:
            logger.exception("通知の送信に失敗しました(endpoint期限切れの可能性)")
