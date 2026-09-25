"""Wer benutzt gerade das Gerät (D175)?

Ein Elterngerät kann die Kinderansicht nur lesend zeigen (mitlesen), vom Kind
selbst benutzt werden (kind) oder im Testmodus des Entwicklerkontos laufen
(test). Die Oberfläche schickt den Zustand als Kopfzeile ``X-View-Mode`` mit.
Es geht um Schutz vor Versehen, nicht um eine Sicherheitsgrenze: Eltern dürfen
ohnehin schreiben. Deshalb genügt die Kopfzeile.
"""

from __future__ import annotations

import contextvars
import re

from fastapi import Request
from fastapi.responses import JSONResponse

HEADER = "x-view-mode"
MODES = {"mirror", "child", "test"}
SAFE = {"GET", "HEAD", "OPTIONS"}
# Für Stellen ohne Zugriff auf die Anfrage, etwa die Belohnung (D173).
current: contextvars.ContextVar[str | None] = contextvars.ContextVar("view_mode", default=None)

MIRROR_DETAIL = "Nur ansehen. Hier wird nichts geändert."
TEST_DETAIL = ("Im Testmodus geht das nicht, weil es die Lerngeschichte verändern würde. "
               "Für den Lernbegleiter „Demo ausprobieren“ nutzen.")

# Im Testmodus gesperrt: alles, was Lernverlauf, Material oder KI-Kosten erzeugt
# und sich nicht sauber zurücknehmen lässt (D158).
TEST_BLOCKED = re.compile(
    r"^/api/accounts/\d+/(learning|materials|afternoon-check|textbooks|exams/|exam-progress|exam-overrides|practice|vocab/)"
)


def mode_of(request: Request) -> str | None:
    value = (request.headers.get(HEADER) or "").strip().lower()
    return value if value in MODES else None


async def middleware(request: Request, call_next):
    mode = mode_of(request)
    request.state.view_mode = mode
    token = current.set(mode)
    if mode and request.method not in SAFE and request.url.path.startswith("/api/"):
        if mode == "mirror":
            current.reset(token)
            return JSONResponse({"detail": MIRROR_DETAIL}, status_code=403)
        if mode == "test" and TEST_BLOCKED.match(request.url.path):
            current.reset(token)
            return JSONResponse({"detail": TEST_DETAIL}, status_code=403)
    try:
        return await call_next(request)
    finally:
        current.reset(token)

