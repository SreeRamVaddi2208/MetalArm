"""Auth request/response shapes."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.core.text import HumanName

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


# The passwords that get tried first. Not a strength meter - length is the
# better rule and pydantic already enforces it - just a refusal to accept the
# handful of strings that are guessed before anything else. Compared
# case-insensitively, so "Password1" is caught with "password1".
COMMON_PASSWORDS = frozenset({
    "password", "password1", "password123", "passw0rd", "12345678", "123456789",
    "1234567890", "qwertyui", "qwerty123", "letmein1", "iloveyou", "welcome1",
    "abc12345", "monkey12", "football", "baseball", "sunshine", "princess",
    "trustno1", "dragon12", "superman", "starwars", "whatever", "changeme",
})


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    display_name: HumanName = Field(min_length=1, max_length=50)
    # IANA zone name. Drives daily/weekly quest reset boundaries and streaks.
    timezone: str = Field(default="UTC", max_length=64)

    _check_password = field_validator("password")(_validate_password)

    @model_validator(mode="after")
    def _password_is_not_the_first_guess(self) -> "SignupRequest":
        """Refuse the password everyone tries, and the one written on the form
        above it.

        Checked here rather than in the field validator because it needs the
        email and the name, which a field validator cannot see. Both halves of
        the address count: somebody using "sree@example.com" as their password
        is no safer for having typed the domain too.

        These two messages are written as whole sentences, capital and all,
        because a model-level error has no field to name: the clients show it on
        its own, where "that password is..." would read like a fragment. A
        field-level message stays lowercase - it appears after "Password: ".
        """
        lowered = self.password.casefold()
        if lowered in COMMON_PASSWORDS:
            raise ValueError("That is one of the most commonly used passwords - please pick another.")

        email = str(self.email).casefold()
        forbidden = {email, email.split("@")[0], self.display_name.casefold()}
        if lowered in forbidden:
            raise ValueError("Your password cannot be your email address or your name.")
        return self

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


class LogoutRequest(BaseModel):
    # The refresh token is still valid after the access token has expired, so
    # a client signing out with it always reaches its own session.
    refresh_token: str = Field(min_length=1)


class DeleteAccountRequest(BaseModel):
    # Re-entered on purpose: an unlocked phone in the wrong hands must not be
    # able to erase the account with one tap.
    password: str = Field(min_length=1)
