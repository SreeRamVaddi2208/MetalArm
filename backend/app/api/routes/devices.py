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
from app.models.push_device import PushDevice
from app.schemas.push_device import PushDeviceRegister, normalize_push_token

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
