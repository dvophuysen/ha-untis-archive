"""Generate an unsigned iOS Webclip (.mobileconfig) per child.

A Webclip places an app-like icon on the home screen that opens the
child's Schul-Cockpit URL in full-screen. It also lets the home icon show
up as its own entry under Screen Time → App Limits, so it can be set to
'Always Allowed' without unblocking all of Safari.
"""

from __future__ import annotations

import base64
import plistlib
import uuid
from pathlib import Path

from .config import SETTINGS

# Deterministic namespace so each (account) gets a stable UUID across
# downloads (re-installing replaces, not duplicates).
_NS = uuid.UUID("7c3a1e2b-9d4f-4a6c-8b1e-5f2a0c9d7e10")


def _icon_b64() -> str | None:
    # The 512px PWA icon ships in the built frontend, which IS in the image.
    candidates = []
    if SETTINGS.frontend_dir:
        candidates.append(SETTINGS.frontend_dir / "icon-512.png")
        candidates.append(SETTINGS.frontend_dir / "icon-192.png")
    candidates.append(Path(__file__).parent.parent / "icon.png")
    for p in candidates:
        try:
            return base64.b64encode(p.read_bytes()).decode("ascii")
        except OSError:
            continue
    return None


def build_webclip(account_id: int, account_name: str, base_url: str) -> bytes:
    """Return the .mobileconfig bytes for one child."""
    url = f"{base_url.rstrip('/')}/?acc={account_id}"
    label = f"Schule {account_name}".strip()

    payload_uuid = str(uuid.uuid5(_NS, f"clip:{account_id}"))
    profile_uuid = str(uuid.uuid5(_NS, f"profile:{account_id}"))

    clip: dict = {
        "PayloadType": "com.apple.webClip.managed",
        "PayloadVersion": 1,
        "PayloadIdentifier": f"de.ophuysen.schulcockpit.webclip.{account_id}",
        "PayloadUUID": payload_uuid,
        "PayloadDisplayName": label,
        "URL": url,
        "Label": label,
        "IsRemovable": True,
        "FullScreen": True,           # open standalone, no Safari chrome
        "IgnoreManifestScope": True,
    }
    icon = _icon_b64()
    if icon:
        # plistlib serialises raw bytes as a <data> element (Data class was
        # removed in modern Python).
        clip["Icon"] = base64.b64decode(icon)
        clip["Precomposed"] = True

    profile: dict = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": f"de.ophuysen.schulcockpit.{account_id}",
        "PayloadUUID": profile_uuid,
        "PayloadDisplayName": f"Schul-Cockpit · {account_name}",
        "PayloadDescription": "Legt das Schul-Cockpit als App-Icon auf den Home-Bildschirm.",
        "PayloadContent": [clip],
    }
    return plistlib.dumps(profile)


def external_url_or_none() -> str | None:
    return SETTINGS.external_url or None
