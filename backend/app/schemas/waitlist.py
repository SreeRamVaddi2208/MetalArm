"""Waitlist request and response shapes."""

from pydantic import BaseModel, EmailStr, Field


class WaitlistJoin(BaseModel):
    email: EmailStr
    # Which section of the marketing page the person joined from. Optional,
    # and never trusted for anything beyond a note to ourselves.
    source: str | None = Field(default=None, max_length=40)


class WaitlistOut(BaseModel):
    """Deliberately says the same thing whether or not the address was already
    on the list: a different answer would turn this into a way to test whether
    someone had signed up."""

    joined: bool = True
    message: str = "You're on the list."
