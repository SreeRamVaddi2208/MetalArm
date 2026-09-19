"""Push device registration payloads (app/api/routes/devices.py)."""

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

_HEX = re.compile(r"^[0-9a-f]+$")


class PushEnvironment(StrEnum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


def normalize_push_token(value: str) -> str:
    """Lowercase hex with no spaces or angle brackets, whatever form it came
    in: older iOS code printed the token as "<a1b2 c3d4 ...>", and one device
    registered twice in two spellings would be notified twice."""
    token = value.strip().strip("<>").replace(" ", "").lower()
    if not token or not _HEX.fullmatch(token) or len(token) % 2:
        raise ValueError("token must be the device token as hex")
    return token


class PushDeviceRegister(BaseModel):
    # 64 hex characters today; Apple reserves the right to lengthen it.
    token: str = Field(min_length=16, max_length=200)
    environment: PushEnvironment

    @field_validator("token")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_push_token(value)
