"""Register a device for server push, and take it off again.

Only the registry: nothing is SENT yet. Delivery needs an APNs key from the
Apple Developer account (docs/launch-checklist.md, "Push notifications"), and
will read this table - every row belongs to a signed-in device, because
signing out deletes the rows (app/api/routes/auth.py).
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import CurrentSessionID, CurrentUser, DbSession
from app.core.config import get_settings
from app.models.push_device import PushDevice
from app.models.web_push import WebPushSubscription
from app.schemas.push_device import PushDeviceRegister, normalize_push_token
from app.schemas.web_push import WebPushConfigOut, WebPushSubscribe

logger = logging.getLogger("metalarm.push")

router = APIRouter(prefix="/devices", tags=["devices"])

# Anyone signing in again and again on new installs would otherwise grow the
# table without bound. Ten is more phones and tablets than anyone carries; the
# least recently registered go first.
MAX_DEVICES_PER_USER = 10


@router.put("/push-token", status_code=status.HTTP_204_NO_CONTENT)
def register_push_token(
    payload: PushDeviceRegister,
    current_user: CurrentUser,
    session_id: CurrentSessionID,
    db: DbSession,
) -> None:
    """Register this device's APNs token, or refresh it.

    Idempotent: the app sends it on every launch, because iOS can hand out a
    new token at any time. A token already registered - to this account or
    another one signed in earlier on the same phone - moves to this account
    and this sign-in session.
    """
    # clock_timestamp(), not now(): now() is frozen for the whole transaction,
    # and the cap below needs registrations ordered. Set on the update path
    # too, because ON CONFLICT bypasses the ORM's onupdate.
    registered_at = func.clock_timestamp()
    db.execute(
        insert(PushDevice)
        .values(
            user_id=current_user.id,
            session_id=session_id,
            token=payload.token,
            environment=payload.environment.value,
            updated_at=registered_at,
        )
        .on_conflict_do_update(
            index_elements=[PushDevice.token],
            set_={
                "user_id": current_user.id,
                "session_id": session_id,
                "environment": payload.environment.value,
                "updated_at": registered_at,
            },
        )
    )
    _enforce_cap(db, current_user.id)
    db.commit()


def _enforce_cap(db: DbSession, user_id: uuid.UUID) -> None:
    stale = db.scalars(
        select(PushDevice.id)
        .where(PushDevice.user_id == user_id)
        .order_by(PushDevice.updated_at.desc(), PushDevice.id)
        .offset(MAX_DEVICES_PER_USER)
    ).all()
    if stale:
        db.execute(delete(PushDevice).where(PushDevice.id.in_(stale)))
        logger.info("user %s: dropped %d oldest push devices", user_id, len(stale))


@router.delete("/push-token/{token}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_push_token(token: str, current_user: CurrentUser, db: DbSession) -> None:
    """Stop notifying this device - the user turned notifications off.

    Succeeds whether or not the token was registered, so a retry is harmless,
    and only ever removes the caller's own token.
    """
    try:
        normalized = normalize_push_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    db.execute(
        delete(PushDevice).where(
            PushDevice.token == normalized, PushDevice.user_id == current_user.id
        )
    )
    db.commit()


# --- Web Push -------------------------------------------------------------
# The same registry, for browsers. Delivery is app/core/web_push.py; this is
# only who has asked to be told.


@router.get("/web-push/config", response_model=WebPushConfigOut)
def web_push_config() -> WebPushConfigOut:
    """The public half of the VAPID pair, or nothing.

    Unauthenticated on purpose: it is a public key, and the client needs it
    before it can decide whether to offer notifications at all. An empty answer
    means this deployment has no keys configured, and the client should not
    offer a button that cannot work.
    """
    return WebPushConfigOut(public_key=get_settings().vapid_public_key)


@router.post("/web-push", status_code=status.HTTP_204_NO_CONTENT)
def subscribe_web_push(
    payload: WebPushSubscribe,
    current_user: CurrentUser,
    session_id: CurrentSessionID,
    db: DbSession,
) -> None:
    """Subscribe this browser, or refresh an existing subscription.

    Idempotent for the same reason the APNs route is: a browser may hand back
    the same endpoint on every load, and a subscription already registered -
    to this account or to another one signed in earlier on the same browser -
    moves to this account and this session rather than notifying both.
    """
    registered_at = func.clock_timestamp()
    db.execute(
        insert(WebPushSubscription)
        .values(
            user_id=current_user.id,
            session_id=session_id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            updated_at=registered_at,
        )
        .on_conflict_do_update(
            index_elements=[WebPushSubscription.endpoint],
            set_={
                "user_id": current_user.id,
                "session_id": session_id,
                "p256dh": payload.keys.p256dh,
                "auth": payload.keys.auth,
                "updated_at": registered_at,
            },
        )
    )
    _enforce_web_cap(db, current_user.id)
    db.commit()


def _enforce_web_cap(db: DbSession, user_id: uuid.UUID) -> None:
    """Same cap as the phones, and for the same reason: a new subscription per
    browser profile would otherwise grow the table without bound."""
    stale = db.scalars(
        select(WebPushSubscription.id)
        .where(WebPushSubscription.user_id == user_id)
        .order_by(WebPushSubscription.updated_at.desc(), WebPushSubscription.id)
        .offset(MAX_DEVICES_PER_USER)
    ).all()
    if stale:
        db.execute(delete(WebPushSubscription).where(WebPushSubscription.id.in_(stale)))
        logger.info("user %s: dropped %d oldest web push subscriptions", user_id, len(stale))


@router.delete("/web-push", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe_web_push(
    payload: WebPushSubscribe, current_user: CurrentUser, db: DbSession
) -> None:
    """Stop notifying this browser. Succeeds whether or not it was subscribed,
    so a retry is harmless, and only ever removes the caller's own row."""
    db.execute(
        delete(WebPushSubscription).where(
            WebPushSubscription.endpoint == payload.endpoint,
            WebPushSubscription.user_id == current_user.id,
        )
    )
    db.commit()
