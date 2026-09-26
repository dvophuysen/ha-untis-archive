# Entwurf: Vokabeln mit zeitlichem Abstand (ergänzt D155)

Stand 26.09.2026, nicht gebaut. Zur Abstimmung mit dem Nutzer.

## Heute

`vocab.replay` rechnet die Stufe eines Wortes aus allen Antworten:

- zwei richtige Antworten in Folge heißen „sitzt“ (`CLEAN_RUN = 2`), auch
  wenn beide in derselben Runde und wenige Sekunden auseinander liegen;
- eine weitere richtige Antwort frühestens drei Tage danach heißt „gefestigt“
  (`CHECK_AFTER_DAYS = 3`);
- eine falsche Antwort setzt auf „wackelt“ zurück;
- ein gefestigtes Wort wird nie wieder fällig.

Folge: Weil `rank()` das eben richtig beantwortete Wort („wackelt“) wieder
nach vorn stellt, ist eine Einheit in wenigen Minuten „sitzt“. Das sagt wenig
darüber, ob das Wort am nächsten Tag noch da ist, und gefestigte Wörter
verschwinden aus dem Pensum.

## Vorschlag

1. **„Sitzt“ braucht Abstand.** Die zweite richtige Antwort zählt für „sitzt“
   nur, wenn seit der ersten mindestens eine Stunde vergangen ist oder sie an
   einem anderen Tag kommt. In derselben Runde bleibt das Wort „wackelt“,
   bekommt aber sichtbar den Fortschritt „1 von 2“.
2. **Wiederholen nach wachsenden Abständen.** Ein gefestigtes Wort wird nach
   7, 21 und 60 Tagen wieder fällig. Jede richtige Antwort zum Termin schiebt
   den nächsten Abstand an, eine falsche setzt auf „wackelt“ zurück (wie heute).
3. **Pensum.** Fällige gefestigte Wörter kommen ins Tagespensum, höchstens
   fünf am Tag und hinter den neuen und wackelnden Wörtern (D181 bleibt: das
   Pensum wird am Morgen festgelegt).
4. **Kein rückwirkender Verlust.** Die neue Regel gilt nur für Antworten ab dem
   Tag der Umstellung. Was heute „sitzt“ oder „gefestigt“ ist, bleibt es; die
   Termine für gefestigte Wörter beginnen am Umstellungstag. So fällt kein
   Kind über Nacht in seinem sichtbaren Stand zurück (D158).
5. **Belohnung.** „Wortschatz“ und die Extrameile zählen weiter je Wort und Tag
   (1.34.0); eine Wiederholung zum Termin zählt wie ein geübtes Wort.

## Offene Fragen an den Nutzer

- Eine Stunde Abstand für „sitzt“ oder erst am nächsten Tag? Empfehlung: eine
  Stunde, damit Lernen am Vorabend einer Arbeit noch zu „sitzt“ führt.
- Abstände 7/21/60 Tage oder kürzer vor einer Arbeit (dann alle Wörter der
  Einheit in den drei Tagen davor)? Empfehlung: 7/21/60, dazu vor einer
  Vokabelarbeit die ganze Einheit.
- Höchstens fünf Wiederholungen am Tag? Empfehlung: ja, sonst wächst das
  Pensum nach einigen Wochen spürbar.

## Umfang

`vocab.replay` und `rank`, `vocab_pensum` (fällige gefestigte Wörter),
Anzeige „1 von 2“ im Trainer, Tests mit echten Antwortfolgen. Etwa ein
halber Tag, danach eine Woche beobachten.
