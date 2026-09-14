# Materialablage: ein zentraler Ort für Blätter, Hefte, Scans und Arbeiten

Stand: 14.09.2026. Entwurf zur Abstimmung. Nichts in diesem Dokument ist durch sein Aufschreiben beschlossen; Vorschläge sind als solche gekennzeichnet.

Anlass: Ein Übungsblatt der Lehrkraft sollte dauerhaft für die Testvorbereitung nutzbar sein. Der vorhandene Weg dorthin ist für ein Kind nicht auffindbar und für Eltern umständlich. Die Prüfung des Bestands zeigt, dass nicht die Oberfläche das eigentliche Problem ist, sondern ein fehlendes gemeinsames Materialobjekt.

## Bestand

Material entsteht heute an drei Stellen, die nichts voneinander wissen.

**Chatanhang** (`mentor_attachments`): Das Kind fotografiert im Gespräch. Die Datei hängt an genau einer Lerneinheit, bekommt vom Modell eine Abschrift (`transcript`) und ist danach für jeden anderen Zweck verloren. Kein Fach, kein Datum, keine Wiederverwendung.

**Lernmaterial** (`learning_materials`): dauerhaft, aber zwingend an ein Thema gebunden (`topic_id NOT NULL`). Erreichbar nur in der Elternansicht, dort eingeklappt hinter „Echte Einstellungen und Übungen verwalten", danach Thema wählen, danach „Hinzufügen". Mentor und Übungsklausur lesen ausschließlich `content_text` und nur bei `verified=1`; je Fach die vier beziehungsweise fünf neuesten, gekürzt auf 1500 beziehungsweise 2000 Zeichen. Eine hochgeladene Datei löscht den Text und setzt die Prüfung zurück. PDFs werden nie gelesen, Bilder nur über den Knopf „KI-Entwurf aus ausgewählten Quellen". Grenzen: 8 MB je Datei, 100 MB je Kind.

**Buchseiten** (`digital_textbook_pages`, seit 0.39): Seiten aus dem persönlichen Medienregal werden auf Zuruf geholt und zwischengespeichert. Das deckt Schulbücher ab und ist kein Fall für die Ablage.

Damit bleibt genau die Lücke, um die es geht: alles Gedruckte und Geschriebene, das nicht im Medienregal liegt.

## Wo Material tatsächlich entsteht

Aus der Nutzung, nicht aus einer Systematik abgeleitet:

- Arbeitsblatt der Lehrkraft, ausgegeben zur Übung oder zur Vorbereitung auf eine Arbeit.
- Arbeitsheft-Seiten. In Mathematik, Deutsch, Englisch, Spanisch und Latein liegt neben dem Buch ein Heft, in dem Aufgaben bearbeitet werden. Das Medienregal kennt diese Hefte nicht.
- Aufgabenstellungen, zu denen das Kind Rückfragen hat oder die es gemeinsam durchgehen will.
- Eigene Mitschriften. Ein Kind führt in fast allen Fächern ein digitales Heft und erzeugt PDFs aus einer Notiz-App; ein anderes arbeitet mit Papierheften und Mappen, also mit Fotos.
- Von der Lehrkraft bereitgestelltes Material, das bearbeitet werden soll.
- Bearbeitete Lösungen des Kindes, die korrigiert und besprochen werden sollen.
- Zurückgegebene Klassenarbeiten und Klausuren, die analysiert und für gezieltes Training genutzt werden sollen.

Zwei Dateiarten decken das ab: Bild (Foto, Scan) und PDF (Notiz-App, Verlags- oder Lehrerdatei).

## Leitgedanke

Ablegen ist eine Handlung, kein Formular. Das Kind fotografiert und ist fertig. Fach, Art, Datum, Themenbezug und lesbarer Text entstehen aus der Auswertung, nicht aus einer Eingabemaske. Eltern korrigieren und geben frei, statt zu erfassen.

Daraus folgt eine Umkehrung gegenüber heute: Ein Material gehört zuerst dem Kind, nicht einem Thema. Themen, Aufgaben und Arbeiten sind Verknüpfungen, die später entstehen dürfen und mehrfach sein können.

## Vorgeschlagenes Datenmodell

Eine Tabelle `materials` je Kind, dazu eine Verknüpfungstabelle. `learning_materials` geht darin auf.

**materials**: `id`, `account_id`, `kind`, `subject_name`, `title`, `summary`, `content_text`, `document_date`, `period_start`, `period_end`, `captured_at`, `created_at`, `created_by`, `filename`, `mime_type`, `file_bytes`, `page_count`, `verified`, `contains_solutions`, `locked_fields`, `analysis_model`, `analysis_version`, `analyzed_at`, `analysis_json`, `confidence`.

**material_links**: `material_id`, `kind` (`topic`, `task`, `lesson`, `exam`), `target_id`, `origin` (`ai`, `mensch`), `created_at`. Ein Arbeitsblatt darf zu mehreren Themen gehören, ein Heftauszug zu einer Hausaufgabe und zugleich zu einem Thema.

**Materialarten** (`kind`), weil die Verwendung sich unterscheidet: `worksheet` Arbeitsblatt, `workbook` Arbeitsheft-Seite, `book_page` Buchseite auf Papier, `notes` eigene Mitschrift oder Heftseite, `assignment` Aufgabenstellung, `own_work` bearbeitete Lösung des Kindes, `exam` geschriebene Arbeit, `handout` Informations- oder Merkblatt, `other`.

**Drei Datumsangaben**, weil sie unterschiedliche Fragen beantworten: `created_at` ist der Upload, `captured_at` die Aufnahme der Datei (aus den Bilddaten, sonst Upload), `document_date` der Tag, zu dem das Material inhaltlich gehört. Nur letzteres taugt für die Frage „Was gehört in den Prüfungszeitraum?". Für Hefte über mehrere Wochen gibt es zusätzlich `period_start`/`period_end`.

**Wiederauswertbarkeit**: `analysis_model`, `analysis_version` und `analyzed_at` halten fest, womit ausgewertet wurde. Eine spätere Neuauswertung mit einem besseren Modell ist damit gezielt möglich, einzeln oder als Lauf über einen Bestand. `locked_fields` schützt jedes Feld, das ein Mensch korrigiert hat, vor Überschreiben durch eine Neuauswertung. Ohne diese Sperre wäre jede Korrektur nur bis zum nächsten Lauf haltbar.

## Auswertung durch die KI

Aus Bild oder PDF entsteht ein Vorschlag: Titel, Kurzbeschreibung, Materialart, Fach, inhaltliches Datum, Themenbezüge, genannte Seiten- und Aufgabennummern, der lesbare Text und ein Kennzeichen, ob Lösungen enthalten sind. Dazu eine Einschätzung der Sicherheit.

Regeln: Es wird nur wiedergegeben, was tatsächlich lesbar ist. Unleserliche Stellen werden benannt, nicht ergänzt. Ein Fach wird nur vorgeschlagen, wenn es im Material oder im Zusammenhang belegt ist; andernfalls bleibt das Feld offen und wird erfragt. Themenbezüge werden gegen die vorhandenen `learning_topics` des Kindes geprüft, nicht frei erfunden.

PDFs brauchen zwei Wege, weil beide Sorten vorkommen: Text-PDFs aus Notiz-Apps werden serverseitig ausgelesen, ohne KI und ohne Kosten; gescannte PDFs werden seitenweise in Bilder umgewandelt und dem bildfähigen Modell vorgelegt, mit einer Obergrenze an Seiten je Dokument.

## Schutz und Grenzen

**Lösungen.** `own_work`, `exam` und alles mit `contains_solutions` darf nicht in den Gesprächskontext des Kindes gelangen. Sonst liest der Mentor dem Kind die Lösung vor, die es selbst gerade erarbeiten soll. Für Elternanalyse, Fehlerbesprechung und gezieltes Training bleiben diese Materialien nutzbar; die Trennung verläuft über den Zweck des Aufrufs, nicht über eine Kennzeichnung im Text.

**Freigabe.** Die Freigabe bleibt bei den Eltern, serverseitig geprüft. Vorgeschlagen wird eine Unterscheidung, die es heute nicht gibt: Ein gerade vom Kind hochgeladenes Material ist **im laufenden Gespräch sofort** nutzbar, so wie ein Chatfoto heute schon. **Dauerhafte Quelle** für andere Einheiten, Übungsklausuren und Themen wird es erst mit der Freigabe. Damit wartet niemand um 16 Uhr auf ein Häkchen, und der Bestand bleibt geprüft.

**Sichtbarkeit.** Eltern sehen die Materialien ihrer Kinder. Kinder sehen ihre eigenen. Der bestehende Zugriffsschutz je Konto gilt unverändert.

**Speicher.** Bilder werden beim Upload verkleinert wie die Chatfotos. Die Grenze je Kind bleibt bestehen und wird konfigurierbar; bei Annäherung wird gewarnt statt stillschweigend abgelehnt.

**Was nicht hineingehört.** Buchseiten aus dem Medienregal, weil der Abruf sie liefert. Klassenkameraden auf Fotos, Elternbriefe und Organisatorisches ohne Lernbezug.

## Bedienung

**Einwerfen.** Derselbe Knopf an den Stellen, an denen Material tatsächlich anfällt: im Mentorgespräch neben dem vorhandenen Fotoknopf, direkt an einer Hausaufgabe, im Fach, in der Vorbereitung auf eine Arbeit und in der Materialliste selbst. Der Weg ist immer: Kamera oder Datei, dann eine Zeile bestätigen. Die Zeile nennt, was erkannt wurde, etwa „Physik · Arbeitsblatt · gehört zu Stromstärke in verzweigten Stromkreisen". Ein Antippen öffnet die Korrektur, ein Wisch schickt es ab.

Wird aus einer Hausaufgabe oder einem Gespräch heraus fotografiert, sind Fach und Bezug schon bekannt und werden nicht erfragt.

**Verwalten.** Eine Liste je Kind, gefiltert nach Fach, Art und Zeitraum, mit Suche über Titel und Text. Jeder Eintrag zeigt Vorschau, Kurzbeschreibung, Verknüpfungen und den Auswertungsstand. Eltern haben zusätzlich eine kurze Prüfliste der neuen und unsicheren Einträge, korrigieren einzelne Felder, geben frei und können eine Neuauswertung anstoßen.

**Suchen und Ordnen** ersetzen Ordnerbäume. Kein Anlegen von Mappen, keine Pflichtfelder beim Einwerfen.

## Nutzung durch den Mentor

Die heutige Auswahl „die vier neuesten geprüften Materialien des Fachs, hart gekürzt" wird ersetzt durch eine begründete Auswahl:

- **Hausaufgabenhilfe**: Material, das mit der Aufgabe verknüpft ist, danach Material zum selben Thema, danach zeitlich nahes Material desselben Fachs.
- **Übungsklausur**: alle Materialien des Fachs, deren `document_date` in den gewählten Prüfungszeitraum fällt. Genau das fehlt heute und macht die Aufgaben allgemein statt konkret. Die Themengruppierung aus `exam_scope` bekommt damit eine zweite Quelle neben der Unterrichtshistorie.
- **Nacharbeit einer geschriebenen Arbeit**: die Arbeit selbst plus das Material des zugehörigen Zeitraums, um aus den Fehlern gezielte Übungen abzuleiten.

Damit das nicht am Umfang scheitert: In den Kontext gehen zuerst die Kurzbeschreibungen aller in Frage kommenden Materialien, dann der Volltext der wenigen ausgewählten, bis ein festes Budget erreicht ist. Der Mentor nennt, worauf er sich stützt.

Ein konkreter Gewinn aus der Aufgabenliste: „Arbeitsheft S. 12 Nr. 3" ist heute nicht auflösbar, weil das Heft nirgends vorliegt. Mit einer abgelegten Heftseite und erkannter Seitenzahl liest der Mentor die Aufgabenstellung direkt.

## Migration

Vorhandene `learning_materials` werden mit ihrem Themenbezug als Verknüpfung übernommen; Text, Datei und Freigabe bleiben erhalten. Chatanhänge bleiben, wo sie sind, bekommen aber die Möglichkeit, als Material übernommen zu werden, samt der bereits vorhandenen Abschrift. Der alte Verwaltungsbildschirm bleibt zunächst erreichbar, bis die neue Liste ihn vollständig ersetzt.

## Offene Fragen

1. Soll die Sofortnutzung im laufenden Gespräch ohne Elternfreigabe gelten, wie oben vorgeschlagen?
2. Dürfen Kinder Material löschen oder nur ausblenden? Vorschlag: ausblenden, löschen bei den Eltern.
3. Wie lange bleibt Material erhalten? Vorschlag: über Schuljahre hinweg, mit Übernahme wie bei Themen.
4. Wird eine Neuauswertung automatisch angestoßen, wenn ein neues Modell eingerichtet wird, oder nur auf Anforderung? Kosten sprechen für Anforderung.
5. Soll die Auswertung sofort beim Upload laufen oder gebündelt im Hintergrund? Sofort ist verständlicher, kostet aber Wartezeit im Gespräch.
6. Grenze für Seiten je PDF und für die Gesamtzahl ausgewerteter Seiten je Tag.

## Vorgeschlagene Reihenfolge

1. Datenmodell, Migration, Ablage und Liste ohne KI. Manuelles Fach und manueller Titel möglich, Material ist sofort auffindbar.
2. Auswertung für Bilder, Übernahme der Chatanhänge, Prüfliste für Eltern.
3. PDF-Verarbeitung, Text und Scan.
4. Mentor- und Klausurnutzung auf die neue Auswahl umstellen.
5. Neuauswertung, gesperrte Felder, Suche.

Jede Stufe ist für sich nutzbar. Stufe 1 löst bereits den Anlass: Ein Blatt ist abgelegt und wiederfindbar, statt in einem Chat zu verschwinden.
