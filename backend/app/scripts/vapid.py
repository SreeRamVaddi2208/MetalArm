"""Generate a VAPID key pair.

    python -m app.scripts.vapid

Prints the two values to put in the environment. Run once per deployment and
keep the private key with the other secrets: rotating it unsubscribes every
browser, because a subscription is bound to the key that created it.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    print(f"VAPID_PUBLIC_KEY={_b64(public)}")
    print(f"VAPID_PRIVATE_KEY={_b64(private)}")
    print("VAPID_SUBJECT=mailto:you@yourdomain")


if __name__ == "__main__":
    main()
