"""Web Push (VAPID) setup and send helper.

The VAPID keypair is generated once on first start and stored in
schema_meta so it survives across add-on restarts and updates. The
public key (PEM) is exposed to the frontend so each device can
subscribe at the browser's push service.

We send pushes via `pywebpush`, which talks the standard Web Push
Protocol to Apple's APNs / Google's FCM endpoint URLs that browsers
already encoded into their subscriptions.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .db import webapp_conn

_LOGGER = logging.getLogger("schul_cockpit.push")

# How the browser expects the public key: raw uncompressed P-256 point,
# base64url-encoded, no padding. The PEM form is what pywebpush wants on the
# server side.
_META_PRIV = "vapid:private_pem"
_META_PUB_B64 = "vapid:public_b64url"
_META_SUBJECT = "vapid:subject"

# Identifies this app to push services. RFC says it should be mailto: or
# https:// — a generic placeholder is fine because each instance is private.
DEFAULT_SUBJECT = "mailto:schul-cockpit@localhost"


def _b64url_no_pad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _generate_keypair() -> tuple[str, str]:
    priv = ec.generate_private_key(ec.SECP256R1())
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    pub_numbers = priv.public_key().public_numbers()
    # Uncompressed point: 0x04 || X || Y, each 32 bytes for P-256.
    pub_raw = b"\x04" + pub_numbers.x.to_bytes(32, "big") + pub_numbers.y.to_bytes(32, "big")
    return priv_pem, _b64url_no_pad(pub_raw)


def ensure_keys() -> dict[str, str]:
    """Return {'private_pem', 'public_b64url', 'subject'}, creating once."""
    conn = webapp_conn()
    try:
        rows = {
            r["key"]: r["value"]
            for r in conn.execute(
                "SELECT key, value FROM schema_meta WHERE key LIKE 'vapid:%'"
            ).fetchall()
        }
        if _META_PRIV in rows and _META_PUB_B64 in rows:
            return {
                "private_pem": rows[_META_PRIV],
                "public_b64url": rows[_META_PUB_B64],
                "subject": rows.get(_META_SUBJECT, DEFAULT_SUBJECT),
            }
        priv_pem, pub_b64 = _generate_keypair()
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            (_META_PRIV, priv_pem),
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            (_META_PUB_B64, pub_b64),
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            (_META_SUBJECT, DEFAULT_SUBJECT),
        )
        _LOGGER.info("Generated new VAPID keypair")
        return {
            "private_pem": priv_pem,
            "public_b64url": pub_b64,
            "subject": DEFAULT_SUBJECT,
        }
    finally:
        conn.close()


def send_push(
    subscription_info: dict,
    payload: dict[str, Any],
    *,
    ttl: int = 86400,
) -> tuple[bool, int | None]:
    """Send a single push. Returns (ok, status_code_or_None).

    On 404/410 the subscription is gone for good and should be deleted by
    the caller; on transient errors (5xx, timeout) we keep it."""
    from pywebpush import WebPushException, webpush  # local import (heavy)

    keys = ensure_keys()
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=keys["private_pem"],
            vapid_claims={"sub": keys["subject"]},
            ttl=ttl,
        )
        return True, 200
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None) if exc.response is not None else None
        _LOGGER.warning("Push failed (status=%s): %s", status, exc)
        return False, status
    except Exception:
        _LOGGER.exception("Unexpected push error")
        return False, None
