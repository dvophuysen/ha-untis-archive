"""Material inbox and archive. Children may always submit; parents correct."""

from __future__ import annotations

import json
import logging
from contextlib import closing

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import Field

from .. import material_analysis as analysis
from .. import materials as store
from .. import notice_check
from .. import proofread
from .. import sources
from ..auth import CurrentUser, get_current_user
from ..view_mode import acts_as_parent
from ..db import webapp_conn
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
    source_label: str | None = Field(default=None, max_length=40)
    source_page: int | None = Field(default=None, ge=0, le=1999)
    # Eine Doppelseite hat zwei gedruckte Seiten; die erste ist source_page.
    printed_pages: list[int] | None = Field(default=None, max_length=4)


class SuggestionIn(InputModel):
    label: str = Field(max_length=40)
    page: int = Field(ge=1, le=1999)
    suggest: int = Field(ge=1, le=1999)


class SuggestionsIn(InputModel):
    fixes: list[SuggestionIn] = Field(min_length=1, max_length=20)


class DoubtIn(InputModel):
    """Eine Zweifelsstelle erledigen: `replace` gesetzt heißt „so heißt es
    richtig", leer heißt „so stimmt es"."""
    text: str = Field(min_length=1, max_length=300)
    replace: str | None = Field(default=None, max_length=300)


class LinkIn(InputModel):
    kind: str = Field(max_length=10)
    target_id: int = Field(ge=1)
    # Rolle des Bezugs (D85): blatt, ergebnis oder stoff; ohne Angabe folgt sie der Materialart.
    relation: str | None = Field(default=None, pattern=r"^(blatt|ergebnis|stoff)$")


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
    homework_id: int | None = Form(default=None),
    source_label: str = Form(default=""),
    source_page: int | None = Form(default=None),
    # Ein neues Foto für eine unscharfe oder abgeschnittene Seite (D165).
    replaces: int | None = Form(default=None),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Drop a photo or PDF. Everything else is proposed by the analysis.

    Mit source_label und source_page kommt das Foto von der Einkaufsliste und
    belegt genau diese Stelle, ohne dass die Auswertung sie erst erkennen muss.
    """
    access(user, account_id, write=True)
    old = store.detail(account_id, replaces) if replaces else None
    if replaces and (not old or old.get("origin") == "book_fetch"):
        raise HTTPException(404, "Das Material zum Ersetzen gibt es nicht.")
    if old:
        # Das neue Foto zeigt dieselbe Seite: Art, Fach und Stelle übernehmen.
        kind = kind or old.get("kind") or ""
        subject_name = subject_name or old.get("subject_name") or ""
        title = title or old.get("title") or ""
        source_label = source_label or old.get("source_label") or ""
        source_page = source_page or old.get("source_page")
    content = await file.read(store.MAX_FILE + 1)
    await file.close()
    if not content:
        raise HTTPException(422, "Die Datei ist leer.")
    if len(content) > store.MAX_FILE:
        raise HTTPException(413, "Die Datei ist größer als 12 MB.")
    mime = store.sniff(content)
    if not mime:
        raise HTTPException(415, "Bitte ein Foto (JPEG, PNG, WebP) oder ein PDF verwenden.")
    source_label = source_label.strip()
    # Eine Stelle ohne erkennbaren Buchteil („S. 105“ ohne Buch) heißt in der
    # Einkaufsliste „Unbekannte Quelle“. Bis 1.13.31 lehnte der Server ihr Foto
    # als unbekannten Buchteil ab, und in der App geschah scheinbar nichts. Jetzt
    # belegt das Foto die Stelle; welches Buch es ist, erkennt die Auswertung.
    unknown_part = source_label == sources.UNKNOWN_PART
    if source_label and not unknown_part and source_label not in store.BOOK_PARTS:
        raise HTTPException(422, "Unbekannter Buchteil.")
    # Getippt oder gewählt: gespeichert wird die Schreibweise des Stundenplans.
    subject_name = store.canonical_subject(account_id, subject_name) or ""
    # Ein Blatt (Seite 0) wird nicht je Fach beansprucht, sondern an seinen
    # Eintrag gehängt (homework_id oder lesson_id, D85).
    claimed = bool(source_label and source_page and subject_name)
    if source_label and not kind and not unknown_part:
        kind = {"Arbeitsheft": "workbook", "Grammatikheft": "workbook", "Arbeitsblatt": "worksheet"}.get(source_label, "book_page")
    if claimed and not title.strip() and kind != "toc" and not unknown_part:
        title = f"{source_label} {sources.page_list([source_page])}" if source_page else source_label
    hints = {
        "kind": kind if kind in store.KINDS else "",
        "subject_name": subject_name or None,
        "title": title.strip() or None,
        "task_id": task_id, "topic_id": topic_id, "lesson_id": lesson_id, "exam_id": exam_id, "homework_id": homework_id,
        "source_label": (source_label or None) if not unknown_part else None,
        "source_page": source_page if source_page else None,
    }
    try:
        material_id = store.create(account_id, user.id, content, file.filename or "Material", mime, hints)
    except ValueError as exc:
        raise HTTPException(413, str(exc)) from None
    except Exception:
        raise HTTPException(422, "Die Datei konnte nicht gelesen werden.") from None
    if claimed:
        try:
            sources.claim(account_id, subject_name, source_label.strip(), int(source_page), material_id)
        except Exception:
            _LOGGER.warning("Zuordnung des Fotos zur Stelle nicht gespeichert", exc_info=True)
    if old:
        store.replace(account_id, old["id"], material_id)
    background.add_task(_run_analysis, account_id, material_id)
    found = store.detail(account_id, material_id) or {"id": material_id}
    # Dieselbe Seite schon einmal fotografiert? Dann sagen wir es gleich,
    # statt zwei Lesungen zu bezahlen und zwei Einträge zu zeigen.
    found["duplicate_of"] = store.duplicate_of(account_id, material_id)
    return found


@router.get("")
def index(
    account_id: int,
    subject: str | None = None,
    kind: str | None = None,
    start: str | None = None,
    end: str | None = None,
    q: str | None = None,
    state: str | None = None,
    books: bool = True,
    task_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    access(user, account_id)
    # Eltern-Werkzeuge nur in der eigenen Elternansicht, nicht beim Mitlesen
    # oder wenn das Kind das Gerät benutzt (D183).
    manage = acts_as_parent(user)
    # Eine Zeile mehr als verlangt sagt, ob es weitergeht.
    items = store.listing(account_id, subject=subject, kind=kind, start=start, end=end,
                          query=q, state=state, include_hidden=manage, include_books=books,
                          task_id=task_id, offset=offset, limit=min(limit, 300) + 1)
    has_more = len(items) > min(limit, 300)
    items = items[:min(limit, 300)]
    if manage:
        # Zettel zu Arbeiten und Handschrift gegen den Unterricht halten (D79):
        # eine 7 statt einer 1 fällt nur im Zusammenhang auf.
        run = notice_check.checker(account_id)
        for m in items:
            if m.get("origin") == "book_fetch" or m.get("verified"):
                continue
            if m["kind"] == "exam_notice" or m.get("handwritten") or m.get("pupil_entries"):
                m["plausibility"] = run(m)
                # Eine genannte Seite, die es im Fach nie gab, ist ein Zweifel,
                # auch wenn die Lesung sich sicher war — aber nur, wenn das Kind
                # sie geschrieben hat. Ein gedruckter Querverweis ist sicher
                # gelesen und steht selten in einem Stundentext (D118).
                unknown = (m["plausibility"] or {}).get("unknown") or []
                if unknown and (m["kind"] == "exam_notice" or
                                {u["page"] for u in unknown} & notice_check.handwritten_pages(m.get("content_text") or "")):
                    store.call_for_review(m)
    # Ein loses Blatt bekommt Vorschläge, zu welchem Eintrag es gehören könnte;
    # zugeordnet wird mit einem Tipp, von Kind oder Eltern (D85).
    for m in items:
        # Kennung für jedes Blatt, damit es in Listen und im Mentor unter
        # demselben Namen auftaucht: „AB GE 16.09. Lückentext“ (D85, Stufe 2).
        if m["kind"] in sources.SHEET_KINDS:
            bound = next((l for l in m.get("links", []) if l["kind"] in ("task", "homework", "lesson")), None)
            m["sheet_label"] = sources.sheet_label(m, (bound or {}).get("entry_date"))
        if m["kind"] in sources.SHEET_KINDS and not any(l["kind"] in ("task", "homework", "lesson") for l in m.get("links", [])):
            try:
                found = sources.sheet_candidates(account_id, m)
                # Die Auswertung hat das Blatt gesehen und vorsortiert; ihr
                # Vorschlag steht oben und trägt den Beleg vom Blatt (D85, Stufe 2).
                hint = json.loads(m.get("sheet_hint") or "null")
                if hint:
                    for c in found:
                        if c["kind"] == hint["kind"] and c["id"] == hint["id"]:
                            c["reason"] = hint.get("reason") or ""
                    found.sort(key=lambda c: (c.get("reason") is None, not c.get("reason")))
                m["sheet_candidates"] = found
            except Exception:
                _LOGGER.debug("Blatt-Vorschläge für Material %s nicht berechenbar", m["id"], exc_info=True)
    pending = sum(1 for m in items if m["analysis_state"] in ("pending", "failed"))
    return {
        "materials": items,
        "has_more": has_more,
        "offset": offset,
        "kinds": list(store.KINDS),
        "can_write": True,
        "can_manage": manage,
        # Nur, was wirklich einen Blick braucht; sauber Gelesenes zählt nicht
        # mit, auch wenn es niemand bestätigt hat (D118, D165).
        "needs_check": sum(1 for m in items if m.get("needs_review")),
        "retakes": [m["id"] for m in items if m.get("retake")],
        "pending_analysis": pending,
    }


@router.get("/for-task/{task_id}")
def for_task(account_id: int, task_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Bereits abgelegte Materialien, die zu dieser Hausaufgabe passen könnten,
    beste Treffer zuerst, dazu die schon verknüpften. Muss vor /{material_id}
    stehen, sonst liest FastAPI „for-task" als ID (D106)."""
    access(user, account_id)
    with closing(webapp_conn()) as conn:
        task = conn.execute("SELECT id,title,subject_name FROM tasks WHERE id=? AND account_id=?",
                            (task_id, account_id)).fetchone()
    if not task:
        raise HTTPException(404, "Aufgabe nicht gefunden.")
    task = sources.with_subject(account_id, dict(task))
    return {"task_id": task_id, "subject": task["subject_name"] or "",
            "linked": store.listing(account_id, task_id=task_id, limit=50),
            "candidates": sources.task_candidates(account_id, task_id)}


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
    """Den Sammellauf von Hand anstoßen. Er läuft sonst von selbst nach jedem
    Anstoß (neue Quellen) und als Netz um 14 Uhr und nachts; hier für die
    Kontrolle durch die Eltern."""
    access(user, account_id)
    if not acts_as_parent(user):
        raise HTTPException(403, "Nur in der Elternansicht verfügbar")
    from ..source_collector import start_collect
    return start_collect(account_id)


class CompareIn(InputModel):
    tier: str = Field(min_length=1, max_length=20)
    effort: str | None = Field(default=None, pattern=r"^(low|medium|high)$")


@router.post("/{material_id}/analysis/compare")
async def compare_models(account_id: int, material_id: int, body: CompareIn,
                         user: CurrentUser = Depends(get_current_user)) -> dict:
    """Eichung: dieselbe Seite mit einer anderen Modellstufe lesen und gegen den
    gespeicherten Stand halten. Speichert nichts, kostet einen Aufruf."""
    access(user, account_id, write=True, parent=True)
    from .. import ai_gateway as ai
    if body.tier not in ai.TIERS:
        raise HTTPException(422, "Unbekannte Stufe.")
    try:
        return await analysis.compare(account_id, material_id, body.tier, body.effort)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None


class ChapterPatch(InputModel):
    start_page: int | None = Field(default=None, ge=1, le=1999)
    end_page: int | None = Field(default=None, ge=0, le=1999)
    number: str | None = Field(default=None, max_length=20)
    title: str | None = Field(default=None, max_length=160)


@router.patch("/sources/chapters/{chapter_id}")
def correct_chapter(account_id: int, chapter_id: int, body: ChapterPatch,
                    user: CurrentUser = Depends(get_current_user)) -> dict:
    """Ein gelesenes Kapitel von Hand berichtigen; die Korrektur überlebt
    jedes neue Lesen. Danach werden die Stellen sofort neu gebunden."""
    access(user, account_id, write=True, parent=True)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if "end_page" in changes and changes["end_page"] == 0:
        changes["end_page"] = None
    if not changes:
        raise HTTPException(422, "Nichts zu ändern.")
    from ..book_structure import update_chapter
    fixed = update_chapter(account_id, chapter_id, changes)
    if not fixed:
        raise HTTPException(404, "Kapitel nicht gefunden.")
    try:
        sources.sync_links(account_id)
        sources.refresh_status(account_id)
    except Exception:
        _LOGGER.warning("Stellen nach Kapitelkorrektur nicht neu gebunden", exc_info=True)
    from .. import triggers
    triggers.request(account_id, "Kapitel berichtigt")
    return fixed


@router.get("/sources/collect")
def collect_sources_state(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    from ..source_collector import collect_state
    from .. import triggers
    return {**collect_state(account_id), "auto": triggers.state(account_id)}


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
def correct(account_id: int, material_id: int, body: MaterialPatch, background: BackgroundTasks,
            user: CurrentUser = Depends(get_current_user)) -> dict:
    """A parent correction wins and is protected against later analysis runs."""
    access(user, account_id, write=True, parent=True)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    # Ein leeres Textfeld ist keine Korrektur. Das Formular schickte bisher
    # alle Felder mit; ein noch ungelesenes Material bekam so einen leeren,
    # gesperrten Text, den keine Lesung mehr füllen durfte (Textband S. 10/11).
    for field in ("title", "summary", "content_text", "document_date", "period_start", "period_end"):
        if field in changes and not str(changes[field]).strip():
            changes.pop(field)
    if "kind" in changes and changes["kind"] not in store.KINDS:
        raise HTTPException(422, "Unbekannte Materialart.")
    if "source_label" in changes:
        changes["source_label"] = changes["source_label"].strip()
        if changes["source_label"] and changes["source_label"] not in store.BOOK_PARTS:
            raise HTTPException(422, "Unbekannter Buchteil.")
    if "source_page" in changes and not changes["source_page"]:
        changes["source_page"] = None
    if "printed_pages" in changes:
        pages = sorted({int(p) for p in changes["printed_pages"] if 0 < int(p) < 2000})
        changes["printed_pages"] = json.dumps(pages)
        # Die erste gedruckte Seite ist die Seite des Materials, wenn keine gesetzt ist.
        if pages and not changes.get("source_page"):
            changes["source_page"] = pages[0]
    if "subject_name" in changes:
        changes["subject_name"] = store.canonical_subject(account_id, changes["subject_name"])
    if "contains_solutions" in changes:
        changes["contains_solutions"] = int(changes["contains_solutions"])
    found = store.update(account_id, material_id, changes, by_parent=True)
    if not found:
        raise HTTPException(404, "Material nicht gefunden.")
    if changes.keys() & {"kind", "subject_name", "source_label", "source_page", "printed_pages"}:
        # Ein umgewidmetes Foto (Inhaltsverzeichnis, Klausurzettel, andere
        # Seite) wirkt sofort auf Verzeichnis und Einkaufsliste.
        background.add_task(analysis.after_analysis, account_id, material_id)
    return found


@router.post("/{material_id}/plausibility/apply")
def apply_suggestion(account_id: int, material_id: int, body: SuggestionsIn, background: BackgroundTasks,
                     user: CurrentUser = Depends(get_current_user)) -> dict:
    """Die Vorschläge der Gegenlese-Karte mit einem Tipp übernehmen (D79): die
    Seiten einer Angabe werden im gelesenen Text ersetzt und gelten als
    Korrektur der Eltern, die keine Lesung mehr überschreibt. Danach binden
    sich die Stellen neu."""
    access(user, account_id, write=True, parent=True)
    found = store.detail(account_id, material_id)
    if not found:
        raise HTTPException(404, "Material nicht gefunden.")
    text = notice_check.replace_pages(found.get("content_text") or "", [f.model_dump() for f in body.fixes],
                                      found.get("subject_name") or "")
    if text is None:
        raise HTTPException(409, "Diese Stelle steht so nicht mehr im Text. Bitte neu laden.")
    fixed = store.update(account_id, material_id, {"content_text": text}, by_parent=True)
    if not fixed:
        raise HTTPException(404, "Material nicht gefunden.")
    background.add_task(analysis.after_analysis, account_id, material_id)
    return fixed


@router.post("/{material_id}/doubts/resolve")
def resolve_doubt(account_id: int, material_id: int, body: DoubtIn, background: BackgroundTasks,
                  user: CurrentUser = Depends(get_current_user)) -> dict:
    """Eine einzelne Zweifelsstelle erledigen (D118). Mit `replace` wird der
    Text berichtigt und gilt als Korrektur der Eltern, die keine Lesung mehr
    überschreibt; ohne bleibt er, wie er ist. In beiden Fällen ist die Stelle
    danach geklärt. Bleibt keine übrig, verschwindet die Karte von selbst."""
    access(user, account_id, write=True, parent=True)
    found = store.detail(account_id, material_id)
    if not found:
        raise HTTPException(404, "Material nicht gefunden.")
    text = found.get("content_text") or ""
    changes: dict = {}
    if body.replace is not None and body.replace != body.text:
        fixed = proofread.resolve(text, body.text, body.replace)
        if fixed is None:
            raise HTTPException(409, "Diese Stelle steht so nicht mehr im Text. Bitte neu laden.")
        changes["content_text"] = fixed
    elif proofread.resolve(text, body.text, None) is None:
        raise HTTPException(409, "Diese Stelle steht so nicht mehr im Text. Bitte neu laden.")
    rest = [d for d in (found.get("doubts") or []) if (d.get("text") or "").strip() != body.text.strip()]
    with closing(webapp_conn()) as conn, conn:
        conn.execute("UPDATE materials SET doubts=?,updated_at=? WHERE id=? AND account_id=?",
                     (json.dumps(rest, ensure_ascii=False) if rest else "", store.now_iso(),
                      material_id, account_id))
    if changes:
        store.update(account_id, material_id, changes, by_parent=True)
        background.add_task(analysis.after_analysis, account_id, material_id)
    return store.detail(account_id, material_id) or {}


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
        ok = store.link(account_id, material_id, body.kind, body.target_id, relation=body.relation)
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
