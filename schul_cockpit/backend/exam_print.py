"""Printable exercise sheet; all authored strings escaped, no solutions or answers.

Sparsam gedruckt (D191): Schreibplatz nach Punkten (3 mm je Punkt, 15–30 mm) statt pauschal 65 mm, darf
über die Seitengrenze laufen; nur Überschrift und Aufgabentext bleiben
zusammen. ``space="none"`` druckt nur die Aufgaben, gelöst wird im Heft.
"""
from html import escape

MM_PER_POINT = 3
MIN_SPACE, MAX_SPACE = 15, 30


def space_mm(points) -> int:
    try:
        return max(MIN_SPACE, min(MAX_SPACE, int(round(float(points) * MM_PER_POINT))))
    except (TypeError, ValueError):
        return MIN_SPACE


def sheet(exam, tasks, code=None, space="lines"):
    # code: Kennung einer Übungsarbeit (D178); dann gehen alle Seiten zusammen als Fotos in die App.
    only_tasks = space == "none"
    title = escape(exam['title'])
    sections = []
    for i, t in enumerate(tasks):
        room = '' if only_tasks else (f'<div class="space" style="height:{space_mm(t["points"])}mm" '
                                      f'aria-label="Platz für die Antwort"></div>')
        sections.append(f'<section><div class="q"><h2>Aufgabe {i+1} · {t["points"]} Punkte</h2>'
                        f'<p class="task">{escape(t["prompt"])}</p></div>{room}</section>')
    if code:
        hint = ('Löse im Heft oder auf Karopapier und schreibe die Aufgabennummern dazu. ' if only_tasks
                else 'Reicht der Platz nicht, auf einem Extrablatt weiter, mit Aufgabennummer. ')
        hint += 'Fotografiere am Ende alle beschriebenen Seiten gut lesbar, gerade von oben, bei hellem Licht.'
    else:
        hint = ('Schreibe die Aufgabennummer auf jedes zusätzliche Blatt. Fotografiere Antworten gut lesbar '
                'und ordne die Fotos in der App den Aufgaben zu.')
    tools = ('Danach zur App zurückkehren und alle beschriebenen Seiten bei dieser Übungsarbeit fotografieren.' if code
             else 'Danach zur App zurückkehren und unter „Online / Foto bearbeiten“ die Fotos bei der jeweiligen Aufgabe einreichen.')
    return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>
    body{{font:11pt/1.4 system-ui,sans-serif;max-width:190mm;margin:16px auto;padding:0 12px;color:#111;background:white}}
    h1{{font-size:15pt;margin:0 0 4px}}h2{{font-size:11.5pt;margin:0 0 3px}}.meta{{margin:0 0 6px;font-size:10pt}}.hint{{margin:0 0 8px;font-size:9.5pt;color:#333}}
    .task{{white-space:pre-wrap;overflow-wrap:anywhere;margin:0}}section{{margin:0 0 {'8px' if only_tasks else '10px'}}}.q{{break-inside:avoid}}
    .space{{margin-top:4px;background:repeating-linear-gradient(white,white 7.8mm,#ccc 7.8mm,#ccc 8mm)}}
    footer{{font-size:8.5pt;color:#555;margin-top:8px}}.tools{{background:#eee;padding:12px;margin-bottom:10px}}button{{font:inherit;padding:10px}}
    @page{{size:A4;margin:12mm}}@media print{{body{{margin:0;padding:0;max-width:none}}.tools{{display:none}}.space{{background:repeating-linear-gradient(white,white 7.8mm,#bbb 7.8mm,#bbb 8mm);-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
    </style></head><body><div class="tools"><button onclick="window.print()">Drucken / als PDF sichern</button><p>Ohne Lösungen. {tools}</p></div>
    <h1>{title}</h1><p class="meta">{('<strong>Blatt ' + escape(code) + '</strong> · ') if code else ''}{escape(exam['subject'])} · {exam['minutes']} Minuten · {sum(t['points'] for t in tasks)} Punkte · Name: ________________ Datum: __________</p><p class="hint">{hint} Übungsklausur, keine Schulnote · Aufgabenstand {exam['id']}</p>{''.join(sections)}</body></html>'''
