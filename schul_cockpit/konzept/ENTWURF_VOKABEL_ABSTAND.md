# Entwurf: Vokabeln mit zeitlichem Abstand (ergänzt D155)

Stand 26.09.2026, nicht gebaut. Zur Entscheidung durch den Nutzer. Die Zahlen
stammen aus dem Lesezugang (READ_ACCESS.md), Stand 26.09.2026 vormittags;
Kinder hier als Kind A und Kind B.

## Heute

`vocab.replay` rechnet die Stufe eines Wortes aus allen Antworten:

- zwei richtige Antworten in Folge heißen „sitzt“ (`CLEAN_RUN = 2`);
- eine weitere richtige Antwort frühestens drei Tage danach heißt „gefestigt“
  (`CHECK_AFTER_DAYS = 3`);
- eine falsche Antwort setzt auf „wackelt“ zurück;
- ein gefestigtes Wort wird nie wieder fällig.

## Datenlage

| | Kind A | Kind B |
|---|---|---|
| Wörter im Trainer | 1517 (Spanisch 967, Englisch 550) | 573 (Englisch 462, Latein 111) |
| Einheiten, Wörter je Einheit (Median) | 40, 28 | 8, 63 |
| verschieden geübte Wörter | 55 (3,6 %) | 52 (9 %) |
| Antworten, Übungstage | 125 an 3 Tagen | 208 an 3 Tagen |
| Sekunden je Antwort (Median) | 6 | 6 |
| Stand: sitzt / wackelt / gefestigt | 34 / 21 / 0 | 5 / 47 / 0 |
| Treffer 1., 2., 3. Antwort je Wort | 47 %, 83 %, 91 % | 37 %, 29 %, 26 % |

Befunde:

1. **Das „sitzt in derselben Runde“-Problem tritt real nicht auf.** Kind A
   beantwortete ein Wort an 103 von 114 Übungstagen genau einmal. Nachgerechnet
   mit „zweite richtige Antwort frühestens nach einer Stunde“ und mit „erst am
   nächsten Tag“: bei beiden Kindern ändert sich die Stufe von **keinem** Wort.
   Punkt 1 des ersten Entwurfs bringt also nichts und entfällt.
2. **Noch kein Wort ist gefestigt.** Die Umstellung hat heute keinerlei
   rückwirkende Wirkung (D158); früher bauen kostet nichts, später bauen auch
   nicht viel (die Termine beginnen dann am Umstellungstag).
3. **Der Engpass ist die Abdeckung, nicht der Abstand.** Nur 5 % aller Wörter
   wurden je geübt. Kind B braucht für Latein deutlich mehr Anläufe je Wort
   (Trefferquote bleibt bis zur dritten Antwort unter 30 %).

## Aufwand je Modell (Simulation mit den echten Trefferquoten)

Antworten je Wort bis „fertig“, 20 000 Durchläufe je Modell; eine falsche
Antwort setzt zurück wie heute. Tageslast als Obergrenze: das ganze Buch
in einem Schuljahr (190 Schultage), also Kind A 8, Kind B 3 neue Wörter je
Schultag; 8 Sekunden je Antwort mit Rückmeldung.

| Modell | Antworten je Wort A / B | Tageslast A | Tageslast B |
|---|---|---|---|
| heute (sitzt + Prüfung nach 3 Tagen, dann nie mehr) | 5,6 / 10,8 | 45 Antworten ≈ 6 Min. | 33 ≈ 4 Min. |
| **Empfehlung: dazu Wiederholung nach 14 und 45 Tagen** | 10,2 / 21,3 | 82 ≈ 11 Min. | 64 ≈ 9 Min. |
| erster Entwurf: nach 7, 21 und 60 Tagen | 12,6 / 26,6 | 101 ≈ 13,5 Min. | 80 ≈ 11 Min. |
| Leitner mit „falsch = eine Stufe zurück“ | ≈ wie die Zeile darüber | | |

Die Obergrenze liegt weit über dem echten Tempo (der Unterricht behandelt
eine Einheit in einigen Wochen, nicht das ganze Buch). Wichtig für die
Obergrenze „höchstens fünf am Tag“ aus dem ersten Entwurf: Bei 8 neuen Wörtern
am Tag entstehen mit zwei Wiederholungen etwa 16 fällige am Tag. Eine feste
Grenze von fünf baut also Woche für Woche einen Berg auf und ist verworfen.

## Empfehlung

**Zwei Wiederholungen nach 14 und 45 Tagen, sonst alles wie heute.**

1. Ein gefestigtes Wort wird 14 Tage nach dem Festigen wieder fällig, nach
   einer richtigen Antwort dort noch einmal 45 Tage später. Danach ist es
   dauerhaft sicher und kommt nur vor einer Arbeit wieder (wie heute über das
   Test-Pensum, D181).
2. Falsch bei einer Wiederholung setzt auf „wackelt“ wie heute (einfach, ehrlich,
   im Aufwand kaum teurer als „eine Stufe zurück“).
3. Keine eigene Obergrenze: Fällige Wiederholungen laufen über das bestehende
   Pensum (Grundpensum zehn am Tag, vor einem Test das Test-Pensum mit 10–40).
4. Keine Stunden-Regel für „sitzt“ (Befund 1).
5. Die sichtbare Stufe bleibt „gefestigt“, bis eine Antwort falsch ist; die
   Wiederholung steht als „fällig“ in der Karte. Belohnungen wie heute (1.34.0).

Warum nicht mehr: 7/21/60 kostet noch einmal ein Viertel mehr Antworten, und
14 Tage liegen für Klassenarbeiten im Abstand von zwei bis sechs Wochen
günstiger (Abstand etwa ein Drittel bis die Hälfte der Zeit bis zur Prüfung).
Warum kein SM-2 oder FSRS: Beide passen Abstände je Wort an; dafür braucht
FSRS erfahrungsgemäß weit über tausend Wiederholungen je Kind, es gibt bisher
333 Antworten insgesamt. Die Stufen würden für Kinder und Eltern undurchsichtig,
der Umbau (Speicher je Wort, Übernahme alter Antworten, Anzeige) kostet zwei bis
drei Tage statt zwei bis drei Stunden.

Mehr bringt vorerst die Abdeckung: das Tagespensum wirklich schaffen. Dazu
sagt die Tageslast oben, dass auch mit Wiederholungen etwa 10 Minuten am Tag
genügen.

## Umfang

`vocab.replay` (Termin für gefestigte Wörter, Zahl der bestandenen
Wiederholungen), `vocab_pensum._is_due` und `vocab.rank` (fällig gefestigt wie
fällig sitzt), Anzeige „Wiederholung fällig“ im Trainer, Tests mit echten
Antwortfolgen. Zwei bis drei Stunden, danach zwei Wochen beobachten
(erste Wiederholungen werden frühestens 17 Tage nach dem ersten Festigen fällig).
