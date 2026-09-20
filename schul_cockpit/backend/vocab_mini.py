"""Mini-only source transcription. Output stays in quarantine until reviewed.

No tier fallback, no legacy word writes and no activation. Image bytes, crop,
prompt and model configuration all participate in cache identity.
"""
from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageOps
from pydantic import Field

from . import ai_gateway as ai
from .db import webapp_conn
from .learning import InputModel, ai_tiers
from .vocab_catalog import CatalogError, _now

PROMPT = (Path(__file__).parent / 'vocab_mini_prompt.txt').read_text()
PROTOCOL = 'physical-page-ordered-elements-v2'


class PageSpec(InputModel):
    material_id: int = Field(ge=1)
    number: int = Field(ge=1, le=2000)
    side: str = Field(pattern='^(full|left|right)$')


def mini_tier() -> str:
    candidates = [tier for tier, config in ai_tiers().items()
                  if config.get('foundry') == '2' and config.get('model') == 'gpt-5-mini']
    if not candidates:
        raise CatalogError('Für den Vokabelimport muss gpt-5-mini in Foundry 2 eingerichtet sein. Kein Rückfall auf ein anderes Modell.')
    return 'klein' if 'klein' in candidates else sorted(candidates)[0]


def images_for(blob: bytes, side: str) -> list[dict]:
    image = Image.open(io.BytesIO(blob))
    if image.width * image.height > 25_000_000:
        raise CatalogError('Originalbild ist zu groß.')
    image = ImageOps.exif_transpose(image).convert('RGB')
    if side == 'left':
        image = image.crop((0, 0, image.width // 2, image.height))
    elif side == 'right':
        image = image.crop((image.width // 2, 0, image.width, image.height))
    elif side != 'full':
        raise CatalogError('Ungültiger Seitenausschnitt.')
    images = []
    for top, bottom in ((0, int(image.height * .56)), (int(image.height * .50), image.height)):
        part = image.crop((0, top, image.width, bottom))
        part.thumbnail((1600, 1600))
        out = io.BytesIO(); part.save(out, 'PNG')
        images.append({'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode(), 'detail': 'high'}})
    return images


def ordered_transcript(result: dict) -> dict:
    """Derive offsets from source-order elements; never trust model arithmetic.

    This is a draft adapter, not a source reviewer. Box ownership and inherited
    hierarchy are resolved across pages only after the original-source review.
    Raw elements remain in the result for comparing the adapter with the model.
    """
    if not isinstance(result, dict) or not isinstance(result.get('elements'), list):
        raise CatalogError('Modellantwort enthält keine geordnete Quellenlesung.')
    rows, events, references = [], [], []
    boxes = []
    begins = 'continuation'
    for element in result['elements']:
        if not isinstance(element, dict):
            raise CatalogError('Ungültiges Element in der Quellenlesung.')
        kind = element.get('type')
        if kind == 'word':
            word, meanings = element.get('foreign_word'), element.get('meanings')
            if (not isinstance(word, str) or not word.strip() or not isinstance(meanings, list)
                    or not meanings or any(not isinstance(m, str) or not m.strip() for m in meanings)):
                raise CatalogError('Lernwort ohne lesbare Quellübersetzung; keine automatische Ergänzung.')
            if not isinstance(element.get('uncertain'), bool):
                raise CatalogError('Unsicherheit des gelesenen Wortes fehlt.')
            for field in ('grammar', 'parent_word'):
                if not isinstance(element.get(field, ''), str):
                    raise CatalogError('Ungültige grammatische Quellenangabe.')
            rows.append({k: v for k, v in element.items() if k != 'type'})
            rows[-1]['example'] = ''
        elif kind in ('heading', 'subheading', 'box_start'):
            title = element.get('title')
            if kind == 'box_start' and isinstance(title, str) and not title.strip():
                title = 'Vokabelkasten ohne Überschrift'
            if not isinstance(title, str) or not title.strip():
                raise CatalogError('Überschrift ohne prüfbaren Titel.')
            event_kind = 'box' if kind == 'box_start' else 'section' if kind == 'subheading' else element.get('kind')
            if event_kind not in ('unit', 'section', 'box'):
                raise CatalogError('Unbekannte Überschriftenart.')
            events.append({'at': len(rows), 'action': 'open', 'title': title, 'kind': event_kind,
                           'evidence': 'Ungeprüfte Modelllesung: Element in der Quellenreihenfolge.'})
            if kind == 'box_start':
                boxes.append(title)
            if not rows:
                begins = 'new'
        elif kind == 'box_end':
            # Empty local stack may be a box continued from the preceding page.
            events.append({'at': len(rows), 'action': 'close', 'title': boxes.pop() if boxes else '',
                           'kind': 'box', 'evidence': 'Ungeprüfte Modelllesung: Kastenende nach dem vorigen Wort.'})
        elif kind == 'reference_box':
            title, items = element.get('title'), element.get('items')
            if (not isinstance(title, str) or not title.strip() or not isinstance(items, list)
                    or any(not isinstance(x, str) or not x.strip() for x in items)):
                raise CatalogError('Unvollständiger einsprachiger Quellenkasten.')
            references.append({'at': len(rows), 'title': title, 'items': items})
        else:
            raise CatalogError('Unbekanntes Element in der Quellenlesung.')
    return {**result, 'rows': rows, 'events': events, 'reference_boxes': references, 'begins': begins}


async def read_page(account_id: int, subject: str, spec: PageSpec) -> dict:
    tier = mini_tier()
    with closing(webapp_conn()) as c:
        row = c.execute('SELECT account_id,subject_name,file_bytes FROM materials WHERE id=?', (spec.material_id,)).fetchone()
    if not row or row['account_id'] != account_id or row['subject_name'].casefold() != subject.casefold():
        raise CatalogError('Original nicht für dieses Kind und Fach gefunden.')
    blob = row['file_bytes']
    if not blob:
        raise CatalogError('Originalbild fehlt; kein stiller Rückfall auf alten OCR-Text.')
    source_hash = hashlib.sha256(blob).hexdigest()
    fingerprint = hashlib.sha256(json.dumps([source_hash, spec.model_dump(), PROTOCOL, PROMPT, ai_tiers()[tier]], sort_keys=True).encode()).hexdigest()
    with closing(webapp_conn()) as c:
        saved = c.execute('SELECT response FROM vocab_page_reads WHERE account_id=? AND material_id=? AND physical_page=? AND side=? AND fingerprint=?',
                          (account_id, spec.material_id, spec.number, spec.side, fingerprint)).fetchone()
    if saved:
        return json.loads(saved['response'])
    text, usage, _ = await ai.complete(account_id, ai.VOCAB, PROMPT,
                                      {'views': 'Two overlapping crops of ONE physical page, upper then lower. Transcribe overlap exactly once.'},
                                      images=images_for(blob, spec.side), max_output=16000, tier=tier, effort='medium')
    result = ordered_transcript(json.loads(text))
    issues = list(result.get('issues') or [])
    if result.get('printed_page') != spec.number:
        issues.append('Gedruckte Seitenzahl stimmt nicht mit dem Prüfauftrag überein.')
    output = {'material_id': spec.material_id, 'number': spec.number, 'side': spec.side,
              'source_sha256': source_hash, 'fingerprint': fingerprint,
              'model': 'gpt-5-mini', 'foundry': '2', 'usage': usage,
              'result': result, 'issues': issues, 'review_required': True}
    with closing(webapp_conn()) as c, c:
        c.execute('INSERT OR IGNORE INTO vocab_page_reads VALUES(?,?,?,?,?,?,?,?,?)',
                  (account_id, spec.material_id, spec.number, spec.side, fingerprint,
                   json.dumps(output, ensure_ascii=False), 'gpt-5-mini', '2', _now()))
    return output


async def read_sequence(account_id: int, subject: str, specs: list[PageSpec], start_page: int) -> dict:
    numbers = sorted(p.number for p in specs)
    if numbers != list(range(start_page, start_page + len(numbers))):
        raise CatalogError('Der Leseauftrag muss am bestätigten Anfang beginnen und lückenlos in Buchreihenfolge verlaufen.')
    pages = []
    for spec in sorted(specs, key=lambda p: p.number):
        pages.append(await read_page(account_id, subject, spec))
    return {'pages': pages, 'review_required': True, 'activated': False}
