## 0.47.2

- Die Packliste stand abends zweimal auf der Seite: oben in der neuen Karte für morgen und unten in „Nächster Schultag". Die untere Karte entfällt am Abend, weil ihr Inhalt dann oben steht.

## 0.47.1

- Die Übungsmessung auf der Klausurkarte zählt nur die letzten Wochen und nennt den Zeitraum. Vorher hätte eine Lerneinheit aus dem letzten Schuljahr wie frische Vorbereitung ausgesehen.

## 0.47.0

- Ab 18 Uhr zeigt „Heute" zuerst, was für morgen fehlt: offene Aufgaben und die Packliste für den nächsten Schultag. Die Packliste war abends bisher gar nicht zu sehen, sondern nur vor Schulbeginn — also dann, wenn es zum Holen zu spät ist. Vorschläge zum Vorziehen und zum Üben klappen abends zu und lassen sich weiter öffnen. Die Uhrzeit ist dieselbe wie die der Erinnerung.
- Erinnerungen laufen jetzt über die Home-Assistant-App statt über Web-Push. Ein Antippen öffnet das Schul-Cockpit. Grund: Die Bildschirmzeit sperrt eine Web-App vom Startbildschirm während einer Auszeit unabhängig von jeder Freigabeliste, und ältere Geräte bekommen die neuere Bildschirmzeit nie. Die Geräte werden in den Einstellungen ausgewählt, eine Testnachricht ist dort möglich.
- Ein Hausaufgaben-Chat bleibt offen, bis die Hausaufgabe abgehakt ist. Weder der Mentor noch „für heute fertig" beenden ihn; beides pausiert nur. Abgehakte Aufgaben wandern in ein Archiv und kommen zurück, wenn das Häkchen wieder weg ist.
- Klausurkarten zeigen Datum und Abstand immer gemeinsam, dazu eine Einordnung von „noch Zeit" bis „unmittelbar". Vorher stand bis sieben Tage nur der Abstand und danach nur das Datum.
- Unter jeder Klausur steht, was tatsächlich geübt wurde: Lerneinheiten, ohne Hilfe gezeigte Themen, geschriebene Übungsarbeiten. Die Selbsteinschätzung bleibt daneben. Ein Knopf führt direkt ins Üben für dieses Fach.

## 0.46.0

- Zum Schuljahreswechsel lassen sich die Arbeiten des alten Jahres auf einen Knopfdruck ins Archiv legen. Sie verschwinden aus „Arbeiten & Tests" und bleiben dort aufklappbar, mit Note und Lernstand. Gelöscht wird nichts, und das Archiv lässt sich jederzeit wieder einblenden.
- Der Stichtag ist der 1. August, weil dort das Schuljahr beginnt und die Sommerferien den Monatswechsel überspannen.

## 0.45.1

- Zusätzliche Termine lassen sich wieder von Hand eintragen, aber nur für Arbeiten, die der IServ-Klausurplan nicht führt — etwa einen mündlich genannten Nachschreibtermin. Steht der Termin schon im Plan, wird das Eintragen mit Verweis auf den vorhandenen Eintrag abgelehnt.
- In der Übersicht steht bei jedem Termin, woher er kommt: aus dem Klausurplan oder selbst eingetragen. In den Einstellungen steht zusätzlich das Eintragungsdatum.

## 0.45.0

- Klausurtermine lassen sich nicht mehr von Hand eintragen oder ändern. Sie kommen ausschließlich aus dem IServ-Klausurplan und werden nächtlich abgerufen; eine zweite Stelle zum Pflegen läuft nur auseinander.
- Früher von Hand angelegte Termine bleiben im Verlauf sichtbar, mit Note und Lernstand. In den Einstellungen stehen sie als Altbestand, ohne Bearbeiten.

## 0.44.5

- „Arbeiten & Tests" lädt wieder. Sobald ein Klausurtermin aus dem Kalender kam, öffnete die Seite für ihn das Bearbeiten-Formular der von Hand angelegten Termine und brach ab. Kalendertermine haben keine solche Kennung, und zwei fehlende Kennungen galten als gleich.

## 0.44.4

- Die Schulkalender gleichen sich nachts von selbst ab. Klausurtermine verschieben sich im Schuljahr; dafür soll niemand einen Knopf drücken müssen.

## 0.44.3

- „Spanischarbeit" und „Englischarbeit" werden dem Fach zugeordnet. Bisher zählte nur ein eigenes Wort, und zusammengeschriebene Titel blieben ohne Fach liegen. Kürzel bleiben exakt, damit „Ku" nicht den Kuchenverkauf beansprucht.

## 0.44.2

- Der Rückfallweg über den Browser fragte eine falsch zusammengesetzte Adresse ab und kam deshalb leer zurück. Der Klausurplan wird jetzt tatsächlich geholt.

## 0.44.1

- Der Klausurplan wird auch dann gelesen, wenn IServ die einfache Anmeldung für seine Kalender-Schnittstelle ablehnt. Dann übernimmt der Browser, und zwar für alle Zusätze in einem Durchgang.

## 0.44.0

- Die Klausurtermine kommen jetzt an. Sie stehen bei euch nicht in einem Kalender, sondern im Klausurplan — einem Zusatz des IServ-Kalenders, den CalDAV grundsätzlich nicht zeigt. Die sechs erreichbaren Kalender sind das ganze Schuljahr über leer, deshalb blieb die Klausurliste bisher leer.
- Der Klausurplan zählt ohne Nachfrage als Klausurquelle, Ferien und Feiertage sowie gestellte Aufgaben als sonstige Termine. Die Rolle lässt sich wie bei jedem Kalender ändern.
- Ein nicht lesbarer Zusatz lässt den übrigen Abgleich weiterlaufen.

## 0.43.4

- Die Elternansicht kann die Datenadressen des IServ-Kalenders direkt abfragen. Die Anfrage läuft aus der angemeldeten Seite heraus, damit die Sitzung gilt.

## 0.43.3

- Die Portalsuche meldet mit, welche Datenadressen eine Modulseite im Hintergrund abruft. Damit lässt sich die Terminquelle finden, auch wenn sie nirgends verlinkt ist.

## 0.43.2

- Die Portalsuche kann einen echten Browser verwenden. IServ liefert beim reinen Abruf nur ein Gerüst; erst die ausgeführte Seite zeigt die Module und ihre Abo-Adressen.

## 0.43.1

- Die Portalsuche besucht die Terminmodule namentlich, nicht nur was auf der Startseite verlinkt ist, und meldet je Seite, ob überhaupt eine angemeldete Ansicht kam.

## 0.43.0

- Die App meldet sich mit dem gespeicherten IServ-Zugang am Portal an und sucht dort nach Terminquellen. Hintergrund: über CalDAV sind sämtliche Kalender der Schule leer, die Klausurtermine liegen in einem anderen Modul.

## 0.42.3

- Der öffentliche Schulkalender wird mitgefunden. Er gehört keiner Gruppe des Kindes, sondern kommt als freigegebener Bereich, und blieb deshalb bisher außen vor.

## 0.42.2

- Die Elternansicht kann einen einzelnen Kalender befragen, wenn er leer bleibt: angenommene Abfrage, gelieferte Einträge, davon gelesene. Leer und abgelehnt sahen vorher gleich aus.

## 0.42.1

- Wird eine Hausaufgabenhilfe geöffnet, gewinnt der Verlauf mit dem meisten Gespräch, nicht der zuletzt angelegte. Leere Doppel, die vor 0.42.0 bei einer Unterbrechung entstanden sind, verdecken das eigentliche Gespräch damit nicht mehr.

## 0.42.0

- Hausaufgabenhilfe wird nicht mehr nach zehn Minuten oder zwölf Zügen beendet. Sie läuft, bis die Aufgabe verstanden ist; nur „Für heute fertig" schließt sie ab. Vorher brach das Gespräch mitten in einer Rechnung ab.
- Je Hausaufgabe gibt es genau einen Verlauf. Wer die Hilfe erneut öffnet, landet im bisherigen Gespräch — auch wenn es zwischendurch abgeschlossen wurde und unabhängig davon, wer es begonnen hat.
- Abgeschlossene Übungsgespräche lassen sich mit „Hier weitermachen" fortsetzen. Für sie gilt der Tagesrahmen weiterhin, für Hausaufgabenhilfe nie.
- Von Eltern begonnene Gespräche über echte Aufgaben sind jetzt Gespräche des Kindes: auf seinem Gerät sichtbar und fortsetzbar, samt Fotos und Material. Getrennt bleibt allein der Demo-Modus.
- Eltern dürfen in laufenden Kinderverläufen mitschreiben. Jede Nachricht zeigt, ob sie vom Kind oder von den Eltern stammt.
- War ein Gespräch doch nur ein Versuch, kennzeichnen Eltern es danach als Testlauf. Es verschwindet dann aus Lernstand und Kinderansicht und lässt sich ebenso wieder übernehmen. Einzeln zurückgenommene Bewertungen bleiben zurückgenommen.

## 0.41.2

- Material zu einer Hausaufgabe bekommt jetzt den Tag, an dem die Aufgabe gestellt wurde, nicht das Abgabedatum. Arbeitsblätter werden mit der Aufgabenstellung ausgegeben oder nachgereicht, nie zur Abgabe. Der Tag kommt aus der verknüpften Unterrichtsstunde, sonst aus „Gegeben am" im Aufgabentext.
- Die Kalendersuche folgt allen freigegebenen IServ-Bereichen, nicht nur dem persönlichen. Klassen- und Kursbereiche haben je einen eigenen Kalender; vorher blieb nur „Home" übrig.
- Kalendernamen zeigen die Gruppe statt „<Gruppe> Calendar", weil IServ diesen Namen bei Umbenennungen nicht nachzieht. To-do-Listen gelten nicht als Terminkalender.
- Bereits ausgewertete Materialien werden im nächtlichen Lauf mit der neuen Datumsregel nachgezogen. Von Hand korrigierte Datumsangaben bleiben unangetastet.

## 0.41.1

- Die Elternansicht kann die Struktur des IServ-Kalenderkontos abfragen, wenn der Abgleich weniger Kalender findet als erwartet. Ausgegeben werden nur Adressen, Anzeigenamen und Sammlungstypen, keine Termininhalte und keine Zugangsdaten.

## 0.41.0

- Schultermine kommen jetzt direkt aus IServ statt über abonnierte Home-Assistant-Kalender. Grund: HA verwirft die Klausur-Kalender vollständig, weil IServ dort `TZID=+02:00` statt eines Zeitzonennamens schreibt. Der eigene Leser korrigiert das und liest die Termine trotzdem.
- Die Kalender werden bei jedem Abgleich neu gesucht, nicht über eine feste Kennung. Damit überlebt die Anbindung den jährlichen Neuaufbau in IServ. Eine gesetzte Rolle wandert am Kalendernamen mit; verschwundene Kalender werden als solche gekennzeichnet.
- Je Kalender lässt sich in der Elternansicht festlegen, wofür er zählt: Klausuren und Arbeiten, Unterrichtstermine, sonstige Schultermine oder gar nicht. Klausuren dürfen auf mehrere Kalender verteilt sein; derselbe Termin aus zwei Kalendern erscheint einmal.
- Der gespeicherte Zugang heißt jetzt „IServ-Zugang" und gilt für Schulbücher und Kalender gemeinsam.

## 0.40.1

- Der Einstieg zum Ablegen heißt jetzt überall „Material hinzufügen" statt „Blatt".
- Er steht nicht mehr in der Aufgabenliste, sondern dort, wo man ohnehin hinschaut: beim Öffnen einer Aufgabe im Detail und im Mentorgespräch neben „Foto zeigen". Aus einer Hausaufgabenhilfe heraus gehört das Abgelegte automatisch zu dieser Aufgabe.

## 0.40.0

- Neue zentrale Materialablage unter „Übersichten → Materialien". Ein Foto genügt: Fach, Materialart, Datum, Themenbezug und der lesbare Text werden erkannt, niemand muss ein Formular ausfüllen. Mehrere Seiten lassen sich auf einmal aufnehmen.
- Kinder dürfen jederzeit Material einsenden. Direkt an jeder Hausaufgabe gibt es dafür „📎 Blatt"; das Abgelegte gehört dann automatisch zu dieser Aufgabe. Im Lernbereich steht derselbe Einstieg.
- Unterstützt werden Fotos und PDFs bis 12 MB. Text-PDFs aus Notiz-Apps werden ohne KI ausgelesen, gescannte Seiten werden dem bildfähigen Modell vorgelegt.
- Die Auswertung läuft sofort im Hintergrund; die Liste füllt sich von selbst. Nachts werden noch offene, fehlgeschlagene und veraltete Einträge nachgezogen, begrenzt auf 40 je Nacht.
- Eltern korrigieren Fehlerkennungen und markieren Geprüftes. Eine Korrektur bleibt bei jeder späteren Auswertung erhalten. Neu auswerten und Löschen sind ebenfalls dort.
- Hausaufgabenhilfe und Übungsklausur nutzen die Ablage: Material zur passenden Aufgabe zuerst, dann zum Thema, dann zum Fach. Für eine Übungsklausur zählt jetzt alles, dessen Datum in den gewählten Prüfungszeitraum fällt.
- Bisherige Lernmaterialien wandern unverändert in die neue Ablage, samt Themenbezug und Prüfstatus.

## 0.39.13

- Das Seitenbild wird auf die tatsächlich dargestellten Buchseiten zugeschnitten, statt das ganze Fenster samt Werkzeugleisten und Seitenleiste zu zeigen. Bei einer Doppelseite umfasst der Ausschnitt beide Seiten. Miniaturleisten bleiben außen vor. Damit bekommt der Mentor deutlich besser lesbaren Text.

## 0.39.12

- Übernimmt ein Verlagsviewer die getippte Seitenzahl nicht, verlässt der Abruf das Feld und setzt den Wert notfalls direkt. Der PSPDFKit-Leser von Cornelsen nimmt die Tasten an, bleibt aber ohne diesen Schritt auf seiner Seite stehen.

## 0.39.11

- Sprunglinks werden beim Einstieg in den Leser übergangen. Bei Cornelsen heißt der Sprunglink ganz oben ebenfalls „Zum E-Book", zeigt aber auf die Startadresse der Website und warf den Leser weg.
- Von mehreren Einstiegen gewinnt die Beschriftung mit „öffnen" oder „lesen" vor einer allgemeinen.

## 0.39.10

- Führt der Klick auf „E-Book öffnen" nicht in den Leser, wird er zurückgenommen statt den Abruf auf einer leeren Seite stranden zu lassen.
- Der Testabruf zeigt, welche Schaltfläche für den Einstieg angeklickt wurde und wohin sie geführt hat.

## 0.39.9

- Der Einstieg in den Leser klickt nur noch einmal und wählt von mehreren Treffern den kleinsten, also die eigentliche Schaltfläche statt der umgebenden Karte. Ein zweiter Klick hatte den Leser wieder verlassen.

## 0.39.8

- Der Einstieg in den Leser wird jetzt immer ausgeführt, wenn eine Schaltfläche wie „E-Book öffnen" sichtbar ist. Cornelsen hält den Leser unsichtbar im Dokument bereit, während noch die Willkommensseite zu sehen ist — der Abruf blätterte dort im verborgenen Leser und fotografierte trotzdem die Startseite.

## 0.39.7

- Fängt ein Dialog den Klick auf das Seitenfeld ab, setzt der Abruf die Seitenzahl direkt im Feld und löst die Eingabe aus. Das lässt sich von keiner Überlagerung verschlucken.
- Beschriftungen von Dialog- und Einstiegsschaltflächen werden auch gelesen, wenn sie in einem verschachtelten Element stehen. Genau daran scheiterte das Schließen des Cornelsen-Dialogs.

## 0.39.6

- Der Abruf wartet, bis der Verlagsviewer fertig geladen hat, bevor er irgendetwas anklickt. Vorher konnte er mitten im Ladevorgang zugreifen und landete bei BiBox sogar wieder auf der Anmeldeseite.
- Als Einstieg in den Leser gelten nur noch eindeutige Beschriftungen wie „Zum E-Book", „Buch öffnen" oder „Weiterlesen". Ein bloßes „Öffnen", „Lesen" oder „Starten" steht auch auf Regalkacheln und im Kontomenü und führte aus dem Buch heraus.

## 0.39.5

- BiBox liefert wieder Seiten: nach dem vollständigen Laden greift der Seitenwechsel über die Adresszeile.
- Öffnet ein Verlag zuerst eine Startseite statt des Lesers, folgt der Abruf jetzt der Schaltfläche „Zum E-Book", „Buch öffnen", „Lesen" oder „Starten".
- Dialoge ohne erkennbare Beschriftung werden mit Escape geschlossen. Wird ein Klick auf das Seitenfeld doch abgefangen, räumt der Abruf auf und versucht es einmal erneut.
- Die angezeigte Seite wird nur noch von der wirklich sichtbaren, großen Seitenfläche abgelesen. Miniaturleisten melden jede Seite des Buches und konnten so einen Sprung fälschlich bestätigen.
- Beschriftungen werden einzeln geprüft statt aneinandergehängt, sonst passt auf eine Schaltfläche mit Titel und Text keine Regel mehr.

## 0.39.4

- Der Testabruf protokolliert jeden Blätterversuch: welcher Weg probiert wurde, ob ein Bedienelement gefunden wurde, ob der Viewer die Seite bestätigt hat und welche Seite er danach anzeigt. Damit lässt sich ein fehlschlagender Verlagsviewer bestimmen, statt ihn zu erraten.
- Dialoge werden nur noch geschlossen, wenn die Schaltfläche genau „Schließen", „OK", „Verstanden" oder „Akzeptieren" heißt. Vorher konnte „ausblenden" auch eine Seitenleiste oder einen Hinweis im Buch treffen.
- Eine bloße Zahl gilt nur noch als Seitenschaltfläche, wenn sie in einer Blätterleiste steht. Ein Inhaltsverzeichniseintrag „18" führte sonst in ein ganz anderes Kapitel.
- Nach einem Seitenwechsel über die Adresszeile bekommt ein neu ladender Verlagsviewer 30 statt 12 Sekunden, bevor der Versuch als gescheitert gilt.

## 0.39.3

- Werbe- und Cookie-Dialoge der Verlage werden vor dem Blättern geschlossen. Bei BiBox lag ein solcher Dialog über der Seitennavigation und verschluckte jeden Klick.
- Das Seitenfeld wird auch dann gefunden, wenn es gar keinen Namen hat: Trägt ein Nachbar die Beschriftung „Vorherige Seite" oder „Nächste Seite", gilt das Eingabefeld derselben Bediengruppe als Seitenfeld. Cornelsen vergibt dort nur erzeugte React-Ids und verschlüsselte Klassennamen.
- Die angezeigte Seite wird zusätzlich an Beschriftungen wie `aria-label="Seite 12"` der dargestellten Seitenflächen abgelesen, sodass auch Doppelseiten sauber erkannt werden.
- Ein Seitenwechsel über die Adresszeile gilt nicht mehr als gescheitert, nur weil eine Single-Page-Anwendung ihre Ladeanzeige offen lässt.

## 0.39.2

- Das Seitenfeld des Verlagsviewers wird auch dann gefunden, wenn es weder Beschriftung noch Platzhalter hat. Id, Klasse und Name zählen jetzt als Hinweis. click & study von C.C.Buchner benennt sein Feld ausschließlich über die Id `selectPage` — genau daran scheiterte das Blättern.
- Dieselbe Erweiterung gilt für das Ablesen der angezeigten Seite, damit der Sprung auch bestätigt werden kann.

## 0.39.1

- Der Testabruf in der Elternansicht zeigt zusätzlich das ganze Viewer-Fenster mit Bedienleiste, die geöffneten Ansichten und die Bedienelemente des Verlagsviewers. Damit lässt sich bestimmen, wie ein Viewer blättert, wenn keiner der eingebauten Wege greift.
- Erfasst werden ausschließlich Angaben zur Bedienung: Tag, Rolle, Beschriftung, Titel, Platzhalter, Name, Id- und Klassenhinweis sowie Schaltflächentext auf 40 Zeichen gekürzt. Kein Fließtext aus dem Buch. Aus den Adressen werden lange undurchsichtige Zeichenfolgen entfernt, damit keine Sitzungsschlüssel auftauchen.
- Die Diagnose läuft nur im Testabruf der Elternansicht, nicht in der Hausaufgabenhilfe. An die KI geht davon nichts.

## 0.39.0

- Der Seitenabruf meldet die Stufe, an der er scheitert: Anmeldung, Medienregal, Buch öffnen, Seitennavigation oder Seite lesen. Elternansicht und Mentor bekommen dieselbe Angabe statt eines allgemeinen Anzeige-Fehlers.
- Pro Buch gibt es in den Einstellungen einen Testabruf: Seitenzahl eingeben, Ergebnis mit Stufe und Vorschaubild. Dazu steht dort der letzte Abrufversuch aus dem Chat.
- Der Seitenwechsel im Verlagsviewer läuft über vier Wege (Eingabefeld, Auswahlliste, Seitenschaltfläche, Adresszeile) und wird an der Seitenanzeige des Viewers geprüft. Die Bedienelemente werden nach jedem Wechsel neu gesucht, weil der Viewer dabei neu zeichnet.
- Ist das Buch offen, die genannte Seite aber nicht ansteuerbar, geht die sichtbare Doppelseite an den Mentor. Er nennt dann keine Seitenzahl, sondern fragt nach.
- Bildschirmfotos erfassen den Buchbereich statt des ganzen Fensters und warten, bis der Viewer fertig gezeichnet hat.
- Abgerufene Seiten werden pro Kind und Buch zwischengespeichert (30 Tage, 60 Seiten). Eine Folgenachricht im Chat startet keinen zweiten Browserlauf; ein Lauf bricht nach vier Minuten ab.
- Wird der Buchtitel im Regal nicht exakt gefunden, greift ein Titelvergleich mit Zusatz und danach der gespeicherte Öffnen-Link des Regals.
- Chromium startet direkt mit dem mitgelieferten Treiber. Der vergebliche Treiber-Download auf aarch64 entfällt.

## 0.38.2

- Buchstart sucht Originaltitel auch in Shadow-DOM und einfachen Produktkarten, nicht nur in klassischen Links und Bildern.
- Wartet auf dynamisch nachgeladene Buchkarten; gezielte Tests für Karten, Frames, exakte Titel und verzögertes Laden.
- Die vollständige Seitenauslieferung im echten Verlagsviewer bleibt separat zu verifizieren.

## 0.38.1

- Der Buchstart akzeptiert jetzt auch Verlagsviewer, die innerhalb der bestehenden Medienregal-Seite statt in einem neuen Fenster öffnen.
- Fehler beim Seitenabruf benennen ausschließlich den sicheren Navigationsschritt, damit Verlagsunterschiede ohne Zugangsdaten oder Buchinhalte diagnostizierbar sind.

## 0.38.0

- Die Hausaufgabenhilfe ordnet Seitenangaben automatisch dem Fachbuch zu, öffnet das persönliche Medienregal und navigiert im Verlagsviewer zu den genannten Seiten.
- Bis zu vier benötigte Seiten werden als zwei Doppelseiten direkt an den Mentor übergeben. Bei erfolgreichem Abruf fordert er weder Foto noch Abschrift an.
- Nur bei einem echten Viewer-Fehler bleibt das Foto als Rückfalloption erhalten.

## 0.37.1

- Automatisch erkannte Buchfächer bleiben im Dropdown sichtbar, auch wenn das Fach erst in einem späteren Halbjahr im Stundenplan auftaucht (z. B. Geschichte).

## 0.37.0

- Das persönliche Medienregal wird einschließlich eingebetteter Frames und Shadow-DOM gelesen; Cover-Titel kommen unverändert aus Bildbeschriftung, ARIA-Titel oder Buchkarte.
- Regal-Bedienelemente wie „Medium entfernen“, „Titel einblenden“ und „Medienregal aktualisieren“ werden ausgeschlossen.
- Die Elternansicht zeigt links den erkannten Originaltitel und rechts das automatisch erkannte Fach als korrigierbares Dropdown. Korrekturen bleiben bei späteren Scans erhalten.

## 0.36.6

- Buchcover im persönlichen Medienregal werden auch als interaktive Karten und CSS-Hintergrundcover erkannt; ein klassischer Link mit verschachteltem Bild ist nicht mehr erforderlich.

## 0.36.5

- Der IServ-Eduplaces-Connector wird jetzt korrekt als bereits angemeldetes Launchpad behandelt. Der irrtümliche Klick auf das öffentliche Eduplaces-Logo entfällt; die Medienregal-Kachel öffnet direkt das persönliche Bücherregal.

## 0.36.4

- Fehlgeschlagene Regal-Scans protokollieren nur die sichere Navigationsstufe statt einer unbrauchbaren allgemeinen Fehlerklasse; Zugangsdaten, Cookies und Seiteninhalte bleiben ausgeschlossen.

## 0.36.3

- Bereits gespeicherte Eduplaces-Fehlklassifizierungen werden beim Start erkannt und automatisch durch einen frischen, korrigierten Regal-Scan ersetzt.

## 0.36.2

- Der Scanner verwechselt Eduplaces-Kategorien und App-Beschreibungen nicht länger mit Schulbüchern.
- Nach der Medienregal-Kachel wird nun auch die eigentliche Öffnen-/Starten-Aktion ausgeführt; erst im authentifizierten Regal werden anklickbare Produkt-Cover erfasst.
- Ein erfolgreicher neuer Scan ersetzt die beiden zuvor falsch erkannten Navigationseinträge automatisch.

## 0.36.1

- Browsersteuerung auf Selenium und den nativen Alpine-Chromedriver umgestellt, damit der automatische Medienregal-Scan auch auf der aarch64-Home-Assistant-Hardware installierbar ist.
- Der Scan meldet den nicht erreichbaren Navigationsschritt gezielt und wartet auf dynamisch geladene Buchtitel.

## 0.36.0

- Das Add-on verwendet einen echten isolierten Chromium-Browser für IServ → Eduplaces → Bildungslogin. Damit steht derselbe technische Darstellungsweg wie in Safari auch für JavaScript-/Canvas-basierte Verlagsviewer zur Verfügung.
- Das Medienregal wird nach einer bestätigten Verbindung automatisch eingelesen und kann in der Elternansicht erneut gescannt werden.
- Erkannte Bücher erscheinen pro Kind mit automatischer Fachzuordnung; Zugangsdaten, Cookies und Buchinhalte bleiben außerhalb von Logs und API-Antworten.
- Persistenter Buchkatalog als Grundlage für den gezielten Seitenabruf in Hausaufgabenhilfe, Lernmentor und Klausurvorbereitung.

## 0.35.2

- Verbindungstest erkennt das aktuelle IServ-Anmeldeformular auch dann korrekt, wenn es ohne `action` an dieselbe URL sendet.
- Ein leeres Passwortfeld wird nicht mehr als verlorener Zugang missverstanden: Die Elternseite zeigt bei vorhandener verschlüsselter Hinterlegung ausdrücklich „Passwort sicher gespeichert“.

## 0.35.1

- Gespeicherte IServ-Zugänge lassen sich pro Kind direkt prüfen. Die App meldet verständlich, ob Anmeldung und Eduplaces-Einstieg funktionieren.
- Der Verbindungstest verwendet eine kurzlebige Serversitzung; Passwort, Cookies und Seiteninhalt werden weder zurückgegeben noch protokolliert.
- Die Elternansicht unterscheidet „gespeichert“ und erfolgreich „verbunden“.

## 0.35.0

- Eltern können den IServ-/Bildungslogin-Zugang getrennt für jedes Kind in dessen Einstellungen hinterlegen und wieder entfernen. Die Maske zeigt niemals das gespeicherte Passwort an.
- Zugangsdaten sind nur für Eltern/Admins erreichbar. Passwörter liegen verschlüsselt in der App-Datenbank; der getrennte Schlüssel erhält restriktive Dateirechte im Add-on-Datenverzeichnis.
- Sichere Portalvalidierung, schreibgeschützter API-Rückkanal und stabile Zuordnung bei einer erneuten Einrichtung des UNTIS-Kontos.
- Grundlage für die automatische Buchauswahl und das Nachladen genannter Buchseiten in Hausaufgabenhilfe, Lernmentor und Klausurvorbereitung.

## 0.34.1

- Gelöschte Lerngespräche hinterlassen keine leeren Fortschrittskarten mehr. „Was schon klappt“ setzt mindestens einen gültigen Lernnachweis voraus; bereits bestehende leere Reste werden ebenfalls nicht mehr angezeigt oder als Wiederholung eingeplant.
- Der Eltern-Löschpfad entfernt ungenutzte Themenstammsätze samt Planverknüpfungen und abgeleitetem Stand. Themen mit weiteren Gesprächen oder Nachweisen bleiben erhalten; Kostenaufzeichnungen bleiben unverändert.
- Regressionstests für bestehende leere Themen, vollständiges Löschen und Erhalt anderer Lernnachweise.

## 0.34.0

- Grafische Fächerliste mit gleichen Balkenskalen, Anteil verstandener/teilweiser/schwieriger und noch nicht eingeschätzter Themen. Sortierung nach Anteil verstandener unter eingeschätzten Themen; unbekannte Fächer neutral danach.
- Kleine Verlaufslinien aus bis zu zwölf gespeicherten Unterrichtsrückmeldungen, keine geglättete Leistungsprognose. Themen, Quellen, Übungszugänge und einzelne Rückmeldungen erst beim Antippen.
- Enthält das zuvor noch nicht veröffentlichte iPhone-Korrekturpaket 0.33.1. Service-Worker-Cache aktualisiert.
- Keine neue Gesamtnote, keine Kompetenzbewertung durch Erledigungen, keine zusätzliche KI-Anfrage. Elternintegration der Balkenliste bleibt zurückgestellt.

## 0.33.1

- Fälligkeit und Hilfe auch auf dem iPhone rechts untereinander; keine zusätzliche breite Aktionszeile.
- Kleinere sichtbare Checkboxen bei unverändert 44 px großer Bedienfläche, ruhigere Fristen und kompaktere Aufgaben-/Lernzeilen.
- Gemeinsame einfarbige Gesprächssymbole und Navigations-Chevrons statt gemischter Emoji-/Pfeilkombinationen in den zentralen Ansichten.
- Grafische Fächerübersicht mit Statusbalken, Verlauf und Drilldown als separates Folgepaket ausgearbeitet; keine neue Bewertungsformel eingeführt.

## 0.33.0

- Gemeinsame Lernkarten: ganze Zeile antippbar, feste Fachsymbole, kurze Beschriftung und einheitliches Chatzeichen. Fälligkeit und Hausaufgabenhilfe stehen in einer gemeinsamen rechten Spalte.
- Lernplan mit sichtbaren Bereichen „Für heute“ und „Schon vorziehen“; gesamter weiterer Themenkatalog frei auswählbar und nach Fach filterbar. Geplante Termine bleiben lesbar. Bewusst gewählte Übungen lassen sich auch an späteren Tagen außerhalb des automatischen Zeitvorschlags fortsetzen; Anrechnung und KI-Kostenkontrollen bleiben erhalten.
- Elterncockpit mit farbigen Bereichs- und Gesamtzuständen: erledigt, offen, überfällig oder unbekannt. Doppelte Aufgabenliste, doppelte Rückmeldungszeile und Erklärungskasten entfernt. Fachprobleme und Arbeiten führen direkt zu Details; Stundenplan bleibt sichtbar.
- Deutsche Datumsanzeige auch in Lernverläufen und Themenquellen. Weniger Erklärungstext, lesbare Fachnamen und keine abgeschnittenen Unterrichtsthemen in Stundenkarten.
- Browserprüfungen für freie Themenwahl, Statusfarben, Speichern/Fehler und responsive Darstellung; Backendprüfung der freiwilligen Fortsetzung einschließlich einmaliger Tagesanrechnung.

## 0.32.0

- Erledigte Aufgaben: zuletzt abgehakt zuerst; ältere Einträge ohne Abschlusszeit folgen nach Fälligkeit absteigend.
- Kleiner „Hilfe“-Einstieg an offenen Aufgaben statt zusätzlicher Hausaufgabenübungen. Eigenständiger Nachhilfe-Gesprächsmodus erklärt Auftrag und Grundlagen und begleitet einzelne Schritte. Keine zusätzliche Übungsaufgabe, automatische Erledigung oder Anrechnung als selbstständiger Übungsnachweis.
- Redundanter Block „Für deine Aufgaben üben“ entfernt. Freie Fachwahl und selbst gewählte Übungstests bleiben erhalten.
- Gemeinsame Fachzuordnung für Namen, Groß-/Kleinschreibung und bekannte Kürzel. Hausaufgabentitel werden nur bei eindeutiger Fachzuordnung ausgeschrieben; Freitext bleibt erhalten.
- Fächerübersicht als kompakte Fachkarten mit zusammengeführten Themen und separat einsehbaren Stundenrückmeldungen.
- Identische Themen über mehrere Tage und bereits erkannte gemeinsame Themencluster erzeugen einen Lernpunkt. Alte Verknüpfungen, einzelne Rückmeldungen und unterschiedliche Teilfähigkeiten bleiben erhalten; zeitlich neueste Rückmeldung wird berücksichtigt.
- 91 Backendtests, fünf Dashboard-Logiktests, drei Browserabläufe und Produktionsbuild erfolgreich. Hausaufgaben-Coach technisch mit simulierten KI-Antworten geprüft; keine echte Kinderleistung erzeugt.

## 0.31.0

- Elternübersicht mit kompaktem Tagescheck pro Kind: Aufgaben bis morgen, bestätigtes Fachmaterial für den nächsten Schultag und fehlende Rückmeldungen zu beendeten Stunden. Direkter Wechsel in die jeweilige Kinderansicht.
- Gemeinsame Datenbasis mit den Kinder-Checklisten; unbekannte oder nicht lesbare Daten werden nicht als erledigt dargestellt. Aktualisierung bei Rückkehr und jede Minute.
- Offene überfällige Aufgaben heißen nicht mehr „verpasst“: Ein fehlendes Häkchen beweist kein tatsächliches Versäumnis.
- Browserprüfung mit zwei Kindern, Datenfehlern und 320/390/768 Pixeln erfolgreich.

## 0.30.2

- Auch der geschützte Leseexport verwendet die korrigierte Anwesenheit. Verspätungen erzeugen so keine falschen Fehlstunden in externen Lern-Auswertungen.
- Seitenweises Lesen behält die stabilen Archiv-Cursor; originale Verspätungsmeldungen bleiben im Absenzexport erhalten.

## 0.30.1

- Explizite Untis-Meldungen „Verspätet“ zählen nicht als Fehlstunden und sperren die Stundenrückmeldung nicht. Keine Schätzung anhand einer Minutengrenze.
- Korrektur gilt auch für bereits importierte Meldungen: Tagesansicht, Fehlzeiten, Lernmentor und Erinnerungen verwenden denselben bereinigten Anwesenheitsstand. Das Quellarchiv bleibt unverändert.
- Tatsächliche Abwesenheit bleibt berücksichtigt, auch wenn zusätzlich eine Verspätung vorliegt.
- Archiv-Integration korrigiert ihre Zuordnung beim nächsten Abgleich nach ihrem separaten Update ebenfalls.

## 0.30.0

- Optionale tägliche Push-Erinnerung für offene Aufgaben bis morgen, Fachmaterial für morgen und Rückmeldungen zu beendeten Stunden. Gebündelt, nur an angemeldete Kindergeräte und ohne Versand bei erledigten Punkten.
- Eltern legen die Uhrzeit ausdrücklich fest; zunächst ausgeschaltet. Geräteanmeldung, Abmeldung und Testversand in den Einstellungen. Kein automatischer Elternalarm.
- Persistenter Schutz vor doppeltem Versand, begrenztes Zeitfenster, Fehlerstatus und Entfernung ungültiger Geräteanmeldungen. Annahme durch den Pushdienst wird nicht als bestätigter Empfang dargestellt.
- Service Worker zeigt Push-Nachrichten an und öffnet den richtigen Tagesbereich. Private API-Daten werden nicht mehr offline aus einem alten Cache geladen.
- Material- und Erinnerungsdaten folgen bei Konto-ID-Änderungen dem zugehörigen Kind.
- Neue API-, Service-Worker- und Browserprüfungen. Echte Zustellung auf dem jeweiligen Gerät muss nach Anmeldung per Testnachricht geprüft werden.

## 0.29.4

- Nächster Schultag als vollständiger Stundenplan mit Anfang/Ende, Räumen, Lehrerwechseln, Vertretungen und Ausfällen.
- Ein Material-Häkchen beim ersten stattfindenden Termin je Fach; wiederholte Stunden bleiben sichtbar. Mäppchen und Trinken entfallen. Gespeicherte Fachbestätigungen bleiben erhalten.
- Morgenübersicht verwendet denselben Material-Stundenplan ohne doppelte Stundenkarten.
- Kürzerer Hausaufgabenbereich: unnötiger Erklärungssatz entfernt, freundlicher Abschluss mit Party-Emoji bei keinen offenen Aufgaben bis morgen.
- Datenbank- und Browserprüfungen für Materialzustände, Stundenplanänderungen, Doppelstunden und Speicherung bestanden.

## 0.29.3

- Ruhigere gemeinsame Farbpalette: Petrol und Mint, blaue Schulbereiche und dezente Lavendelflächen fürs Üben, mit abgestimmtem Dunkelmodus.
- Emojis mit Text in Hauptnavigation, Lernreitern und Übersichten. Aktiver Bereich zusätzlich mit Fläche und Schriftgewicht markiert.
- Kinder-Lernbereich mit kürzerem Einstieg und kompakteren Empfehlungen. Freie Themenwahl und aktuelle Aufgaben bleiben direkt sichtbar; ausführliche Planung weiterhin in der Planansicht.
- Tastaturfokus auch für Links und Formulare, reduzierte Bewegung gemäß Geräteeinstellung.
- Produktionsbuild sowie Browserprüfungen der Tages-, Kinder-, Eltern- und Löschwege bei 320/390/768 Pixel bestanden.

## 0.29.2

- Freie Fach- und Themenwahl direkt sichtbar; Hausaufgaben führen über „Dafür üben“ in den Lernbereich. Andere Themen öffnen keine unpassende laufende Einheit mehr.
- Kinder können eigene Übungstests ohne Kalendereintrag erstellen. KI-Übungen sind als noch nicht elterngeprüft gekennzeichnet; Lösungen bleiben vor Abgabe verborgen.
- Elternentwürfe benennen ihren Freigabestatus deutlich. Vollständige Leseansicht der Aufgaben; Eingabefelder erst nach „Aufgaben bearbeiten“. Demo bleibt getrennt.
- Eltern können einzelne Mentoreinheiten nach Bestätigung entfernen. Gespräch, Antworten, Lernbelege und angerechnete Zeit werden entfernt; Lernstand und Wiederholungen werden neu berechnet. Angefallene KI-Kosten bleiben erhalten.
- Zusätzliche API- und Browserprüfungen für Kinderwege, Elternfreigabe und Löschung einschließlich Fehlerfall.

## 0.29.1

- Packcheckliste direkt im Tagesdashboard: morgens für heute, danach für den nächsten Schultag.
- Häkchen werden je Schulkonto und Schultag gespeichert und bleiben beim Neuladen erhalten.
- Allgemeine Materialien aus dem Stundenplan, Sportzeug ohne erfundene Spezialausrüstung. Raum- und Zeitänderungen setzen erledigte Punkte nicht zurück; neue Fächer ergänzen offene Punkte.
- Speicherfehler und konkurrierende Änderungen bleiben sichtbar. Keine scheinbar erfolgreiche Bestätigung bei fehlgeschlagener Speicherung.
- Zusätzliche Tests für Datenerhalt, Kontenzugriff, Stundenplanänderungen und Bedienung im Browser. Automatische Reminder folgen separat.

## 0.29.0

- Tagesdashboard mit Unterricht, offenen Rückmeldungen, heutigen und vorziehbaren Aufgaben sowie Lernvorschlägen.
- Freie Aufgabenwahl; gespeicherte Rückmeldungen wechseln in den erreichbaren Verlauf. Speicherfehler lassen offene Einträge bestehen.
- Tagesanzeige aktualisiert sich bei Wiederaufnahme und Tageswechsel; veraltete Antworten nach Kontowechsel werden verworfen.
- Allgemeine Vorschau auf den nächsten Schultag, größere Aufgaben-Häkchen und deutsche Datumsanzeigen in Fachansichten.
- Gespeicherte Packbestätigungen, automatische Reminder und optionale Belohnungen folgen separat.

## 0.28.2

- Kommentare ohne Emoji erzeugen keine Verständnisbewertung; historische Werte bleiben erhalten.
- Reine Aufsicht zählt nicht als Verständnisnachweis. Notizen allein schließen Rückmeldelücken nicht.
- Erinnerungszahlen zählen das Schulkonto einmal, unabhängig von verknüpften Benutzern. Neues oberstes Feed-Feld: `unrated_lessons_today`.
- Elternübersicht benennt Grenzen ihrer bisherigen Rückmeldeauswertung.
- Regressionen für Migration, Kontentrennung und Zählung ergänzt.

## 0.28.1

- Wochenvorschau verteilt Fächer und plant je erkanntem Themengebiet zunächst einen Unterrichtsanlass; einzelne Lernbelege bleiben getrennt.
- Nächste Unterrichtsstunde wird für jeden Vorschautag neu bestimmt.
- Erledigte Aufgaben lösen keine Meldung über offene Hausaufgaben aus; angerechnete Zeit wird als Schätzung gekennzeichnet.
- 51 automatisierte Prüfungen und Produktionsbuild erfolgreich.

## 0.28.0

- Bedarfsabhängige Tagesplanung mit „Voller Tag“, „Normal“ und „Mehr Luft“. Minuten sind Orientierung; bewusst freiwilliges zusätzliches Üben ist möglich.

- Plan, Mentor, Nachmittagsplan und Fächer-Vorbereitung verwenden einen gemeinsamen Planungsdienst mit Minutenrahmen, Sieben-Tage-Vorschau, Auswahlgründen und bewusst verschobenen Anliegen.
- Quellenverknüpfung zwischen Unterrichtsanlass und echten Mentorversuchen; identische Tagesnotizen zusammengefasst, historische Rückmeldungen erhalten.
- Bearbeitung, Hilfe und unabhängige Aufgabenbelege getrennt; Wiederholung nach 2, 7, 14, 30 und 60 Tagen bei passenden Erfolgen. Zurückgenommene Bewertungen berechnen den gültigen Stand neu.
- Gemeinsames Zeitkonto für Hausaufgaben, Mentorblöcke, gespeicherte Übungen und Übungsklausuren; Eltern- und Demo-Versuche zählen nicht für Kinder.
- Klausur-Demo mit mehrwöchigem Beispielunterricht statt einer Stunde pro Fach: Geschichte mit neun Stunden, drei Hausaufgaben und beispielhafter Fehlzeit. Herkunft ausdrücklich als erfunden gekennzeichnet.

## 0.27.1

- Unklare Buchreferenzen und organisatorische Einträge bleiben in der Stoffübersicht sichtbar, werden aber nicht automatisch als Klausurstoff ausgewählt. Nur konkret erkannte Lernbereiche sind vorausgewählt; fehlendes Material kann durch eigene Themen ergänzt werden.
- Gruppierung bewahrt diese Unterscheidung auch über mehrere Verarbeitungsschritte; vorhandene Übersichten werden dafür einmalig neu erschlossen.

## 0.27.0

- Übungsklausuren aus dem Unterrichtsverlauf vorbereiten: Fach und Zeitraum (Schuljahr, seit letzter Klausur, eigenes Datum), KI-Themengruppen zunächst vollständig ausgewählt, abwählbar und um eigene Themen ergänzbar.
- Alle lesbaren Fachstunden im Zeitraum und zugehörige Hausaufgaben werden mit Quellenzuordnung berücksichtigt, auch Fehlzeiten. Leere/gekürzte Notizen und Kalenderfehler sind ausdrücklich sichtbar. Keine stillschweigende Beschränkung auf die jüngsten zwölf Stunden bei Verwendung einer Themenübersicht.
- Themenübersichten und Teilschritte werden dauerhaft wiederverwendet; jeder Quelleneintrag muss genau einer Gruppe zugeordnet sein. Demo verwendet ausschließlich Beispieldaten.
- Druckbare Aufgabenfassung ohne Lösungen, mit Antwortplatz und Aufgabennummern. Danach pro Aufgabe Fotos einreichen oder direkt online antworten und mit KI-Punkten auswerten.
- Separater Weg zur Selbstkontrolle ohne Punkte. Geöffnete Lösungen werden vermerkt; nachfolgende Bewertungen zählen als Übung mit bekannter Lösung, nicht als selbstständiger Leistungsnachweis.

## 0.26.0

- Eltern-Umschalter im Lernmentor: echter Kinderstand und separate Demo mit erfundenen Beispielen für Klasse 6.
- Demo-Gespräche und Demo-Übungsklausuren verwenden keine echten Profile, Unterrichtsdaten, Materialien oder Kinderverläufe. Eigene Eingaben/Fotos bleiben im gespeicherten Demoverlauf; KI-Kosten zählen zum Familienbudget.
- Demo-Arbeiten sind auch nach Freigabe für Kinder unsichtbar. Tests erzeugen keine Kinder-Lernnachweise oder Wiederholungen.
- Echte Kindergespräche und bearbeitete Übungsklausuren sind für Eltern lesbar; Antworten, Fotos und Zeitstände lassen sich dabei nicht als Kind verändern.
- Frühere Eltern-Testgespräche mit Echtkontext bleiben separat zugänglich. Echte Einstellungen und Freigaben sind ausdrücklich beschriftet.
- Den bisherigen globalen Demo-Schalter als Teständerungen an Echtdaten gekennzeichnet: Er ist keine isolierte Simulation.

# 0.25.3 – Prüfbare Entwürfe und verlässliche Fachzuordnung

- Klausurentwürfe lassen sich vor Freigabe in Aufgaben, Lösungen und Punktkriterien bearbeiten. Freigegebene Fassungen bleiben unverändert.
- Halbe Punkte in Kriterienauswertungen werden unterstützt; neue Aufgaben sind auf Antworten per Text, Diktat oder Foto ausgerichtet.
- Fachnamen aus UNTIS und Aufgabenlisten werden unabhängig von Groß-/Kleinschreibung zusammengeführt.
- Verständnisrückmeldungen werden dem Modell mit ihrer ausdrücklichen Bedeutung übergeben.

# 0.25.2 – Themenverbindungen und Aufgaben im Dialog

- Erkannte Themenfelder mit Erklärbildern und Grundlagen fließen jetzt in den Mentor ein; geänderte Originaleinträge entwerten alte Zuordnungen.
- Neue Aufgaben stehen direkt bei der zugehörigen Mentornachricht, damit sie beim Scrollen auf dem iPhone sichtbar bleiben.
- Budgetanzeige nach Modellprüfungen aktualisiert; bestehende Farbvariablen der App verwendet.
- Hintergrundauswertung überspringt Einträge ohne Fachzuordnung.

# 0.25.1 – Unvollständige Unterrichtszuordnung

- Unterrichtseinträge ohne Fachzuordnung werden nicht als Fachvorschlag verwendet und blockieren die Startseite nicht mehr.
- Regressionstest mit leeren und fehlenden Fachnamen aus dem Muster der Live-Daten.

# 0.25.0 – Dauerhafter Lernmentor

- Neuer mobiler Einstieg: Unterrichtsvorschläge, kurze Dialoge, Schnellauswahlen, Fotos, Fortsetzen und Lernbelege.
- Frischer Kontext aus Unterricht, Rückmeldungen, Aufgaben, Nachholen und früheren Lernversuchen; Änderungen während einer Antwort werden erkannt.
- Hinweise, KI-Einschätzungen und spätere Aufgabenvarianten werden getrennt dokumentiert. Eltern-Testläufe zählen nicht als Kinderleistungen.
- Ein gemeinsamer KI-Zugang reserviert konservative Budgetkosten vor jedem Aufruf: 50 Euro/Monat für die Familie, Warnung ab 40 Euro, Hintergrundanteil höchstens 5 Euro.
- Alle bestehenden KI-Entwürfe verwenden dieselbe Budgetsteuerung. Unbekannte Kostensätze und unklarer Altverbrauch sperren neue Aufrufe bis zur Klärung.
- Optionale persistente Hintergrundauswertung statt KI-Aufrufen durch Seitenaufrufe.
- Übungsklausuren mit Themenabdeckung, Elternprüfung, festem Aufgabenstand, gespeicherten Antworten/Fotos, Pause und Kriterienauswertung.
- 30 feste fachliche Prüffälle zur Überprüfung des tatsächlich konfigurierten Modells.
- Spracheingabe zunächst über das Diktat der Gerätetastatur. Eigene Aufnahme/Transkription, automatische Lehrplanbeschaffung und Aussprachebewertung sind noch keine Funktionen dieser Version.

# Vorarbeit 0.24.0 – nicht separat veröffentlicht

- Optionale automatische Themenauswertung beim Öffnen des Eltern-Lernraums, seit Beginn des vergangenen Schuljahres.
- Neue/geänderte Unterrichtsinhalte inkrementell; Verständnisfeedback wird ohne zusätzliche KI-Aufrufe lokal berücksichtigt.
- Erklärungen, Eselsbrücken, Grundlagen, fachliche Ausblicke und prüfbare Kurzcheck-Entwürfe aus Allgemeinwissen.
- Belegte Unterrichtseinträge bleiben von vermuteten Verbindungen und Selbsteinschätzungen getrennt.
- Unklare Stoffangaben erzeugen konkrete Materialfragen. Leere Einträge sind keine Wissenslücken.
- Persistenter Cache, Aufrufgrenze und Anzeige der gemeldeten Tokens erfolgreicher Auswertungen.
- Die erstmalige Auswertung erfolgt schrittweise; kein Hintergrunddienst, keine automatische Lehrplan- oder Klausurstoffermittlung.

# 0.23.3 – Dauerhafter Lesezugang für Analysen

- Separate schlüsselgeschützte Lese-API mit ausdrücklicher Kind-Freigabeliste.
- Unterricht, Hausaufgaben, Rückmeldungen, Nachholen, Kursfilter, Aufgaben und Lernverläufe mit Pagination und Datumsfiltern.
- SQLite ausschließlich read-only; keine freie SQL-Ausführung und keine Ausgabe von Anmeldedaten.
- Neustartfeste Konfiguration, widerrufbar durch Leeren oder Wechseln des Schlüssels.

# 0.23.2 – Lernrahmen mit Auswahlfeldern

- Schuljahr, Jahrgang, Bundesland und Schulform als native Dropdowns.
- Entfernt die fehlerhafte Browser-Formatprüfung beim Schuljahr.
- Dynamische Schuljahresauswahl; gespeicherte Werte bleiben auswählbar.
- Kennzeichnet die bisher rein beschreibenden Angaben zu Bundesland und Schulform.

# 0.23.1 – Azure Responses API

- Erkennt Responses-Endpunkte einschließlich Azure-Preview- und v1-Pfad automatisch.
- Unterstützt Responses-Text- und Bildeingaben; speichert keine Responses-Konversation (`store=false`).
- Liest nur abgeschlossene Textantworten; abgelehnte oder unvollständige Antworten werden nicht als Übungen übernommen.
- Chat-Completions-Unterstützung bleibt erhalten. Echte Azure-Verbindung noch nicht getestet.

# 0.23.0 – Fachübergreifender Lernraum

- Dauerhafte Schuljahresprofile, beliebige Fächer/Themen, Lernziele und Elternsteuerung.
- Unterrichtseingang, Materialien (Text, Foto, Screenshot, PDF), Prüfung und Freigabe.
- Eigene Übungen und optional geprüfte KI-Entwürfe aus ausgewählten Quellen.
- Geführte Einheiten mit eigener Antwort, Hilfe, Kriterienvergleich und Selbsteinschätzung.
- Zeitbudgetabhängige Vorschläge, verteilte Wiederholung und langfristiger Verlauf.
- Schuljahreswechsel ohne Datenverlust; Themen mit erneuter Prüfung fortführen.
- Materialien sind Bestandteil vorhandener Datenbanksicherungen; JSON-Verlaufsexport.
- Kontogebundene API, keine Offline-Zwischenspeicherung der Lernantworten.
- Optionaler KI-Endpunkt in der Add-on-Konfiguration; ohne Verbindung weiter nutzbar.
- Gesamtkonzept und Betriebsgrenzen: `LERNKONZEPT.md`.

# Changelog

Alle relevanten Änderungen am Schul-Cockpit-Add-on. Neueste oben.

## 0.22.1 — Sync verschluckt keine aktuellen Hausaufgaben mehr

Zwei Fehler im HA-ToDo-Sync haben dafür gesorgt, dass aktuelle
Hausaufgaben sowohl aus der HA-ToDo-Liste als auch aus der App
verschwinden konnten:

- **Abhaken traf das falsche Item.** `todo.update_item` wurde per
  **Titel** aufgerufen — bei Untis-Aufgaben ist der Titel aber nur der
  Fachname („Mathematik"). HA nimmt beim Titel-Match das erste Item mit
  diesem Namen, also wurde beim Abhaken in der App regelmäßig eine
  ganz andere, aktuelle Aufgabe desselben Fachs in HA erledigt. Der
  nächste Sync hat das dann in die App übernommen — die Aufgabe war
  überall weg. Der Push adressiert jetzt immer die UID; der
  Titel-basierte Nachschub für verschwundene UIDs ist ersatzlos raus
  (den Fall deckt der Rebind-Pfad ab).
- **Dedup-Schlüssel war mehrdeutig.** Der Tag `[MA260901]` codiert nur
  Fach + Vergabedatum. Gibt eine Lehrkraft am selben Tag zwei Aufgaben
  im selben Fach auf, hat der Dedup aus 0.19.13 die zweite als
  Duplikat der ersten behandelt: kollabiert oder — wenn die erste schon
  abgehakt war — direkt als „erledigt" verschluckt. Der Schlüssel ist
  jetzt Tag **plus normalisierter Aufgabentext**. Fälligkeits-Edits aus
  Untis ändern ihn weiterhin nicht; nur ein geänderter Aufgabentext
  lässt die Aufgabe wieder als offen auftauchen (lieber einmal doppelt
  als eine echte Hausaufgabe verloren).
- Regressionstests für beide Fälle in `tests/test_sync_worker.py`.

Parallel dazu liefert die UNTIS-Archive-Integration ab 0.5.0 im Sensor
`hausaufgaben_offen` pro Eintrag die echte WebUntis-Hausaufgaben-ID
(`items[].id`). Wer seine ToDo-Automation darauf umstellt (ID mit in
den Notes-Tag), macht den Dedup vollständig kollisionsfrei.

## 0.22.0 — Verwaiste Kind-Verlinkungen sichtbar machen (Umschalter fehlt)
Wenn ein Kind aus dem Umschalter verschwindet, lag es bisher daran, dass
`user_account_links.account_id` auf die AUTOINCREMENT-ID der
Untis-Archiv-DB zeigt. Wird diese DB neu angelegt — Schuljahreswechsel,
Restore aus Backup, Integration neu eingerichtet — verschieben sich die
IDs und alte Links zeigen ins Leere. `/api/me` hat solche Kinder
**stillschweigend weggelassen**: bei nur einem verbleibenden Kind
rendert die App den `<select>`-Umschalter gar nicht mehr (er braucht
≥2 Accounts) und auch der Übersicht-Tab fällt weg — es sah aus als sei
der Umschalter kaputt, obwohl die Verlinkung das Problem war.

- **`/api/me` meldet `stale_account_ids`** statt betroffene Kinder
  unsichtbar zu verschlucken.
- **Warnbanner in der App**, sobald eine Verlinkung ins Leere zeigt —
  mit „Reparieren"-Knopf (nur für Admins).
- **Ein-Klick-Reparatur** (`POST /api/link-repair`): biegt den verwaisten
  Link automatisch auf den neuen Account um. Weil ein verwaister Link nur
  noch eine tote Zahl ist — welches Kind das war, steht nirgends —
  passiert das **nur bei zwingender Zuordnung**: genau ein verwaister
  Link und genau ein unverlinkter Account. Sonst führt der Knopf ins
  Setup zur manuellen Auswahl, ohne etwas zu verändern.
- **Schutzschaltung**: findet die Reparatur *keinen einzigen* Account in
  der Untis-Archiv-DB, bricht sie mit 409 ab statt aufzuräumen. Eine
  leere Tabelle heißt fast immer „DB nicht lesbar/nicht gemountet" — dort
  blind zu prunen würde alle gültigen Verlinkungen vernichten.
- **Setup zeigt verwaiste Links explizit** als entfernbare Chips
  („⚠️ Account 2 entfernen"). Vorher waren sie unsichtbar, weil die
  Knopfleiste nur existierende Accounts kennt.
- **Neuer Diagnose-Endpunkt `GET /api/link-health`** (Admin): listet
  Accounts der History-DB, alle Verlinkungen mit aufgelöst/verwaist,
  und die noch unverlinkten Accounts — nach einem ID-Shift genau die
  „neuen" Kinder, auf die umgebogen werden muss.
- **Keine Geisterkarten mehr**: `/api/dashboard` und der Kiosk
  übersprangen verwaiste IDs vorher nicht und bauten daraus eine
  namenlose leere Kind-Karte. Jetzt werden sie ausgelassen und als
  Warnung gemeldet.

## 0.21.3 — Kiosk: Zeilen als kurze Sätze, kein zerrissenes Layout mehr
- **Flex-`gap` raus** — iOS-12-Safari kennt das noch nicht und hat es
  stillschweigend verworfen, dadurch klebten Punkt + Fach + Datum
  aneinander („🔴MAMi · 5T") während die Mini-Pills rechts mit großem
  Loch dazwischen saßen. Abstände jetzt per `margin-left` auf der
  Textzeile, was Safari 12 sauber rendert.
- **Mini-Pills („1", „⚠1") raus** — die isolierten Glyphen waren
  zwischen Lernstand und Hard-Count als „1 ⚠1" für den Schnellblick
  unklar. Jede Zeile ist jetzt EIN zusammenhängender Satz:
  „🔴 MA · Mi · in 5 Tagen · 4 schwer". Lernstand-Pill ist im Kiosk
  weg — diese feinkörnige Info bleibt der App vorbehalten.
- **Mitlernen / Hausaufgaben analog**: „SN · 2 von 4 schwer" bzw.
  „🟠 Span · S.42 Nr.4-7 · Di" — lesen sich von links nach rechts wie
  Stichworte, keine Tabellen-Spalten mit Lücken.

## 0.21.2 — Kiosk: CSS-Punkte statt Emojis, linksbündig gepackt
- **Farbige Punkte / Learn-Pills als CSS** statt Unicode-Emoji-Glyphen.
  iOS 12 Safari rendert weder die Unicode-12-Farbkreise (🔴🟠🟢⚪)
  noch zuverlässig die Gesichts-Emojis (😟😐😀) — die zeigte das
  Küchen-iPad als „…"-Platzhalter und ganze Zellen wurden unlesbar.
  Punkte sind jetzt einfache CSS-Spans mit `background`, Learn-State
  ist eine kleine farbige Text-Pill („–"/„1"/„2"/„✓").
- **Linksbündig zusammengepackte Zeilen** in Klausuren / Mitlernen /
  Hausaufgaben — Flex-Rows statt Tabelle. Vorher hat `table-layout:
  fixed` die Spalten über die ganze Karten-Breite gespreizt, mit dem
  Datum ganz rechts und großen Lücken dazwischen. Jetzt sitzen Dot,
  Fach, Datum und Marker direkt nebeneinander, der Blick liest die
  Zeile als kurzen Satz von links nach rechts.
- **Fach-Kürzel hart gekürzt** (max. 4 Zeichen) — wenn Untis keinen
  Short hat und nur der volle Name vorliegt („Spanisch", „Mathematik"),
  wird in der Kiosk-Ansicht auf „Span" / „Math" gekürzt, damit die
  Spalte schmal bleibt.

## 0.21.1 — Kiosk: beide Kinder nebeneinander im iPad-Hochformat
- **Zwei feste Spalten**: das Kiosk-Dashboard rendert beide Kinder
  zwangsweise nebeneinander, auch bei 768 px Breite (iPad mini /
  Air 1 im Hochformat). Vorher haben sich die Karten unter 920 px
  übereinander gestapelt — Scrollen war Pflicht.
- **Engerer Satz**: Schriften, Zellpadding und Plan-Cell-Höhe sind
  reduziert, damit der ganze Dashboard-Inhalt eines Kindes ohne
  Scrollen in eine halbe iPad-Breite passt. Kompromisslos für den
  Küchen-Blick aus 1–2 m Entfernung optimiert.
- **Klausur-Marker im Plan-Grid nur als pinker Rahmen** (kein „KA"-
  Inline-Tag mehr) — der Rahmen ist eindeutig, das Tag hätte in den
  jetzt schmaleren Zellen überlappt.

## 0.21.0 — Kiosk-Fallback für alte iPads (iOS 12 Safari)
- **Neuer Kiosk-Modus** unter `/kiosk` als reine HTML-Variante des
  Eltern-Dashboards — kein JavaScript, nur Tabellen + Server-Render.
  Damit kann das alte Küchen-iPad mit iOS 12 das Eltern-Dashboard
  anzeigen, obwohl der moderne Svelte-Bundle dort an Optional Chaining
  & Co. scheitert. Auto-Refresh alle 5 Minuten via `<meta refresh>`.
- **Automatische Erkennung**: Wenn ein iPad/iPhone mit iOS < 13 die App
  öffnet, leitet der SPA-Catchall direkt auf `/kiosk` um — der Nutzer
  landet nicht mehr auf einer leeren weißen Seite, sondern sieht sofort
  das Dashboard.
- **Login-Form ohne JS**: `/kiosk/login` ist eine klassische
  HTML-Form-POST-Maske, die direkt an die bestehende PIN-Auth dockt.
  Cookie hält 30 Tage, also einmal anmelden → läuft monatelang.
- **Datenquelle identisch zur SPA**: das Kiosk-Render benutzt
  dasselbe `_dashboard_for_account` wie `/api/dashboard`, damit
  Klausur-Ampel, Mitlernen-Schwellen und Plan-Grid auf beiden Geräten
  exakt gleich aussehen.
- Read-only — für Eingaben (Lernstand setzen, HA abhaken) bleiben Handy
  und Desktop zuständig. Der Kiosk ist Anzeige.

## 0.20.1 — Plan-Grid auf fixe Periodenzeilen, klarere Vertretung
- **Fixe Stundenzeilen**: Das Plan-Grid auf der Übersicht alignt jetzt
  zeilenweise auf die Startzeit der Stunde. Periode 1 steht über alle
  Tage hinweg in derselben Zeile, leere Zellen entstehen wo ein Tag in
  der Periode keinen Unterricht hat. Vorher haben die Spalten unabhängig
  gepackt — wer sehen wollte, wann Mathe wiederkommt, musste mitzählen.
- **Vertretungen kompakt in einer Zelle**: Bei Fachersatz wird das
  ursprüngliche Fach durchgestrichen *und* das neue Fach in derselben
  Zelle gezeigt (z. B. `M̶u̶ MA`). Bleibt das Fach gleich und es ist nur
  Lehrer/Raum-Vertretung, erscheint ein ⇄-Symbol neben dem Fach.
- **Roter Ampel-Punkt auf Entfällen entfernt**: durchgestrichener,
  gestrichelter Rahmen ist Signal genug. Klausuren behalten ihr 📝-Eck.
- **„Heute"-Rahmen als Overlay**: liegt jetzt hinter den Zellen, damit
  die Mo–Fr-Reihen sauber alignt bleiben statt von der Padding-Box des
  alten Spalten-Wrappers verschoben zu werden.

## 0.20.0 — Eltern-Dashboard „Übersicht" für mehrere Kinder
- **Neue Startseite „Übersicht" 🏠** für Eltern-Accounts mit mindestens
  zwei verlinkten Kindern. Zeigt pro Kind nebeneinander: NOW-Streifen
  („jetzt 3. Std Mathe · bis 13:20"), anstehende Klausuren mit
  Ampel-Punkt, offene Hausaufgaben, Fächer mit Unterstützungsbedarf
  („Mitlernen 🤝") und einen 5-Tage-Plan-Grid Mo–Fr. Klick auf einen
  Block schaltet das Kind aktiv und springt in den Detail-View — die
  bisherige Switching-Mechanik bleibt unverändert.
- **Klausur-Ampel zentral**: kombiniert Tage bis zur Klausur, Lernstand
  (😟/😐/😀) und das Verständnis-Signal aus den Lesson-Checkins der
  letzten 21 Tage im jeweiligen Fach. Eine Klausur in einem Sorgenfach
  ohne Lernstart kippt früh auf 🟠/🔴, eine gut sitzende bleibt 🟢 auch
  knapp vor dem Termin.
- **Hausaufgaben-Ampel im Eltern-Stil**: heute fällig = ❗ (im Unterricht
  schon abgefragt), morgen = 🔴 (jetzt handeln), diese Woche = 🟠,
  später = 🟢.
- **Plan-Grid „rollende Schulwoche"**: feste Mo–Fr-Spalten; bereits
  vergangene Wochentage werden mit demselben Wochentag der Folgewoche
  aufgefüllt, heute bekommt einen blauen Rahmen. Am Wochenende zeigt das
  Grid komplett die kommende Woche. Klausur-Slots, Vertretungen,
  Entfälle und Sondertermine erscheinen als kleine Eck-Emojis (📝 🔁 🛑).
- **Backend-Aggregator** `GET /api/dashboard` liefert alle Blöcke für
  alle verlinkten Kinder in einem Roundtrip — kein Fanout von sechs
  Endpoints × zwei Kindern im Frontend.
- Eltern mit nur einem verlinkten Kind sehen die App wie bisher: keine
  Tab-Änderung, kein Default-Switch, das Dashboard ist nicht erreichbar.

## 0.19.14 — Hotfix Sync-500: UNIQUE-Constraint beim Untis-ID-Dedup
- **Bugfix:** 0.19.13 hat den Keeper-Eintrag auf eine UID rebinded, die
  noch in einer anderen Reihe der gleichen Gruppe lag → kollidierte mit
  `UNIQUE(account_id, ha_uid)`, der Sync brach mit 500 ab, Duplikate
  blieben stehen. Reihenfolge gefixt: erst die anderen Reihen löschen,
  dann den Keeper rebinden.

## 0.19.13 — HA-Dedup nutzt die Untis-Hausaufgaben-ID, nicht den Inhalt
- **Untis-ID als kanonischer Dedup-Schlüssel:** Der Tag `[MA260611]` &
  Co. in den Notes ist über alle Varianten derselben Aufgabe konstant —
  egal wie oft die HA-Automation neue UIDs vergibt. Sync gruppiert
  ha_todo-Reihen jetzt darüber statt über `(title, due_date, notes)`,
  was bei kleinsten Untis-Änderungen (z.B. Fälligkeit nachgeschoben)
  durchgerutscht ist.
- **Cross-Status:** der Dedup räumt jetzt auch offene Reihen weg, wenn
  für dieselbe Untis-ID schon eine erledigte Reihe existiert. Done
  schlägt offen — kein „erledigte HA poppt wieder auf" mehr.
- Beim Sync wird die Keeper-Reihe an die aktuell von HA gelieferte UID
  rebinded, damit sie beim nächsten Lauf wiedererkannt wird (statt vom
  Orphan-Pfad weggeräumt zu werden).

## 0.19.12 — Klausuren direkt auf der Klausuren-Seite bearbeiten
- Eltern/Admin sehen jetzt oben rechts auf der Klausuren-Seite einen
  „✏️ verwalten"-Link, der direkt in die volle Verwaltung (Kalender,
  Fach-Zuordnung, Termine ergänzen) führt. War vorher nur tief im Setup
  versteckt.
- **Manuelle Termine inline bearbeiten:** Pro manuellem Eintrag im
  „Ausstehend"-Block gibt es „✏️ bearbeiten" und „✕". Bearbeiten öffnet
  ein kleines Datum/Titel-Formular direkt in der Karte — typischer
  Fall: Nachschreibtermin wegen Krankheit verschoben.
- **Kalender-Termine** zeigen einen Hinweis: dort muss die Quelle (z.B.
  iServ) angefasst werden, alternativ über Verwalten dismissen und
  manuell neu anlegen. Wir können iServ-Termine nicht von uns aus
  zurückschreiben.
- Backend: neuer Endpoint `PATCH /accounts/{id}/manual-exams/{id}` für
  Datum/Fach/Titel/Notiz. Nur Eltern/Admin.

## 0.19.11 — Erledigte HA poppt nicht mehr auf, wenn HA-Automation UID wechselt
- **Bugfix:** Abgehakte Hausaufgaben tauchten wieder im aktiven Block
  auf, sobald die HA-Automation für denselben Inhalt eine neue UID
  ausgeliefert hat. Der Dedup-Pfad aus 0.19.8 hatte abgeschlossene
  Einträge bewusst stehen lassen (Historie), aber den Insert-Pfad nicht
  gegen Done-History abgeglichen — also wurden neue Aktiv-Reihen
  angelegt, obwohl die Aufgabe als erledigt bekannt war.
- Sync prüft jetzt vor jedem Insert: existiert eine ERLEDIGTE Aufgabe
  mit identischem `(Fach, Fälligkeit, Aufgabentext)`? Wenn ja → die alte
  Done-Reihe übernimmt die neue UID (rebind), kein neuer Aktiv-Eintrag.
- Toast „N alte/doppelte HA aufgeräumt" zählt diese Rebinds mit.

## 0.19.10 — Heute-Stundenplan bleibt, Morgen als gestrichelte Vorschau drunter
- 0.19.9 hat den Stundenplan nach Schulschluss zu früh auf „Morgen"
  umgeschaltet — Feedback (😀/😐/😟) für den heutigen Tag konnte man
  damit nachmittags nicht mehr geben. Korrigiert: „Heute" bleibt immer
  oben (mit allen Bewertungs-Buttons), darunter erscheint die
  „Morgen"-Vorschau zum Tasche packen.
- Vorschau-Stunden sind visuell dezent (gestrichelter Rahmen,
  transparenter Hintergrund, kein Detail-Modal, keine Rating-Spalte) —
  klar als Vorschau erkennbar, lenkt nicht vom Heute-Block ab.
- HeaderChips bleiben wie in 0.19.9: rote Klausur-Leiste verschwindet
  nach Schulschluss, Cram-Karte für die nächste nicht-sattelfeste
  Klausur erscheint prominent.

## 0.19.9 — Heute schaltet nach Schulschluss auf Morgen, Klausur sichtbar rot
- **Heute-Klausur-Leiste verschwindet jetzt zuverlässig**, sobald die
  zugeordnete Schulstunde Beginn passiert ist oder Schulschluss erreicht
  ist. Vorher stand die rote „🚨 Heute Klausur: SPANISCH"-Leiste nach
  Schulende noch stundenlang.
- **Cram-Karte auch auf Heute**: Klausur in ≤3 Tagen mit Lernstand noch
  nicht „sicher" landet als eigene rote Karte unter der Klausur-Leiste —
  spiegelt das „Muss lernen"-Layout aus dem Plan. Der entsprechende
  📝-Chip entfällt, damit nichts doppelt steht.
- **Stundenplan-Block schaltet nach Schulschluss auf den nächsten
  Schultag.** Überschrift ist jetzt groß und sprechend („Morgen ·
  Do. 12.06." statt „Stundenplan 2026-06-11"). Backend `/today` liefert
  dafür neu `next: {date, lessons}` für den nächsten Tag mit Stunden
  (Wochenende/Ferien werden bis zu 7 Tagen übersprungen).
- SW-Cache erneut gebumpt für die installierten PWAs.

## 0.19.8 — HA-Todo-Sync räumt Orphans und Duplikate auf
- **Bugfix:** Wenn die HA-Automation für dieselbe Hausaufgabe pro Lauf
  eine neue UID vergeben hat (oder wenn ein HA-Eintrag gelöscht wurde),
  blieb der Eintrag in der App-DB stehen. Dadurch konnten sich
  identische Aufgaben mehrfach ansammeln.
- Sync löscht jetzt **offene `ha_todo`-Zeilen**, deren UID nicht mehr in
  der HA-Liste auftaucht. Erledigte Einträge bleiben (sind Historie).
- Zusätzlich werden offene Einträge mit identischem `(Fach, Fälligkeit,
  Aufgabentext)` auf einen kollabiert — fängt parallel angelegte
  Duplikate ein, ohne zwei echte Mathe-HAs am gleichen Tag falsch
  zusammenzulegen (Untis-Titel ist nur das Fach, der Aufgabentext steckt
  in den Notes).
- Der „↻ Sync"-Knopf gibt eine kurze Rückmeldung, wenn Einträge bereinigt
  wurden („✓ N alte/doppelte HA aufgeräumt").

## 0.19.7 — Klausur-Endspurt: eigene MUSS-Sektion + klares Stufensystem
- **Nicht-sattelfeste Klausuren in ≤ 3 Tagen** rutschen aus „Sollte
  heute" raus und werden im Plan als eigene **„Muss lernen"**-Sektion
  oben angezeigt. Eigene rot eingefasste Karte pro Klausur, grosses
  Lernstand-Emoji rechts — geht so nicht mehr unter.
- Pensum-Banner mit klarem 5-Stufen-System statt einem nichtssagenden
  „lerntag":
  - 🟢 *Frei — Pause heute* (nichts Pflicht)
  - 🟢 *Wenig zu tun* (1–2 HAs)
  - 🟡 *Überschaubar* (3–4 HAs)
  - 🟠 *Viel — fang mit den schnellen an* (≥5 HAs)
  - 🔴 *🔥 Klausur-Endspurt — heute lernen* (sobald eine cram-Klausur
    aktiv ist; überschreibt die HA-basierte Stufe).
- Endspurt-Banner ist rot hinterlegt und groesser als die anderen.
- Service-Worker-Cache gebumpt, damit installierte PWAs sicher neu
  laden statt das alte Banner-Layout zu cachen.

## 0.19.6 — Lernstand der Klausur überall sichtbar + harter Lerntag im Plan
- **Lernstand-Emoji überall**: 😟 (viel offen) / 😐 (mittel) / 😀 (sicher)
  / ⚪ (nicht begonnen) erscheint jetzt direkt auf dem 📝-Klausur-Chip
  auf „Heute", auf der roten „Heute Klausur"-Leiste und auf jeder
  „… vorbereiten"-Karte im Plan. Vorher lag das nur auf der
  Klausuren-Seite — der wichtigste Vorbereitungs-Signal-Wert war damit
  praktisch unsichtbar.
- **„Sollte heute"-Vorbereiten-Karte für heutige Klausur ausgeblendet.**
  Vorbereiten kann man am Klausurmorgen nichts mehr; das Item war reines
  Rauschen und stand zwischen den echten To-Dos.
- **Neuer Pensum-Status „harter Lerntag — Klausur steht an"** (rot)
  überschreibt „wenig/überschaubar/viel" sobald in den nächsten zwei
  Tagen eine Klausur ansteht, deren Lernstand noch nicht „sicher" ist.
  Damit zeigt der Plan-Banner endlich die Realität: zwei Hausaufgaben +
  morgen Mathe-Klausur auf mittlerem Niveau ist kein „wenig zu tun".

## 0.19.5 — Untis-ID `[EN260612]` & Co. werden jetzt zuverlässig versteckt
- `stripUntisMetadata` hat nur Tags mit dem festen Präfix `SN`
  ausgeblendet. Englisch (`[EN…]`), Deutsch (`[DE…]`), Mathe (`[MA…]`)
  blieben sichtbar und blähten die Hausaufgaben-Zellen auf.
- Filter ist jetzt generisch: `[<1–5 Buchstaben><Ziffern>]` — passt auf
  alle Untis-Fach-Kürzel.

## 0.19.4 — Alle anstehenden Klausuren als eigene Chips
- Bisher hat der Header nur die **nächste** Klausur als 📝-Chip gezeigt.
  Wer zwei Klausuren in zwei Tagen schreibt, sah nur die erste;
  weitere anstehende Klausuren fehlten im Header.
- Jetzt bekommt jede Klausur in den nächsten 7 Tagen einen eigenen
  Chip. Das harte 4-Chip-Limit ist weg; die Reihe wickelt sich um.

## 0.19.3 — Klausur-Chip nutzt jetzt die kuratierte Klausur-Quelle
- **Bugfix:** Der neue 📝-Chip und die rote "Heute Klausur"-Leiste lasen
  Untis' eigenes `period_info_json.exam`-Feld — das ist für die
  Schüler-Rolle bekanntermaßen tot und liefert keine Klausuren. Folge:
  Kinder mit anstehenden Klausuren sahen nichts. Beide ziehen jetzt aus
  `/api/accounts/{id}/exams` (HA-Kalender + manuelle Einträge), wie die
  Klausuren-Seite selbst.
- Rote Leiste springt zur ersten heutigen Stunde des passenden Faches.

## 0.19.2 — Versionsanzeige im Frontend repariert (war immer "dev")
- `vite.config.js` las die Add-on-Version aus `../config.yaml`, im
  Docker-Build-Kontext fehlte die Datei aber — also fiel die Anzeige
  immer auf `dev` zurück. Damit war im Login/Setup nicht erkennbar,
  welche Version wirklich läuft, was Cache-Probleme schwer
  diagnostizierbar machte. Jetzt wird `config.yaml` in den
  Frontend-Build-Stage kopiert, die Versionsanzeige zeigt die echte
  Add-on-Version.

## 0.19.1 — Bugfix: PWAs der Kinder bekamen die 0.19.0-Chips nicht
- In 0.19.0 wurde nur das Frontend-Bundle neu gebaut, `sw.js` selbst
  blieb byte-identisch. Damit registriert der Browser keinen neuen
  Service Worker → kein `skipWaiting`, kein automatischer Reload, die
  installierten PWAs zeigten weiter den alten Heute-Header.
- Cache-Marker in `sw.js` gebumpt; beim nächsten Öffnen der App
  installiert sich der SW neu, leert den alten Cache und lädt die Seite
  einmalig automatisch nach.

## 0.19.0 — Heute-Header: Aktions-Chips statt Status-Banner
- Die alte „X heute · Y bald · N Klausuren"-Zeile auf „Heute" ist weg.
  Stattdessen oben eine handlungs-orientierte Kopfleiste.
- Phase „vor Unterrichtsschluss" (= solange noch eine Stunde aussteht):
  Chips zeigen ⚡ Plan-Änderungen für die noch kommenden Stunden, 🗣
  mündlich-Tipps für Fächer, die heute noch dran sind, 📚 HA bis morgen,
  und 📝 die nächste Klausur in ≤ 7 Tagen.
- Phase „nach Schluss" (auch an Wochenenden / freien Tagen): nur 📚 und
  📝 — was bis morgen vorbereitet sein muss.
- Steht heute noch eine Klausur an, gibt es eine eigene rote Leiste
  „🚨 Heute Klausur: <Fach>" über den Chips.
- Chips sind klickbar und springen direkt ans Ziel (Stundenkarte,
  Klausur-Seite, Fach-Detail oder zur „Heute zu erledigen"-Sektion).

## 0.18.0 — Check-ins gehören dem Kind, nicht der eintragenden Person
- **Bugfix:** Wenn Eltern Stunden-Feedback (😀 😐 😟) für ein Kind
  eintrugen, sah das Kind weiterhin alles unausgefüllt — und umgekehrt.
  Grund: die Check-in-Reihe war pro `(Account, Stunde, User)` eindeutig,
  also bekam jede:r eine eigene Kopie. Jetzt ist sie pro `(Account,
  Stunde)` eindeutig: alle, die Zugriff auf das Kind haben, sehen
  dasselbe Feedback und können sich gegenseitig ergänzen/korrigieren.
- Migration läuft beim ersten Start: bestehende Doppel-Reihen werden
  zusammengeführt, der **neueste** Eintrag (nach `updated_at`) gewinnt.
  `user_id` bleibt als „zuletzt bearbeitet von" für das Audit-Log.
- Gleicher Fix für „Stoff nachgeholt"-Häkchen (caught_up).
- Mündlich-Vorschläge, Plan-Frühwarnung, Nachmittags-Vorschläge und
  Notiz-Suche profitieren automatisch — sie sehen jetzt alles Feedback
  zum Kind, egal wer es eingetragen hat.

## 0.17.2 — Webclip: inline statt attachment (iOS-Installer öffnen)
- Profil wird jetzt mit `Content-Disposition: inline` ausgeliefert. iOS
  hat keinen Download-Manager — `attachment` führte zu einer leeren
  Seite. Mit `inline` erkennt Safari den MIME-Typ und übergibt das
  Profil direkt an Settings.app („Profil installieren?").

## 0.17.1 — Webclip-Download für iOS-PWA gefixt
- Webclip-Knopf nutzt jetzt direkte Navigation statt fetch+Blob —
  iOS-Standalone-PWAs ignorieren den `<a download>`-Trick still, sodass
  vorher gar nichts passierte. Direkte Navigation triggert den System-
  Profile-Installer zuverlässig.
- Service-Worker-Cache invalidiert, damit der Fix auch in installierten
  PWAs ankommt.

## 0.17.0 — iPhone-Bildschirmzeit-Hilfe + Webclip
- Neue Sektion „iPhone-Bildschirmzeit" in den Einstellungen mit
  Klick-Anleitung: App-Domain zum Kopieren für „Erlaubte Websites".
- **Webclip-Download** pro Kind (unsigniertes .mobileconfig): legt ein
  Vollbild-App-Icon mit Deep-Link auf das richtige Kind an und erscheint
  als eigener Eintrag in Bildschirmzeit → App-Limits (dort auf „Immer
  erlaubt" setzbar, ohne ganz Safari freizugeben). Nur Admin; erfordert
  gesetzte externe URL.

## 0.16.0 — Datensicherung (Backup/Restore)
- Neue Admin-Sektion „Datensicherung" in den Einstellungen.
- **Backup-Download** als ein ZIP mit **beiden** Datenbanken (App-Daten
  `webapp.db` + UNTIS-Archiv `history.db`) plus Manifest — konsistent
  per SQLite-Online-Backup (sauberer WAL-Checkpoint). Die beiden DBs
  sind voneinander abhängig und werden so zum selben Zeitpunkt gesichert.
- **Restore**: spielt aus ZIP oder .db die `webapp.db` zurück (Schema
  geprüft; alte DB wird vorher als `.bak` gesichert, die letzten 3
  bleiben erhalten). `history.db` wird bewusst NICHT überschrieben
  (Integration hält sie live offen) — Wiederherstellung über
  HA-Backup-Restore, mit Hinweis in der App.
- **Statusanzeige**: Zähler (Aufgaben/Check-ins/Klausuren/Noten), DB-
  Größe, Zeitpunkt des letzten HA-Backups; Warnung, wenn noch kein
  HA-Backup gefunden wurde. Nur für Admin.

## 0.15.1 — Stundenkarte: Marker & Check-in-Reihe
- Vertretungs-/Änderungs-/Ausfall-/Klausur-Markierung wieder als
  deutliche farbige Badges (statt blasser Mini-Emojis): ❌ Ausfall,
  ↺ Vertretung (auch bei Lehrer-/Raum-/Fachwechsel, mit „statt …"),
  🤒 versäumt, 📝 Klausur.
- Check-in-Emojis einheitlich in EINER Zeile: 👀 links als optionaler
  Slot (nur bei Vertretung), bei normalen Stunden leer freigehalten,
  dann 😀 😐 😟 — immer an derselben Position.

## 0.15.0 — Nicht belegte Kurse/Wahlfächer ausblenden
- Neue Einstellungs-Sektion **„Kurse / Wahlfächer"** (🛠 Einstellungen):
  jeder Kurs (Fach + Lehrer) mit Häufigkeit und Schalter belegt /
  nicht belegt; pro Fach ein „ganzes Fach aus/ein"-Knopf.
- Ausgeblendete Kurse verschwinden aus Heute, Woche, Fächern,
  „mündlich punkten"-Vorschlägen und der Klausur-Fach-Erkennung.
- Behebt die überzähligen Parallelkurse aus dem WebUntis-Kursband
  (z.B. mehrere Instrumental-/Gesang-Kurse, die das Kind nicht belegt).
- Wer genau einen Parallelkurs belegt, lässt den an und blendet die
  anderen aus.

## 0.14.0 — Plan & Aufgaben zusammengeführt, Note als Dropdown
- **Plan und Aufgaben sind jetzt eine Seite** (Tab „Plan"). Der separate
  „Aufgaben"-Tab entfällt → wieder 6 Tabs, Platz für „Klausur".
  Aufbau: Pensum · Heute zu erledigen · Sollte heute · Demnächst (diese
  Woche / später / ohne Datum) · „erledigte anzeigen" · + anlegen · Sync.
- **Klausur-Note als Dropdown** statt Freitext. Intern als KMK-Punkte
  0–15 gespeichert (umrechenbar). Sek I zeigt Noten mit Tendenz
  (1+ … 5− · 6), Sek II Punkte — Grundlage für späteren Notenausgleich.

## 0.13.0 — Eigene Klausuren-Seite (Lernstand + Noten)
- Neuer Tab **„Klausur"** mit zwei Blöcken:
  - **Ausstehend** (nächste zuerst): pro Klausur ein Lernstand-Wahlfeld
    (nicht begonnen / viel offen / mittel / sicher) als Selbsteinschätzung.
  - **Vergangen** (jüngste zuerst): Feld zum Eintragen der erhaltenen
    **Note**.
- Quelle wie gehabt: verknüpfter Kalender + manuelle Termine.
- Lernstand/Note werden pro Klausur gespeichert (Kind setzt Lernstand,
  Eltern/Kind die Note).

## 0.12.0 — Neuer Plan: MUSS/SOLLTE/KANN + Klausuren statt Budget
- **Budget-Knöpfe entfernt.** Der Plan zeigt stattdessen oben einen
  Pensum-Indikator (nichts/wenig/überschaubar/viel).
- **Muss heute**: überfällige + heute/morgen fällige Hausaufgaben,
  schnellste zuerst (damit Kleinkram nicht zum Berg wird).
- **Sollte heute** (max. 3, bedarfsgetrieben): Klausur-Vorbereitung
  (Frühwarnung „Klausur in X Tagen" aus den erkannten Terminen),
  versäumter Stoff nachholen, wiederkehrende Verständnislücken.
- **Anstehende Klausuren**: sichtbare Übersicht der nächsten 4 Wochen
  direkt im Plan — aus verknüpftem Kalender + manuellen Terminen.
- Damit nutzt der Plan jetzt die in 0.11 eingeführte Klausur-Erkennung.

## 0.11.1 — Changelog nachgeholt
- Diese `CHANGELOG.md` angelegt, damit HA den Verlauf im Add-on-Store
  anzeigt. Inhaltlich keine Funktionsänderung gegenüber 0.11.0.

## 0.11.0 — Klausur-Erkennung aus verknüpftem Kalender + Diagnose
- Klausurtermine kommen jetzt aus einem **pro Kind verknüpften HA-Kalender**
  (z.B. iServ-Abo), gelesen über die Supervisor-API. Grund: die WebUntis-
  Schüler-Logins geben Klausuren nicht her (live verifiziert: dedizierter
  Endpoint 403, Stundenplan nur ±9 Tage). `period_info_json.exam` bleibt
  nur als Fallback.
- Automatische **Fach-Erkennung** aus dem Termin-Text via Alias (MA/Mathe/
  Mathematik → Mathematik, WN/WuN/Werte und Normen, BI/Bio …), gespeist
  aus den echten Fächern des Kindes — nicht belegte Fächer (z.B.
  Religion) matchen dadurch automatisch nicht.
- **Übersteuerung**: Termine manuell einem Fach zuordnen oder als „nicht
  zutreffend" markieren (Turnier/Ausflug/ungenutzter Nachschreibtermin);
  konfigurierbare Ausschluss-Wörter.
- **Mündlich abgesprochene** Prüfungstermine manuell ergänzbar.
- Neue **Diagnose-Ansicht** „Klausuren verwalten" (Setup-Bereich): zeigt
  alle Kalender-Termine mit Erkennungs-Status zum Prüfen/Kuratieren.
- Die Plan-Steuerung (Anzeige & Frühwarnung) folgt in v0.12.0 auf dieser
  jetzt verlässlichen Klausur-Basis.

## 0.10.0 — Tagesbudget folgt dem Nds. Hausaufgaben-Erlass
- Tagesbudget je Kind kommt aus dem [RdErl. d. MK v. 12.09.2019]
  (Primar 30, Sek I 60, Sek II 120 min werktags; Wochenende 0;
  Nachmittagsunterricht ×0,75).
- Klassenstufe wird aus den UNTIS-Stammdaten erkannt (z.B. „5a" → Sek I,
  „EF/Q1" → Sek II), bei exotischer Klassenbezeichnung manuell setzbar.
- Setting „An Erlass orientieren" als Toggle; manueller Override in
  beide Richtungen weiterhin möglich.

## 0.9.0 — Notify-API für HA-Automationen (Hermes/WhatsApp)
- Pro Kind ein Notify-Token (Setup → Benachrichtigungen).
- `GET /api/notify/<id>/summary?token=…` liefert kompakte Zahlen
  (Tasks, Fehlstunden, nächste Klausur) + Deep-Links + fertige
  deutsche Nachrichten-Templates.
- Add-on-Option `external_url` für vollständige URLs in den Templates.
- Deep-Link-Support `?acc=<id>` setzt den aktiven Account beim Aufruf.

## 0.8.x — Stabilisierung & UX
- 0.8.8: Fehlstunden im Wochenraster visualisiert (🤒 / ✓ pro Stunde,
  ganztägige Abwesenheit am Tag-Header).
- 0.8.7: Vorbereitung-Vorschläge schauen nach vorne (nächste Stunde des
  Fachs), nicht zurück auf heute.
- 0.8.6: Klick auf abgelaufene Stunde im Wochenplan öffnet das
  Check-in-Sheet (gleiche Komponente wie Heute).
- 0.8.5: Erledigte Lernzeit zählt gegen das Tagesbudget; Tagesbudget-
  Schnellwahl im Plan nur für Eltern/Admin.
- 0.8.4: Bug-Fix — abgehakte Hausaufgaben springen nicht mehr zurück
  (Konfliktauflösung beim HA-ToDo-Sync neu, App-Done gewinnt immer).
- 0.8.3: Add-on-Panel auch für Nicht-Admin-HA-User sichtbar
  (`panel_admin: false`).
- 0.8.2: Sticky-Bottom-Nav-Fix für Safari-Tab-Modus.
- 0.8.1: Hausaufgaben-Checkbox war im Safari-Tab unzuverlässig
  (verschachteltes `<button>` aufgelöst), Optimistic-UI + sichtbare
  Fehlermeldung statt stillem Stehenbleiben.
- 0.8.0: „Fehlt"-Seite (🤒 Cluster-Übersicht der Abwesenheiten mit
  Wochenend-Brückenlogik) + freie Lernzeit + +-Übernehmen-Vorschläge
  im Plan.

## 0.7.x — Plan-Detail & Layout-Politur
- 0.7.0: Hausaufgaben-Inhalt im Plan sichtbar; HA-todo-Metadaten
  (Gegeben/Fällig/SN) aus der Anzeige gestrippt; Frist als natürliche
  Sprache („morgen fällig", „4 Tage überfällig").
- Diverse Safari-/PWA-Layoutfixe (Bottom-Nav, Status-Bar-Überlagerung,
  Rubber-Band).

## 0.6.x — PWA-Updates, Cache, Versionsanzeige
- 0.6.3: Timezone-Fix („morgen" wurde fälschlich als „heute" gewertet).
- 0.6.2: Service-Worker macht Hands-off-Updates (skipWaiting +
  controllerchange-Reload) — neues PWA-Update kommt automatisch beim
  nächsten Öffnen an.
- 0.6.1: Cloudflare-/Browser-Caching von `sw.js` / `index.html`
  deaktiviert (no-cache-Header). Versionsnummer ist im Bundle einge-
  backen und im Login/Setup sichtbar.
- 0.6.0: Bottom-Nav klebt wieder am Rand (alle Sticky/Flex-Versuche
  zurückgedreht), HA-Beschreibung im Plan sichtbar.

## 0.5.x — PIN-Login + Direct-URL (PWA-Installation)
- 0.5.9: Hausaufgaben mit Fälligkeit „morgen" zählen jetzt als „heute
  zu erledigen".
- 0.5.x: PIN-Login pro Kind, eigene Direct-URL, 1-Jahres-Sliding-
  Session, PWA-Installierbarkeit, ID-Stabilität gegen Re-Setup.

## 0.4.x / 0.3.x / 0.2.x / 0.1.x
- Erste Version: Add-on-Skelett, Ingress-Auth, Untis-Datenanbindung
  (read-only `history.db`), Today/Plan/Aufgaben/Woche/Fächer, HA-ToDo-
  Sync bidirektional, Demo-Modus, Audit-Log, Service-Worker, App-Shell.
