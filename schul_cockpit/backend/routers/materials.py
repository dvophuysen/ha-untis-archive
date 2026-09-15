"""Material inbox and archive. Children may always submit; parents correct."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import Field

from .. import material_analysis as analysis
from .. import materials as store
from .. import sources
from ..auth import CurrentUser, get_current_user
from ..learning import InputModel
from .learning import access

router = APIRouter(prefix="/accounts/{account_id}/materials", tags=["materials"])
_LOGGER = logging.getLogger("schul_cockpit.materials")


class MaterialPatch(InputModel):
    kind: str | None = Field(default=None, max_length=20)
    subject_name: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=600)
    content_text: str | None = Field(default=None, max_length=30000)
    document_date: str | None = Field(default=None, max_length=10)
    period_start: str | None = Field(default=None, max_length=10)
    period_end: str | None = Field(default=None, max_length=10)
    contains_solutions: bool | None = None


class LinkIn(InputModel):
    kind: str = Field(max_length=10)
    target_id: int = Field(ge=1)


class FlagIn(InputModel):
    value: bool = True


async def _run_analysis(account_id: int, material_id: int) -> None:
    try:
        await analysis.analyze(account_id, material_id)
    except Exception:
        _LOGGER.warning("Materialauswertung für %s nicht möglich", material_id)


@router.post("")
async def upload(
    account_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    kind: str = Form(default=""),
    subject_name: str = Form(default=""),
    title: str = Form(default=""),
    task_id: int | None = Form(default=None),
    topic_id: int | None = Form(default=None),
    lesson_id: int | None = Form(default=None),
    exam_id: int | None = Form(default=None),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Drop a photo or PDF. Everything else is proposed by the analysis."""
    access(user, account_id, write=True)
    content = await file.read(store.MAX_FILE + 1)
    await file.close()
    if not content:
        raise HTTPException(422, "Die Datei ist leer.")
    if len(content) > store.MAX_FILE:
        raise HTTPException(413, "Die Datei ist größer als 12 MB.")
    mime = store.sniff(content)
    if not mime:
        raise HTTPException(415, "Bitte ein Foto (JPEG, PNG, WebP) oder ein PDF verwenden.")
    hints = {
        "kind": kind if kind in store.KINDS else "",
        "subject_name": subject_name.strip() or None,
        "title": title.strip() or None,
        "task_id": task_id, "topic_id": topic_id, "lesson_id": lesson_id, "exam_id": exam_id,
    }
    try:
        material_id = store.create(account_id, user.id, content, file.filename or "Material", mime, hints)
    except ValueError as exc:
        raise HTTPException(413, str(exc)) from None
    except Exception:
        raise HTTPException(422, "Die Datei konnte nicht gelesen werden.") from None
    background.add_task(_run_analysis, account_id, material_id)
    return store.detail(account_id, material_id) or {"id": material_id}


@router.get("")
def index(
    account_id: int,
    subject: str | None = None,
    kind: str | None = None,
    start: str | None = None,
    end: str | None = None,
    q: str | None = None,
    state: str | None = None,
    books: bool = False,
    limit: int = 100,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    access(user, account_id)
    manage = bool(user.is_admin or user.role == "parent")
    items = store.listing(account_id, subject=subject, kind=kind, start=start, end=end,
                          query=q, state=state, include_hidden=manage, include_books=books, limit=limit)
    pending = sum(1 for m in items if m["analysis_state"] in ("pending", "failed"))
    return {
        "materials": items,
        "kinds": list(store.KINDS),
        "can_write": True,
        "can_manage": manage,
        "needs_check": sum(1 for m in items if not m["verified"]),
        "pending_analysis": pending,
    }


@router.get("/sources")
def missing_sources(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Die Einkaufsliste: welche im Unterricht genannten Quellen noch fehlen.

    Muss vor /{material_id} stehen, sonst versucht FastAPI, „sources" als ID
    zu lesen. Hier wird nur gerechnet; angefordert oder abgerufen wird nichts.
    """
    access(user, account_id)
    try:
        return sources.ledger(account_id)
    except Exception:
        _LOGGER.warning("Quellenbilanz nicht berechenbar", exc_info=True)
        raise HTTPException(503, "Die Quellen konnten gerade nicht ausgewertet werden.")


@router.post("/sources/collect", status_code=202)
async def collect_sources(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Den Sammellauf von Hand anstoßen. Er läuft sonst um 14 Uhr und nachts;
    hier für den ersten Durchlauf und für die Kontrolle durch die Eltern."""
    access(user, account_id)
    if not (user.is_admin or user.role == "parent"):
        raise HTTPException(403, "Nur in der Elternansicht verfügbar")
    from ..source_collector import start_collect
    return start_collect(account_id)


@router.get("/sources/collect")
def collect_sources_state(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    from ..source_collector import collect_state
    return collect_state(account_id)


@router.get("/{material_id}")
def one(account_id: int, material_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    found = store.detail(account_id, material_id)
    if not found:
        raise HTTPException(404, "Material nicht gefunden.")
    return found


@router.get("/{material_id}/file")
def download(account_id: int, material_id: int, user: CurrentUser = Depends(get_current_user)) -> Response:
    access(user, account_id)
    row = store.file_of(account_id, material_id)
    if not row or not row["file_bytes"]:
        raise HTTPException(404, "Keine Datei hinterlegt.")
    return Response(row["file_bytes"], media_type=row["mime_type"],
                    headers={"Cache-Control": "private, no-store",
                             "Content-Disposition": f'inline; filename="{row["filename"] or "material"}"'})


@router.patch("/{material_id}")
def correct(account_id: int, material_id: int, body: MaterialPatch,
            user: CurrentUser = Depends(get_current_user)) -> dict:
    """A parent correction wins and is protected against later analysis runs."""
    access(user, account_id, write=True, parent=True)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "kind" in changes and changes["kind"] not in store.KINDS:
        raise HTTPException(422, "Unbekannte Materialart.")
    if "contains_solutions" in changes:
        changes["contains_solutions"] = int(changes["contains_solutions"])
    found = store.update(account_id, material_id, changes, by_parent=True)
    if not found:
        raise HTTPException(404, "Material nicht gefunden.")
    return found


@router.post("/{material_id}/verified")
def verify(account_id: int, material_id: int, body: FlagIn,
           user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id, write=True, parent=True)
    found = store.set_flag(account_id, material_id, "verified", int(body.value))
    if not found:
        raise HTTPException(404, "Material nicht gefunden.")
    return found


@router.post("/{material_id}/hidden")
def hide(account_id: int, material_id: int, body: FlagIn,
         user: CurrentUser = Depends(get_current_user)) -> dict:
    """Children tidy up by hiding; only parents delete for good."""
    access(user, account_id, write=True)
    found = store.set_flag(account_id, material_id, "hidden", int(body.value))
    if not found:
        raise HTTPException(404, "Material nicht gefunden.")
    return found


@router.post("/{material_id}/analysis")
async def reanalyze(account_id: int, material_id: int, background: BackgroundTasks,
                    user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id, write=True, parent=True)
    found = store.detail(account_id, material_id)
    if not found:
        raise HTTPException(404, "Material nicht gefunden.")
    background.add_task(_run_analysis, account_id, material_id)
    return {"queued": True}


@router.post("/{material_id}/links")
def add_link(account_id: int, material_id: int, body: LinkIn,
             user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id, write=True)
    try:
        ok = store.link(account_id, material_id, body.kind, body.target_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if not ok:
        raise HTTPException(404, "Material nicht gefunden.")
    return store.detail(account_id, material_id) or {}


@router.delete("/{material_id}/links")
def drop_link(account_id: int, material_id: int, kind: str, target_id: int,
              user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id, write=True)
    store.unlink(account_id, material_id, kind, target_id)
    return store.detail(account_id, material_id) or {}


@router.delete("/{material_id}", status_code=204)
def delete(account_id: int, material_id: int, user: CurrentUser = Depends(get_current_user)) -> Response:
    access(user, account_id, write=True, parent=True)
    if not store.remove(account_id, material_id):
        raise HTTPException(404, "Material nicht gefunden.")
    return Response(status_code=204)
