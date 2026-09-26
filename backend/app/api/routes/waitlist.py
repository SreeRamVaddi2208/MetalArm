"""The marketing site's waitlist: one public POST.

The only unauthenticated write in MetalArm besides signup, so it is deliberately
small and deliberately boring. It says the same thing whether the address is
new or already present - answering differently would make it an oracle for
"has this person signed up?" - and it is rate limited per address for the same
reason signup is.
"""

import logging

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession
from app.core import rate_limit
from app.core.security import normalize_email
from app.models.waitlist import WaitlistEntry
from app.schemas.waitlist import WaitlistJoin, WaitlistOut

logger = logging.getLogger("metalarm.waitlist")

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


@router.post("", response_model=WaitlistOut, status_code=200)
def join_waitlist(payload: WaitlistJoin, request: Request, db: DbSession) -> WaitlistOut:
    rate_limit.enforce(rate_limit.WAITLIST_PER_IP, rate_limit.client_ip(request))

    email = normalize_email(payload.email)
    existing = db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == email))
    if existing is not None:
        return WaitlistOut()

    db.add(WaitlistEntry(email=email, source=payload.source))
    try:
        db.commit()
    except IntegrityError:
        # Two requests for the same address at once; the UNIQUE did its job.
        db.rollback()
        return WaitlistOut()
    logger.info("waitlist joined from %s", payload.source or "unknown")
    return WaitlistOut()
