"""Wer benutzt gerade das Gerät (D175)?

Ein Elterngerät kann die Kinderansicht nur lesend zeigen (mitlesen), vom Kind
selbst benutzt werden (kind) oder im Testmodus des Entwicklerkontos laufen
(test). Die Oberfläche schickt den Zustand als Kopfzeile ``X-View-Mode`` mit.
Es geht um Schutz vor Versehen, nicht um eine Sicherheitsgrenze: Eltern dürfen
ohnehin schreiben. Deshalb genügt die Kopfzeile.
"""

from __future__ import annotations

import re

from fastapi import Request
from fastapi.responses import JSONResponse

HEADER = "x-view-mode"
MODES = {"mirror", "child", "test"}
SAFE = {"GET", "HEAD", "OPTIONS"}

MIRROR_DETAIL = "Nur ansehen. Hier wird nichts geändert."
TEST_DETAIL = ("Im Testmodus geht das nicht, weil es die Lerngeschichte verändern würde. "
               "Für den Lernbegleiter „Demo ausprobieren“ nutzen.")

# Im Testmodus gesperrt: alles, was Lernverlauf, Material oder KI-Kosten erzeugt
# und sich nicht sauber zurücknehmen lässt (D158).
TEST_BLOCKED = re.compile(
    r"^/api/accounts/\d+/(learning|materials|afternoon-check|textbooks|exams/|exam-progress|exam-overrides)"
)


def mode_of(request: Request) -> str | None:
    value = (request.headers.get(HEADER) or "").strip().lower()
    return value if value in MODES else None


async def middleware(request: Request, call_next):
    mode = mode_of(request)
    request.state.view_mode = mode
    if mode and request.method not in SAFE and request.url.path.startswith("/api/"):
        if mode == "mirror":
            return JSONResponse({"detail": MIRROR_DETAIL}, status_code=403)
        if mode == "test" and TEST_BLOCKED.match(request.url.path):
            return JSONResponse({"detail": TEST_DETAIL}, status_code=403)
    return await call_next(request)


def acting_child(request: Request | None, user) -> bool:
    """Handelt hier das Kind? Eigene Anmeldung oder „Kind am Elterngerät“."""
    if getattr(user, "role", None) == "child":
        return True
    mode = getattr(getattr(request, "state", None), "view_mode", None) if request is not None else None
    return mode == "child"
