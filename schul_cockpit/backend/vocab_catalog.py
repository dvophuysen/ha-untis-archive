"""Versioned vocabulary catalogs, isolated from the children's learning log.

Drafts contain source-backed occurrences and arbitrary-depth chapter trees.
Activation changes only a catalog pointer and additive word/alias records.
Original attempts, word IDs and previous catalogs remain intact.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import uuid

from .db import webapp_conn
from .vocab_sequence import Boundary, Page, compile_book, exact_text


class CatalogError(ValueError):
    pass


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat()


def validate(c, account_id: int, subject: str, payload: dict) -> dict:
    """Validate originals and explicit review evidence, not AI self-confidence."""
    issues = []
    pages = []
    if not payload.get('book_key') or not payload.get('title'):
        raise CatalogError('Buchkennung und Titel fehlen.')
    if not isinstance(payload.get('start_page'), int) or not isinstance(payload.get('end_page'), int):
        raise CatalogError('Der geprüfte Seitenbereich fehlt.')
    if payload['end_page'] < payload['start_page']:
        raise CatalogError('Ungültiger Seitenbereich.')
    for p in payload.get('pages', []):
        material = c.execute('SELECT account_id,subject_name,file_bytes FROM materials WHERE id=?',
                             (p['material_id'],)).fetchone()
        if not material or material['account_id'] != account_id or exact_text(material['subject_name']) != exact_text(subject):
            raise CatalogError('Originalseite gehört nicht zu Kind und Fach.')
        source_hash = hashlib.sha256(material['file_bytes'] or b'').hexdigest()
        if not material['file_bytes'] or source_hash != p.get('source_sha256'):
            issues.append({'page': p['number'], 'code': 'source_changed_or_missing'})
        # Explicit external review, including the complete ordered row content.
        # A model-produced confidence score is never accepted as this evidence.
        review = p.get('review', {})
        reviewed_content = {'rows': p['rows'], 'boundaries': p['boundaries'], 'begins': p['begins']}
        if review.get('method') != 'source_visual_review' or not review.get('reviewer') or review.get('content_sha256') != _digest(reviewed_content):
            issues.append({'page': p['number'], 'code': 'content_review_missing_or_stale'})
        if review.get('row_count') != len(p['rows']):
            issues.append({'page': p['number'], 'code': 'row_count_mismatch'})
        for i, row in enumerate(p['rows']):
            if row.get('uncertain') or '[?]' in _json(row):
                issues.append({'page': p['number'], 'position': i, 'code': 'uncertain_transcription'})
            if not isinstance(row.get('meanings'), list) or not all(isinstance(m, str) and m.strip() for m in row.get('meanings', [])):
                raise CatalogError('Ungültige Bedeutungen.')
        pages.append(Page(p['number'], source_hash, tuple(p['rows']),
                          tuple(Boundary(**b) for b in p['boundaries']), p['begins']))
    result = compile_book(pages, start_page=payload['start_page'])
    if sorted(p.number for p in pages) != list(range(payload['start_page'], payload['end_page'] + 1)):
        issues.append({'code': 'incomplete_page_range'})
    issues.extend(result.issues)
    return {'valid': result.structurally_valid and not issues, 'issues': issues,
            'compiled': asdict(result), 'occurrences': len(result.occurrences),
            'pages': len(pages), 'content_digest': _digest(payload)}


def stage(account_id: int, subject: str, payload: dict) -> dict:
    """Store a draft. No vocab_words, attempts or active catalog are modified."""
    subject = subject.casefold()
    with closing(webapp_conn()) as c, c:
        report = validate(c, account_id, subject, payload)
        run_id = str(uuid.uuid4())
        c.execute('INSERT INTO vocab_catalog_runs(id,account_id,subject,book_key,title,payload,digest,status,report,created_at) '
                  'VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (run_id, account_id, subject, payload['book_key'], payload['title'], _json(payload),
                   _digest(payload), 'verified' if report['valid'] else 'draft', _json(report), _now()))
    return {'id': run_id, **report}


def _attempt_fingerprint(c, account_id):
    return _digest([dict(r) for r in c.execute('SELECT * FROM vocab_attempts WHERE account_id=? ORDER BY id', (account_id,))])


def activate(account_id: int, run_id: str, expected_digest: str) -> dict:
    """Atomically publish a verified snapshot; preserve every attempt byte-for-byte.

    Recheck originals inside the write transaction. A practised legacy word
    missing from the same subject's replacement stops activation. No fuzzy
    matching, history deletion, replacing material rows or automatic regrading.
    """
    from .vocab import plain
    with closing(webapp_conn()) as c:
        try:
            c.execute('BEGIN IMMEDIATE')
            run = c.execute('SELECT * FROM vocab_catalog_runs WHERE id=? AND account_id=?', (run_id, account_id)).fetchone()
            if not run or run['digest'] != expected_digest:
                raise CatalogError('Prüfbestand nicht gefunden oder inzwischen verändert.')
            if run['status'] == 'active':
                return {'id': run_id, 'already_active': True}
            payload = json.loads(run['payload'])
            report = validate(c, account_id, run['subject'], payload)
            if not report['valid']:
                raise CatalogError('Freigabe gesperrt: Quellen- oder Gliederungsprüfung nicht bestanden.')
            before = _attempt_fingerprint(c, account_id)
            legacy = [dict(r) for r in c.execute('SELECT * FROM vocab_words WHERE account_id=? AND lower(subject)=?',
                                                (account_id, run['subject']))]
            practiced = {r[0] for r in c.execute('SELECT DISTINCT a.word_id FROM vocab_attempts a JOIN vocab_words w ON w.id=a.word_id '
                                                 'WHERE a.account_id=? AND lower(w.subject)=?', (account_id, run['subject']))}
            by_word = {}
            for w in legacy:
                by_word.setdefault(exact_text(w['foreign_word']), []).append(w)
            occurrences = report['compiled']['occurrences']
            new_keys = {exact_text(o['row']['foreign_word']) for o in occurrences}
            # Other active books in this subject continue to preserve their words.
            covered = {r[0] for r in c.execute('SELECT e.word_id FROM vocab_catalog_entries e JOIN vocab_catalog_runs r ON r.id=e.run_id '
                                               "WHERE r.account_id=? AND r.subject=? AND r.status='active' AND r.book_key!=?",
                                               (account_id, run['subject'], run['book_key']))}
            missing = [w['id'] for w in legacy if w['id'] in practiced and w['id'] not in covered
                       and exact_text(w['foreign_word']) not in new_keys]
            if missing:
                raise CatalogError(f'{len(missing)} bereits geübte Wörter sind noch nicht sicher zugeordnet.')
            page_sources = {p['number']: p['material_id'] for p in payload['pages']}
            canonicals = {}
            for i, occurrence in enumerate(occurrences):
                row = occurrence['row']; key = exact_text(row['foreign_word'])
                if key not in canonicals:
                    matches = by_word.get(key, [])
                    existing_aliases = {r[0] for w in matches for r in c.execute(
                        'SELECT canonical_id FROM vocab_learning_aliases WHERE account_id=? AND word_id=?', (account_id, w['id']))}
                    if len(existing_aliases) > 1:
                        raise CatalogError('Widersprüchliche Lernwort-Verknüpfung; manuelle Prüfung erforderlich.')
                    canonical = next(iter(existing_aliases), None)
                    if canonical is None and matches:
                        canonical = min(matches, key=lambda w: (w['id'] not in practiced, w['id']))['id']
                    if canonical is None:
                        cursor = c.execute('INSERT INTO vocab_words(account_id,subject,material_id,source_label,page,position,foreign_word,plain,meanings_json,grammar,forms_json,example,created_at) '
                                           'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                           (account_id, run['subject'], page_sources[occurrence['page']], payload['title'], occurrence['page'],
                                            occurrence['position'], row['foreign_word'], plain(row['foreign_word']), _json(row['meanings']),
                                            row.get('grammar', ''), _json(row.get('forms', {})), row.get('example', ''), _now()))
                        canonical = cursor.lastrowid
                    canonicals[key] = canonical
                    for wid in {canonical, *(w['id'] for w in matches)}:
                        c.execute('INSERT OR IGNORE INTO vocab_learning_aliases(account_id,word_id,canonical_id) VALUES(?,?,?)',
                                  (account_id, wid, canonical))
                c.execute('INSERT OR IGNORE INTO vocab_catalog_entries(run_id,occurrence,word_id) VALUES(?,?,?)', (run_id, i, canonicals[key]))
            c.execute("UPDATE vocab_catalog_runs SET status='archived' WHERE account_id=? AND subject=? AND book_key=? AND status='active'",
                      (account_id, run['subject'], run['book_key']))
            if before != _attempt_fingerprint(c, account_id):
                raise CatalogError('Lernverlauf-Prüfsumme hat sich verändert; Aktivierung zurückgerollt.')
            report['preservation'] = {'attempt_digest_before': before, 'attempt_digest_after': before,
                                      'practiced_words': len(practiced), 'canonical_words': len(canonicals)}
            c.execute("UPDATE vocab_catalog_runs SET status='active',activated_at=?,report=? WHERE id=?", (_now(), _json(report), run_id))
            c.commit()
            return {'id': run_id, 'preservation': report['preservation'], 'words': len(canonicals), 'occurrences': len(occurrences)}
        except BaseException:
            c.rollback()
            raise


def active(account_id: int, subject: str) -> list[dict]:
    with closing(webapp_conn()) as c:
        return [dict(r) for r in c.execute("SELECT * FROM vocab_catalog_runs WHERE account_id=? AND subject=? AND status='active' ORDER BY created_at,id",
                                           (account_id, subject.casefold()))]


def catalog_words(account_id: int, subject: str) -> list[dict]:
    """One card per exact printed word, all memberships and meanings retained."""
    words = {}
    with closing(webapp_conn()) as c:
        for run in active(account_id, subject):
            report = json.loads(run['report'])
            nodes = {n['id']: n for n in report['compiled']['nodes']}
            mapping = dict(c.execute('SELECT occurrence,word_id FROM vocab_catalog_entries WHERE run_id=?', (run['id'],)))
            for i, occurrence in enumerate(report['compiled']['occurrences']):
                wid = mapping[i]; row = occurrence['row']
                membership = {'run_id': run['id'], 'book': run['title'], 'page': occurrence['page'],
                              'position': occurrence['position'],
                              'nodes': [run['id'] + '/' + n for n in occurrence['node_ids']],
                              'path': [nodes[n]['title'] for n in occurrence['node_ids']]}
                if wid not in words:
                    words[wid] = {'id': wid, 'foreign_word': row['foreign_word'], 'meanings': [],
                                  'grammar': row.get('grammar', ''), 'forms': row.get('forms', {}),
                                  'example': row.get('example', ''), 'unit': membership['path'][0],
                                  'source_label': run['title'], 'page': occurrence['page'], 'memberships': []}
                w = words[wid]
                for meaning in row['meanings']:
                    if exact_text(meaning) not in {exact_text(m) for m in w['meanings']}:
                        w['meanings'].append(meaning)
                w['memberships'].append(membership)
    return list(words.values())


def units(account_id: int, subject: str) -> list[dict]:
    from .vocab import word_states, STAGES
    words = catalog_words(account_id, subject)
    with closing(webapp_conn()) as c:
        states = word_states(c, account_id, [w['id'] for w in words])
    result = []
    for run in active(account_id, subject):
        nodes = json.loads(run['report'])['compiled']['nodes']
        lookup = {n['id']: n for n in nodes}
        for root in (n for n in nodes if n['parent_id'] is None):
            key = run['id'] + '/' + root['id']
            members = [w for w in words if any(key in m['nodes'] for m in w['memberships'])]
            u = {'unit': key, 'label': root['title'], 'book': run['title'], 'words': len(members),
                 'pages': [], 'unread': 0, 'sections': [], 'order': [root['page'], root['position']],
                 's1': {s: 0 for s in STAGES}, 's2': {s: 0 for s in STAGES}, 'catalog': True}
            for w in members:
                for stage in ('s1', 's2'):
                    u[stage][states[w['id']][stage]['stage']] += 1
            for node in nodes:
                path = [node]
                while path[-1]['parent_id'] is not None:
                    path.append(lookup[path[-1]['parent_id']])
                if path[-1]['id'] != root['id'] or node['id'] == root['id']:
                    continue
                node_key = run['id'] + '/' + node['id']
                count = sum(any(node_key in m['nodes'] for m in w['memberships']) for w in members)
                u['sections'].append({'section': node_key, 'label': ' › '.join(n['title'] for n in reversed(path[:-1])),
                                      'words': count, 'boxes': [], 'depth': len(path) - 1})
            result.append(u)
    return result


def selected_words(account_id: int, subject: str, unit: str, section: str = '') -> list[dict]:
    wanted = section or unit
    words = []
    for word in catalog_words(account_id, subject):
        matches = [m for m in word['memberships'] if wanted in m['nodes'] and unit in m['nodes']]
        if matches:
            # The first occurrence INSIDE the selection determines book order.
            word = dict(word)
            word['page'] = matches[0]['page']; word['source_label'] = matches[0]['book']
            word['_at'] = (matches[0]['page'], matches[0]['position'])
            words.append(word)
    return sorted(words, key=lambda w: w['_at'])


def cards(account_id: int, subject: str, unit: str, stage: int, limit: int, section: str = '', *, book_order=False) -> list[dict]:
    from .vocab import word_states, rank
    words = selected_words(account_id, subject, unit, section)
    with closing(webapp_conn()) as c:
        states = word_states(c, account_id, [w['id'] for w in words])
    if not book_order:
        if stage == 2:
            words = [w for w in words if states[w['id']]['s1']['stage'] in ('sitzt', 'gefestigt')]
        words.sort(key=lambda w: rank(states[w['id']], 's2' if stage == 2 else 's1'))
    return [{**{k: v for k, v in w.items() if k not in ('_at', 'source_label')},
             'label': w['source_label'], 'state': states[w['id']]} for w in words[:limit]]


def effective_word(account_id: int, word: dict) -> dict:
    """Use the active catalog's reviewed text for grading, retaining the old ID."""
    found = next((w for w in catalog_words(account_id, word['subject']) if w['id'] == word['id']), None)
    if found:
        word = {**word, **{k: v for k, v in found.items() if k not in ('memberships', 'meanings')}}
        word['meanings_json'] = _json(found['meanings'])
        word['forms_json'] = _json(found['forms'])
    return word


async def capture_sources(account_id: int, subject: str, pages: list[int]) -> dict:
    """Append original captures to quarantine; never overwrite prior materials.

    Navigation claims are not accepted as printed-page verification. No model
    or automatic legacy extraction runs here; the isolated audit follows.
    """
    from .textbook_context import book_and_credentials, fetch_pages
    from .textbook_browser import looks_blank
    from .source_collector import to_jpeg
    from .materials import account_usage, MAX_ACCOUNT_FILES
    book, credentials = book_and_credentials(account_id, subject=subject)
    if not book or not credentials:
        raise CatalogError('Kein digitales Buch mit Zugang für dieses Fach hinterlegt.')
    result = await fetch_pages(account_id, book, credentials, sorted(set(pages)), use_cache=False, survey=True)
    saved = []
    for claimed_page, image in result['shots']:
        if claimed_page is None or looks_blank(image):
            continue
        blob = to_jpeg(image); stamp = _now()
        with closing(webapp_conn()) as c, c:
            c.execute('BEGIN IMMEDIATE')
            if account_usage(c, account_id) + len(blob) > MAX_ACCOUNT_FILES * .9:
                raise CatalogError('Materialspeicher voll; vorhandene Originale bleiben erhalten.')
            mid = c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_book,source_page,"
                            "file_bytes,mime_type,filename,analysis_state,origin,hidden,created_at,updated_at) "
                            "VALUES(?,'book_page',?,?,?,?,?,?,'image/jpeg',?,'ready','vocab_capture',1,?,?)",
                            (account_id, subject, f'Prüfaufnahme S. {claimed_page}', book['title'], book['title'], claimed_page,
                             blob, f'pruefaufnahme-{claimed_page}.jpg', stamp, stamp)).lastrowid
            saved.append({'material_id': mid, 'requested_page': claimed_page, 'printed_page_verified': False,
                          'sha256': hashlib.sha256(blob).hexdigest()})
    return {'sources': saved, 'status': result['status'], 'navigation': result.get('seen').attempts if result.get('seen') else []}
