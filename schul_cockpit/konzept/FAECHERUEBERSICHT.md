# Umsetzung 0.73.0: Balken aus dem Lernstand

Seit 0.73.0 (D71) zeigt der Balken je Fach die Verteilung der Stufen der
Themen dieses Schuljahrs (gefestigt, sitzt, wackelt, angefangen, neu), die
App liest sie aus den Antworten ab (D59). Der Trend sind die gezählten
Stufenwechsel der letzten vier Wochen; ohne Wechsel steht „kein Wechsel“.
Fächer ohne Themenliste zeigen weiter die Selbsteinschätzung, so beschriftet.
Damit ist die unten offen gelassene Datenbedeutung festgelegt.

# Testbare Umsetzung 0.34.0

Der Auftrag zur Fertigstellung und Bereitstellung umfasst jetzt die grafische Fächerliste. Umgesetzt sind die Balken, ein aufklappbares Fachdetail und der direkte Verlauf tatsächlicher Unterrichtsrückmeldungen. Balken = Anteile vorhandener Themen-Selbsteinschätzungen (inklusive unbekannt), kein neuer Kompetenzscore. Die Zeitlinie zeigt bis zu zwölf Beobachtungen ohne Glättung oder Trendbehauptung. Genaue Leistungs-/Trendbewertung und Elternintegration bleiben offen. Der folgende Abschnitt dokumentiert den vorausgegangenen Entwurf, dessen Vorschläge nicht sämtlich schon Funktionen sind.

---

# Arbeitspaket: grafische Fächerübersicht

Stand 13.09.2026. Produktentwurf aus der erneuten UI-Abstimmung, keine produktive Bewertungsregel.

## Verbindliche Zielrichtung

Eine grafische, kompakte Übersicht über alle Fächer ersetzt die großen offenen Fachkarten. Nach Status sortieren, entsprechend D11 stärkenorientiert. Details und Analyse erst beim Antippen als Drilldown. Entwicklung soll schon in der Übersicht erkennbar werden. iPhone zuerst. Eine spätere Übernahme der ganzen Liste oder eines Auszugs in die Elternstartseite bleibt ausdrücklich offen.

## Vorgeschlagene Darstellung

Eine gemeinsame ruhige Liste statt einer Karte je Fach. Jede Fachzeile enthält:

1. Fachname mit dem bestehenden einheitlichen Fachsymbol; rechts ein knapper Status.
2. Darunter einen schmalen horizontalen Balken mit identischer Skala über alle Fächer. Daneben eine kleine Verlaufslinie; Trend zusätzlich verständlich benennen.
3. Einen einzigen einheitlichen Chevron als Detailzugang. Die ganze Zeile öffnet dasselbe Ziel.

Etwa 64–80 px pro Fachzeile bei normaler iPhone-Schrift; bei vergrößerter Schrift darf sie wachsen. Fünf bis sieben Fächer sollen auf einer üblichen Bildschirmhöhe vergleichbar sein. Keine Themenlisten, Stundenanzahlen, Analyseabsätze oder Üben-Knöpfe im geschlossenen Zustand.

Balken werden gegenüber Sternen bevorzugt vorgeschlagen: Sie lassen sich besser mit einem zeitlichen Verlauf kombinieren. Sterne würden leicht wie eine Benotung oder Belohnung wirken. Weder Sterne noch ein frei erfundener 0–100-Gesamtscore werden jetzt eingeführt.

## Datenbedeutung vor Implementierung festlegen

- Ein Balken muss eine erklärte Größe darstellen. Vorschlag für einen ersten belastbaren Stand: Anteile der zuletzt eingeschätzten Themen nach verstanden / teilweise / noch schwierig, mit getrennt sichtbarer fehlender Datenabdeckung. Selbsteinschätzung bleibt als solche erkennbar.
- Unterrichtsrückmeldung, selbstständig gezeigtes Können, Hilfe und Erledigung dürfen nicht still gemittelt werden. Spätere Übungsbelege können einen Themenstand aktualisieren, brauchen aber nachvollziehbare Prioritäts-/Gültigkeitsregeln.
- Keine Rückmeldung ergibt „Noch offen“ beziehungsweise „Noch keine Einschätzung“, keinen leeren Leistungsbalken und keine Null-Sterne-Bewertung.
- Keine neue Sortierbewegung während einer Interaktion. Stärken zuerst; unbekannte Fächer als neutrale eigene Gruppe. Gleichstände stabil alphabetisch als Vorschlag.
- Verlauf nur aus gespeicherten, vergleichbaren Zeitständen. Bei fehlenden oder zu wenigen Daten „Noch kein Verlauf“. Neue Themen, andere Aufgabenanforderungen und veränderte Hilfen dürfen nicht automatisch eine Verschlechterung behaupten.
- Zeitraum, Mindestbelege, Datenalter, Gewichtung, Trendgrenzen und Gleichstandsregel sind Vorschläge bzw. offene Entscheidungen, keine bereits beschlossene Formel.

## Drilldown

Antippen klappt das Fach unmittelbar unter der Zeile auf; erneutes Tippen schließt es. aria-expanded und zugeordnete Detailregion; kein zusätzlicher Modal-Workflow. Zunächst: ausführlicher Verlauf, Gelungenes, offene Themen, nächster sinnvoller Schritt. Bestehende Übungslinks und Stundenquellen werden hier erreichbar. KI-Analyse darunter erst auf ausdrücklichen Aufruf, vorhandene Kosten-/Freigabegrenzen beibehalten.

Nur ein offenes Fach gleichzeitig ist ein Vorschlag für die iPhone-Ansicht. Gewählte Sortierung und Scrollposition beim Rückweg erhalten.

## Abnahme des Folgepakets

- Alle Fächer erreichbar, starke und unbekannte Fächer korrekt unterscheidbar.
- Vergleichbare Balkenskalen, beschriftete Trends; keine erfundenen Historien.
- 320/390/430 px, größere Schrift und Dunkelmodus; keine abgeschnittenen Fachnamen.
- Details per Touch und Tastatur, sichere Rückkehr zur ursprünglichen Fachzeile.
- Gemischte/veraltete/fehlende Daten und Datenladefehler ausdrücklich geprüft.
- Elternintegration bleibt Folgeentscheidung nach visueller Abnahme dieser Fächerliste.
