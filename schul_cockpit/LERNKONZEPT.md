> Fortschreibung: [Masterplan](MASTERPLAN.md) und [aktueller Mentor-Betrieb](MENTOR_BETRIEB.md).

# Lernraum – Gesamtkonzept und technische Umsetzung

> Fortschreibung vom 12. September 2026: [Lernmentor, adaptive Lernstandsprüfung und nachhaltiges Wissen](MENTOR_KONZEPT.md). Dort sind implementierter Stand und geplante Architektur getrennt.

Stand: 11. September 2026 · Schul-Cockpit 0.23.0

## Auftrag und Zielbild

Der Lernraum unterstützt Kinder und Eltern dauerhaft über Fächer und Schuljahre hinweg. Er verbindet Unterricht, Material, Übung, Rückmeldung und Planung in der vorhandenen Schul-App. Ein Chat oder eine einzelne Pilotübung ist keine Voraussetzung für den täglichen Betrieb.

Erfolg hat vier Dimensionen: fachliches Können, Selbstständigkeit, vertretbarer Aufwand und Zufriedenheit. Schulnoten sind eine zusätzliche Rückmeldung, keine alleinige Steuergröße. Die Software kann diese Entwicklung unterstützen, aber weder Bestnoten noch Schulfreude garantieren.

Das Datenmodell ist nicht auf einzelne Kinder, Deutsch oder einen Jahrgang zugeschnitten. Jede bereits freigegebene Kind-Zuordnung kann Schuljahre für Jahrgang 1–13, beliebige Fächer und Themen aufnehmen. Kein Inhalt wird wegen eines Schuljahreswechsels gelöscht. Weitere Unterrichtsmaterialien können kontinuierlich ergänzt werden.

## Pädagogisches Betriebsmodell

### Ein Thema durchläuft mehrere Phasen

1. **Orientieren:** Thema, Lernziel, relevantes Vorwissen und ein kleines Beispiel. Ein kurzer Ausblick auf eine kommende Stunde ist möglich, sobald deren Inhalt bekannt ist.
2. **Aufgabe verstehen:** Arbeitsauftrag in eigene Worte übersetzen. Operator und geforderte Antwortform beachten.
3. **Selbst versuchen:** Erst eine eigene Antwort oder ein Arbeitsergebnis festhalten.
4. **Passende Hilfe:** Bei Bedarf einen Hinweis und eine Erklärung öffnen. Hilfe wird am Lernversuch dokumentiert.
5. **Prüfen:** Eigene Antwort mit einer möglichen Lösung und konkreten Kriterien vergleichen.
6. **Anpassen:** Noch einmal, teilweise oder selbstständig gelungen einschätzen und Belastung festhalten.
7. **Später abrufen:** Dieselbe Fähigkeit an weiteren Tagen und an veränderten Aufgaben aufgreifen.

Neue Inhalte dürfen erklärt werden; der Lernraum zwingt Kinder nicht zum erfolglosen Raten. Eine erste erfolgreiche Wiederholung gilt nicht als gesicherter Nachweis für dauerhaftes Können. Ein wiederholt geübter identischer Arbeitsauftrag ersetzt keine neue Transferaufgabe.

### Anforderungsbereiche und Lerntätigkeiten

Anforderungsbereiche beschreiben Aufgaben: I reproduzieren, II verknüpfen und anwenden, III reflektieren und Probleme lösen. Der ganze Auftrag und die Unterrichtsvoraussetzungen bestimmen die Zuordnung; das Signalwort allein reicht nicht. Die Zuordnung ist keine automatische Note.

Die Wahl der Lernmethode richtet sich nach der Tätigkeit, nicht nach einem festen vermeintlichen Lerntyp des Kindes:

| Tätigkeit | Geeignete Schritte |
|---|---|
| Wissen und Wortschatz | Frei abrufen, korrigieren, mit zeitlichem Abstand wiederholen, im Kontext verwenden |
| Verfahren und Rechenwege | Gelöstes Beispiel erklären, ähnliche Aufgabe selbst lösen, Verfahren bei veränderter Aufgabe wählen |
| Zusammenhänge | Ursachen erklären, Skizzen einsetzen, Vorhersagen begründen |
| Texte und Argumentation | Arbeitsauftrag analysieren, Antwort strukturieren, schreiben, anhand der Kriterien überarbeiten |
| Sprechen und Zuhören | Laut sprechen, Hörverstehen gesondert üben, Ergebnis reflektieren |
| Praktische und kreative Arbeit | Vorgehen planen, durchführen, Ergebnis dokumentieren und überprüfen |

Für praktische/mündliche Aufgaben wird zunächst eine schriftliche Ergebnisnotiz erfasst. Audioaufnahme, Spracherkennung, Aussprachebewertung und eine automatische Prüfung praktischer Arbeiten sind **nicht** implementiert.

### Selbstorganisation und Freude

Die Unterstützung geht schrittweise vom Vormachen über gemeinsames Entscheiden zum eigenen Planen über. Das persönliche Ziel wird mit dem Kind formuliert. Die App zeigt wenige nächste Schritte; Eltern können die Auswahl über Schwerpunkte, Themenstatus, Zieldatum, Lerntage und Zeitgrenzen beeinflussen.

Es gibt keine Geschwisterrangliste, keinen Streak-Verlust als Strafe und keine automatisch wachsenden Aufgabenberge nach einer schlechten Selbsteinschätzung. Eine kurze Rückmeldung „anstrengend“ wird dokumentiert; sie löst keine zusätzlichen Aufgaben aus.

Ein wöchentliches Gespräch betrachtet: Was wurde leichter? Welche Hilfe war nützlich? Was war unnötig oder belastend? Wenn die Belastung steigt, wird der Umfang reduziert. Soziale Schwierigkeiten in der Schule bleiben ein eigener Gesprächsanlass und werden nicht als fachliche Wissenslücke behandelt.

## Quellen und Stoffumfang

Verbindliche Unterrichtsaufträge, Themenlisten und Bewertungskriterien haben Vorrang vor allgemeinen Erklärungen. Untis liefert den Unterrichtsverlauf; leere Felder bleiben unbekannt. Ein versäumter Unterricht, eine subjektive Unsicherheit und ein misslungener Lernversuch werden getrennt angezeigt.

Schulinterne Arbeitspläne und Landesvorgaben bilden den Orientierungsrahmen. Sie verraten nicht automatisch die Reihenfolge einzelner Unterrichtsstunden oder den Inhalt einer konkreten Klassenarbeit. Für Niedersachsen ist https://cuvo.nibis.de/ die offizielle Ausgangsquelle.

Materialien enthalten Titel, Quellenart, Fundstelle/Ausgabe/Seite, relevanten Text, optional einen Anhang und einen Prüfstatus. Ein Schulbuch-Link wird nicht automatisch ausgelesen. Die Eltern wählen explizit, welche geprüften Materialien für eine KI-Anfrage verwendet werden.

### Praktischer Materialfluss

- Ein Unterrichtseintrag kann ein Thema vorbefüllen. Lernziel und passende Tätigkeit werden ergänzt.
- Bei verbindlichem Wortschatz wird die tatsächliche Wortliste hinterlegt.
- Für Verfahren und Aufgabentypen genügen oft wenige typische Aufgaben und die Vorgaben zum Lösungsweg.
- Arbeitsblätter und Seiten können als PNG, JPEG, WebP oder PDF gespeichert werden.
- Für PDFs wird der relevante Text zusätzlich eingetragen; alternativ wird eine einzelne Seite als Bild bereitgestellt.
- Ein bildfähiges, entsprechend konfiguriertes KI-Modell kann ausgewählte Bilder direkt auswerten. Automatische lokale OCR ist nicht enthalten.
- Neue oder ersetzte Anhänge setzen den Prüfstatus zurück. Beim Ersetzen wird eine alte Textübertragung gelöscht, damit nicht versehentlich der Text einer früheren Datei weiterverwendet wird.

### Was „alle Fächer und Jahrgänge“ bedeutet

Die **Software** ist fach- und jahrgangsoffen. Sie ist keine bereits vollständig erstellte Sammlung aller deutschen Schulcurricula und Schulbücher. Konkrete Themen, Lehrkraftvorgaben und lizenzierte Materialien werden während der Nutzung aufgenommen. So bleibt der Lernraum an den wirklichen Unterricht anschlussfähig, statt vermeintlich passende Inhalte zu erfinden.

Ein neues Schuljahr wird ausdrücklich angelegt und aktiviert. Alte Daten bleiben lesbar. Ein altes Thema kann mitsamt Materialien und Übungen ins aktive Jahr kopiert werden; dort müssen Inhalte erneut geprüft und Übungen freigegeben werden. Alte Lernversuche bleiben unverändert beim ursprünglichen Thema. Dateispeicher wird vor dem Kopieren geprüft.

## Produktoberfläche

| Bereich | Aufgabe |
|---|---|
| Heute | Persönliches Ziel, Hausaufgabenreservierung, begrenzte Übungsauswahl, abgeschlossene Lernzeit und Termine |
| Themen | Fächer und Schuljahre durchsuchen; Lernziele, Quellen und Übungen verwalten |
| Unterricht | Vergangene 21 und kommende 7 Tage aus Untis; Rückmeldungen und Nachholstatus unterscheiden |
| Entwicklung | Die letzten bis zu 200 abgeschlossenen Einheiten, Zeit, Belastung und AFB-Verteilung |
| Steuern | Schuljahr, Jahrgang, Bundesland, Schulform, persönliches Ziel, Zeitgrenzen, Lerntage, KI-Freigabe und Export |

Der vorhandene Kind-Umschalter wechselt zwischen den Lernräumen. Der vorhandene Tagesplan verlinkt den Lernraum. Es wird kein zweiter Hausaufgabenbestand angelegt. Frühere Daten sind zusätzlich vollständig im JSON-Export und in der Datenbanksicherung zugänglich.

## Auswahl und Wiederholungen

Die deterministische Planung funktioniert ohne KI-Verbindung:

1. Nur veröffentlichte Übungen des aktiven Schuljahres und aktiver Themen kommen in die tägliche Auswahl. Bei geplanten Themen sind nur Vorschauen vorgesehen.
2. Anstehende Zieldaten bzw. Klausuren und ausdrücklich gesetzte Themenschwerpunkte beeinflussen die Reihenfolge.
3. Fällige Wiederholungen werden gegenüber noch nicht begonnenen Übungen bevorzugt.
4. Die Auswahl wird durch die pro Schuljahr konfigurierten Lerntage, Minuten und Anzahl an Einheiten begrenzt.
5. Das bestehende gesamte Tagesbudget begrenzt zusätzlich. Überfällige, heute und morgen fällige Hausaufgaben werden reserviert; ohne Aufwandsschätzung werden 20 Minuten angenommen. Bereits abgeschlossene Aufgaben und Lerneinheiten zählen mit.
6. Nicht verfügbare Budgetdaten pausieren Vorschläge. Kalenderfehler erscheinen als Fehlerhinweis und werden nicht als gesicherte Terminleere ausgegeben.

Die Standardabstände nach selbstständig eingeschätzter Bearbeitung ohne Hilfe sind 2, 7, 14 und 30 Tage. Mit Hilfe oder bei Unsicherheit wird am Folgetag erneut vorgeschlagen. Mehrfaches Bearbeiten am gleichen Tag darf den Abstand nicht wie mehrere verteilte Lerntage steigern. Die Regeln sind verständliche Startwerte, kein validiertes individuelles Gedächtnismodell.

Die Obergrenzen steuern die **täglichen Vorschläge**. Ein Kind kann freiwillig eine freigegebene Übung in der Themenansicht öffnen. Das ist transparent vom automatischen Tagespensum getrennt.

Klausurbezug: Der Lernraum verwendet die gemeinsame `resolve_exams`-Funktion. Ein späterer Mehrkalenderumbau an dieser Funktion kann dadurch ohne zweite Kalenderkonfiguration übernommen werden. Es werden keine selbst erfundenen Klausurtermine oder Prüfungsumfänge erzeugt.

## Technische Architektur

Bestehender Stack: Svelte 5/Vite im Frontend, FastAPI/Python im Backend, SQLite im Home-Assistant-Add-on. Keine neue Hostingplattform, kein zusätzliches Familienkonto und keine zweite externe Datenbank.

- `history.db`: ausschließlich lesender Zugriff auf Unterricht und vorhandene Konten.
- `webapp.db`: Schuljahre, Themen, Materialien, Übungen, Lernversuche und Wiederholungen; bestehende Backups/Restore enthalten diese Daten.
- `learning_schema.sql`: additive, namensraumgetrennte Migration `learning_001`, um parallele Änderungen nicht mit einer laufenden Migrationsnummer zu kollidieren.
- `learning.py`: validierte Eingaben, Methoden, Zeitbasis Europe/Berlin und Wiederholungsregeln.
- `routers/learning.py`: kontogebundene API unter `/api/accounts/{account_id}/learning`.
- `Learning.svelte`: Kinderansicht und Elternsteuerung.
- `LearningActivityEditor.svelte`: Prüfung und Freigabe eigener oder KI-generierter Aufgaben.

### Datenbeziehungen

`Kind → Schuljahr → Thema → Material / Übung → Lernversuch → Wiederholungsstand`

Der Kind-Bezug liegt am Schuljahresprofil. Alle nachgeordneten Zugriffe prüfen die gesamte Beziehung bis zum Kind. Die bestehende Konten-Reconciliation aktualisiert `learning_profiles` und `learning_ai_usage`, wenn die Untis-Integration interne Account-IDs neu vergibt. Themen und Lernversuche bleiben über ihre internen Referenzen verbunden.

Pro Kind kann genau ein Schuljahr aktiv sein. Schuljahr und Jahrgang sind getrennte Eigenschaften, damit Wiederholungen eines Jahrgangs oder Änderungen des Schulverlaufs möglich bleiben. Themen haben ausdrücklich ihren ursprünglichen Schuljahresbezug.

Lernversuche speichern einen Snapshot des Arbeitsauftrags, der Hilfen, Lösung und Kriterien. Eine spätere Bearbeitung der Übung verändert diesen Versuch nicht. Änderungen an Aufgabe, Lösung oder Kriterien setzen die aktuelle Wiederholungsplanung zurück. Abschlüsse einer veralteten Übungsfassung überschreiben keinen neuen Übungsstand.

### Rollen

- Kinder sehen ihren zugeordneten Lernraum, laden Material hoch und bearbeiten freigegebene Übungen.
- Verknüpfte Eltern mit Schreibrecht verwalten Schuljahre, Themen, Prüfstatus und Übungsfreigaben.
- Admins verwenden die bestehenden administrativen Rechte.
- Verknüpfungen mit `can_edit=0` bleiben lesend. Nicht freigegebene Konten erhalten keinen Lernraumzugriff.
- Im bestehenden Demo-Modus sind Lernraumänderungen gesperrt, weil dessen generische Rückgängig-Funktion diese neuen Datentypen noch nicht unterstützt.

Material- und Session-IDs allein gewähren keinen Zugriff auf ein anderes Kind. Lösungen werden in der Kinder-API erst nach einer gespeicherten ersten Antwort ausgeliefert. Hilfe wird serverseitig gespeichert. Doppelte Abschlüsse sind idempotent und zählen nicht erneut.

### Dateispeicher und Wiederherstellung

Anhänge werden absichtlich als BLOB in der bestehenden App-Datenbank gespeichert: dadurch bleiben bestehender Datenbankdownload, kombinierte ZIP-Sicherung und Restore vollständig. Maximal 8 MB je Datei, 100 MB Anhänge je Kind. Der Dateityp wird am Inhalt geprüft. HTML/SVG und ausführbare Uploads werden nicht akzeptiert.

Downloads sind authentifiziert, werden als Anhang und mit `nosniff` ausgeliefert. Lernraum-API-Antworten sind `private, no-store`; der Service Worker legt sie nicht im Offlinecache ab. So bleiben Lernantworten nicht versehentlich nach einem Kontowechsel im gemeinsamen PWA-Cache verfügbar. Für den Lernraum ist deshalb eine Verbindung zum Add-on erforderlich.

Der vollständige JSON-Export enthält Profile, Themen, Textmaterialien, Übungen und Lernversuche. Binäre Anhänge gehören in die Datenbanksicherung. Ein Import fremder JSON-Pakete ist noch nicht implementiert; die Wiederherstellung erfolgt über die vorhandene Datenbankfunktion.

## KI-Anbindung

Die KI ist eine optionale Autorenhilfe, keine Voraussetzung für die Verwaltung oder Wiederholungsplanung. Das Backend verwendet einen konfigurierten HTTPS-Endpunkt für Responses oder Chat Completions. Ein Gateway oder ein kompatibler Modellanbieter kann eingesetzt werden; Modellname, Endpunkt und Schlüssel sind betrieblich zu konfigurieren und mit dem jeweiligen Anbieter zu prüfen.

Add-on-Optionen:

- `learning_ai_url`: vollständiger HTTPS-Endpunkt einschließlich des erforderlichen API-Pfads und ggf. API-Version.
- `learning_ai_key`: API-Schlüssel; in der Add-on-Oberfläche als Passwortfeld, nur serverseitig verwendet.
- `learning_ai_model`: Modell- oder Deploymentname.
- `learning_ai_url_2`, `learning_ai_key_2`: zweiter Zugang für eine schrittweise Umstellung auf eine andere Ressource.
- `learning_ai_models_2`: Liste der Deployment-Namen, die über den zweiten Zugang laufen. Alles Ungenannte bleibt beim ersten.

Die Runtime übernimmt diese Werte als `LEARNING_AI_URL`, `LEARNING_AI_KEY`, `LEARNING_AI_MODEL`, `LEARNING_AI_URL_2`, `LEARNING_AI_KEY_2` und `LEARNING_AI_MODELS_2`. Der Client sendet Bearer- und `api-key`-Header für kompatible Gateways. Er folgt keinen Weiterleitungen. Zugangsdaten werden nicht in Browser, Logs oder Lernexport übernommen. Die vorhandene Sicherung der Add-on-Konfiguration kann wie üblich Betriebsgeheimnisse enthalten und muss entsprechend behandelt werden.

Zusätzlich wird KI pro Schuljahr durch Eltern aktiviert. Vor jedem Entwurf sind konkrete geprüfte Quellen auszuwählen. Übertragen werden Jahrgang, Fach, Thema, Lernziel, Lernmethode und ausgewählte Quellentexte/Bilder. Keine Namen, Fehlzeiten, privaten Rückmeldungen, bisherigen Antworten oder vollständigen Kontoprofile werden dem Prompt hinzugefügt. Persönliche Angaben, die im ausgewählten Material selbst stehen, werden nicht automatisch entfernt; das Material wird vor Auswahl geprüft.

Das Modell erhält keine Tools und kann keine App-Aktionen ausführen. Material wird als untrusted Inhalt markiert. Ausgaben werden gegen ein enges JSON-Schema validiert; Quell-IDs müssen zu den ausgewählten Materialien gehören. Das ersetzt keine fachliche Prüfung. Alle generierten Übungen bleiben Entwürfe, selbst wenn das Modell `published=true` liefert.

Technische Begrenzungen: höchstens 6 Materialien, insgesamt 40.000 Textzeichen bzw. 8 MB Bilder pro Anfrage, 2–4 vorgesehene Übungen (Schema akzeptiert 1–4 bei begrenztem Material), 60 Sekunden Zeitlimit und höchstens zwölf Entwurfsanfragen pro Kind und Tag. Ein Modellaufruf zur Zeit im Add-on. Fehler werden ohne vertrauliche Anbieterantwort angezeigt und veröffentlichen keine Teilresultate.

**Betriebsstand bei Auslieferung:** Der Adapter und seine Fehlerfälle sind implementiert und mit einem simulierten Provider getestet. Ein echter Modell-Endpunkt wurde nicht konfiguriert oder aufgerufen. Die API-Verbindung, passende Bildfähigkeit, Kosten und gewünschte Verarbeitungsregion müssen mit dem tatsächlich eingesetzten Dienst abschließend geprüft werden. Ohne Schlüssel gibt die Oberfläche einen klaren Status aus und bietet eigene Übungen an.

## Was diese Version bewusst noch nicht automatisiert

- Vollständiger Lehrplanimport mit automatisch überprüfter Zuordnung zu Schule, Jahrgang und Unterrichtsfolge.
- Zugriff auf lizenzierte Verlagssysteme ohne reguläre verfügbare Schnittstelle.
- Lokale OCR, PDF-Textextraktion, Audioaufnahme oder Aussprachebewertung.
- Automatische Benotung freier Antworten, diagnostische Aussagen oder behauptete fachliche Beherrschung.
- Ein adaptiver fachlicher Kompetenzgraph mit automatischer Erkennung von Voraussetzungen.
- Vollständig unbeaufsichtigte Veröffentlichung KI-generierter Inhalte.

Die Schnittstellen und Datenbeziehungen erlauben diese Erweiterungen gezielt. Sie sind kein Grund, die vorhandene fachübergreifende Plattform auf ein Pilotfach zu beschränken. Nach Betriebserfahrung werden Erweiterungen anhand konkreter Engpässe ausgewählt, nicht als Voraussetzung für den Start gesammelt.

## Inbetriebnahme und langfristiger Betrieb

1. Bestehendes Add-on inklusive `/data` sichern, Version 0.23.0 installieren und starten. Die Migration ergänzt Tabellen; die Untis-Archivdatenbank bleibt unverändert.
2. Je Kind den Lernraum öffnen und das aktuelle Schuljahr, den Jahrgang, Schulform/Bundesland, ein gemeinsam formuliertes Ziel sowie Zeitgrenzen festlegen.
3. Unterrichtseinträge nach Bedarf als Themen übernehmen. Keine pauschale Umwandlung aller alten Unsicherheiten in Defizite.
4. Relevante Materialien zuordnen. Eigene Übungen freigeben oder nach Einrichtung der KI zunächst Entwürfe prüfen.
5. Mit dem Kind den Ablauf einmal vormachen; danach im normalen Alltag nutzen. Die Plattform umfasst alle Fächer, die tägliche Auswahl bleibt klein.
6. Wöchentlich Belastung und Nutzen besprechen. Vor Klassenarbeiten verbindliche Stofflisten ergänzen und verschiedene Anforderungsbereiche abdecken.
7. Zum Schuljahreswechsel ein neues Profil anlegen, prüfen und aktivieren. Relevante ältere Themen ausdrücklich fortführen. Bestehende Datenbanksicherungen beibehalten.

## Qualitätsprüfung und Anschlussstellen

Automatisierte Integrationstests prüfen Kontentrennung, Schreibrechte, Lösungssperre, Hilfeverwendung, idempotente Abschlüsse, Übungssnapshots, Schuljahreswechsel, Tagesbudget, Anhänge, Wiederherstellbarkeit, Konten-Reconciliation und die KI-Grenze mit simuliertem Anbieter. Der vorhandene Frontend-Produktionsbuild wird ausgeführt. Ein echter Browserlauf gegen die laufende Familieninstanz und ein echter Modellaufruf sind gesonderte Betriebsprüfungen.

Beim Zusammenführen paralleler Arbeiten insbesondere beachten: `main.py`, `db.py`, `config.yaml`, `CHANGELOG.md` und Navigation können ebenfalls geändert worden sein. Die Kalenderlogik selbst wird vom Lernmodul nicht ersetzt. Vor Auslieferung den aktuellen Hauptbranch erneut vergleichen; kein erzwungenes Überschreiben.

## Fachliche Ausgangsquellen

- IES / What Works Clearinghouse: *Organizing Instruction and Study to Improve Student Learning* — https://ies.ed.gov/ncee/wwc/PracticeGuide/1
- Education Endowment Foundation: *Metacognition and self-regulation* — https://educationendowmentfoundation.org.uk/education-evidence/teaching-learning-toolkit/metacognition-and-self-regulation
- KMK: *Einheitliche Prüfungsanforderungen Geschichte*, Darstellung der Anforderungsbereiche S. 6–8. Abiturquelle zur Systematik, kein Bewertungsschlüssel für alle Jahrgänge — https://www.kmk.org/fileadmin/veroeffentlichungen_beschluesse/1989/1989_12_01-EPA-Geschichte.pdf
- Niedersächsisches Curriculumportal — https://cuvo.nibis.de/

Die Forschung stützt einzelne Lernprinzipien, nicht die Wirksamkeit dieser neu entwickelten App als Gesamtprogramm. Die praktische Bewertung erfolgt deshalb mit zeitversetzten eigenen Leistungen, benötigter Unterstützung und empfundener Belastung.


### Ergänzung 0.23.1: Azure Responses

Die API-Art wird anhand des Endpunktpfads erkannt. `/openai/responses?api-version=...` und `/openai/v1/responses` verwenden `input` und `instructions`; die konfigurierte URL inklusive API-Version bleibt erhalten. Text- und Bildteile werden in das Responses-Format übersetzt. Als Modellname ist in Azure der Deploymentname erforderlich.

Mit `store=false` wird keine abrufbare Responses-Konversation angelegt. Das ist keine Aussage über sämtliche sonstigen Aufbewahrungs- oder Verarbeitungsregeln des Azure-Dienstes. Der Bereitstellungstyp und die gewünschten regionalen Vorgaben sind separat zu prüfen. Die Ressourcennennung „swedencentral“ allein reicht dafür nicht aus.

Referenz: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses

### Ergänzung 0.82.0: zwei Ressourcen nebeneinander

Adresse und Schlüssel gehören zum Deployment, nicht zur App. `ai_endpoint()` in `backend/learning.py` entscheidet je Deployment-Name, welcher der beiden Zugänge ihn bedient; `ai_gateway.complete()` und die Transkription bauen Aufruf, Nutzlast und Header daraus. Weil die API-Art am Pfad erkannt wird, dürfen die beiden Zugänge unterschiedliche Formen haben, etwa Responses auf der einen und Chat Completions auf der anderen Ressource.

Ein Deployment, das in `learning_ai_models_2` steht, wird nie über den ersten Zugang aufgerufen. Ist der zweite Zugang unvollständig, endet der Aufruf mit 503 und einer Meldung, die das Deployment nennt. Der stille Rückfall wäre die gefährlichere Variante: Er würde nach einer vermeintlich abgeschlossenen Umstellung weiter Kinderdaten an die alte Ressource senden.

Die Budgetanrechnung in `ai_gateway.RATES` hängt am Deployment-Namen, nicht am Zugang. Rechnen die beiden Ressourcen unterschiedlich ab, stimmen die Sätze nach einem Umzug nicht mehr und sind anzupassen.
