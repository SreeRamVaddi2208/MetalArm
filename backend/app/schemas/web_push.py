"""Web Push subscription shapes."""

from pydantic import BaseModel, Field


class WebPushKeys(BaseModel):
    """Exactly what PushSubscription.toJSON() puts under `keys`."""

    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class WebPushSubscribe(BaseModel):
    """The browser's subscription, posted verbatim.

    The shape is the browser's, not ours - taking it as-is means the client can
    send `JSON.stringify(subscription)` without reshaping it, and there is one
    less place for the two to disagree.
    """

    endpoint: str = Field(min_length=1, max_length=2000)
    keys: WebPushKeys


class WebPushConfigOut(BaseModel):
    """What a browser needs before it can subscribe at all."""

    # Empty when the server has no VAPID key configured, which is the honest
    # answer: the client then knows not to offer notifications.
    public_key: str = ""
