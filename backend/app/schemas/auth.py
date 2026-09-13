"""Auth request/response shapes."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES

MIN_PASSWORD_LENGTH = 8


def _validate_password(value: str) -> str:
    """Reject over-long passwords at the edge with a 422.

    bcrypt>=4 raises ValueError past 72 BYTES. Measured in bytes, not
    characters: 'ü' is two UTF-8 bytes and an emoji is four, so a 30-character
    password can exceed the limit. Truncating instead would be worse than
    rejecting - it would make every password sharing the first 72 bytes open
    the same account.
    """
    encoded = value.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"password must be at most {MAX_PASSWORD_BYTES} bytes "
            f"({len(encoded)} given; non-ASCII characters use more than one byte)"
        )
    return value


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    display_name: str = Field(min_length=1, max_length=50)
    # IANA zone name. Drives daily/weekly quest reset boundaries and streaks.
    timezone: str = Field(default="UTC", max_length=64)

    _check_password = field_validator("password")(_validate_password)

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        """Reject unknown zones instead of falling back silently.

        Storing an unrecognized zone would leave the user permanently on the
        UTC fallback while their profile claimed otherwise - and daily quests
        would reset at the wrong hour with no visible cause.
        """
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"unknown IANA timezone: {value!r}") from None
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    # Exchanged at /auth/refresh for a new pair, so a mobile client stays
    # signed in without keeping the password. Clients that only need the
    # access token (the Reflex frontend) can ignore it.
    refresh_token: str
    refresh_expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class DeleteAccountRequest(BaseModel):
    # Re-entered on purpose: an unlocked phone in the wrong hands must not be
    # able to erase the account with one tap.
    password: str = Field(min_length=1)
