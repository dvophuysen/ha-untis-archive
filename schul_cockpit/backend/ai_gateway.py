"""Single metered boundary for every learning model call (micro-euro accounting).

Rates deliberately overestimate published Standard Global list prices including
cache writes and a currency/tax buffer. They are budget charges, not an Azure
invoice. Unknown models/expired rates fail closed. No provider conversation state.
"""
from __future__ import annotations
import asyncio
import json
import base64
import io
import math
import uuid
from contextlib import closing
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit
import httpx
import logging
from fastapi import HTTPException
from .db import webapp_conn
from .learning import (MAIN_TIER, SPEECH_TIER, TIERS, AiEndpointMissing, AiTierUnknown, ai_platforms,
                       ai_settings, ai_tiers, model_payload, model_output, now_iso, today_local, uses_responses)

LOG = logging.getLogger('schul_cockpit.ai')

RATE_SOURCE = 'https://azure.microsoft.com/en-us/blog/gpt-5-6-now-available-in-microsoft-foundry/'
RATE_UNTIL = date(2026, 12, 1)
# EUR je Million Token, ohne Cache-Rabatt. Grundlage ist der veröffentlichte
# Listenpreis für Standard Global in USD (Sol 5/30, Terra 2/12, Luna 0.20/1.20),
# darauf Faktor 2 auf den Eingang und 1,5 auf den Ausgang. Der Aufschlag deckt
# Währung, Steuer, Cache-Writes und den Aufpreis für Datenzonenstandard, den
# Microsoft nicht veröffentlicht. Eigene Sätze je Stufe stehen in der
# Add-on-Konfiguration und gehen diesen hier vor.
RATES = {'gpt-5.6-sol': (10.0, 45.0), 'gpt-5.6-terra': (5.0, 18.0), 'gpt-5.6-luna': (0.4, 1.8),
         # Spracheingabe: Audio-Token (etwa 1000 je Minute) und Text; Listenpreis 6 $/M plus Puffer.
         'gpt-4o-transcribe': (6.5, 11.0),
         # GPT-5-Familie nach derselben Regel: Listenpreis Standard Global in USD
         # (mini 0.25/2.00, nano 0.05/0.40, gpt-5 und gpt-5.1 1.25/10), Faktor 2
         # auf den Eingang und 1,5 auf den Ausgang. Bis 1.13.10 stand für mini ein
         # Platzhalter von 0,40/1,80 €, der den Ausgang unter Listenpreis buchte.
         'gpt-5-mini': (0.5, 3.0), 'gpt-5-nano': (0.1, 0.6),
         'gpt-5': (2.5, 15.0), 'gpt-5.1': (2.5, 15.0),
         # GPT-6 (seit 22.09.2026) nach derselben Regel: Listenpreis Standard
         # Global bis zur langen Kontextstufe, Sol 2.00/10.00, Luna 0.10/0.50 USD.
         'gpt-6-sol': (4.0, 15.0), 'gpt-6-luna': (0.2, 0.75)}
# Modelle, deren Satz ein Platzhalter ist. Die Elternansicht sagt das dazu,
# damit eine geschätzte Buchung nicht wie eine gemessene aussieht.
ESTIMATED: set[str] = set()
# Eine Minute Sprache sind rund tausend Audio-Token; die Schätzung rechnet großzügig.
AUDIO_TOKENS_PER_SECOND = 20
TRANSCRIBE_MAX_BYTES = 8 * 1024 * 1024
TRANSCRIBE_MAX_SECONDS = 180
BACKGROUND = {'discovery', 'background'}
# Der Quellenbestand (Buchseiten lesen, Inhaltsverzeichnisse ablesen) hat
# seinen eigenen Rahmen, damit er die Auswertung der Kinderfotos nicht
# verdrängt und umgekehrt. Beides bleibt innerhalb des Monatsrahmens.
SOURCES = 'sources'
MENTOR_CHAT = 'mentor'
# Bilder je Aufruf; alles andere zwei.
MAX_IMAGES = {SOURCES: 6, MENTOR_CHAT: 6}
# Der erste Zug einer Einheit: eigener Zweck, damit sein Modell geeicht werden kann.
OPENING = 'opening'
# Vokabellisten in Wörter zerlegen: Formatarbeit auf gedrucktem, sauberem Text,
# mit einer harten Prüfung dahinter — ein Wort wird verworfen, wenn sein Stamm
# nicht auf der Seite steht. Eigener Zweck, damit die Stufe unabhängig vom
# übrigen Abschreiben gewählt und geeicht werden kann (D103).
VOCAB = 'vocab'
# Eine Übungseinheit darf bis hierhin kosten; danach wird der Stand gesichert.
SESSION_MICRO = 4_000_000


def init_config(c):
    month = today_local().strftime('%Y-%m')
    old = c.execute('SELECT COALESCE(SUM(calls),0) FROM learning_ai_usage WHERE day LIKE ?', (month+'%',)).fetchone()[0]
    c.execute('INSERT OR IGNORE INTO mentor_ai_config(id,opening_month,opening_confirmed,updated_at) VALUES(1,?,?,?)',
              (month, int(old == 0), now_iso()))
    return dict(c.execute('SELECT * FROM mentor_ai_config WHERE id=1').fetchone())


def effective_sum(c, where, args=()):
    # Abgerechnet zählt der Betrag, freigegeben zählt gar nichts, alles andere
    # steht mit seiner Reservierung da, bis es sich klärt.
    return c.execute("SELECT COALESCE(SUM(CASE WHEN status='settled' THEN charged_micro "
                     "WHEN status='released' THEN 0 ELSE reserved_micro END),0) FROM mentor_ai_calls WHERE "+where,args).fetchone()[0]


def release(key, reason):
    """Eine Reservierung auflösen, wenn der Anbieter die Anfrage nie angenommen
    hat. Sie stehen zu lassen kostet Buchwert für Token, die nie verbraucht
    wurden: Ein falsch eingetragener Endpunkt hat so an einem Vormittag 0,80 €
    gebunden, ohne dass ein einziges Token geflossen wäre (D89)."""
    with closing(webapp_conn()) as c,c:
        c.execute("UPDATE mentor_ai_calls SET status='released',charged_micro=0,finished_at=?,error=? "
                  "WHERE id=? AND status!='settled'",(now_iso(),reason,key))


# Ein Aufruf, der nach einer Stunde weder abgerechnet noch gescheitert ist, ist
# abgestürzt. Seine Reservierung blockiert sonst dauerhaft die Schätzung.
STALE_AFTER_SECONDS = 3600


def release_stale():
    cutoff=(datetime.fromisoformat(now_iso())-timedelta(seconds=STALE_AFTER_SECONDS)).isoformat()
    with closing(webapp_conn()) as c,c:
        if c.execute("SELECT 1 FROM mentor_ai_calls WHERE status='reserved' AND created_at<? LIMIT 1",(cutoff,)).fetchone():
            c.execute("UPDATE mentor_ai_calls SET status='released',charged_micro=0,finished_at=?,error='abgebrochen' "
                      "WHERE status='reserved' AND created_at<?",(now_iso(),cutoff))


def projection(c, month, used_micro, today):
    """Wo der Monat landet, wenn es so weitergeht.

    Grundlage sind die letzten sieben Tage, nicht der Monatsschnitt: Ein
    einmaliges Einlesen eines Buchbestands am Monatsanfang würde die
    Hochrechnung sonst dauerhaft verzerren."""
    import calendar
    days_in_month=calendar.monthrange(today.year,today.month)[1]
    window=[(today-timedelta(days=n)).isoformat() for n in range(7)]
    recent=effective_sum(c,'day IN (%s)'%','.join('?'*len(window)),tuple(window))
    per_day=recent/min(7,today.day)
    return round((used_micro+per_day*(days_in_month-today.day))/1e6,2),round(per_day/1e6,3)


def status():
    release_stale()
    with closing(webapp_conn()) as c:
        cfg = init_config(c)
        month = today_local().strftime('%Y-%m')
        opening = cfg['opening_micro'] if cfg['opening_month'] == month else 0
        used = effective_sum(c,'month=?',(month,)) + opening
        bg = effective_sum(c,"month=? AND purpose IN ('discovery','background')",(month,))
        src = effective_sum(c,"month=? AND purpose='sources'",(month,))
        counts = c.execute('SELECT status,COUNT(*) n FROM mentor_ai_calls WHERE month=? GROUP BY status',(month,)).fetchall()
        # Nur Aufrufe, die Cache- und Denk-Token schon erfassen (ab 1.13.15),
        # je Zweck: So lässt sich ablesen, ob die Reihenfolge im Mentor wirkt.
        tokens = [dict(r) for r in c.execute(
            "SELECT purpose,COUNT(*) calls,SUM(input_tokens) input,SUM(cached_tokens) cached,"
            "SUM(output_tokens) output,SUM(reasoning_tokens) reasoning FROM mentor_ai_calls "
            "WHERE month=? AND status='settled' AND cached_tokens IS NOT NULL GROUP BY purpose ORDER BY purpose",(month,))]
    today=today_local()
    with closing(webapp_conn()) as c:
        projected,per_day=projection(c,month,used,today)
        over=[r[0] for r in c.execute("SELECT DISTINCT over_budget FROM mentor_ai_calls WHERE month=? AND over_budget IS NOT NULL",(month,))]
    tiers=ai_tiers()
    model=tiers[MAIN_TIER]['model']
    # Die App wählt Stufen, keine Modellnamen: Ein Modellwechsel in der
    # Add-on-Konfiguration lässt die Auswahl der Eltern unberührt (D88).
    rates={}
    for name,entry in tiers.items():
        rate=rate_for(entry)
        rates[name]=dict(model=entry['model'],input_per_m=rate[0] if rate else None,
                         output_per_m=rate[1] if rate else None,foundry=entry['foundry'],
                         # Geschätzt heißt: kein eigener Satz eingetragen und der
                         # hinterlegte ist nur ein Platzhalter.
                         estimated=rate_is_estimate(entry))
    return dict(month=month,used_eur=round(used/1e6,4),limit_eur=cfg['monthly_micro']/1e6,daily_limit_eur=cfg['daily_micro']/1e6,
                background_limit_eur=cfg['background_micro']/1e6,session_limit_eur=SESSION_MICRO/1e6,
                model=model,sources_model=cfg.get('sources_model') or None,opening_model=cfg.get('opening_model') or None,
                background_model=cfg.get('background_model') or None,vocab_model=cfg.get('vocab_model') or None,
                models=[t for t in TIERS if t!=SPEECH_TIER and tiers[t]['model']],
                rates=rates,
                warning_eur=cfg['warning_micro']/1e6,background_eur=round(bg/1e6,4),
                sources_eur=round(src/1e6,4),sources_limit_eur=cfg['sources_micro']/1e6,
                # Gewarnt wird, wenn der Monat auf den Richtwert zuläuft, nicht erst
                # wenn er ihn erreicht hat: Eine Warnung hinterher nützt nichts (D89).
                warning=used>=cfg['warning_micro'] or projected*1e6>=cfg['warning_micro'],
                projected_eur=projected,per_day_eur=per_day,
                over_budget=sorted({x for row in over for x in row.split(',') if x}),
                remaining_eur=max(0,(cfg['monthly_micro']-used)/1e6),
                opening_confirmed=bool(cfg['opening_confirmed'] or cfg['opening_month']!=month),
                opening_eur=opening/1e6,rate_available=bool(rate_for(tiers[MAIN_TIER])),
                accounting='Konservative Budgetanrechnung, keine Azure-Rechnung',rate_valid_until=RATE_UNTIL.isoformat(),
                calls={r['status']:r['n'] for r in counts},tokens=tokens)


def tier_for(purpose, cfg=None, override=None):
    """Welche Stufe einen Aufruf bedient. Das Hauptgespräch, Erklären und Üben
    laufen auf „hoch"; für den Einstieg in eine Einheit und fürs Abschreiben
    samt Hintergrundauswertung wählen die Eltern in der App eine Stufe."""
    if override: return override
    # Der Einstieg hat seine eigene, geeichte Stufe; die Hintergrundauswertung
    # ebenso, getrennt vom Abschreiben der Buchseiten (D94).
    column=('opening_model' if purpose==OPENING else 'background_model' if purpose in BACKGROUND
            else 'vocab_model' if purpose==VOCAB else 'sources_model' if purpose==SOURCES else None)
    if not column: return MAIN_TIER
    # Das Lesen der Vokabellisten gehört zum Abschreiben und folgt dessen Stufe,
    # solange keine eigene gewählt ist; erst eine Auswahl trennt beides (D103).
    columns=[column,'sources_model'] if purpose==VOCAB else [column]
    if cfg is None:
        # Nur lesen, keine Konfiguration anlegen: Das tut reserve() selbst.
        with closing(webapp_conn()) as c:
            row=c.execute(f"SELECT {','.join(columns)} FROM mentor_ai_config WHERE id=1").fetchone()
        cfg={name:(row[name] if row else None) for name in columns}
    for name in columns:
        chosen=(cfg.get(name) or '').strip()
        if chosen in TIERS: return chosen
    return MAIN_TIER


def model_name(tier=MAIN_TIER):
    """Nur der Modellname einer Stufe, ohne Zugang zu prüfen. Für Kennungen
    gespeicherter Ergebnisse und für Anzeigen, die auch ohne KI-Zugang tragen."""
    return (ai_tiers().get(tier) or {}).get('model') or ''


def settings_for(tier):
    """Modell, Deployment, Adresse, Schlüssel und Preissatz einer Stufe, mit
    lesbarer Meldung statt Rückfall auf die andere Foundry."""
    try:
        return ai_settings(tier)
    except AiEndpointMissing as exc:
        raise HTTPException(503,f'Die Foundry für die Stufe {tier} ist nicht eingerichtet ({exc}).') from None
    except AiTierUnknown:
        raise HTTPException(503,f'Für die Stufe {tier} ist kein Modell hinterlegt.') from None


def rate_for(settings):
    """Der Kostensatz einer Stufe: erst der eigene aus der Konfiguration, sonst
    der hinterlegte des Modells. Ohne beides wird nicht gerechnet und nicht
    aufgerufen, damit nie ungemessen Geld ausgegeben wird.

    Ein hinterlegter Satz nach RATE_UNTIL gilt weiter, aber als Schätzung: Bis
    1.13.10 fiel er an diesem Tag ersatzlos weg, und jede Stufe ohne eigenen
    Satz hätte ab dann jeden Aufruf verweigert — Stillstand ist nach D89 der
    schlechtere Ausgang als eine möglicherweise veraltete Anrechnung."""
    if settings.get('rate'): return settings['rate']
    return RATES.get(settings['model'])


def rate_is_estimate(settings):
    """Ob die Anrechnung einer Stufe auf einem Platzhalter oder einem
    abgelaufenen Satz beruht. Ein eigener Satz aus der Konfiguration nie."""
    if settings.get('rate') or settings['model'] not in RATES: return False
    return settings['model'] in ESTIMATED or today_local()>=RATE_UNTIL


def endpoint_overview():
    """Logzeile für den Start: welche Stufe welches Modell über welchen Host
    fährt. Ohne Schlüssel und ohne Pfad, damit sie im Add-on-Log stehen kann."""
    platforms=ai_platforms();parts=[]
    for tier,entry in ai_tiers().items():
        if not entry['model']:
            parts.append(f'{tier}: kein Modell');continue
        host=urlsplit(platforms[entry['foundry']]['url']).hostname or 'ohne Adresse'
        name=entry['model'] if entry['deployment']==entry['model'] else f"{entry['model']} als {entry['deployment']}"
        rate=rate_for({**entry})
        parts.append(f"{tier}: {name} über Foundry {entry['foundry']} ({host})"
                     +('' if rate else ', ohne Kostensatz')+(', Kostensatz geschätzt' if rate and rate_is_estimate(entry) else ''))
    return '; '.join(parts) or 'kein Modell eingerichtet'


# Die Rahmen sperren nicht mehr, sie melden. Der Betreiber hat sie ausdrücklich
# als Beobachtung gewollt, nicht als Tor: Die Schul-App muss laufen, auch wenn
# ein Rahmen reißt, denn ein blockierter Mentor mitten in einer Abfrage ist ein
# schlechterer Ausgang als ein überschrittener Richtwert (D89).
def thresholds(c, cfg, account_id, purpose, session_id, day, month, upper):
    """Welche Richtwerte dieser Aufruf überschreitet. Nur zur Meldung."""
    opening=cfg['opening_micro'] if cfg['opening_month']==month else 0
    own = purpose not in (SOURCES,VOCAB) and purpose not in BACKGROUND
    over=[]
    if effective_sum(c,'month=?',(month,))+opening+upper>cfg['monthly_micro']:
        over.append('monat')
    if own and effective_sum(c,"day=? AND account_id=? AND purpose NOT IN ('sources','vocab','background','discovery')",(day,account_id))+upper>cfg['daily_micro']:
        over.append('tag')
    if session_id is not None and effective_sum(c,'session_id=? AND account_id=?',(session_id,account_id))+upper>SESSION_MICRO:
        over.append('einheit')
    if purpose in BACKGROUND and effective_sum(c,"month=? AND purpose IN ('discovery','background')",(month,))+upper>cfg['background_micro']:
        over.append('hintergrund')
    if purpose in (SOURCES,VOCAB) and effective_sum(c,"month=? AND purpose IN ('sources','vocab')",(month,))+upper>cfg['sources_micro']:
        over.append('quellen')
    return over


def reserve(account_id, purpose, session_id, input_max, output_max, settings=None):
    settings=settings or settings_for(tier_for(purpose))
    model=settings['model']
    rate=rate_for(settings)
    if not model or not rate:
        raise HTTPException(503,'Für dieses Modell müssen die Budget-Kostensätze geprüft werden.')
    ri,ro=rate
    upper=math.ceil(input_max*ri+output_max*ro)
    day=today_local().isoformat(); month=day[:7]; key=uuid.uuid4().hex
    with closing(webapp_conn()) as c,c:
        c.execute('BEGIN IMMEDIATE');cfg=init_config(c)
        if cfg['opening_month']==month and not cfg['opening_confirmed']:
            raise HTTPException(409,'Bitte als Eltern zuerst die bisherigen KI-Kosten dieses Monats im Mentor bestätigen.')
        over=thresholds(c,cfg,account_id,purpose,session_id,day,month,upper)
        c.execute('INSERT INTO mentor_ai_calls(id,account_id,session_id,purpose,month,day,model,status,reserved_micro,input_rate,output_rate,created_at,over_budget) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (key,account_id,session_id,purpose,month,day,model,'reserved',upper,ri,ro,now_iso(),','.join(over) or None))
        if over:LOG.warning('KI-Richtwert überschritten (%s), der Aufruf läuft trotzdem: %s',purpose,', '.join(over))
    return key


def _count(value):
    return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else None


def settle(key, result=None, error=None):
    usage=(result or {}).get('usage') or {}
    inp=usage.get('input_tokens',usage.get('prompt_tokens'));out=usage.get('output_tokens',usage.get('completion_tokens'))
    valid=isinstance(inp,int) and not isinstance(inp,bool) and inp>=0 and isinstance(out,int) and not isinstance(out,bool) and out>=0
    # Responses-API und Chat Completions nennen die Einzelheiten verschieden.
    cached=_count((usage.get('input_tokens_details') or usage.get('prompt_tokens_details') or {}).get('cached_tokens'))
    reasoning=_count((usage.get('output_tokens_details') or usage.get('completion_tokens_details') or {}).get('reasoning_tokens'))
    with closing(webapp_conn()) as c,c:
        row=c.execute('SELECT * FROM mentor_ai_calls WHERE id=?',(key,)).fetchone()
        if valid:
            charge=math.ceil(inp*row['input_rate']+out*row['output_rate'])
            # Never conceal an accounting overrun: disable calls pending reconciliation.
            if charge>row['reserved_micro']:
                c.execute('UPDATE mentor_ai_config SET opening_confirmed=0,opening_month=? WHERE id=1',(today_local().strftime('%Y-%m'),))
            # Gebucht wird weiter der volle Eingangssatz, auch für Cache-Token:
            # Die Anrechnung bleibt konservativ, die Zahlen zeigen die Wirkung.
            c.execute("UPDATE mentor_ai_calls SET status='settled',charged_micro=?,input_tokens=?,output_tokens=?,"
                      "cached_tokens=?,reasoning_tokens=?,finished_at=?,error=? WHERE id=?",
                      (charge,inp,out,cached,reasoning,now_iso(),error,key))
        else:
            c.execute("UPDATE mentor_ai_calls SET status='uncertain',finished_at=?,error=? WHERE id=?",(now_iso(),error or 'usage_missing',key))


EFFORTS=('low','medium','high')
# Eine Drosselung (429) hat nichts gekostet und ist nach Sekunden vorbei. Bis
# 1.13.20 gab die App sofort auf, das Kind sah einen Fehler. Jetzt wartet sie,
# so lange Azure es nennt, höchstens RATE_WAIT_MAX Sekunden, und versucht es
# bis zu RATE_RETRIES Mal neu. Nennt Azure eine längere Wartezeit, bleibt es
# beim Fehler: Ein Kind soll nicht minutenlang auf eine Antwort warten.
RATE_RETRIES=2
RATE_WAIT_MAX=20.0


def retry_wait(response):
    """Wie lange Azure nach einer Drosselung warten lässt, in Sekunden;
    None, wenn es länger ist, als die App wartet."""
    for name,scale in (('retry-after-ms',1000),('retry-after',1)):
        try: wait=float(response.headers[name])/scale
        except (KeyError,ValueError): continue
        return None if wait>RATE_WAIT_MAX else max(0.5,wait)
    return 5.0


# --- Seitenbilder in bestmöglicher Auflösung (D169) --------------------------
# Ein Bild mit "page": True ist eine Seite, auf der jedes Detail zählt:
# Handschrift, Brüche, Graphen, Schaltskizzen, Noten. Wie es am besten ankommt,
# hängt vom Modell ab (OpenAI-Dokumentation „Images and vision“):
# - Die Kachel-Modelle (gpt-5, gpt-5-mini, gpt-5.1, gpt-4o) verkleinern jedes
#   Bild, bis die kurze Seite 768 Pixel misst. Eine ganze Heftseite kam so mit
#   rund 60 % an. Sie bekommen einen Überblick über die ganze Seite und dazu
#   Ausschnitte, jeder so klein, dass er unverkleinert ankommt.
# - Die neueren Modelle (ab gpt-5.4, gpt-5.6, gpt-6) nehmen mit „auto“ die volle
#   Auflösung bis 6000 Pixel. Sie bekommen das Original als ein Bild; ein Graph
#   bleibt so im Ganzen.
TILE_SHORT = 760
TILE_LONG = 2048
TILE_OVERLAP = 60
TILE_TARGET = (2400, 2000, 1600)
MAX_PAGE_IMAGES = 14   # Azure nimmt bis 50 Bilder je Aufruf; mit Abstand darunter
WHOLE_PIXELS = 10_000_000
WHOLE_SIDE = 6000


def vision_style(model: str | None) -> str:
    """„whole“ für Modelle, die ein Bild in voller Auflösung nehmen, sonst „tile“."""
    import re
    return "whole" if re.match(r"gpt-(?:5\.(?:[4-9]|\d\d)|[6-9])", (model or "").lower()) else "tile"


def _jpeg(img) -> str:
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def _grid(width: int, height: int) -> list[tuple[int, int, int, int]]:
    """Überlappende Ausschnitte, jeder höchstens TILE_LONG breit und TILE_SHORT
    hoch, von oben nach unten und links vor rechts."""
    def cuts(size: int, span: int) -> list[tuple[int, int]]:
        if size <= span:
            return [(0, size)]
        count = math.ceil((size - TILE_OVERLAP) / (span - TILE_OVERLAP))
        step = (size - TILE_OVERLAP) / count
        return [(int(i * step), size if i == count - 1 else int(i * step + step + TILE_OVERLAP)) for i in range(count)]
    return [(left, top, right, bottom) for top, bottom in cuts(height, TILE_SHORT) for left, right in cuts(width, TILE_LONG)]


def _tile_page(img, target: int) -> list:
    page = img.copy()
    page.thumbnail((target, target))
    # Kommt die Seite ohnehin unverkleinert an, braucht sie keine Ausschnitte.
    if min(page.size) <= 768 and max(page.size) <= TILE_LONG:
        return [page]
    boxes = _grid(*page.size)
    if len(boxes) == 1:
        return [page]
    overview = img.copy()
    overview.thumbnail((TILE_LONG, TILE_LONG))
    return [overview] + [page.crop(box) for box in boxes]


def page_images(pages: list, model: str | None) -> tuple[list[dict], list[int]]:
    """Seitenbilder für das Modell aufbereiten. Gibt die Bildteile zurück und je
    Seite die Zahl der Bilder (für den Hinweis an das Modell)."""
    if vision_style(model) == "whole":
        parts, counts = [], []
        for img in pages:
            whole = img.copy()
            whole.thumbnail((WHOLE_SIDE, WHOLE_SIDE))
            if whole.width * whole.height > WHOLE_PIXELS:
                scale = math.sqrt(WHOLE_PIXELS / (whole.width * whole.height))
                whole = whole.resize((int(whole.width * scale), int(whole.height * scale)))
            parts.append({"type": "image_url", "image_url": {"url": _jpeg(whole), "detail": "auto"}})
            counts.append(1)
        return parts, counts
    for target in TILE_TARGET:
        sets = [_tile_page(img, target) for img in pages]
        if sum(len(x) for x in sets) <= MAX_PAGE_IMAGES:
            break
    else:
        sets = [[_tile_page(img, TILE_LONG)[0]] for img in pages]
    parts = [{"type": "image_url", "image_url": {"url": _jpeg(piece), "detail": "high"}} for group in sets for piece in group]
    return parts, [len(group) for group in sets]


def image_bound(width: int, height: int, style: str) -> int:
    """Obergrenze der Bild-Token für die Vorab-Buchung, statt pauschal 32.768."""
    if style == "whole":
        return 20_000
    scale = min(1.0, 2048 / max(width, height))
    w, h = width * scale, height * scale
    if min(w, h) > 768:
        scale = 768 / min(w, h)
        w, h = w * scale, h * scale
    return 85 + 170 * math.ceil(w / 512) * math.ceil(h / 512)


def layout_note(counts: list[int], offset: int = 0) -> str:
    """Sagt dem Modell, welche Bilder zu welcher Seite gehören."""
    notes, index = [], offset + 1
    for page, count in enumerate(counts, 1):
        if count == 1:
            notes.append(f"Bild {index}: Seite {page} ganz")
        else:
            notes.append(f"Bild {index}: Seite {page} im Überblick; Bilder {index + 1} bis {index + count - 1}: "
                         f"Ausschnitte derselben Seite in voller Auflösung, zeilenweise von oben nach unten und links vor "
                         f"rechts, mit Überlappung")
        index += count
    return ("; ".join(notes) + ". Lies Zahlen, Handschrift und Feinheiten aus den Ausschnitten, den Aufbau und "
            "Abbildungen im Zusammenhang aus dem Überblick. Gib jede Stelle nur einmal wieder.") if any(c > 1 for c in counts) else ""


async def complete(account_id, purpose, instruction, context, images=None, max_output=4096, session_id=None, tier=None, effort=None,
                   tail_keys=()):
    # Reasoning-Tiefe: bisher fest low; für die Eichung je Aufruf wählbar (D77).
    effort=effort or 'low'
    if effort not in EFFORTS: raise ValueError('Invalid reasoning effort')
    # Die Stufe bestimmt alles Weitere: Modell fürs Buchen, Deployment für den
    # Aufruf, Adresse und Schlüssel der zugeordneten Foundry (D88).
    config=settings_for(tier_for(purpose,override=tier))
    endpoint,api_key=config['url'],config['key'];url=urlsplit(endpoint)
    if not api_key or not config['model'] or url.scheme!='https' or not url.hostname or url.username or url.password:
        raise HTTPException(503,'Die KI-Verbindung ist noch nicht eingerichtet.')
    # Die Denkschritte zählen mit in dieses Budget. Eine dichte Heftseite
    # braucht für ihren Text allein mehrere tausend Token; bei 8000 kam von
    # einer vollgeschriebenen Seite nur noch „incomplete: max_output_tokens"
    # zurück, also gar nichts, bei vollen Kosten (D119). Abgerechnet wird
    # ohnehin der Verbrauch, die Grenze bucht nur vor.
    if not 256<=max_output<=16000: raise ValueError('Invalid output boundary')
    images=images or []
    normalized=[]
    # Übung: zwei Bilder. Der Quellenbestand liest ein fotografiertes
    # Inhaltsverzeichnis mit bis zu sechs Aufnahmen in einem Aufruf; zusammen-
    # gefügt würden sie beim Verkleinern auf 1600 Pixel unlesbar. Der Chat
    # darf ebenso sechs: Hausaufgabenhilfe und Kontrolle nehmen mehrere selbst
    # gewählte Heftseiten mit, dazu die Buchseiten der Aufgabe.
    most=MAX_IMAGES.get(purpose,2)
    if len(images)>most: raise HTTPException(413,f'Bitte höchstens {most} Bilder auf einmal verwenden.')
    style=vision_style(config['model'])
    bounds=[];pending_pages=[];counts=[]

    def flush_pages():
        # Aufeinanderfolgende Seitenbilder gemeinsam: Die Zahl der Ausschnitte
        # richtet sich nach allen Seiten eines Aufrufs (D169).
        if not pending_pages:return
        parts,sizes=page_images(pending_pages,config['model'])
        counts.append((len(normalized),sizes))
        for part in parts:
            from PIL import Image
            img=Image.open(io.BytesIO(base64.b64decode(part['image_url']['url'].split(',',1)[1])))
            bounds.append(image_bound(img.width,img.height,style if part['image_url']['detail']=='auto' else 'tile'))
        normalized.extend(parts);pending_pages.clear()

    for part in images:
        try:
            from PIL import Image,ImageOps
            uri=part['image_url']['url']
            if not uri.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')):raise ValueError()
            blob=base64.b64decode(uri.split(',',1)[1],validate=True)
            img=Image.open(io.BytesIO(blob))
            if img.width*img.height>(50_000_000 if part.get('page') else 25_000_000):raise ValueError()
            img=ImageOps.exif_transpose(img).convert('RGB')
            if part.get('page'):
                pending_pages.append(img);continue
            flush_pages()
            img.thumbnail((1600,1600))
            out=io.BytesIO();img.save(out,format='JPEG',quality=85)
            normalized.append({'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode(),'detail':'high'}})
            bounds.append(32768)
        except (ValueError,KeyError,OSError):raise HTTPException(422,'Das Bild ist nicht lesbar oder zu groß.') from None
    flush_pages()
    images=normalized
    notes=[layout_note(sizes,offset) for offset,sizes in counts]
    if any(notes):
        context={**context,'bildaufbau':' '.join(n for n in notes if n)}
    # Each UTF-8 byte is a conservative text-token upper bound. Vision inputs
    # must be locally constrained; 32k tokens/image also leaves ample patch margin.
    raw=json.dumps(context,ensure_ascii=False)
    text_bytes=len((instruction+raw).encode())
    if text_bytes>48000: raise HTTPException(413,'Zu viel Material für einen Schritt. Bitte einen kleineren Abschnitt wählen.')
    upper_input=text_bytes+1024+sum(bounds)
    # In den Aufruf geht der Bereitstellungsname, nicht der Modellname.
    # tail_keys: was sich von Zug zu Zug ändert (Verlauf, neue Nachricht),
    # steht hinter den Bildern. Azure rechnet einen gleichbleibenden Anfang
    # verbilligt aus dem Cache ab; stand der Verlauf vorn, fiel alles dahinter,
    # auch die Bilder, jedes Mal heraus.
    payload=model_payload(endpoint,config['deployment'],instruction,context,images,tail_keys=tail_keys)
    if uses_responses(endpoint):
        payload['max_output_tokens']=max_output
        payload['reasoning']={'effort':effort}
    else:
        payload['max_completion_tokens']=max_output
        payload['reasoning_effort']=effort
    key=reserve(account_id,purpose,session_id,upper_input,max_output,settings=config)
    result=None
    try:
        # Die Wartezeit wächst mit dem Ausgabebudget: Ein Gespräch antwortet in
        # Sekunden, eine dichte Heftseite mit 14.000 Token schreibt minutenlang.
        # Fest 90 Sekunden hieß, dass ein bezahlter Aufruf kurz vor dem Ergebnis
        # abgeschnitten wurde (D119).
        patience=min(300,max(90,round(max_output/50)))
        async with httpx.AsyncClient(timeout=patience,follow_redirects=False) as client:
            for attempt in range(RATE_RETRIES+1):
                response=await client.post(endpoint,json=payload,headers={'api-key':api_key})
                wait=retry_wait(response) if response.status_code==429 and attempt<RATE_RETRIES else None
                if wait is None: break
                LOG.info('KI-Aufruf (%s) gedrosselt, neuer Versuch in %.1f s',purpose,wait)
                await asyncio.sleep(wait)
            response.raise_for_status();result=response.json()
        if not isinstance(result,dict): raise ValueError('Invalid envelope')
        settle(key,result)
        raw=model_output(endpoint,result).strip()
        if raw.startswith('```'): raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
        return raw,result,key
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
        # Der Grund gehört ins Log, sonst heißt jeder Fehler nur „502": Status der
        # Antwort, warum sie unvollständig blieb, was an Ausgabe kam.
        if result is None:
            # Eine abgelehnte Anfrage (falsche Adresse, falscher Schlüssel, Drosselung)
            # hat kein Token gekostet: Reservierung auflösen statt buchen. Zeitüberschreitung
            # und Serverfehler bleiben stehen, dort kann das Modell gelaufen sein.
            status=getattr(getattr(exc,'response',None),'status_code',None)
            if (status is not None and status<500) or isinstance(exc,httpx.ConnectError):
                release(key,f'nicht angenommen ({status or "keine Verbindung"})')
            else:
                settle(key,error='provider_error')
            LOG.warning('KI-Aufruf (%s) ohne verwertbare Antwort: %s',purpose,f'{type(exc).__name__}: {str(exc)[:200]}')
        else:
            outputs=[(o.get('type'),o.get('status')) for o in (result.get('output') or []) if isinstance(o,dict)][:6]
            LOG.warning('KI-Antwort (%s) nicht verwertbar: status=%s incomplete=%s output=%s fehler=%s',purpose,result.get('status'),
                        result.get('incomplete_details'),outputs,f'{type(exc).__name__}: {str(exc)[:200]}')
        raise HTTPException(502,'Die Antwort konnte noch nicht verarbeitet werden. Dein Stand bleibt erhalten; es wird nicht automatisch erneut angefragt.') from None


def transcribe_url(config=None):
    """Die Adresse der Spracheingabe, aus der Foundry ihrer Stufe abgeleitet
    (Azure-Pfad je Bereitstellung)."""
    # Leer, solange die Stufe keinen Zugang hat: Die Uebersichten fragen hier
    # nur, ob ein Mikrofon angeboten werden kann. Wer wirklich aufnimmt, geht
    # durch transcribe() und bekommt dort die Meldung.
    if config is None:
        try:
            config=ai_settings(SPEECH_TIER)
        except (AiEndpointMissing,AiTierUnknown):
            return ''
    url=urlsplit(config['url'])
    if not url.hostname:return ''
    return f"{url.scheme}://{url.netloc}/openai/deployments/{config['deployment']}/audio/transcriptions?api-version=2025-03-01-preview"


async def transcribe(account_id, audio, mime, language=None, prompt='', session_id=None, seconds=None):
    """Gesprochenes in Text, mit demselben Budget wie jede Kinderanfrage.

    language ist ein Sprachhinweis (de, en, es, fr) oder None; prompt nennt Fach
    und erwartete Wörter, damit Fachbegriffe und lateinische Formen nicht zu
    Alltagswörtern werden. Zurück kommt der Text, den das Kind vor dem Senden
    sieht und berichtigen kann."""
    config=settings_for(SPEECH_TIER);url=transcribe_url(config);parsed=urlsplit(url)
    model=config['deployment'];api_key=config['key']
    if not api_key or parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(503,'Die Spracheingabe ist noch nicht eingerichtet.')
    if not audio or len(audio)>TRANSCRIBE_MAX_BYTES:raise HTTPException(413,'Die Aufnahme ist zu lang. Bitte in kürzeren Stücken sprechen.')
    seconds=min(TRANSCRIBE_MAX_SECONDS,max(1,int(seconds or 0) or max(1,len(audio)//4000)))
    prompt=(prompt or '')[:600]
    upper_input=seconds*AUDIO_TOKENS_PER_SECOND+len(prompt.encode())//2+64
    key=reserve(account_id,'mentor',session_id,upper_input,400,settings=config)
    ext={'audio/mp4':'m4a','audio/x-m4a':'m4a','audio/aac':'m4a','audio/webm':'webm','audio/ogg':'ogg','audio/wav':'wav','audio/x-wav':'wav','audio/mpeg':'mp3'}.get((mime or '').split(';')[0].strip(),'webm')
    data={'model':model,'response_format':'json','temperature':'0'}
    if prompt:data['prompt']=prompt
    if language:data['language']=language
    result=None
    try:
        async with httpx.AsyncClient(timeout=60,follow_redirects=False) as client:
            response=await client.post(url,data=data,files={'file':(f'aufnahme.{ext}',audio,(mime or 'audio/webm').split(';')[0].strip())},headers={'api-key':api_key})
            response.raise_for_status();result=response.json()
        if not isinstance(result,dict) or not isinstance(result.get('text'),str):raise ValueError('Invalid envelope')
        usage=result.get('usage') or {}
        # Ohne Verbrauchsangabe gilt die Schätzung als verbraucht; nie stillschweigend günstiger buchen.
        if not isinstance(usage.get('input_tokens'),int):result['usage']={'input_tokens':upper_input,'output_tokens':min(400,len(result['text'])//2+1)}
        settle(key,result)
        return result['text'].strip()
    except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
        if result is None:
            status=getattr(getattr(exc,'response',None),'status_code',None)
            if (status is not None and status<500) or isinstance(exc,httpx.ConnectError):
                release(key,f'nicht angenommen ({status or "keine Verbindung"})')
            else:
                settle(key,error='provider_error')
        raise HTTPException(502,'Die Aufnahme konnte nicht in Text umgewandelt werden. Du kannst deine Antwort tippen.') from None

