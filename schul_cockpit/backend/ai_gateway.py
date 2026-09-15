"""Single metered boundary for every learning model call (micro-euro accounting).

Rates deliberately overestimate published Standard Global list prices including
cache writes and a currency/tax buffer. They are budget charges, not an Azure
invoice. Unknown models/expired rates fail closed. No provider conversation state.
"""
from __future__ import annotations
import json
import base64
import io
import math
import uuid
from contextlib import closing
from datetime import date
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException
from .db import webapp_conn
from .learning import ai_settings, model_payload, model_output, now_iso, today_local, uses_responses

RATE_SOURCE = 'https://azure.microsoft.com/en-us/blog/gpt-5-6-now-available-in-microsoft-foundry/'
RATE_UNTIL = date(2026, 12, 1)
# EUR per million tokens, deliberately no prompt-cache discount.
RATES = {'gpt-5.6-sol': (10.0, 45.0), 'gpt-5.6-terra': (5.0, 18.0), 'gpt-5.6-luna': (1.9, 9.0)}
BACKGROUND = {'discovery', 'background'}
# Der Quellenbestand (Buchseiten lesen, Inhaltsverzeichnisse ablesen) hat
# seinen eigenen Rahmen, damit er die Auswertung der Kinderfotos nicht
# verdrängt und umgekehrt. Beides bleibt innerhalb des Monatsrahmens.
SOURCES = 'sources'
# Eine Übungseinheit darf bis hierhin kosten; danach wird der Stand gesichert.
SESSION_MICRO = 4_000_000


def init_config(c):
    month = today_local().strftime('%Y-%m')
    old = c.execute('SELECT COALESCE(SUM(calls),0) FROM learning_ai_usage WHERE day LIKE ?', (month+'%',)).fetchone()[0]
    c.execute('INSERT OR IGNORE INTO mentor_ai_config(id,opening_month,opening_confirmed,updated_at) VALUES(1,?,?,?)',
              (month, int(old == 0), now_iso()))
    return dict(c.execute('SELECT * FROM mentor_ai_config WHERE id=1').fetchone())


def effective_sum(c, where, args=()):
    return c.execute("SELECT COALESCE(SUM(CASE WHEN status='settled' THEN charged_micro ELSE reserved_micro END),0) FROM mentor_ai_calls WHERE "+where,args).fetchone()[0]


def status():
    with closing(webapp_conn()) as c:
        cfg = init_config(c)
        month = today_local().strftime('%Y-%m')
        opening = cfg['opening_micro'] if cfg['opening_month'] == month else 0
        used = effective_sum(c,'month=?',(month,)) + opening
        bg = effective_sum(c,"month=? AND purpose IN ('discovery','background')",(month,))
        src = effective_sum(c,"month=? AND purpose='sources'",(month,))
        counts = c.execute('SELECT status,COUNT(*) n FROM mentor_ai_calls WHERE month=? GROUP BY status',(month,)).fetchall()
    model = ai_settings()['model']
    return dict(month=month,used_eur=round(used/1e6,4),limit_eur=cfg['monthly_micro']/1e6,daily_limit_eur=cfg['daily_micro']/1e6,
                warning_eur=cfg['warning_micro']/1e6,background_eur=round(bg/1e6,4),
                sources_eur=round(src/1e6,4),sources_limit_eur=cfg['sources_micro']/1e6,
                warning=used>=cfg['warning_micro'],remaining_eur=max(0,(cfg['monthly_micro']-used)/1e6),
                opening_confirmed=bool(cfg['opening_confirmed'] or cfg['opening_month']!=month),
                opening_eur=opening/1e6,rate_available=model in RATES and today_local()<RATE_UNTIL,
                accounting='Konservative Budgetanrechnung, keine Azure-Rechnung',rate_valid_until=RATE_UNTIL.isoformat(),
                calls={r['status']:r['n'] for r in counts})


def reserve(account_id, purpose, session_id, input_max, output_max):
    cfg_ai = ai_settings(); model=cfg_ai['model']
    if model not in RATES or today_local()>=RATE_UNTIL:
        raise HTTPException(503,'Für dieses Modell müssen die Budget-Kostensätze geprüft werden.')
    ri,ro=RATES[model]
    upper=math.ceil(input_max*ri+output_max*ro)
    day=today_local().isoformat(); month=day[:7]; key=uuid.uuid4().hex
    with closing(webapp_conn()) as c,c:
        c.execute('BEGIN IMMEDIATE');cfg=init_config(c)
        if cfg['opening_month']==month and not cfg['opening_confirmed']:
            raise HTTPException(409,'Bitte als Eltern zuerst die bisherigen KI-Kosten dieses Monats im Mentor bestätigen.')
        opening=cfg['opening_micro'] if cfg['opening_month']==month else 0
        if effective_sum(c,'month=?',(month,))+opening+upper>cfg['monthly_micro']:
            raise HTTPException(429,'Der KI-Rahmen ist ausgeschöpft. Gespeicherte Übungen und Antworten bleiben verfügbar.')
        # Die Tagesgrenze je Kind schützt das Üben und Fragen des Kindes. Was
        # die App selbst im Hintergrund tut (Quellen einlesen, Materialien
        # auswerten, Einstiegshilfen), zählt nicht dagegen: Am 15.09. hatten
        # 26 Auswertungen Josias Tagesrahmen aufgebraucht, bevor er eine Frage
        # gestellt hatte. Die Höhe steht in mentor_ai_config.daily_micro.
        own = purpose!=SOURCES and purpose not in BACKGROUND
        if own and effective_sum(c,"day=? AND account_id=? AND purpose NOT IN ('sources','background','discovery')",(day,account_id))+upper>cfg['daily_micro']:
            raise HTTPException(429,'Für heute ist der KI-Rahmen erreicht. Wir sichern deinen Stand.')
        if session_id is not None and effective_sum(c,'session_id=? AND account_id=?',(session_id,account_id))+upper>SESSION_MICRO:
            raise HTTPException(429,'Für diese Einheit ist der KI-Rahmen erreicht. Dein Stand bleibt gespeichert.')
        if purpose in BACKGROUND and effective_sum(c,"month=? AND purpose IN ('discovery','background')",(month,))+upper>cfg['background_micro']:
            raise HTTPException(429,'Die weitere Hintergrundauswertung wartet auf das nächste Monatsbudget.')
        if purpose==SOURCES and effective_sum(c,"month=? AND purpose='sources'",(month,))+upper>cfg['sources_micro']:
            raise HTTPException(429,'Der Rahmen für den Quellenbestand ist für diesen Monat ausgeschöpft.')
        c.execute('INSERT INTO mentor_ai_calls(id,account_id,session_id,purpose,month,day,model,status,reserved_micro,input_rate,output_rate,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                  (key,account_id,session_id,purpose,month,day,model,'reserved',upper,ri,ro,now_iso()))
    return key


def settle(key, result=None, error=None):
    usage=(result or {}).get('usage') or {}
    inp=usage.get('input_tokens',usage.get('prompt_tokens'));out=usage.get('output_tokens',usage.get('completion_tokens'))
    valid=isinstance(inp,int) and not isinstance(inp,bool) and inp>=0 and isinstance(out,int) and not isinstance(out,bool) and out>=0
    with closing(webapp_conn()) as c,c:
        row=c.execute('SELECT * FROM mentor_ai_calls WHERE id=?',(key,)).fetchone()
        if valid:
            charge=math.ceil(inp*row['input_rate']+out*row['output_rate'])
            # Never conceal an accounting overrun: disable calls pending reconciliation.
            if charge>row['reserved_micro']:
                c.execute('UPDATE mentor_ai_config SET opening_confirmed=0,opening_month=? WHERE id=1',(today_local().strftime('%Y-%m'),))
            c.execute("UPDATE mentor_ai_calls SET status='settled',charged_micro=?,input_tokens=?,output_tokens=?,finished_at=?,error=? WHERE id=?",
                      (charge,inp,out,now_iso(),error,key))
        else:
            c.execute("UPDATE mentor_ai_calls SET status='uncertain',finished_at=?,error=? WHERE id=?",(now_iso(),error or 'usage_missing',key))


async def complete(account_id, purpose, instruction, context, images=None, max_output=4096, session_id=None):
    config=ai_settings();url=urlsplit(config['url'])
    if not config['key'] or not config['model'] or url.scheme!='https' or not url.hostname or url.username or url.password:
        raise HTTPException(503,'Die KI-Verbindung ist noch nicht eingerichtet.')
    if not 256<=max_output<=8000: raise ValueError('Invalid output boundary')
    images=images or []
    normalized=[]
    # Chat und Übung: zwei Bilder. Der Quellenbestand liest ein fotografiertes
    # Inhaltsverzeichnis mit bis zu sechs Aufnahmen in einem Aufruf; zusammen-
    # gefügt würden sie beim Verkleinern auf 1600 Pixel unlesbar.
    most=6 if purpose==SOURCES else 2
    if len(images)>most: raise HTTPException(413,f'Bitte höchstens {most} Bilder auf einmal verwenden.')
    for part in images:
        try:
            from PIL import Image,ImageOps
            uri=part['image_url']['url']
            if not uri.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')):raise ValueError()
            blob=base64.b64decode(uri.split(',',1)[1],validate=True)
            img=Image.open(io.BytesIO(blob))
            if img.width*img.height>25_000_000:raise ValueError()
            img=ImageOps.exif_transpose(img).convert('RGB');img.thumbnail((1600,1600))
            out=io.BytesIO();img.save(out,format='JPEG',quality=85)
            normalized.append({'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode(),'detail':'high'}})
        except (ValueError,KeyError,OSError):raise HTTPException(422,'Das Bild ist nicht lesbar oder zu groß.') from None
    images=normalized
    if len(images)>most: raise HTTPException(413,f'Bitte höchstens {most} Bilder auf einmal verwenden.')
    # Each UTF-8 byte is a conservative text-token upper bound. Vision inputs
    # must be locally constrained; 32k tokens/image also leaves ample patch margin.
    raw=json.dumps(context,ensure_ascii=False)
    text_bytes=len((instruction+raw).encode())
    if text_bytes>48000: raise HTTPException(413,'Zu viel Material für einen Schritt. Bitte einen kleineren Abschnitt wählen.')
    upper_input=text_bytes+1024+32768*len(images)
    payload=model_payload(config['url'],config['model'],instruction,context,images)
    if uses_responses(config['url']):
        payload['max_output_tokens']=max_output
        payload['reasoning']={'effort':'low'}
    else:
        payload['max_completion_tokens']=max_output
        payload['reasoning_effort']='low'
    key=reserve(account_id,purpose,session_id,upper_input,max_output)
    result=None
    try:
        async with httpx.AsyncClient(timeout=90,follow_redirects=False) as client:
            response=await client.post(config['url'],json=payload,headers={'api-key':config['key']})
            response.raise_for_status();result=response.json()
        if not isinstance(result,dict): raise ValueError('Invalid envelope')
        settle(key,result)
        raw=model_output(config['url'],result).strip()
        if raw.startswith('```'): raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
        return raw,result,key
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
        if result is None: settle(key,error='provider_error')
        raise HTTPException(502,'Die Antwort konnte noch nicht verarbeitet werden. Dein Stand bleibt erhalten; es wird nicht automatisch erneut angefragt.') from None
