"""Vokabeltrainer: Einheiten, Karten, Antworten, Spracheingabe."""
from __future__ import annotations
from contextlib import closing
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import Field
from ..auth import CurrentUser, get_current_user
from ..db import webapp_conn
from ..learning import InputModel
from .. import ai_gateway as ai, vocab, vocab_catalog
from .learning import access

router = APIRouter(prefix='/accounts/{account_id}/learning/vocab', tags=['vocab'])


class ExtractIn(InputModel):
    material_ids: list[int] = Field(min_length=1, max_length=12)


@router.get('/languages')
def languages(account_id: int, user: CurrentUser = Depends(get_current_user)):
    """Einstieg ohne Fach: alle Fremdsprachen des Kindes mit Trainerstand."""
    access(user, account_id)
    return {'languages': vocab.languages(account_id), 'speech': bool(ai.transcribe_url())}


@router.get('/{subject}/units')
def units(account_id: int, subject: str, background: BackgroundTasks, user: CurrentUser = Depends(get_current_user)):
    """Read the active corpus. Opening the trainer never starts an import."""
    access(user, account_id)
    lang = vocab.language_of(subject)
    found = vocab.units(account_id, subject)
    from ..vocab_progress import annotate
    overview = annotate(account_id, subject, found)
    # Imports are explicit parent actions and stay separate from this GET.
    reading = 0
    return {'subject': subject, 'language': lang, 'units': found, 'reading': reading, 'overview': overview,
            'speech': bool(ai.transcribe_url()), 'hesitation_seconds': vocab.HESITATION_SECONDS}


@router.post('/{subject}/extract')
async def extract(account_id: int, subject: str, body: ExtractIn, user: CurrentUser = Depends(get_current_user)):
    """Die genannten Seiten lesen: Wörter und Überschriften, je Seite und
    Textstand einmal. Die Gliederung setzt danach `regroup()` über alle Seiten."""
    access(user, account_id, write=True)
    if vocab_catalog.active(account_id, subject):
        raise HTTPException(409, 'Für dieses Fach ist ein geprüfter Buchbestand aktiv. Neue Seiten zuerst in einem Prüfbestand einlesen.')
    with closing(webapp_conn()) as c:
        allowed = {r[0] for r in c.execute(
            'SELECT id FROM materials WHERE account_id=? AND lower(subject_name)=lower(?) AND hidden=0', (account_id, subject))}
    counts = {}
    for mid in body.material_ids:
        if mid not in allowed:
            raise HTTPException(404, 'Seite nicht gefunden.')
        counts[mid] = await vocab.extract(account_id, mid)
        try:
            await vocab.read_heads(account_id, mid)
        except Exception as exc:
            # Die Überschriften sind ein Zugewinn, keine Bedingung: Ohne sie
            # behält die Seite die Gliederung, die sie hat.
            vocab.note_error('vocab_headings', mid, account_id, exc)
    vocab.regroup(account_id, subject)
    return {'words': counts, 'units': vocab.units(account_id, subject)}


@router.get('/{subject}/outline')
def outline(account_id: int, subject: str, user: CurrentUser = Depends(get_current_user)):
    """Eltern: was die Gliederung zu sehen bekommt — die gelesenen Überschriften
    je Seite mit ihrem errechneten Rang. Kostet keinen Aufruf."""
    access(user, account_id, parent=True)
    return {'subject': subject, 'pages': vocab.outline(account_id, subject)}


class CompareIn(InputModel):
    material_id: int = Field(ge=1)
    tiers: list[str] = Field(min_length=1, max_length=4)


@router.post('/{subject}/compare')
async def compare(account_id: int, subject: str, body: CompareIn, user: CurrentUser = Depends(get_current_user)):
    """Eichung für die Eltern: dieselbe Vokabelseite mit mehreren Stufen lesen,
    ohne etwas abzulegen. Zeigt je Stufe, was die Seitenprüfung übersteht und
    was gegenüber der ersten Stufe fehlt oder hinzukommt (D103)."""
    access(user, account_id, write=True, parent=True)
    with closing(webapp_conn()) as c:
        allowed = c.execute('SELECT 1 FROM materials WHERE id=? AND account_id=? AND hidden=0 '
                            'AND lower(subject_name)=lower(?)', (body.material_id, account_id, subject)).fetchone()
    if not allowed:
        raise HTTPException(404, 'Seite nicht gefunden.')
    return await vocab.compare(account_id, body.material_id, body.tiers)


class CatalogIn(InputModel):
    payload: dict


class ActivateCatalogIn(InputModel):
    digest: str = Field(min_length=64, max_length=64)


class CaptureCatalogIn(InputModel):
    pages: list[int] = Field(min_length=1, max_length=4)


class ReadCatalogIn(InputModel):
    start_page: int = Field(ge=1, le=2000)
    pages: list[dict] = Field(min_length=1, max_length=100)


@router.post('/{subject}/catalog-read')
def read_catalog(account_id: int, subject: str, body: ReadCatalogIn, user: CurrentUser = Depends(get_current_user)):
    access(user, account_id, write=True, parent=True)
    from ..vocab_mini import PageSpec, mini_tier, read_sequence
    from ..textbook_context import start_job
    try:
        mini_tier()
        specs = [PageSpec.model_validate(p) for p in body.pages]
        if sorted(p.number for p in specs) != list(range(body.start_page, body.start_page + len(specs))):
            raise ValueError('Seitenfolge ist nicht lückenlos.')
    except (ValueError, vocab_catalog.CatalogError) as exc:
        raise HTTPException(422, str(exc)) from None
    return start_job((account_id, 'vocab-read', subject.casefold()),
                     lambda: read_sequence(account_id, subject, specs, body.start_page))


@router.get('/{subject}/catalog-read')
def catalog_read_status(account_id: int, subject: str, user: CurrentUser = Depends(get_current_user)):
    access(user, account_id, parent=True)
    from ..textbook_context import job_state
    return job_state((account_id, 'vocab-read', subject.casefold()))


@router.post('/{subject}/catalog-capture')
def capture_catalog(account_id: int, subject: str, body: CaptureCatalogIn, user: CurrentUser = Depends(get_current_user)):
    access(user, account_id, write=True, parent=True)
    if any(p < 1 or p > 2000 for p in body.pages):
        raise HTTPException(422, 'Ungültige Seitenzahl.')
    from ..textbook_context import start_job
    return start_job((account_id, 'vocab-capture', subject.casefold()),
                     lambda: vocab_catalog.capture_sources(account_id, subject, body.pages))


@router.get('/{subject}/catalog-capture')
def catalog_capture_status(account_id: int, subject: str, user: CurrentUser = Depends(get_current_user)):
    access(user, account_id, parent=True)
    from ..textbook_context import job_state
    return job_state((account_id, 'vocab-capture', subject.casefold()))


@router.post('/{subject}/catalogs')
def stage_catalog(account_id: int, subject: str, body: CatalogIn, user: CurrentUser = Depends(get_current_user)):
    access(user, account_id, write=True, parent=True)
    try:
        return vocab_catalog.stage(account_id, subject, body.payload)
    except (vocab_catalog.CatalogError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f'Prüfbestand ungültig: {exc}') from None


@router.post('/{subject}/catalogs/{run_id}/activate')
def activate_catalog(account_id: int, subject: str, run_id: str, body: ActivateCatalogIn,
                     user: CurrentUser = Depends(get_current_user)):
    access(user, account_id, write=True, parent=True)
    with closing(webapp_conn()) as c:
        if not c.execute('SELECT 1 FROM vocab_catalog_runs WHERE id=? AND account_id=? AND subject=?',
                         (run_id, account_id, subject.casefold())).fetchone():
            raise HTTPException(404, 'Prüfbestand nicht gefunden.')
    try:
        return vocab_catalog.activate(account_id, run_id, body.digest)
    except vocab_catalog.CatalogError as exc:
        raise HTTPException(409, str(exc)) from None


@router.get('/{subject}/word-list')
def word_list(account_id: int, subject: str, unit: str, section: str = '', user: CurrentUser = Depends(get_current_user)):
    access(user, account_id)
    return {'words': vocab_catalog.cards(account_id, subject, unit, 1, 10000, section, book_order=True)}


@router.get('/{subject}/cards')
def cards(account_id: int, subject: str, unit: str, stage: int = 1, direction: str = 'from', limit: int = 40,
          section: str = '', box: str = '', user: CurrentUser = Depends(get_current_user)):
    """Die Karten eines Bündels. Standard ist die ganze Einheit; `section`
    schränkt auf einen Abschnitt ein, den die Vokabelliste selbst nennt (D100)."""
    access(user, account_id)
    if stage not in (1, 2) or direction not in ('from', 'into'):
        raise HTTPException(422, 'Unbekannte Stufe oder Richtung.')
    lang = vocab.language_of(subject)
    if direction == 'into' and lang and not lang['into']:
        raise HTTPException(422, 'In diesem Fach wird nur in die Muttersprache übersetzt.')
    if stage == 2 and direction != 'into':
        raise HTTPException(422, 'Die Schreibweise wird nur in die Fremdsprache geprüft.')
    return {'unit': unit, 'section': section, 'box': box, 'stage': stage, 'direction': direction,
            'cards': vocab.cards(account_id, subject, unit, stage, direction, max(1, min(limit, 80)), section=section, box=box),
            'language': lang, 'speech': bool(ai.transcribe_url())}


@router.post('/attempts')
async def attempts(account_id: int, body: vocab.AttemptIn, user: CurrentUser = Depends(get_current_user)):
    access(user, account_id, write=True)
    from ..vocab_semantic import submit
    return await submit(account_id, body, user_id=user.id)


@router.delete('/{subject}/attempts')
def reset(account_id: int, subject: str, user: CurrentUser = Depends(get_current_user)):
    """Eltern: den Stand des Trainers für eine Sprache auf Null setzen (Versuche
    löschen, Wörter bleiben). Für Probeläufe der Eltern."""
    access(user, account_id, write=True, parent=True)
    with closing(webapp_conn()) as c, c:
        gone = c.execute("DELETE FROM vocab_attempts WHERE account_id=? AND word_id IN "
                         "(SELECT id FROM vocab_words WHERE account_id=? AND lower(subject)=lower(?))",
                         (account_id, account_id, subject)).rowcount
    return {'removed': gone, 'units': vocab.units(account_id, subject)}


class ReviewIn(InputModel):
    attempt_ids: list[int] = Field(min_length=1, max_length=250)
    reason: str = Field(min_length=5, max_length=500)
    excluded: bool = True
    digest: str | None = None


@router.post('/{subject}/attempt-review')
def review_attempts(account_id: int, subject: str, body: ReviewIn, user: CurrentUser = Depends(get_current_user)):
    access(user, account_id, write=True, parent=True)
    from ..vocab_review import review
    return review(account_id, subject, body.attempt_ids, body.reason, body.excluded, user.id, body.digest)


@router.post('/{subject}/transcribe')
async def transcribe(account_id: int, subject: str, file: UploadFile = File(...), unit: str = Form(''), direction: str = Form('from'),
                     seconds: int = Form(0), user: CurrentUser = Depends(get_current_user)):
    """Gesprochene Antwort in Text: Sprache nach Richtung, Hinweis mit allen Wörtern
    der Einheit, nie nur dem gefragten."""
    access(user, account_id, write=True)
    lang = vocab.language_of(subject)
    if direction == 'into' and (not lang or not lang['into'] or not lang['code']):
        raise HTTPException(422, 'Gesprochene Antworten in dieser Sprache werden nicht erkannt.')
    language = lang['code'] if (direction == 'into' and lang) else 'de'
    blob = await file.read(ai.TRANSCRIBE_MAX_BYTES + 1)
    text = await ai.transcribe(account_id, blob, file.content_type or '', language=language,
                               prompt=vocab.prompt_for(account_id, subject, unit, direction), seconds=seconds)
    return {'text': text, 'language': language}
