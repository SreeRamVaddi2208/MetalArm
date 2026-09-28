"""Sending a Web Push notification, and deciding whether to.

The launch checklist's rule, applied here rather than left to the caller:
"Decide what is worth waking someone for. Party events only, and never a nag."
So this module exposes named reasons rather than a generic send(), and there
is no way to reach it with arbitrary copy.

A dead subscription is not an error worth retrying. A push service answers 404
or 410 for one the browser has thrown away - a cleared site, an uninstall, a
rotated endpoint - and the only correct response is to forget it, which is
what happens here. Anything else and the table fills with addresses that can
never be delivered to.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.web_push import WebPushSubscription

logger = logging.getLogger("metalarm.webpush")

# The push services answer with these when a subscription is gone for good.
GONE = {404, 410}


@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    # Where tapping it should land. Always a path within the app.
    path: str = "/dashboard"


def party_quest_completed(who: str, quest: str) -> Notification:
    return Notification(title="Your party moved", body=f"{who} completed “{quest}”.", path="/parties")


def duel_challenge(who: str) -> Notification:
    return Notification(title="You have been challenged", body=f"{who} wants a duel.", path="/duels")


def duel_resolved(won: bool, who: str) -> Notification:
    return Notification(
        title="A duel has ended",
        body=f"You beat {who}." if won else f"{who} beat you.",
        path="/duels",
    )


def configured() -> bool:
    """Whether this deployment can send at all. The two keys are validated as a
    pair at startup (Settings), so checking one is enough."""
    return bool(get_settings().vapid_private_key)


def send_to_user(db: Session, user_id, notification: Notification) -> int:
    """Notify every browser this user has subscribed. Returns how many were
    delivered to; never raises, because a notification failing must not take
    down whatever was being done when it fired."""
    if not configured():
        return 0
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:  # pragma: no cover - the dependency is optional
        logger.warning("pywebpush is not installed; not sending")
        return 0

    settings = get_settings()
    payload = json.dumps(
        {"title": notification.title, "body": notification.body, "path": notification.path}
    )
    sent = 0
    dead: list[str] = []
    for row in db.scalars(select(WebPushSubscription).where(WebPushSubscription.user_id == user_id)):
        try:
            webpush(
                subscription_info={
                    "endpoint": row.endpoint,
                    "keys": {"p256dh": row.p256dh, "auth": row.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
                timeout=10,
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in GONE:
                dead.append(row.endpoint)
            else:
                logger.warning("web push to %s failed: %s", row.endpoint[:40], status or exc)
        except Exception as exc:  # noqa: BLE001 - never let a notification break a request
            logger.warning("web push error: %s", exc)

    if dead:
        db.execute(delete(WebPushSubscription).where(WebPushSubscription.endpoint.in_(dead)))
        db.commit()
        logger.info("dropped %d dead web push subscriptions", len(dead))
    return sent
