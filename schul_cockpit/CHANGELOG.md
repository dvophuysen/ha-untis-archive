## 0.86.0

- Der Bestand einer Abfrage wird jetzt von der App geführt, nicht mehr vom Mentor in einem Fließtext. Bisher schrumpfte der Merkzettel über ein langes Gespräch zusammen: Nach 36 Zügen mit unregelmäßigen Verben stand dort ein einziger Satz, und die Fehler der ersten Runde waren am Ende vergessen. Der Mentor meldet nur noch, was sich in dieser Runde geändert hat; die App führt die Liste, gibt sie jede Runde zurück und weiß, was offen ist. Ein Fehler gilt erst als erledigt, wenn das Kind die Reihe selbst richtig gesagt hat.
- Unter dem Gespräch steht, was noch zu wiederholen ist. Das Kind musste bisher danach fragen, und die Antwort war unvollständig.
- Buchseiten gehen nicht mehr bei jedem Zug mit. Sobald der Bestand einer Abfrage steht, fragt der Mentor aus der Liste ab statt vom Bild. Im Verben-Gespräch wanderten 36 Züge lang Seitenbilder mit, obwohl ab dem dritten Zug alles Nötige bekannt war; das war der größte Einzelposten bei den Kindergesprächen.

## 0.85.0

- Materialien werden in zwei Durchgängen gelesen. Die günstige Modellstufe liest jede Seite zuerst und ordnet sie ein; nur Seiten, bei denen die Eichung einen Qualitätsverlust gezeigt hat, werden gründlich neu gelesen und nur diese Lesung gespeichert. Gründlich gelesen werden Handschrift, eigene Bearbeitungen, Arbeitshefte und Arbeitsblätter, alles aus Mathematik und den Naturwissenschaften sowie alles Unlesbare. Wertetabellen und Formelseiten zusätzlich mit tiefer Prüfung, weil dort sonst Werte fehlen — das galt auch für die hohe Stufe.
- Grundlage ist eine Messung an zehn echten Seiten: Gedruckter Buchtext kam auf der günstigen Stufe Zeichen für Zeichen gleich heraus, Handschrift verlor Zahlen (Trefferquote 1,00 gegen 0,82), Arbeitsheftseiten verloren Zeilen, und eine Seite mit Wertetabellen war erst mit tiefer Prüfung vollständig. Schaltpläne aus der Physik gaben alle Stufen richtig wieder.
- Die nächtliche Nacharbeit erkennt beide Lesestufen als erledigt an. Sonst hätte sie jede günstig gelesene Seite jede Nacht erneut gelesen.

## 0.84.0

- Die KI-Rahmen sperren nicht mehr. Monat, Tag je Kind, Quellenbestand, Hintergrund und der Deckel je Gespräch sind jetzt Richtwerte: Wird einer überschritten, läuft der Aufruf trotzdem und die Überschreitung wird vermerkt. Ein Kind soll nicht mitten in einer Abfrage stehenbleiben, weil eine Zahl erreicht ist.
- Hochrechnung statt Restanzeige: Die Elternansicht zeigt den bisherigen Verbrauch, den Schnitt der letzten Tage und wo der Monat landet, wenn es so weitergeht. Gewarnt wird, sobald die Hochrechnung den eingestellten Richtwert übersteigt, nicht erst beim Erreichen. Die Hochrechnung glättet über sieben Tage, damit ein einmaliges Einlesen eines Buchbestands nicht den ganzen Monat hochrechnet.
- Fehlgeschlagene Aufrufe binden kein Budget mehr: Hat der Anbieter die Anfrage nie angenommen (falsche Adresse, falscher Schlüssel, Drosselung), wird die Reservierung aufgelöst. Ein falsch eingetragener Endpunkt hatte so an einem Vormittag 0,80 € gebunden, ohne dass ein Token geflossen wäre. Zeitüberschreitungen und Serverfehler bleiben gebucht, dort kann das Modell gelaufen sein.
- Abgestürzte Aufrufe, die nach einer Stunde weder abgerechnet noch gescheitert sind, geben ihre Reservierung frei.

## 0.83.2

- Fehler behoben: Unter „Materialien" führte „Kapitel prüfen" im Block „Bitte gegenlesen" auf eine leere Seite mit „Unbekannte Seite". Der Link zeigte auf einen Anker derselben Seite, und den hat die Seitensteuerung als Namen einer eigenen Seite gelesen. Jetzt springt der Knopf zum passenden Buch weiter unten und klappt dessen Kapitelliste gleich auf.

## 0.83.1

- Fehler behoben: Mit 0.83.0 antwortete die Mentor-Übersicht mit einer Fehlermeldung, solange noch keine Foundry eingetragen war. Die Übersicht fragt dort nur, ob ein Mikrofon angeboten werden kann; diese Frage darf nicht scheitern. Jetzt bleibt die App ohne KI-Zugang bedienbar, und erst eine wirkliche Aufnahme oder Anfrage meldet, dass die Plattform fehlt.

## 0.83.0

- KI-Einrichtung an einer Stelle: Die Add-on-Konfiguration hat jetzt einen Block **KI-Plattformen** mit zwei Azure-Foundry-Ressourcen (Endpunkt und API-Schlüssel) und darunter **KI-Modelle** mit vier Stufen — Hoch, Mittel, Niedrig, Transkription. Je Stufe stehen Modellname, ein abweichender Bereitstellungsname, die Foundry zur Auswahl und wahlweise eigene Kostensätze. Damit zieht ein Modell einzeln auf die zweite Ressource um, ohne dass an der übrigen Einrichtung etwas zu ändern wäre. Die alten Einstellungen `learning_ai_*` entfallen; Endpunkt und Schlüssel sind einmal neu einzutragen.
- Die App wählt Stufen statt Modellnamen: Unter den Budgetgrenzen steht jetzt „Stufe für den Einstieg" und „Stufe fürs Abschreiben" mit Hoch, Mittel und Niedrig zur Wahl. Ein Modellwechsel in der Konfiguration lässt diese Wahl unberührt. Bestehende Einstellungen werden einmalig übersetzt.
- Der Bereitstellungsname geht in den Aufruf, der Modellname in Abrechnung, Log und die Kennungen gespeicherter Ergebnisse. Heißt ein Deployment in der neuen Ressource anders, bleiben Preise, Eichungsläufe und Zwischenstände trotzdem gültig.
- Kostensätze je Stufe sind eintragbar. Ohne Eintrag gilt die hinterlegte Tabelle; für ein Modell, für das weder das eine noch das andere vorliegt, wird kein Aufruf gemacht, statt ungemessen Geld auszugeben. Der hinterlegte Satz für gpt-5.6-luna war deutlich zu hoch angesetzt (1,90/9,00 € statt 0,40/1,80 €) und ist berichtigt; das Modell war bisher nicht im Einsatz, an der bisherigen Abrechnung ändert sich dadurch nichts.
- Zeigt eine Stufe auf eine Foundry ohne Endpunkt oder Schlüssel, bricht ihr Aufruf mit einer Meldung ab, statt auf die andere Ressource auszuweichen. Beim Start steht im Add-on-Log, welche Stufe welches Modell über welchen Host fährt.

## 0.82.1

- Fehler behoben: 0.82.0 ließ sich nicht starten. Die neue Option `learning_ai_models_2` war als `list(str)?` beschrieben, was in Home Assistant eine Auswahl aus festen Werten ist und nicht eine Liste; der Supervisor lehnte daraufhin sämtliche Optionen ab („value must be one of ['str']"). Jetzt steht dort ein Listenschema. Ein Test prüft künftig, dass jede Option mit Listen-Vorgabe auch ein Listenschema hat.

## 0.82.0

- Zwei Foundry-Zugänge nebeneinander (D87): Für eine schrittweise Umstellung nehmen die neuen Add-on-Optionen `learning_ai_url_2` und `learning_ai_key_2` eine zweite Ressource auf. `learning_ai_models_2` listet die Deployment-Namen, die schon dort liegen; alle übrigen bleiben beim ersten Zugang. Umgezogen wird also je Modell, ohne die restliche Einrichtung anzufassen. Ein gelistetes Deployment läuft ausschließlich über den zweiten Zugang: Fehlt dort Adresse oder Schlüssel, bricht der Aufruf mit einer Meldung ab, statt still wieder die alte Ressource zu verwenden. Die Spracheingabe folgt dem Zugang ihres eigenen Deployments. Welches Modell über welchen Host läuft, steht beim Start im Add-on-Log; in der App ändert sich nichts.

## 0.81.0

- Arbeitsblätter mit Bezug (D85): Ein Blatt wird nie mehr geraten. Bisher belegte ein loses Foto desselben Fachs innerhalb von fünf Tagen jede Hausaufgabe mit „Arbeitsblatt“; jetzt belegt nur ein ausdrücklicher Bezug, den Kind oder Eltern mit einem Tipp setzen. Ein loses Blatt zeigt in der Materialliste Vorschläge („Gehört das Blatt zu … Hausaufgabe 16.09.: Arbeitsblatt beenden“), ein Tipp ordnet zu. In „Was mir noch fehlt“ steht jedes Blatt je Eintrag, mit „Vorhandenes Blatt zuordnen“ für schon fotografierte Blätter; ein Foto von dort hängt am Eintrag, nicht am Fach. Ein ausgefülltes Blatt ist Blatt und Bearbeitung zugleich. Verknüpfungen tragen eine Rolle (Blatt, Bearbeitung, Stoff).
- Doppelseiten von Hand: Im Korrekturformular heißt das Feld „Gedruckte Seite(n)“ und nimmt „10-11“ an; beide Seiten gelten dann als vorhanden. Bisher ließ sich nur eine Seite eintragen.
- Begriffe: „Mitschrift“ und „Aufgabenbearbeitung“, egal ob die Aufgabe im Unterricht oder zu Hause bearbeitet wurde. Die Auswertung unterscheidet mitgeschriebenen Stoff von der eigenen Bearbeitung einer Aufgabe.

## 0.80.1

- Materialart „Erledigte Hausaufgabe (eigene Bearbeitung)“: Die Art gab es schon (intern own_work), hieß aber „Meine Bearbeitung“ und war so nicht zu finden; „Mitschrift“ heißt jetzt „Mitschrift aus dem Unterricht“. Die Auswertung bekommt den Auftrag der Hausaufgabe als Hinweis und ordnet eine handschriftliche Seite, die an eine Hausaufgabe gehängt wurde, als erledigte Hausaufgabe ein, nicht als Mitschrift, außer sie ist erkennbar ein Blatt der Lehrkraft. Anlass: eine Recherche-Ausarbeitung wurde als Mitschrift abgelegt.

## 0.80.0

- Fehler behoben: Ein Foto, das an eine Hausaufgabe gehängt wurde, galt als Arbeitsblatt für jede Hausaufgabe desselben Fachs in den Nachbartagen. So bekam die neueste Geschichte-Hausaufgabe „Arbeitsblatt beenden“ ein „Blatt liegt vor“, obwohl nur die Ausarbeitung des Kindes zu einer alten Aufgabe fotografiert worden war. Jetzt gilt: Ein angehängtes Foto gehört zu seiner Aufgabe und zu keiner anderen, und es belegt auch die eigene Hausaufgabe nur, wenn die Auswertung ein Blatt gesehen hat (Arbeitsblatt oder Handout), nicht bei Mitschrift, Ausarbeitung oder Unbestimmtem. Lose Fotos ohne Aufgabe zählen weiter nur, wenn sie ein Blatt sind.
- Mentor beim Abfragen: Will das Kind abgefragt werden oder heißt die Hausaufgabe lernen, fängt der Mentor sofort im gewünschten Format an, nennt bei Fehlern die ganze Reihe mit Merksatz, lässt sie wiederholen, fragt jedes falsche Item nach drei bis fünf weiteren noch einmal und am Ende alle gesammelt. Er führt dafür einen Merkzettel über das ganze Gespräch (Bestand, Reihenfolge, Fehler, nächstes Item), weil er nur die letzten Nachrichten sieht; und er nimmt den Bestand der Items nur von der Buchseite oder dem Foto, statt eine Liste zu erfinden. Anlass: Abfrage unregelmäßiger Verben, bei der am Ende die Fehler vergessen waren.

## 0.79.0

- Gespräche gelten als Gespräche des Kindes. Kinder lernen auch auf den Geräten der Eltern; bisher stand dann „Eltern“ als Sprecher im Verlauf. Jetzt gilt jedes Gespräch als Gespräch des Kindes, egal wer angemeldet ist. Nur der bewusst eingeschaltete Demo-Modus ist eine Simulation. Bestehende Verläufe werden einmalig umgestellt; „War nur ein Test“ bleibt als nachträgliche Kennzeichnung.
- Verläufe wiederfinden: In der Liste steht bei Hausaufgaben der Wortlaut der Aufgabe („Irregular verbs p. 206 …“) statt „Hilfe: Englisch“, dazu die Art des Gesprächs (Hilfe zur Hausaufgabe, Lösung geprüft, Thema der Arbeit, Üben), der Stand (offen, beendet, Hausaufgabe abgehakt), Datum und Uhrzeit des letzten Dialogs und die Zahl der Nachrichten. Abgehakte Hausaufgaben stehen nicht mehr eingeklappt darunter, sondern in derselben Liste, sortiert nach dem letzten Dialog. Über dem Gespräch steht ebenfalls der Wortlaut und der letzte Dialog.

## 0.78.0

- Lösung prüfen lassen: An jeder offenen Hausaufgabe steht neben „Hilfe im Chat“ jetzt „Lösung prüfen lassen“. Das Kind zeigt ein Foto seiner fertigen Lösung, der Mentor geht sie Aufgabe für Aufgabe durch und sagt zu jeder: richtig, fast oder falsch, bei fast und falsch mit dem Grund und einem Hinweis, wo noch einmal hinzuschauen ist. Die richtige Lösung sagt er nicht vor, auch nicht auf Nachfrage als Ergebnis; erklärt wird nur, wenn das Kind fragt. Die Kontrolle ist ein eigener Verlauf neben dem Hilfegespräch, hat keine Uhr, zählt nicht auf den Tagesplan und erzeugt keine Einschätzung im Lernstand. Die Buchseiten der Aufgabe liegen dem Mentor dabei immer vor. Am Ende schlägt er das Ende vor, mit einem Satz, was zu wiederholen wäre; das Kind entscheidet („Für heute fertig“ oder „Noch eine Seite zeigen“).
- Gegenlesen: Der Vorschlag der Plausibilitätsprüfung lässt sich mit einem Tipp übernehmen („So korrigieren: Textband S. 10, 11“). Eine Seitenangabe wird dabei als Ganzes berichtigt, weil aus „S. 70, 71“ nach der ersten Berichtigung „S. 10, 71“ keine Aufzählung mehr wäre. Die Übernahme gilt als Korrektur der Eltern, die keine Lesung mehr überschreibt; danach binden sich die Stellen neu und holen das Material. Lektions- und Aufgabennummern bleiben unangetastet.

## 0.77.0

- Gegenlesen mit Kontext: Bei einer Themenliste oder einer handschriftlichen Seite hält die App jede genannte Stelle gegen die Stellen, die Unterricht und Hausaufgaben desselben Fachs in diesem Schuljahr nennen. Eine Seite, die nirgends vorkommt, steht rot in der Gegenlese-Karte, und wenn eine Ziffernverwechslung (1/7, 0/6, 4/9) auf eine bekannte Stelle führt, steht der Vorschlag dabei: „Textband S. 70 kommt im Unterricht nicht vor · gemeint S. 10?“ Stimmen alle Stellen, steht auch das da. Entschieden wird weiter von Hand.

## 0.76.0

- Handschrift geht immer zum Gegenlesen. Jede Lesung sagt jetzt, welche Seitenart sie gesehen hat (Text, Tabelle, Handschrift, Zeichnung, Formeln, gemischt) und ob handschriftliche Einträge dabei waren; solche Materialien stehen auf der Materialseite zur Bestätigung, egal wie sicher sich das Modell fühlt. Anlass: Auf einem handschriftlichen Zettel wurde bei der Eichung aus jeder 1 eine 7.
- Das Messwerkzeug der Eichung vergleicht neben Wörtern auch Zahlen und ganze Zeilen und liefert die volle Lesung statt eines Ausschnitts. Fehler wie „= 4“ statt „= 0“ auf einem Mathe-Arbeitsblatt waren vorher unsichtbar, weil die Ziffern anderswo auf der Seite vorkamen.
- Die Reasoning-Tiefe lässt sich für die Eichung je Aufruf wählen (low, medium, high). Im Betrieb bleibt sie unverändert.

## 0.75.1

- Eine Korrektur der Eltern sperrte auch leere Textfelder: Das Formular schickte alle Felder mit, und ein noch ungelesenes Material bekam einen leeren, gesperrten Text, den keine Lesung mehr füllen durfte. So stand die Latein-Doppelseite 10/11 seit dem 15.09. als „gelesen“ ohne ein Wort Text da. Leere Textfelder gelten jetzt nicht als Korrektur, das Formular schickt nur Geändertes, und betroffene Materialien werden einmal neu gelesen.

## 0.75.0

- Der Mentor bricht keine Einheit mehr ab. Erreicht eine Übungseinheit ihre Zeit- oder Zuggrenze, fragt die App ohne KI-Aufruf: „Willst du für heute aufhören oder noch weitermachen?“ Beides ist eine Antwort zum Antippen; nach „Noch weitermachen“ geht es normal weiter, und die Frage kommt frühestens sechs Züge später wieder. Nur „Für heute fertig“ beendet.
- Auch der Abschluss durch den Mentor ist jetzt ein Vorschlag: Er sagt, was gezeigt wurde (bei Themen der Themenliste mit Stufe und Termin der Kurzprüfung, bei Nachholen mit dem Satz zur Stunde) und fragt, ob das Kind aufhören oder noch eine Aufgabe will. Die Einheit bleibt offen, bis das Kind entscheidet.
- Verstehen als Einstieg: Nach „nicht“ oder „teils verstanden“ an einer Stunde steht dort „Mit dem Mentor verstehen“. Der Mentor ordnet das Thema ein, fasst den Stoff aus dem Material zusammen und fragt, was unklar ist; eine Erklärung vor der ersten Aufgabe zählt nicht als Hilfe.

## 0.74.1

- Fachansicht: Die Unterrichtsthemen unter einem Fach stehen jetzt mit der neuesten Stunde zuerst. Vorher galt die Reihenfolge des Lernplans (nach thematischem Feld, darin Aufbaufolge, Themen ohne Feld zuletzt); ohne sichtbares Feld wirkte das zufällig. Der Plan selbst sortiert unverändert.

## 0.74.0

- Wochenrückblick für Eltern: In der Elternübersicht steht je Kind „Diese Woche“ mit wenigen Sätzen aus gespeicherten Zahlen: an wie vielen Abenden vor einem Schultag vor der Erinnerung alles erledigt war (mit Vorwoche), welche Themen eine Stufe weiter oder zurück sind, bestandene Kurzprüfungen, Einheiten mit dem Mentor und ihre Dauer, Vokabelabfragen, erledigte und überfällige Aufgaben, die Antworten nach der Schule, fehlendes Material für Arbeiten in den nächsten zwei Wochen und die KI-Kosten der Woche. Kein Modellaufruf, keine Note, kein Vergleich zwischen Kindern. Zuerst drei Zeilen, aufklappbar alle.
- Dieselben Zahlen liefert `GET /api/accounts/{id}/week-review` für Kind und Eltern.

## 0.73.0

- Fächerübersicht auf dem Lernstand: Der Balken je Fach zeigt jetzt die Stufen der Themen dieses Schuljahrs (gefestigt, sitzt, wackelt, angefangen, neu), so wie die App sie aus den Antworten abliest, nicht mehr die Anteile der Selbsteinschätzungen. Darunter steht, was es heißt („2 von 5 sitzen · 1 wackelt“). Rechts stehen die Stufenwechsel der letzten vier Wochen („↑ 2 Themen besser“); ohne Wechsel steht das so da, ein Verlauf wird nicht erfunden.
- Fächer mit gemessenem Stand stehen oben, sortiert nach Anteil sicherer Themen, dann Fächer mit bloßer Selbsteinschätzung (Balken wie bisher, jetzt so beschriftet), zuletzt Fächer ohne beides. Kein Fach fällt weg.
- Aufgeklappt: die Themen mit Stufe, Grund und Gefühl, Wackler zuerst, mit „Üben“ oder „Prüfen“ und dem Weg zur Arbeit; die Selbsteinschätzungen aus dem Unterricht bleiben darunter erreichbar und heißen so.

## 0.72.0

- Nachholen mit dem Mentor: In der Nachhol-Liste und in der Stundenansicht steht an jeder versäumten Stunde „Mit dem Mentor nachholen“. Der Mentor nennt die versäumte Stunde, fasst den Stoff aus dem Untis-Text und den Buchseiten dieser Stunde zusammen und stellt eine leichte Aufgabe. Die Seiten, die der Stundentext nennt, liegen ihm dabei vorn im Material.
- Endet die Einheit (Knopf oder Abschluss durch den Mentor), gilt die Stunde als nachgeholt, mit demselben Eintrag wie der Haken in der Liste („Mit dem Mentor nachgeholt“); der Schlusssatz sagt es. Eine nachgeholte Stunde startet danach nicht mehr als Nachholen.

## 0.71.0

- Die Frage nach der Schule: Kurz nach der letzten Stunde fragt die App einmal „Alles von heute notiert?“ Die Antwort ist ein Foto oder „nichts Neues“, sonst nichts. Aus dem Foto entsteht sofort eine Hausaufgabe in der Liste, vorläufig fällig zum nächsten Schultag; sobald das Foto gelesen ist, stehen Fach, Titel und der Termin der nächsten Stunde dieses Fachs daran. Die Karte steht nachmittags oben auf der Startseite bis zum Abend oder bis jemand „nichts Neues“ antwortet.
- Die Mitteilung dazu läuft über die Home-Assistant-App, ab Werk aus, mit einstellbarem Abstand zur letzten Stunde (Eltern-Einstellungen, „Nach der Schule“). Einmal je Gerät und Tag, nicht an Tagen ohne Unterricht, nicht mehr, sobald geantwortet wurde. Ausgefallene Stunden zählen nicht als Schulende.
- Ein Test, der in der Prüfumgebung ohne eingerichtete Datenbank scheiterte, nutzt jetzt die Testdatenbank.

## 0.70.0

- Web-Push ist raus. Die Erinnerungen laufen seit 0.51 über die Home-Assistant-App; der alte Browser-Weg lief trotzdem noch mit, und jede Abendmitteilung hinterließ im Log einen Fehler über einen unlesbaren Schlüssel. Abonnements, Schlüssel, Route und der Abschnitt „Älterer Weg über den Browser“ in den Erinnerungs-Einstellungen sind entfernt.
- Tests laufen bei jedem Push auf GitHub (Backend-Tests und Frontend-Build), nicht mehr nur von Hand. `python3 -m pytest tests` funktioniert jetzt aus dem Repo-Wurzelverzeichnis.
- Diagnoseskript `scripts/ha_diagnose.py` fällt bei einem 403 des Sandbox-Proxys auf curl zurück statt abzubrechen.
- Namen der Kinder aus den öffentlichen Dokumenten, Beispielen und Testdaten genommen; die veraltete Übergabenotiz `docs/handover.md` aus Version 0.2.0 ist gelöscht.

## 0.69.8

- Materialliste: „Arbeitsheft S. 26 · Arbeitsheft“ stand doppelt; steht Buch und Seite da, entfällt die Art.

## 0.69.7

- Materialliste: Jede Zeile nennt zuerst Buch und Seite („Arbeitsheft S. 28“, „¡Apúntate! S. 48–49“). Fotos mit Buchteil und Seite stehen nach Buchteil und Seitenzahl, Buchseiten je Buch nach Seitenzahl, alles andere nach Datum.

## 0.69.6

- Scheitert die Verarbeitung einer KI-Antwort, steht der Grund im Add-on-Log (Status, warum unvollständig, was an Ausgabe kam) statt nur „502“.

## 0.69.5

- Klausurkarte: Scheitert das Lesen eines Materials am erschöpften KI-Rahmen, steht das jetzt so da („wartet auf freien KI-Rahmen“) statt „Lesen ist gescheitert“. Ein Arbeitsblatt ohne Seitenzahl heißt „Arbeitsblatt“, nicht „Arbeitsblatt S. 0“.
- Ein am KI-Rahmen gescheitertes Material wird so lange alle fünfzehn Minuten erneut versucht, bis wieder Rahmen frei ist; die Höchstzahl von drei Anläufen gilt nur für echte Lesefehler.

## 0.69.4

- Angenommene Themen bekommen ihre Stellen auch aus den Hausaufgaben vom Tag der Stunde (viele Lehrkräfte nennen die Seiten dort, nicht im Stundentext), und die Stellen wachsen mit dem Unterricht nach.

## 0.69.3

- Arbeiten ohne offizielle Themenliste (Spanisch, Deutsch, Mathe): Die aus dem Unterricht erschlossenen Themen werden jetzt wie Themen der Themenliste geführt, mit Stufe, Stellen aus ihren Stunden und Üben-Knopf. Vorher klappte nur eine Liste ohne Übungen auf. Kommt später eine Themenliste, treten die angenommenen Themen zurück.

## 0.69.2

- Klausurkarte: Das „✕“ zum Entfernen eines Themas ist aus den Zeilen verschwunden. Eltern finden es unter „Themen bearbeiten (Eltern)“ mit Rückfrage; Kinder sehen es nicht.
- Vokabeltrainer: Eltern können den Stand einer Sprache zurücksetzen (Versuche löschen, Wörter bleiben), für Probeläufe. Der Knopf „Vorlesen“ ist entfernt.
- Einstieg: Nach der Eichung an zwei echten Themen erzeugt das mittlere Modell den Einstieg (gleiche Qualität wie das Hauptmodell, halber Preis); das kleine Modell erfand ein „letztes Mal“ und fällt aus.

## 0.69.1

- Einstieg: Der Termin der Arbeit wird beim Start der Einheit aus dem Kalender geholt, wenn die Klausurseite ihn noch nicht gemerkt hat. Fehlende Angaben nennt der Mentor nicht mehr („kein Termin angegeben“), und er erfindet kein „letztes Mal“.

## 0.69.0

- Der Mentor beginnt wie ein Coach, nicht wie ein Formular. Die App erkennt die Lage selbst (Arbeit vorbereiten, Kurzprüfung, Verstehen nach schlechter Stunden-Rückmeldung, Nachholen nach Fehlzeit, Hausaufgabe, frei) und das Modell formuliert den ersten Zug daraus: Termin und Buchstelle, Erinnerung an das letzte Mal, dann sofort die erste Aufgabe (passend zur Stufe) oder bei „Verstehen“ eine Zusammenfassung aus dem Material mit der Frage, was unklar ist. Die Tipps zum Antippen kommen aus dem Inhalt. Kein Umschalter: Sagt das Kind, es versteht das Thema nicht, wechselt der Mentor im Gespräch zum Erklären.
- Eine Erklärung vor der ersten Aufgabe ist Lernen, keine Hilfe; erst ein Hinweis während einer offenen Aufgabe zählt für die Stufe.
- Jede Themen-Einheit endet mit einem konkreten Satz: Stand, Grund, wann die Kurzprüfung kommt. „Für heute schließen wir ab“ ist Geschichte.
- Der Kopf der Einheit zeigt die Lage und den Abstand zur Arbeit. Scheitert der Einstieg vom Modell (Budget, Netz), bleibt eine kurze feste Begrüßung.
- Eltern: Das Modell für den Einstieg ist eigens wählbar und wird geeicht (Vergleich derselben Einheit mit allen Modellen).

## 0.68.1

- Vokabeltrainer direkt erreichbar: Unter Lernen steht die Karte „Vokabeln üben“. Sie führt zur Sprachauswahl mit allen Fremdsprachen aus dem Stundenplan (Englisch, Latein, Spanisch, Französisch) und dem Stand je Sprache; fehlt eine Wortseite, steht dort, was zu fotografieren ist.

## 0.68.0

- Verarbeitung nach Änderung statt nach Uhrzeit: Ein neues Foto, ein neues Verzeichnis oder eine Themenliste, neue Aufgaben aus Home Assistant, ein geändertes Bücherregal oder ein berichtigtes Kapitel stoßen den Sammellauf des Kindes an; nach einer Sammelfrist von anderthalb Minuten läuft er (mehrere Fotos ergeben einen Lauf). Neue Untis-Einträge, die die Integration ohne Wissen des Add-ons schreibt, werden alle fünf Minuten auf neue Stellen abgehorcht. Gescheiterte Auswertungen werden nach einer Viertelstunde erneut versucht, höchstens dreimal. Die Läufe um zwei und um vierzehn Uhr bleiben als Netz.
- Materialseite: Unter „Jetzt einsammeln“ steht, was vorgemerkt ist und was zuletzt automatisch lief, mit Grund.

## 0.67.4

- Vokabeltrainer: Wortseiten werden von selbst in Lernwörter zerlegt, sobald eine Seite gelesen ist oder der Trainer geöffnet wird. Der Knopf „Wörter von den Seiten lesen“ und der Satz „noch nicht in Wörter zerlegt“ sind weg; solange etwas läuft, steht dort „Ich lese gerade noch eine Seite …“ und die Ansicht lädt nach. Eine gelesene Seite ohne Lernwörter galt fälschlich als ungelesen, darum änderte der Knopf nichts.
- Klausurkarte: „1 unterwegs“ beim Material sagt jetzt, was los ist: „Textband S. 22 liegt da, Lesen ist gescheitert und wird wiederholt“, „liegt da, wird noch gelesen“ oder „wird aus dem Buch geholt“, mit Link zur Seite. Anlass: Ein Foto von Textband S. 22 war während der Sicherung an der Datenbanksperre gescheitert.

## 0.67.3

- Vokabeltrainer: Grammatikseiten des Begleitbands (Deklination, Konjugation, Infinitiv) galten wegen ihrer vielen „Form — Erklärung“-Zeilen als Wortseiten und wurden zum Zerlegen angeboten; jetzt nicht mehr. Ein Durchgang zeigt alle Wörter einer Einheit (bis 80), nicht nur die ersten 40.

## 0.67.2

- Klausurkarte auf dem Telefon: Die drei Punkte nutzen die ganze Breite (Name und Text in einer Zeile, Knopf rechts), der Übungsknopf und die Gefühlsauswahl stehen untereinander. Geprüft an echten Karten eines Kontos.

## 0.67.1

- Klausurkarte: Der Wochentag stand doppelt („Montag, Mo. 21.09.“), jetzt „Montag, 21.09.“; der lange Titel aus dem Klausurplan steht in einer eigenen, abgeschnittenen Zeile.

## 0.67.0

- Klausurseite neu: Jede Arbeit zeigt drei Punkte mit Ampel: Stoff (offizielle Themenliste liegt vor oder angenommen), Material (Stellen da oder fehlt, mit Foto-Link) und Üben (wie viele Themen sitzen, wackeln, neu sind). „Für Latein üben“ klappt die Themenliste auf: sortiert, Wackler zuerst, je Thema Stufe, Grund, Stelle, Materialstand, Üben- oder Prüfen-Knopf und das Gefühl des Kindes. Darunter „Auch behandelt, nicht auf der Liste“, die Kapitel im Zeitraum und der Weg zur Übungsarbeit. Arbeiten in mehr als drei Wochen stehen kompakt in einer Zeile, vergangene Arbeiten hinter einem Aufklapper.
- Vokabeltrainer: Die Karten einer Einheit folgen jetzt der Seitenreihenfolge des Buchs statt sich zwischen zwei Seiten abzuwechseln.

## 0.66.0

- Vokabeltrainer, zuerst für Latein und Englisch: Die Lernwörter kommen aus den abgelegten Originalseiten (Begleitband „Lernwörter der Lektion 1“, Green Line „Irregular verbs“), einmal je Seite gelesen und am Seitentext geprüft. Stufe 1 fragt die Bedeutung, gesprochen: Latein → Deutsch wie in der Arbeit, Englisch in beide Richtungen; eine Bedeutung genügt, wenn sie im Buch steht, bei unsicherem Verstehen fragt die App nach statt zu werten. Stufe 2 prüft die Schreibweise in die Fremdsprache, getippt ohne Autokorrektur; ein Buchstabe daneben heißt „fast“, nicht richtig. Kein Multiple Choice, kein Abschreiben.
- Je Wort und Stufe wird der Stand abgelesen: zweimal hintereinander richtig ohne Zögern (unter zwölf Sekunden) heißt sitzt, drei Tage später noch einmal richtig heißt gefestigt, ein Fehler setzt auf wackelt. Wackler und fällige Wörter kommen zuerst.
- Die Klausurkarte verbindet ein Vokabel-Thema der offiziellen Themenliste („Voc. 1. Lektion“) mit dem Trainer: „Üben“ führt dorthin, und die Stufe des Themas ergibt sich aus den Wörtern seiner Stellen.
- Die Spracheingabe im Trainer hört in der richtigen Sprache je Richtung (Deutsch, Englisch) und kennt als Hinweis alle Wörter der Lektion, nie nur das gefragte. Das Vorlesen der Fremdsprache übernimmt die Stimme des Geräts.

## 0.65.1

- Spracheingabe: Aus Stille oder Rauschen erfand die Erkennung Text, der zum Hinweis passt („Mit der a-Deklination.“). Der Browser misst jetzt die Lautstärke mit; leise Aufnahmen werden gar nicht gesendet, mit der Bitte, näher am Gerät zu sprechen.

## 0.65.0

- Spracheingabe im Mentor: Ein großer Knopf „Halten und antworten“ nimmt auf, die App erkennt den Text mit einem eigenen Modell (gpt-4o-transcribe in derselben Azure-Ressource) und zeigt ihn erst zum Prüfen im Textfeld; gesendet wird per Knopf. Tippen bleibt immer möglich. Die Erkennung bekommt Fach, Thema und die aktuelle Aufgabe als Hinweis, damit Fachbegriffe und lateinische Formen nicht zu Alltagswörtern werden; Englisch, Spanisch und Französisch werden in der Sprache des Fachs erkannt.
- Der Mentor weiß, wenn ein Text gesprochen war: Groß-/Kleinschreibung und ähnlich klingende Wörter sind dann Hörfehler, keine Fehler des Kindes.
- Neue Add-on-Optionen `learning_ai_transcribe_model` (Deployment-Name, Standard gpt-4o-transcribe) und `learning_ai_transcribe_url` (nur nötig, wenn die Adresse nicht aus `learning_ai_url` abgeleitet werden kann). Die Aufnahmen werden mit dem Kinderbudget verrechnet (rund 0,4 Cent je Minute) und nicht gespeichert.

## 0.64.0

- Lernstand je Thema: Liegt die offizielle Themenliste der Lehrkraft vor, zerlegt die App sie in ihre Themen und zeigt zu jedem die Stufe: neu, angefangen, wackelt, sitzt, gefestigt. Die Stufe wird aus den Antworten abgelesen, nicht behauptet: „sitzt“ heißt drei Aufgaben hintereinander richtig ohne Hilfe, ohne Zögern (unter 40 Sekunden, kaum Umformulieren), in mindestens zwei Aufgabenarten. „gefestigt“ erst, wenn Kurzprüfungen nach drei und nach sieben Tagen ohne Hilfe bestanden sind; eine Prüfung mit Hilfe setzt zurück auf „wackelt“.
- Eine Einheit zu einem Thema hat keine Uhr mehr. Sie endet, wenn die Stufe erreicht ist oder das Kind aufhört; der Mentor wechselt die Aufgabenart, erklärt bei einer Kurzprüfung nicht vorweg und schreibt am Ende den fachlichen Grund ans Thema („Genitiv Plural zweimal falsch, dann mit Hinweis richtig“).
- Klausurkarte: Die Themen stehen sortiert unter der Arbeit, Wackler und fällige Prüfungen zuerst, mit Stelle und Materialstand; „Üben“ startet die Einheit direkt zum Thema. Das Gefühl des Kindes je Thema (unsicher, mittel, sicher) sortiert nur, es zählt nie als Beleg. Themen, die die Lehrkraft mündlich genannt hat, lassen sich von Hand ergänzen.
- Der Link „Für diese Arbeit üben“ führte auf eine nicht vorhandene Seite; behoben.

## 0.63.3

- Während einer Sicherung schlugen Anfragen mit „database is locked" fehl (Vorschaubilder auf der Materialseite). Die Datenbank läuft jetzt im WAL-Modus, in dem Leser und Schreiber einander nicht anhalten, wartet bis zu dreißig Sekunden auf einen anderen Schreiber, und das Vermerken von „zuletzt gesehen" beim Anmelden darf nie eine Anfrage scheitern lassen.
- Der Knopf „Jetzt in Home Assistant sichern“ hat funktioniert; die Sicherung entstand nach etwa zwei Minuten, nur die Antwort kam über Nabu Casa nicht mehr an (Zeitlimit des Proxys). Die Anzeige holt sich den Stand danach selbst.

## 0.63.2

- Ein Wort für eine Sache: Was die Lehrkraft für eine Arbeit nennt, heißt überall „offizielle Themenliste“, egal ob Tafelabschrift, Zettel oder Nachricht. Die Wörter Ankündigung und Zettel sind aus Materialseite, Klausurkarte, Stoffplan und Lesehinweisen verschwunden. Ein Punkt darauf ist ein „Thema“, Buchteil plus Seite eine „Stelle“.

## 0.63.1

- Die App startete nach 0.63.0 nicht: Ein Syntaxfehler beim Beenden der Hintergrundaufgaben. Ein Test übersetzt jetzt jedes Backend-Modul vor der Auslieferung.
- Korrektur zur Sicherung: Die automatischen HA-Backups enthalten das Add-on sehr wohl, die Anzeige hatte nur wegen der fehlenden Berechtigung nichts gesehen. Die Nachtsicherung des Add-ons springt nur ein, wenn länger als einen Tag kein HA-Backup mit dem Add-on entstanden ist.

## 0.63.0

- Backup-Anzeige: Sie meldete fälschlich „kein Backup vorhanden“, weil dem Add-on die Berechtigung fehlte, Backups aufzulisten (403). Es hat jetzt die Rolle „backup“ und zeigt die letzte Sicherung, die dieses Add-on enthält, warnt ab zwei Tagen und hat den Knopf „Jetzt in Home Assistant sichern“.
- Fehlt länger als einen Tag ein HA-Backup mit dem Add-on, sichert es sich nachts zwischen drei und sechs Uhr selbst als Teil-Backup und behält die letzten sieben eigenen.
- Der ZIP-Download scheiterte mit „database is locked“, weil der vollständige Checkpoint auf alle Schreiber wartete und den Server dabei anhielt. Der Schnappschuss läuft jetzt im Hintergrund, mit passivem Checkpoint und seitenweisem Kopieren.

## 0.62.0

- Der Einwilligungsdialog des Verlags im Medienregal wird erkannt und gemeldet statt als Bücher gespeichert; die App stimmt nicht an Stelle der Eltern zu. Ein Regaleintrag lässt sich in den Einstellungen entfernen.
- Beim Ablegen eines Fotos meldet die App sofort, wenn dieselbe Seite schon vorliegt (gleicher Bildabdruck) und bietet an, das neue Foto zu löschen. Ein unscharfes Foto wird als solches genannt, mit der Bitte um ein neues bei gutem Licht; gelesen wird es trotzdem. Die Liste markiert unscharfe Fotos.

## 0.61.1

- Die Eichung misst zusätzlich, ob jedes Wort und jede Zahl der Seite in der zweiten Lesung vorkommt (Wortabdeckung), und nennt die fehlenden Wörter. Die reine Zeichenfolge bestraft eine anders angeordnete Tabelle, obwohl nichts fehlt.

## 0.61.0

- Das Modell fürs Abschreiben von Quellen und für die Hintergrundauswertung ist getrennt wählbar; Erklären und Üben bleiben beim Hauptmodell. Umgestellt wird erst nach einer Eichung an echten, bereits gelesenen Seiten: Ein Vergleichsaufruf liest dieselbe Seite mit dem anderen Modell und meldet, ob Seitenzahl, Buchteil und Art stimmen und wie viel vom Wortlaut übereinstimmt. Gespeichert wird dabei nichts.
- Die Rahmen der Eltern stehen in der Mentor-Ansicht unter „KI-Rahmen einstellen“: Monat, Warnung, Tag je Kind, Quellenbestand, Hintergrund und das Modell fürs Abschreiben. Bisher ging das nur in der Datenbank.

## 0.60.1

- Rückt bei einer Kapitelkorrektur der Nachbar, rückt das nicht ausdrücklich gesetzte Ende des berichtigten Kapitels mit. Nur eine von Hand gesetzte Endseite bleibt stehen.

## 0.60.0

- Fotografierte Inhaltsverzeichnisse gelten auch für digitale Bücher, deren Verzeichnis der Abruf auf den ersten Seiten nicht findet (Spanisch, Englisch, Geschichte). Die Kapitel landen beim digitalen Buch, der Sammellauf holt danach ganze Kapitel und sucht das Verzeichnis nicht weiter.
- Kapitel lassen sich von Hand berichtigen: Unter „Bücher“ auf der Materialseite stehen alle gelesenen Einheiten mit Anfangs- und Endseite zum Ändern; die Nachbarn rücken nach, die Korrektur überlebt jedes neue Lesen und die Stellen werden sofort neu gebunden.
- Verzeichnisfotos stehen zum Gegenlesen als ein Eintrag je Buch, nicht mehr je Foto.

## 0.59.0

- Die Ankündigung der Lehrkraft legt den Klausurstoff fest. Liegt ein Zettel vor, gruppiert der Stoffplan den Unterricht entlang seiner Punkte; was im Unterricht behandelt, aber nicht angekündigt wurde, erscheint als eigene Kategorie „nicht angekündigt“ und wird nur auf Wunsch geübt. Gilt für jedes Fach, jeden Jahrgang und jedes Kind.
- Lesungen mit Folgen bitten um ein Gegenlesen: Zettel zu einer Arbeit, Inhaltsverzeichnisse und alles, was die Auswertung selbst für unsicher hält, stehen oben auf der Materialseite mit dem erkannten Text und den Knöpfen „Stimmt so“ und „Korrigieren“. Die Klausurkarte sagt, ob die Ankündigung gegengelesen ist, und zeigt ihren Text.
- Stellen ohne Buchteil („S. 10, 11“) bekommen das wahrscheinlichste Buch: das mit einem gerade angeschnittenen Kapitel, das die Seite enthält. Die Einkaufsliste schreibt „vermutlich Begleitband“, ein Foto von dort bekommt den Buchteil mit; ein Foto des anderen Buchs streicht die Stelle weiterhin. Zwei gleich gute Kandidaten bleiben offen.

## 0.58.2

- Ausgeblendete Kurse zählen nicht mehr als offene Rückmeldung. Französisch und Religion eines Kindes, das die Fächer nicht besucht, standen auf dem Dashboard als „zwei Rückmeldungen offen“, ohne im Stundenplan zu erscheinen. Das gilt auch für die Zählung in der abendlichen Mitteilung.

## 0.58.1

- Der Tagesrahmen je Kind zählt nur noch, was das Kind selbst übt und fragt. Das Einlesen von Quellen, das Auswerten von Fotos und die Einstiegshilfen laufen im Hintergrund und hatten den Tagesrahmen eines Kindes am Nachmittag aufgebraucht, bevor er eine Frage gestellt hatte. Der Tagesrahmen steigt von 5 auf 10 Euro je Kind, der Rahmen einer einzelnen Übungseinheit von 2 auf 4 Euro. Der Monatsrahmen von 50 Euro bleibt.

## 0.58.0

- Die Klausurkarte unter „Arbeiten & Tests“ zeigt den Materialstand für den angenommenen Stoff: wie viele genannte Stellen gelesen vorliegen, was unterwegs ist und was fehlt, mit Link auf die Einkaufsliste des Fachs. Dazu je angeschnittenes Kapitel die fotografierten oder abgerufenen Seiten und ob die Ankündigung der Lehrkraft vorliegt.
- Fotos und Scans, die vor 0.57.0 gelesen wurden, kennen ihre gedruckte Seite noch nicht; der Nachtlauf liest sie nach. Für die Englisch-Seite 206 eines Kontos wurde das von Hand angestoßen, die Hausaufgabe ist grün.

## 0.57.5

- Auch eine direkt genannte Einführungsseite eines Teils („TB S. 10, 11“) holt nicht mehr den ganzen Teil: Ein Eintrag ohne Nummer, unter dem Lektionen liegen, ist eine Überschrift. Die Einkaufsliste für Latein schrumpft damit auf die angeschnittenen Lektionen.

## 0.57.4

- Der Begleitband nennt jede Lektion „Wortschatz“, und das Modell hielt sie für Vokabelteile statt Kapitel; die Lektion 1 fehlte deshalb in der Bilanz. Eine nummerierte Einheit der obersten Ebene ist ein Kapitel. Die Bücherzeile zeigt, mit wie vielen Kapiteln ein Verzeichnis gelesen wurde.

## 0.57.3

- Ein Teil ohne Nummer im Inhaltsverzeichnis („Gefahr im Circus Maximus“, Lektionen 1–3) ist eine Überschrift über mehreren Lektionen, kein Kapitel: Er kommt nicht mehr als Ganzes auf die Einkaufsliste, nur die angeschnittene Lektion.

## 0.57.2

- Das fotografierte Inhaltsverzeichnis eines Papierbuchs wird mit bis zu sechs Aufnahmen in einem Aufruf gelesen, jede für sich: Die Schnittstelle verkleinert jedes Bild auf 1600 Pixel und ließ bisher nur zwei Bilder zu; zwei Handyfotos übereinander wären unlesbar, fünf Seiten scheiterten mit 413.
- Eine fotografierte Doppelseite belegt beide gedruckten Seiten, nicht nur die erste.

## 0.57.1

- Fotos von Buch- und Heftseiten, Inhaltsverzeichnisse und Klausurzettel werden im Quellen-Rahmen gelesen, nicht im Tagesrahmen des Kontos: 26 Latein-Uploads an einem Nachmittag blieben sonst mit 429 liegen.
- Fünf Handyfotos eines Inhaltsverzeichnisses in voller Größe wies der KI-Dienst mit 413 ab; die Aufnahmen werden vor dem Lesen auf 1800 Pixel Kante verkleinert. Ein gescheitertes Lesen löscht das zuvor gelesene Verzeichnis nicht.

## 0.57.0

- Latein hat zwei Bücher: „TB" ist jetzt der Textband, „BB" der Begleitband; beide sind eigene Quellen, eine Seite 13 gibt es in jedem. Eine Begleitband-Seite belegt keine Textband-Stelle und umgekehrt; ein nacktes „S. 19" meint weiter das Hauptbuch.
- Aufzählungen wie „S. 10, 11, 14, 15" gelten vollständig, nicht nur die erste Zahl. „S. 12, 3a" bleibt Seite 12 mit Aufgabe 3a.
- Der Zettel der Lehrkraft, was in der Arbeit vorkommt, ist eine eigene Materialart „Ankündigung einer Arbeit". Jede darauf genannte Stelle kommt wie ein Untis-Eintrag auf die Liste, wird beim Holen vorgezogen und steht im Klausurstoff ganz vorn.
- Bücher, die nur auf Papier existieren, bekommen ihr Inhaltsverzeichnis aus Fotos (Materialart „Inhaltsverzeichnis", Buchteil dazu). Danach gilt für sie die Kapitelregel: Wird eine Seite genannt, steht die ganze Lektion auf der Einkaufsliste, und die Bilanz zeigt je Kapitel, wie viele Seiten fotografiert vorliegen.
- Ein Foto oder Scan merkt sich, welche gedruckte Seite welchen Buchteils es zeigt: von der Einkaufsliste mitgegeben oder von der Auswertung abgelesen. Eine von Hand gescannte Seite 19 verschwindet damit von der Liste. Ein Verweis „→ S. 12" im Text einer Seite 15 belegt keine Seite 12 mehr.
- Das Fach wird auf der Materialseite aus dem Stundenplan gewählt, nicht mehr getippt, und beim Speichern auf dessen Schreibweise gebracht: kein „Latein" neben „LATEIN" mehr. Vor dem Fotografieren lassen sich Fach, Art, Buchteil und Seite vorgeben; die Korrektur eines Materials kennt Buchteil und gedruckte Seite.

## 0.56.11

- Fenster 3000 mal 2100 Pixel: eine Doppelseite kommt mit rund 2300 Pixeln Breite an, gemessen 1970 bei 2600.

## 0.56.10

- Schärfe, dritter Anlauf: Der Gerätefaktor kam auch über DevTools nicht im Screenshot an. Der Browser läuft jetzt in einem 2600 mal 1900 Pixel großen Fenster, der Betrachter zeichnet die Seiten entsprechend größer. Der Seitentest meldet die Rohgröße des gelieferten Bildes.

## 0.56.9

- Die Schärfe aus 0.56.6 kam nicht an: Das Chromium-Flag für den Gerätefaktor greift im Headless-Betrieb nicht, die Seiten blieben bei 1308 Pixeln Breite. Der Faktor wird jetzt über das DevTools-Protokoll gesetzt.

## 0.56.8

- Der Quellen-Rahmen steht auf 30 Euro im Monat, wo bisher die Voreinstellung von 15 Euro galt. Gemessen kostet eine gelesene Buchseite rund 13 Cent, weil der Text wortgetreu abgeschrieben wird; der Altstand des Schuljahresbeginns braucht mehr als 15 Euro. Ein selbst gesetzter Wert bleibt.

## 0.56.7

- Der Altstand wird jetzt eingelesen. Der KI-Tagesrahmen von 5 Euro je Kind gilt nicht mehr für den Quellenbestand; der hat seinen eigenen Monatsrahmen. Der Sammellauf nimmt zuerst die Seiten offener Hausaufgaben, dann die Fächer mit einer Arbeit in den nächsten zwei Wochen, dann den Rest, und liest je Lauf bis zu 40 abgelegte, noch ungelesene Seiten nach.

## 0.56.6

- „Was mir noch fehlt" ist eine Checkliste: je Seite ein Eintrag mit Kamera und Datei. Antippen, fotografieren, und das Foto gehört genau zu dieser Stelle; sie verschwindet von der Liste, noch bevor die Auswertung die Seitenzahl gelesen hat. Die Zuordnung von Hand hat Vorrang vor jeder Herleitung.
- Buchseiten kommen scharf. Der Browser nahm mit Gerätefaktor 1 auf, eine Doppelseite hatte rund 650 Pixel je Seite. Jetzt Faktor 2, gespeichert bis 2400 Pixel Kantenlänge, etwa 300 KB je Seite. Vorhandene unscharfe Seiten tauscht der Sammellauf nach und nach gegen scharfe Bilder aus, bis zu 20 je Lauf; die Auswertung bleibt, nur das Bild wird ersetzt.
- Die Materialseite ist je Fach aufklappbar gruppiert; Fotos und Scans stehen direkt darin, Buchseiten je Buch noch einmal eingeklappt und nach Seite sortiert. Das Detail öffnet sich unmittelbar unter der angetippten Zeile statt am Seitenende.
- „Konnte nicht gelesen werden" war für Seiten, die am KI-Tagesrahmen scheiterten, die falsche Auskunft. Sie heißen jetzt „wartet auf KI-Rahmen"; die Seite sagt oben, wie viele es sind. Gelesen werden sie im nächsten Lauf, sobald der Tagesrahmen wieder frei ist.
- Der Hintergrund-Rahmen für die Fotos der Kinder steht auf zehn Euro im Monat, wo bisher die Voreinstellung von fünf Euro galt; die war im September aufgebraucht, bevor das erste Foto des jüngeren Kindes gelesen war. Ein selbst gesetzter Wert bleibt unverändert.

## 0.56.5

- Aufgaben- und Stundenansichten ziehen die Quellenverknüpfungen selbst nach, wenn sie älter als zehn Minuten sind. Bisher zeigte ein neuer Untis-Eintrag seine Quelle erst nach der Materialseite oder dem nächsten Sammellauf.

## 0.56.4

- Ein Arbeitsblatt ohne Seitenzahl („Arbeitsblatt beenden") ist eine Quelle: Das Wort wird zum roten Link mit Kamera, bis ein Foto an der Aufgabe hängt oder ein Blatt-Foto des Fachs aus den Tagen um den Eintrag da ist. Auf der Einkaufsliste steht es als „Arbeitsblatt ohne Seitenangabe".
- Der Auftrag einer Untis-Hausaufgabe stand in der Ansicht zweimal.

## 0.56.3

- Deutsch trägt wieder ein Icon (Schreibfeder) statt der Flagge; nur Fremdsprachen haben ihre Landesflagge.

## 0.56.2

- Steht die Untis-Kennung in derselben Zeile wie ein Datum, blieb diese Zeile Teil des Auftrags. Kennungen werden jetzt überall aus dem Text genommen.

## 0.56.1

- Bei Aufgaben aus Untis steht der Auftrag in den Notizen, der Titel ist nur das Fach. Die Quell-Links und die Zuordnung zur Untis-Hausaufgabe gehen jetzt vom Auftrag aus; in 0.56.0 blieben sie leer.

## 0.56.0

- Überall, wo der Unterricht eine Buchstelle nennt, ist sie jetzt ein Link in der Farbe ihres Stands: grün liegt vor und ist gelesen, gelb wird gerade geholt oder gelesen, rot fehlt und muss fotografiert werden. In der Aufgabenzeile, der Stundenkarte, dem Stundendetail und dem Fachdetail. Grün und gelb führen zum Material, rot zur Kamera, das Foto hängt dann an der Aufgabe.
- Die Hausaufgabe ist neu aufgebaut: oben die Fakten (Fach, gestellt am, fällig am, Herkunft, Stand), dann der Auftrag mit seinen Quell-Links, eine Einstiegshilfe in zwei, drei Sätzen, das Material als Vorschaubilder zum Vergrößern und der Weg in den Hilfe-Chat. Typ, Aufwand in Minuten und Teilaufgaben sind aus der Ansicht verschwunden; eigene Aufgaben haben Titel, Fälligkeit und Notiz.
- Die Einstiegshilfe entsteht im Hintergrund im Sammellauf, sobald die Quellen einer Hausaufgabe da sind, höchstens acht je Lauf aus dem Quellen-Rahmen. Sie sagt, worum es geht und womit man anfängt, keine Lösung.
- Die Materialseite zeigt alles, Buchseiten eingeschlossen, mit „Mehr laden" statt einer stillen Grenze. Ein Material lässt sich per Link direkt öffnen.
- Sprachen tragen ihre Flagge: Deutsch, Englisch, Spanisch, Französisch. Englisch und Erdkunde waren beide ein Globus, Spanisch eine Sonne.

## 0.55.1

- Ein Sammellauf je Kind zugleich; abgelegte, noch ungelesene Seiten werden zuerst gelesen; Buchseiten füllen den Speicher höchstens zu 90 Prozent; die Arbeiten für die Abendkarte werden alle zehn Minuten statt jede Minute bestimmt. Diese vier Punkte standen schon unter 0.55.0, waren aber erst nach dessen automatischer Installation fertig.

## 0.55.0

- Stunden ohne Seitenangabe finden ihr Kapitel. Steht eine Lektionsnummer im Text („Lektion 3: Wortschatz Stadt"), entscheidet sie allein; sonst ordnet das Modell die neuen Stundentexte eines Fachs mit dem Inhaltsverzeichnis in einem Aufruf je Buch zu. Ein so erschlossenes Kapitel wird wie ein genanntes eingesammelt, steht aber als Hypothese gekennzeichnet: „aus dem Stundenthema erschlossen". Einmal zugeordnet bleibt zugeordnet, auch ein „passt zu keinem Kapitel".
- Fachgewohnheit. Schreibt eine Lehrkraft sonst immer „AH", ist ein nacktes „S. 12" im selben Fach das Arbeitsheft, nicht das Schulbuch: ab drei ausdrücklichen Angaben, von denen vier Fünftel auf denselben Teil zeigen. Die Stelle wandert dann auf die Einkaufsliste statt in den Abruf, mit genau diesem Hinweis.
- Vor einer Arbeit bittet die App um die Heftseiten, die der Unterricht nennt und die weder digital noch fotografiert vorliegen: in der Abendkarte, mit Heft, Seite und Unterrichtszitat, höchstens drei Bitten, nur bei einer Arbeit in den nächsten zwei Wochen. Die abendliche Mitteilung nennt „Heftseiten für die Arbeit" als offenen Punkt. Ohne Arbeit steht die Liste weiter nur auf der Materialseite.

## 0.54.0

- Das Buch sagt selbst, wie weit der Stoff reicht. Je Buch liest die App einmal das Inhaltsverzeichnis von den ersten Seiten ab und kennt danach Kapitel, Abschnitte, Vokabel- und Grammatikteile mit ihren Seiten. Nennt der Unterricht eine Seite aus einem Kapitel, holt die App das ganze Kapitel, bei Sprachen mit dem Vokabelteil der Lektion, und führt es als kommenden Klausurstoff. Genannte Seiten kommen vor Kapitelseiten.
- Der Klausurstoff nennt die im Zeitraum angeschnittenen Kapitel mit Seitenbereich und Anhängen als eigene Einträge; der Mentor bekommt bei der Hausaufgabenhilfe den Kapitelzusammenhang der genannten Seite mit.
- Der Quellenbestand hat einen eigenen KI-Rahmen von 15 Euro im Monat, sichtbar in der Kostenübersicht. Der erste Sammellauf hatte den Hintergrund-Rahmen von 5 Euro getroffen, der schon von der Auswertung der Fotos fast aufgebraucht war; keine der zwölf geholten Seiten wurde gelesen. Beide Rahmen liegen innerhalb des Monatsrahmens.
- Die Karte „Was mir noch fehlt" zeigt je Fach die angeschnittenen Kapitel und wie viele ihrer Seiten schon da sind; in den Eltern-Einstellungen steht an jedem Buch, ob das Inhaltsverzeichnis gelesen ist. Dieselbe Seite, einmal als „Schulbuch" und einmal ohne Buchteil genannt, zählte doppelt.
- Kurztitel der Buchseiten ohne Ausgabenkürzel („Politik & Co. 8 S. 30" statt „Politik & Co. 8 ab S. 30").

## 0.53.0

- Der Quellenbestand. Jede Stelle, die der Unterricht in Untis nennt, ob in der Stundenbeschreibung oder in der Hausaufgabe, wird an ihren Eintrag gebunden. Genannte Schulbuchseiten holt die App sich selbst aus dem Medienregal und legt sie als Material ab, mit Buch, Seite und dem Tag, an dem sie drankamen; die Materialauswertung liest sie wie ein Foto. Zwei Läufe am Tag: um 14 Uhr, wenn Hausaufgaben und Stundeneinträge stehen, und nachts für alles, was später kam. Der erste Lauf arbeitet den Bestand seit Schuljahresbeginn ab, danach nur noch die Differenz, höchstens 40 Seiten je Kind und Lauf.
- Eine gelieferte Seite gilt erst, wenn Buchinhalt darauf ist und die gedruckte Seitenzahl zur Bestellung passt. Der Betrachter meldet die Bestellung zurück, nicht die Lieferung: Bestellung 50 brachte einmal die Seiten 48/49. Weicht sie ab, wird einmal mit dem Versatz nachbestellt. Erst eine so bestätigte Seite gilt als Nachweis, dass ein Buch abrufbar ist; ein Treffer im Katalog allein zählt nicht mehr.
- Stellen ohne Buchteil („S. 64/5 zu Ende notieren") gelten zuerst als Schulbuch. Passt der Seiteninhalt nicht zum Zitat, war es ein anderes Heft; die Stelle wandert auf die Einkaufsliste mit genau diesem Hinweis.
- Die Hausaufgabenhilfe nimmt Buchseiten aus dem Bestand und startet nur noch für Seiten, die dort fehlen, den Browser. Sie versteht dabei jetzt auch „p. 50" und lässt Arbeitsheftseiten aus.
- Die Karte „Was mir noch fehlt" unterscheidet, was fotografiert werden muss, was die App gerade selbst holt und was digital vorliegt, je Fach mit Grund. Eltern können den Sammellauf von Hand anstoßen. In den Eltern-Einstellungen steht an jedem Buch, ob der Abruf nachgewiesen ist und wie viele Seiten im Bestand liegen.
- Beim Kontowechsel ziehen die Buchseiten-Zwischenspeicher, der Abrufnachweis und die gebundenen Stellen mit um.

## 0.52.6

- Der Browser des Add-ons bekommt eine Software-GPU. Die Browser-Prüfung aus 0.52.5 hat gezeigt: Das Chromium von Alpine bringt keinen SwiftShader-Treiber mit, jede GPU-Einstellung scheiterte an einer fehlenden Vulkan-Erweiterung, der GPU-Prozess startete in Schleife neu und der Browser kam zwei Minuten lang nicht hoch. Das Image enthält jetzt Mesa mit Lavapipe (Software-Vulkan) und llvmpipe (Software-GL); WebGL läuft über ANGLE auf Vulkan. Ein WebGL-Start, der fehlschlägt, wird bis zum nächsten Neustart nicht wiederholt, damit kein Abruf mehr zwei Minuten verliert.
- Die Browser-Prüfung probiert die Mesa-Varianten durch und listet die vorhandenen Vulkan- und DRI-Treiber.

## 0.52.5

- Browser-Prüfung für die Eltern-Diagnose: Chromium wird mit mehreren GPU-Einstellungen direkt gestartet und meldet, ob WebGL zur Verfügung steht und was der Browser dazu sagt. Hintergrund: Der Browser des Add-ons kommt auf dem Raspberry Pi mit jeder GPU-Einstellung nicht hoch, ohne GPU zeichnet der BiBox-Betrachter aber keine Seiten. Kein Portal und kein Zugang werden dabei berührt.

## 0.52.4

- Der Browser des Add-ons kam mit den WebGL-Flags aus 0.52.3 auf dem Raspberry Pi nicht mehr hoch; jeder Abruf lief in einen Zeitüberschreitungsfehler. Software-WebGL wird jetzt ohne den Griff nach einer echten GPU angefordert, und wenn der Browser so nicht startet, startet er ein zweites Mal ohne GPU wie zuvor. Start, Abschluss und Ende jedes Browserlaufs stehen mit Dauer im Protokoll.
- Der Seitentest in den Eltern-Einstellungen läuft im Hintergrund. Ein Abruf dauert bis zu einigen Minuten, der Fernzugriff über Nabu Casa kappt eine Anfrage aber nach 100 Sekunden; bisher endete der Test dann in einem Fehler, obwohl er im Add-on weiterlief. Die Seite fragt jetzt nach, bis das Ergebnis da ist.

## 0.52.3

- Die BiBox-Bücher (Mathematik, Erdkunde) liefern ihre Seiten. Der Betrachter zeichnet mit WebGL, und das war im Browser des Add-ons abgeschaltet; er meldete „geladen" und zeigte eine weiße Fläche. WebGL läuft jetzt in Software. Eine Seite, die nach dem Blättern noch leer ist, bekommt bis zu 15 Sekunden Zeit, bevor sie als leer gilt.
- Der Sprung vom IServ-Portal ins Medienregal scheiterte gelegentlich, weil die Kachel noch nicht gezeichnet war („Das Medienregal wurde nicht gefunden"). Der Klick wartet jetzt auf die Kachel und lädt die Seite bei Bedarf neu.

## 0.52.2

- Der Seitentest in den Eltern-Einstellungen sagt jetzt, warum ein Betrachter nichts zeigt. Zwei BiBox-Bücher melden „geladen", liefern aber eine leere Fläche; bisher war nicht zu sehen, ob die Seite nie gezeichnet wurde oder eine Anfrage scheiterte. Der Test wartet bei leerer Seite bis zu 15 Sekunden auf Inhalt und hält fest, was die Seitenbereiche enthalten, welche Anfragen fehlschlugen, was die Konsole meldet und ob WebGL verfügbar ist. Bricht der Abruf früher ab, kommt dieselbe Auskunft von der Stelle, an der er stand.

## 0.52.1

- Ein Fach stand zweimal auf der Einkaufsliste, einmal unter seinem Namen und einmal unter dem Kürzel der Hausaufgabe („LATEIN" und „LA"). Hausaufgaben führen in Untis keine Fach-ID, nur das Kürzel; es wird jetzt über das echte Untis-Kürzel der Stunde aufgelöst. Ein selbst gepflegter Fach-Alias hat Vorrang.

## 0.52.0

- Die Materialseite führt eine Einkaufsliste: „Was mir noch fehlt", je Fach aufklappbar. Sie sammelt aus Stunden- und Hausaufgabentexten die genannten Buchstellen („TB S. 13 Aufg. C, AH S. 7", „#cda, p. 28") und zeigt, welche davon weder digital im Regal liegen noch fotografiert wurden. Mit Zitat und Datum, damit erkennbar ist, worum es geht.
- Gezählt wird nur eine ausdrückliche Seitenangabe. „#libro, p. 50 vocabulario 4 b" ergibt Seite 50, nicht Seite 4; die 4 b ist die Aufgabe.
- Angefordert oder abgerufen wird nichts. Die Liste ist zum Ansehen da.

## 0.51.2

- Der Knopf zum Tagesabschluss ist wieder weg. Er verlangte ein Ritual, das es nicht gibt: Aufgaben bleiben offen oder sind erledigt, niemand schließt einen Tag ab. Ein Abend gilt jetzt als erledigt, sobald nichts mehr offen ist — keine Aufgabe mehr fällig, die Tasche für morgen bestätigt, die Stunden zurückgemeldet. Zu sehen gibt es dazu nichts Neues; daran hängt nur, wer am Morgen noch eine Mitteilung bekommt.

## 0.51.1

- Die Morgenmitteilung ist ab Werk aus. Sie ist eine Verabredung, keine Auslieferung: Wer sie will, schaltet sie in den Eltern-Einstellungen ein, die Uhrzeit steht auf 06:45 vor.

## 0.51.0

- Der Tag lässt sich abschließen. Unter der Abendkarte steht ein Knopf; festgehalten wird, wann, von wem und ob die Erinnerung da schon draußen war. Abschließen geht auch mit offenen Punkten — sie werden so vermerkt, wie sie sind.
- Wer am Abend nicht abgeschlossen hat, bekommt am Morgen vor dem Aufbruch eine zweite, kürzere Mitteilung. Wer abgeschlossen hat, bekommt nichts. Uhrzeit und Abschaltung stehen in den Eltern-Einstellungen.
- Die Abendkarte zeigt, an wie vielen Abenden dieser Woche selbst abgeschlossen wurde — gezählt werden nur Abende vor einem Schultag und nur Abschlüsse ohne vorherige Erinnerung.
- Ein Kontowechsel verlor bisher die für Mitteilungen gewählten Telefone. Sie werden jetzt mit umgezogen.

## 0.50.1

- Der Stoff einer Arbeit beginnt nie vor dem Schuljahr. Eine Arbeit desselben Fachs aus dem vorigen Schuljahr öffnete bisher ein Fenster über die Sommerferien hinweg und zog den Stoff des alten Jahrgangs mit hinein.

## 0.50.0

- Jede anstehende Arbeit zeigt ihren angenommenen Stoff: alle Themen des Fachs seit der letzten Arbeit desselben Fachs, sonst seit Schuljahresbeginn. Dazu, wie viele davon schon selbstständig gezeigt wurden, und die Themen einzeln zum Aufklappen mit Haken.
- Die Annahme steht ausdrücklich dabei. Solange keine Lehrkraft eingegrenzt hat, gilt alles als relevant, was im Unterricht behandelt wurde; anders lässt sich nicht vorbereiten.

## 0.49.2

- Die Deckung eines Themenfeldes zählt über alle seine Teile, nicht nur über die gerade angezeigten. Vorher konnte dort „Schritt 3 von 2" stehen, weil ältere Teile außerhalb des Planfensters lagen. Sind nicht alle Teile in der Liste, steht jetzt dabei, wie viele davon gerade zu sehen sind.

## 0.49.1

- Die Elternansicht kann ein Fach sofort zu Themenfeldern ordnen lassen, statt auf den nächtlichen Lauf zu warten.

## 0.49.0

- Die Themenliste ist nach Fächern gruppiert und innerhalb eines Fachs nach Themenfeldern geordnet. Vorher stand sie rein nach Aktualität, wodurch Einheiten desselben Fachs weit auseinanderlagen.
- Ein Themenfeld ist das, worüber eine Klassenarbeit geschrieben wird, etwa Bruchrechnung oder Elektrische Stromkreise. Es ordnet seine Teilthemen in der Reihenfolge, in der sie aufeinander aufbauen, und zeigt, wie viele davon schon selbstständig gezeigt wurden. Geübt und nachgewiesen werden weiterhin ausschließlich die einzelnen Teilthemen; das Feld trägt keinen eigenen Lernstand und keine eigene Aufgabe.
- Nachts wird je Kind ein Fach neu geordnet, frühestens eine Woche nach dem letzten Mal. Dabei wird nur gruppiert und sortiert, nie zusammengeführt: Welcher Teil sitzt und welcher nicht, bleibt sichtbar.

## 0.48.1

- Die Auswertung unterscheidet jetzt zwei Gründe, warum ein Eintrag kein Thema bekommt: ohne Lerninhalt (Klassengeschäfte, Bücherausgabe, Vertretung ohne Thema) oder inhaltlich, aber zu knapp beschrieben (Unit-Titel, Seitenzahlen, Geschichtentitel). Nur der erste Fall verschwindet aus den Übungsaufgaben. Ein knapp beschriebener Fachinhalt bleibt als Stunde bestehen und trägt die offene Rückfrage. Im Zweifel gilt inhaltlich.
- Sport, Schwimmen und Verfügungsstunde erzeugen keine Übungsaufgaben mehr. Bewegung lässt sich am Handy nicht nachholen, und die Verfügungsstunde ist kein Lernfach. Die Regel gilt jetzt in Plan und Tagesvorschlägen gemeinsam statt nur im Plan.
- Die Elternansicht kann Einträge ohne Thema erneut auswerten lassen, wenn sich die Anweisung an die Auswertung geändert hat. Erkannte Themen und alles daran Geübte bleiben unberührt.

## 0.48.0

- Organisatorische Unterrichtseinträge erscheinen nicht mehr als Übungsaufgabe. Die Auswertung hatte sie längst als „kein Lernthema" eingestuft und eine Rückfrage hinterlegt; der Plan hat dieses Urteil nicht gelesen und stattdessen den rohen Eintragstext als Titel genommen. So standen eine AG-Vorstellung, eine Bücherausgabe und eine Vertretungsstunde als Lerneinheiten in der Liste.

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
