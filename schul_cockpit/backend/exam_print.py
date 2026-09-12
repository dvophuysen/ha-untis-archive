"""Printable exercise sheet; all authored strings escaped, no solutions or answers."""
from html import escape

def sheet(exam,tasks):
    title=escape(exam['title']);sections=[]
    for i,t in enumerate(tasks):
        sections.append(f'<section><h2>Aufgabe {i+1} · {t["points"]} Punkte</h2><p class="task">{escape(t["prompt"])}</p><div class="space" aria-label="Platz für die Antwort"></div></section>')
    return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>
    body{{font:12pt system-ui,sans-serif;max-width:190mm;margin:20px auto;padding:0 14px;color:#111;background:white}}h1{{font-size:20pt}}h2{{font-size:14pt}}.task{{white-space:pre-wrap;overflow-wrap:anywhere}}section{{break-inside:avoid;margin:20px 0}}.space{{height:65mm;background:repeating-linear-gradient(white,white 8mm,#ccc 8mm,#ccc 8.2mm)}}.tools{{background:#eee;padding:14px}}button{{font:inherit;padding:12px}}@page{{size:A4;margin:18mm}}@media print{{body{{margin:0;padding:0;max-width:none}}.tools{{display:none}}.space{{background:none;border-bottom:1px solid #bbb}}}}
    </style></head><body><div class="tools"><button onclick="window.print()">Drucken / als PDF sichern</button><p>Ohne Lösungen. Auf dem iPhone auch über Teilen → Drucken. Danach zur App zurückkehren und unter „Online / Foto bearbeiten“ die Fotos bei der jeweiligen Aufgabe einreichen.</p></div>
    <h1>{title}</h1><p>{escape(exam['subject'])} · {exam['minutes']} Minuten · {sum(t['points'] for t in tasks)} Punkte</p><p>Name: ____________________ Datum: ______________</p><p>Schreibe die Aufgabennummer auf jedes zusätzliche Blatt. Fotografiere Antworten gut lesbar und ordne die Fotos in der App den Aufgaben zu.</p>{''.join(sections)}<footer>Übungsklausur · keine echte Schulnote · Aufgabenstand {exam['id']}</footer></body></html>'''
