"""Kiosk-Fallback für alte Browser (iOS 12 Safari, IE/Edge Legacy etc.).

Die moderne Svelte-App nutzt Optional Chaining, Nullish Coalescing und
CSS-color-mix() — auf iOS-12-Safari (iPad Air 1, mini 2/3) kippt der
Bundle mit Syntax-Errors. Damit das Küchen-iPad trotzdem das
Eltern-Dashboard anzeigen kann, rendert dieses Modul eine reine
HTML-Variante derselben Übersicht: server-side gebaut, kein JS, Tabellen
statt CSS-Grid, Auto-Refresh per Meta-Tag.

Die Datenbeschaffung läuft über `dashboard._dashboard_for_account` —
eine Quelle der Wahrheit zwischen SPA und Kiosk.
"""

from __future__ import annotations

from datetime import date
from html import escape as h

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import CurrentUser, get_current_user, linked_account_ids
from ..db import history_conn, webapp_conn
from ..pin_auth import (
    SESSION_COOKIE,
    SESSION_TTL_DAYS,
    PinError,
    create_session,
    verify_pin,
)
from .dashboard import _dashboard_for_account

router = APIRouter()

_LEARN_EMOJI = ["⚪", "😟", "😐", "😀"]
_PRIO_DOT = {"red": "🔴", "orange": "🟠", "green": "🟢"}
_URG_DOT = {"missed": "❗", "red": "🔴", "orange": "🟠", "green": "🟢"}
_WEEKDAY_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _safe_user(request: Request) -> CurrentUser | None:
    try:
        return get_current_user(request)
    except HTTPException:
        return None


# ---------- Endpoints ----------------------------------------------------


@router.get("/kiosk", response_class=HTMLResponse)
async def kiosk_dashboard(request: Request) -> HTMLResponse:
    user = _safe_user(request)
    if user is None:
        return RedirectResponse("/kiosk/login", status_code=303)

    today = date.today()
    account_ids = sorted(linked_account_ids(user.id))
    if not account_ids:
        return HTMLResponse(
            _layout("Übersicht", "<p class='empty'>Noch keine Kinder verlinkt.</p>")
        )

    conn = history_conn()
    try:
        placeholder = ",".join("?" for _ in account_ids)
        rows = conn.execute(
            f"SELECT id, name FROM accounts WHERE id IN ({placeholder}) ORDER BY name",
            account_ids,
        ).fetchall()
        names = {r["id"]: r["name"] for r in rows}
    finally:
        conn.close()

    kids = []
    for acc_id in account_ids:
        kids.append(
            await _dashboard_for_account(acc_id, names.get(acc_id, ""), today)
        )

    body = "<div class='dash'>" + "".join(_render_kid(k) for k in kids) + "</div>"
    return HTMLResponse(
        _layout(
            f"Schul-Cockpit · {h(user.display_name or 'Übersicht')}",
            body,
            autorefresh=300,
        )
    )


@router.get("/kiosk/login", response_class=HTMLResponse)
def kiosk_login_form(request: Request, err: str = "") -> HTMLResponse:
    # Wenn der Browser per Ingress-Header schon authentifiziert ist, gibt
    # es nichts zu loggen — gleich aufs Dashboard.
    if _safe_user(request) is not None:
        return RedirectResponse("/kiosk", status_code=303)

    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT id, display_name FROM users "
            "WHERE role IN ('admin','parent','kid') "
            "AND pin_hash IS NOT NULL "
            "ORDER BY display_name"
        ).fetchall()
    finally:
        conn.close()

    options = "\n".join(
        f'<option value="{u["id"]}">{h(u["display_name"] or "")}</option>'
        for u in rows
    )
    err_html = f'<div class="err">{h(err)}</div>' if err else ""
    body = f"""
      <form method="post" action="/kiosk/login" class="login-form">
        <h2>Anmelden</h2>
        {err_html}
        <label>Nutzer
          <select name="user_id" required>{options}</select>
        </label>
        <label>PIN
          <input name="pin" type="password" inputmode="numeric"
                 autocomplete="off" autofocus required>
        </label>
        <button type="submit">Anmelden</button>
      </form>
    """
    return HTMLResponse(_layout("Anmelden", body))


@router.post("/kiosk/login")
def kiosk_login_submit(
    request: Request,
    response: Response,
    user_id: int = Form(...),
    pin: str = Form(...),
):
    conn = webapp_conn()
    try:
        try:
            ok = verify_pin(conn, user_id, pin)
        except PinError as exc:
            return RedirectResponse(
                f"/kiosk/login?err={h(exc.message)}", status_code=303
            )
        if not ok:
            return RedirectResponse(
                "/kiosk/login?err=Falscher+PIN", status_code=303
            )
        token, _ = create_session(conn, user_id)
    finally:
        conn.close()

    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").lower()
    is_https = request.url.scheme == "https" or forwarded_proto == "https"
    resp = RedirectResponse("/kiosk", status_code=303)
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        path="/",
        secure=is_https,
    )
    return resp


# ---------- Rendering ----------------------------------------------------


def _render_kid(kid: dict) -> str:
    return (
        '<section class="kid">'
        + _render_head(kid)
        + _render_now(kid)
        + _render_exams(kid)
        + _render_support(kid)
        + _render_tasks(kid)
        + _render_plan(kid)
        + _render_feedback(kid)
        + "</section>"
    )


def _render_head(kid: dict) -> str:
    return f"<div class='kid-head'><h2>{h(kid['name'])}</h2></div>"


def _render_now(kid: dict) -> str:
    n = kid.get("now") or {}
    icon = n.get("icon") or ""
    label = n.get("label") or ""
    return f"<div class='now'>{h(icon)} {h(label)}</div>"


def _render_exams(kid: dict) -> str:
    exams = kid.get("exams") or []
    head = (
        "<h3>Klausuren"
        + (f"<span class='count'>{len(exams)}</span>" if exams else "")
        + "</h3>"
    )
    if not exams:
        return f"<div class='block'>{head}<div class='empty-small'>keine geplant</div></div>"
    rows = []
    for e in exams:
        dot = _PRIO_DOT.get(e["priority"], "")
        learn = _LEARN_EMOJI[e["learn_state"]] if e.get("learn_state") is not None else _LEARN_EMOJI[0]
        comp = e.get("comprehension") or {}
        hard = comp.get("hard", 0)
        hard_cell = f"⚠{hard}" if hard > 0 else ""
        rows.append(
            "<tr>"
            f"<td class='dot'>{dot}</td>"
            f"<td class='subj'>{h(e.get('subject_short') or '')}</td>"
            f"<td class='when'>{h(_when_label(e['date'], e['days_until']))}</td>"
            f"<td class='num'>{e['days_until']}</td>"
            f"<td class='learn'>{learn}</td>"
            f"<td class='hard'>{hard_cell}</td>"
            "</tr>"
        )
    return (
        f"<div class='block'>{head}"
        "<table class='tbl exam-tbl'>"
        + "".join(rows)
        + "</table></div>"
    )


def _render_support(kid: dict) -> str:
    support = kid.get("support") or []
    head = "<h3>Mitlernen 🤝</h3>"
    if not support:
        return f"<div class='block'>{head}<div class='empty-small'>alles im grünen Bereich</div></div>"
    rows = []
    for s in support:
        label = s.get("subject_short") or s.get("subject_name") or ""
        rows.append(
            "<tr>"
            f"<td class='subj'>{h(label)}</td>"
            f"<td class='hard'>⚠ {s['hard_count']}</td>"
            f"<td class='num'>/{s['total_count']}</td>"
            "</tr>"
        )
    return (
        f"<div class='block'>{head}"
        "<table class='tbl sup-tbl'>"
        + "".join(rows)
        + "</table></div>"
    )


def _render_tasks(kid: dict) -> str:
    tasks = (kid.get("tasks") or {}).get("items") or []
    count = (kid.get("tasks") or {}).get("open_count", 0)
    head = (
        "<h3>Hausaufgaben"
        + (f"<span class='count'>{count}</span>" if count else "")
        + "</h3>"
    )
    if not tasks:
        return f"<div class='block'>{head}<div class='empty-small'>keine offenen Aufgaben</div></div>"
    rows = []
    for t in tasks:
        dot = _URG_DOT.get(t.get("urgency") or "", "")
        rows.append(
            "<tr>"
            f"<td class='dot'>{dot}</td>"
            f"<td class='subj'>{h(t.get('subject_short') or '')}</td>"
            f"<td class='title'>{h(t.get('title') or '')}</td>"
            f"<td class='when'>{h(_due_label(t.get('due_date')))}</td>"
            "</tr>"
        )
    return (
        f"<div class='block'>{head}"
        "<table class='tbl hw-tbl'>"
        + "".join(rows)
        + "</table></div>"
    )


def _render_plan(kid: dict) -> str:
    plan = kid.get("plan") or {}
    cols = plan.get("columns") or []
    times = plan.get("period_times") or []
    weekend_hint = " · nächste Woche" if plan.get("is_weekend") else ""
    head = f"<h3>Plan<span class='muted small'>{h(weekend_hint)}</span></h3>"

    # Header row
    head_cells = []
    for col in cols:
        cls = []
        if col.get("is_today"):
            cls.append("is-today")
        if col.get("is_filler"):
            cls.append("filler")
        cls_attr = (" class='" + " ".join(cls) + "'") if cls else ""
        dt = col["date"]
        date_disp = f"{dt[8:10]}.{dt[5:7]}."
        head_cells.append(
            f"<th{cls_attr}>{h(col['weekday'])}"
            f"<span class='pdate'>{date_disp}</span></th>"
        )

    # Body rows — one per period_time. The cell-by-column-by-time map
    # makes empty slots show as blank cells, which keeps periods aligned
    # across all 5 days exactly like the modern Plan-Grid.
    body_rows = []
    for t in times:
        cells = []
        for col in cols:
            lesson = next(
                (lx for lx in (col.get("lessons") or []) if lx.get("start_hhmm") == t),
                None,
            )
            cells.append(_render_plan_cell(lesson, col.get("is_today")))
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    if not times:
        body = "<tr><td class='empty' colspan='5'><span class='muted'>keine Stunden in Sicht</span></td></tr>"
    else:
        body = "".join(body_rows)

    return (
        f"<div class='block'>{head}"
        "<table class='plan'>"
        f"<thead><tr>{''.join(head_cells)}</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table></div>"
    )


def _render_plan_cell(lesson: dict | None, is_today: bool) -> str:
    if lesson is None:
        return "<td class='empty'></td>"
    cls = []
    if is_today:
        cls.append("today-col")
    if lesson.get("is_cancelled"):
        cls.append("cancelled")
    elif lesson.get("is_irregular") or lesson.get("is_subject_substituted"):
        cls.append("substitution")
    if lesson.get("has_exam") and not lesson.get("is_cancelled"):
        cls.append("has-exam")
    cls_attr = (" class='" + " ".join(cls) + "'") if cls else ""

    if lesson.get("is_cancelled"):
        # Nur das ursprüngliche Fach durchstreichen — kein Symbol nötig,
        # der gestrichelte Rahmen plus Strikethrough sind klar genug.
        label = lesson.get("subject_orig_short") or lesson.get("subject_short") or ""
        content = f"<span class='old'>{h(label)}</span>"
    elif lesson.get("is_subject_substituted") and lesson.get("subject_orig_short"):
        old = lesson["subject_orig_short"]
        new = lesson.get("subject_short") or ""
        content = (
            f"<span class='old'>{h(old)}</span>"
            f"<span class='new'>{h(new)}</span>"
        )
    else:
        label = lesson.get("subject_short") or ""
        swap = ""
        if (
            lesson.get("is_irregular")
            or lesson.get("is_teacher_substituted")
            or lesson.get("is_room_substituted")
        ):
            swap = "<span class='swap'>⇄</span>"
        content = f"<span>{h(label)}</span>{swap}"

    if lesson.get("has_exam") and not lesson.get("is_cancelled"):
        content += "<span class='exam-tag'>KA</span>"

    return f"<td{cls_attr}>{content}</td>"


def _render_feedback(kid: dict) -> str:
    fg = kid.get("feedback_gap") or {}
    total = fg.get("total_lessons", 0)
    if total == 0:
        return ""
    miss = fg.get("unrated_lessons", 0)
    if miss == 0:
        text = "🩺 alles bewertet (7 Tage)"
    else:
        text = f"🩺 {miss} Stunden noch ohne Feedback"
    return f"<div class='hyg'>{text}</div>"


def _when_label(iso: str, days: int) -> str:
    if days == 0:
        return "heute"
    if days == 1:
        return "morgen"
    if days <= 6:
        d = date.fromisoformat(iso)
        return _WEEKDAY_DE[d.weekday()]
    d = date.fromisoformat(iso)
    return f"{d.day:02d}.{d.month:02d}."


def _due_label(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return ""
    today = date.today()
    delta = (d - today).days
    if delta < 0:
        return "verpasst"
    if delta == 0:
        return "heute"
    if delta == 1:
        return "morgen"
    if delta <= 6:
        return _WEEKDAY_DE[d.weekday()]
    if delta <= 13:
        return "nä. Wo."
    return f"{d.day:02d}.{d.month:02d}."


# ---------- Layout shell -------------------------------------------------


def _layout(title: str, body: str, autorefresh: int | None = None) -> str:
    refresh_tag = (
        f'<meta http-equiv="refresh" content="{autorefresh}">'
        if autorefresh
        else ""
    )
    return (
        "<!doctype html>"
        '<html lang="de"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        f"{refresh_tag}"
        f"<title>{h(title)}</title>"
        f"<style>{_CSS}</style>"
        "</head><body>"
        f"<header><h1>{h(title)}</h1></header>"
        f"<main>{body}</main>"
        "</body></html>"
    )


# CSS bewusst iOS-12-kompatibel: keine color-mix(), keine :has(), keine
# Container-Queries, kein clamp(), kein logical-properties-Spielzeug.
# Tabellen statt CSS-Grid für das Plan-Layout — Tabellen alignen Zeilen
# und Spalten von Haus aus zuverlässig, und Safari 12 hat damit Null
# Probleme.
_CSS = """
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font: 16px/1.4 -apple-system, BlinkMacSystemFont, "Helvetica Neue",
        Arial, sans-serif;
  background: #f5f6f8;
  color: #1a1a1a;
  -webkit-text-size-adjust: 100%;
}
header {
  background: #fff;
  border-bottom: 1px solid #e2e6ea;
  padding: 0.6rem 1rem;
}
header h1 { margin: 0; font-size: 1rem; font-weight: 600; color: #5b6b7c; }
main { padding: 0.8rem; max-width: 1400px; margin: 0 auto; }

.dash {
  display: flex;
  flex-wrap: wrap;
  margin: -0.4rem;
}
.kid {
  background: #fff;
  border-radius: 12px;
  padding: 0.9rem 1rem;
  margin: 0.4rem;
  flex: 1 1 460px;
  min-width: 0;
}
.kid-head h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
}
.now {
  font-size: 0.95rem;
  color: #5b6b7c;
  padding: 0.35rem 0 0.55rem;
  border-bottom: 1px solid #e2e6ea;
}

.block { padding-top: 0.7rem; }
.block h3 {
  margin: 0 0 0.4rem;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #5b6b7c;
  font-weight: 700;
  display: block;
}
.count {
  background: #eef0f3;
  color: #1a1a1a;
  padding: 0 0.4rem;
  border-radius: 8px;
  font-size: 0.7rem;
  font-weight: 700;
  border: 1px solid #e2e6ea;
  margin-left: 0.45rem;
  text-transform: none;
  letter-spacing: 0;
}
.muted, .empty-small { color: #5b6b7c; font-size: 0.88rem; }
.empty-small { padding: 0.15rem 0 0.3rem; }
.small { font-size: 0.8rem; }

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.tbl td {
  padding: 0.35rem 0.4rem;
  vertical-align: middle;
  border-top: 1px solid #f0f2f5;
}
.tbl tr:first-child td { border-top: none; }
.tbl .dot { width: 1.6em; text-align: center; }
.tbl .subj { font-weight: 600; width: 4em; }
.tbl .when { color: #5b6b7c; font-size: 0.85rem; }
.tbl .num {
  color: #98a4b1;
  font-size: 0.8rem;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.tbl .learn { text-align: center; width: 1.8em; }
.tbl .hard { color: #f59e0b; font-size: 0.8rem; text-align: right; }
.tbl .title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 220px;
}
.exam-tbl td.subj, .hw-tbl td.subj { width: 3.5em; }

/* Plan-Tabelle. table-layout: fixed sorgt dafür, dass alle Spalten
   gleich breit sind, egal wieviel Text drin steht. */
.plan {
  width: 100%;
  border-collapse: separate;
  border-spacing: 3px;
  table-layout: fixed;
  font-size: 0.85rem;
}
.plan th {
  padding: 0.2rem 0 0.4rem;
  font-weight: 700;
  text-align: center;
}
.plan th.is-today { color: #2563eb; }
.plan th .pdate {
  display: block;
  font-size: 0.7rem;
  color: #5b6b7c;
  font-weight: 400;
  margin-top: 0.1rem;
}
.plan th.filler .pdate { color: #98a4b1; }

.plan td {
  background: #fff;
  border: 1px solid #e2e6ea;
  border-radius: 4px;
  padding: 0.3rem 0.15rem;
  text-align: center;
  height: 32px;
  font-size: 0.8rem;
  vertical-align: middle;
}
.plan td.empty { background: transparent; border-color: transparent; }
.plan td.today-col { background: #eff5ff; }
.plan td.cancelled { border-style: dashed; color: #98a4b1; }
.plan td.substitution { box-shadow: inset 0 0 0 1px #8b5cf6; }
.plan td.has-exam { box-shadow: inset 0 0 0 2px #db2777; }
.plan td.substitution.has-exam { box-shadow: inset 0 0 0 2px #db2777, inset 0 0 0 3px #8b5cf6; }
.plan td .old { text-decoration: line-through; color: #98a4b1; }
.plan td .new {
  font-weight: 700;
  color: #8b5cf6;
  margin-left: 0.25rem;
}
.plan td .swap { color: #8b5cf6; margin-left: 0.2rem; }
.plan td .exam-tag {
  background: #db2777;
  color: #fff;
  font-size: 0.6rem;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 0.25rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.hyg {
  margin-top: 0.6rem;
  padding-top: 0.55rem;
  border-top: 1px dashed #e2e6ea;
  color: #5b6b7c;
  font-size: 0.85rem;
}

/* Login-Maske, JS-frei. */
.login-form {
  max-width: 360px;
  margin: 3rem auto;
  background: #fff;
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.login-form h2 { margin: 0 0 0.8rem; }
.login-form label {
  display: block;
  margin: 0.7rem 0;
  font-size: 0.9rem;
  color: #5b6b7c;
}
.login-form select, .login-form input {
  display: block;
  width: 100%;
  margin-top: 0.3rem;
  padding: 0.7rem;
  font: inherit;
  border: 1px solid #e2e6ea;
  border-radius: 8px;
  min-height: 44px;
  background: #fff;
  color: #1a1a1a;
}
.login-form button {
  display: block;
  width: 100%;
  padding: 0.8rem;
  background: #2563eb;
  color: #fff;
  border: 0;
  border-radius: 8px;
  font: inherit;
  font-weight: 600;
  margin-top: 1rem;
  min-height: 48px;
}
.err {
  background: #fef2f2;
  color: #991b1b;
  padding: 0.55rem 0.7rem;
  border-radius: 6px;
  margin-bottom: 0.8rem;
  font-size: 0.9rem;
}
.empty {
  padding: 2rem;
  text-align: center;
  color: #5b6b7c;
}

@media (prefers-color-scheme: dark) {
  body { background: #0f1419; color: #e6e9ed; }
  header { background: #1a2028; border-bottom-color: #2a323c; }
  header h1 { color: #9ba8b5; }
  .kid { background: #1a2028; }
  .now, .block h3, .muted, .empty-small, .plan th .pdate, .hyg,
  .tbl .when, .login-form label { color: #9ba8b5; }
  .count { background: #232a34; border-color: #2a323c; color: #e6e9ed; }
  .tbl td { border-top-color: #232a34; }
  .plan td { background: #1a2028; border-color: #2a323c; }
  .plan td.today-col { background: #1d2a44; }
  .plan td.empty { background: transparent; border-color: transparent; }
  .plan th.is-today { color: #60a5fa; }
  .hyg { border-top-color: #2a323c; }
  .login-form { background: #1a2028; }
  .login-form select, .login-form input { background: #232a34; color: #e6e9ed; border-color: #2a323c; }
}
"""
