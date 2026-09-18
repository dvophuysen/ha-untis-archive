"""Vokabeltrainer: Einheiten, Karten, Antworten, Spracheingabe."""
from __future__ import annotations
from contextlib import closing
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import Field
from ..auth import CurrentUser, get_current_user
from ..db import webapp_conn
from ..learning import InputModel
from .. import ai_gateway as ai, vocab
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
    """Die Einheiten des Fachs. Ungelesene Wortseiten werden dabei im Hintergrund
    zerlegt; die Antwort sagt, wie viele noch laufen, damit die Ansicht nachlädt."""
    access(user, account_id)
    lang = vocab.language_of(subject)
    found = vocab.units(account_id, subject)
    reading = sum(u['unread'] for u in found)
    if reading and lang:
        background.add_task(vocab.read_unread, account_id, subject)
    return {'subject': subject, 'language': lang, 'units': found, 'reading': reading,
            'speech': bool(ai.transcribe_url()), 'hesitation_seconds': vocab.HESITATION_SECONDS}


@router.post('/{subject}/extract')
async def extract(account_id: int, subject: str, body: ExtractIn, user: CurrentUser = Depends(get_current_user)):
    """Die Lernwörter der genannten Seiten lesen (einmal je Seite und Textstand)."""
    access(user, account_id, write=True)
    with closing(webapp_conn()) as c:
        allowed = {r[0] for r in c.execute(
            'SELECT id FROM materials WHERE account_id=? AND lower(subject_name)=lower(?) AND hidden=0', (account_id, subject))}
    counts = {}
    for mid in body.material_ids:
        if mid not in allowed:
            raise HTTPException(404, 'Seite nicht gefunden.')
        counts[mid] = await vocab.extract(account_id, mid)
    return {'words': counts, 'units': vocab.units(account_id, subject)}


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
def attempts(account_id: int, body: vocab.AttemptIn, user: CurrentUser = Depends(get_current_user)):
    access(user, account_id, write=True)
    return vocab.attempt(account_id, body)


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
