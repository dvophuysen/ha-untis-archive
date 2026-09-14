# Verantwortung übernehmen statt erinnert werden

Stand: 14.09.2026, überarbeitet nach Rückmeldung aus dem Alltag. Entwurf zur
Entscheidung, keine beschlossene Funktion.

Anlass ist kein Komfortproblem. Die tägliche Organisation (Hausaufgaben notieren und
erledigen, Material mitnehmen, Rückmeldung zu den Stunden) scheitert regelmäßig,
obwohl die Kinder motiviert sind und es anders machen wollen. Lehrkräfte melden sich
zu Hause und werfen den Eltern mangelnde Unterstützung vor. Die Eltern reagieren mit
engmaschiger Kontrolle, die weder das Vergessen behebt noch die Kinder selbstständiger
macht, und die alle belastet. Im vorigen Schuljahr endete dieselbe Spirale in einer
psychisch stark belastenden Situation.

Die erste Fassung dieses Entwurfs setzte auf langsame Übergabe und einen
Wochenrückblick. Das greift zu kurz. Bei einer Vergesslichkeit dieses Ausmaßes hilft
kein freundlicher Blick nach einer Woche, sondern nur Unterstützung in dem Moment, in
dem etwas vergessen wird.

## Technischer Befund

Am 14.09.2026 an der laufenden Instanz geprüft.

Die App wird auf den Kindergeräten bisher als Web-App vom Startbildschirm genutzt. Für
iOS ist das der schlechteste verfügbare Weg:

Die Bildschirmzeit behandelt eine Web-App wie Webinhalte. Während einer Auszeit werden
Webinhalte auch dann gesperrt, wenn der Browser unter „Immer erlaubt" steht. Eine
Ausnahme je Adresse, die eine Auszeit überlebt, gibt es nicht. Das erklärt, warum die
App täglich von Hand freigegeben werden muss. Solange das so ist, kann ein Kind die App
nicht eigenständig nutzen, und jede Erinnerungsfunktion ist wertlos.

Ein Gerät aus der Baureihe von 2018 bleibt dauerhaft auf iOS 18. Apple hat diese
Generation mit iOS 26 aus der Unterstützung genommen. Die neuere Bildschirmzeit wird
dort nie ankommen; Warten ist keine Option.

Der Ausweg liegt bereits auf beiden Geräten: Die Home-Assistant-App ist auf beiden
Kinder-iPhones registriert und aktiv. Damit ändert sich alles Wesentliche.

Die Home-Assistant-App ist eine echte App. Sie lässt sich in der Bildschirmzeit unter
„Immer erlaubt" eintragen und ist damit von der Auszeit ausgenommen. Das Schul-Cockpit
ist darin über den vorhandenen Ingress-Zugang erreichbar, ohne zweite Anmeldung.

Ihre Benachrichtigungen laufen über den regulären Apple-Dienst statt über Web-Push. Der
Umweg über eine zum Startbildschirm hinzugefügte Web-App mit ausdrücklicher
Push-Erlaubnis entfällt, ebenso die Unsicherheit, ob Web-Push auf einem älteren iOS
zuverlässig ankommt.

Benachrichtigungen können Tasten tragen, bis zu zehn je Nachricht. Ein Tippen darauf
löst in Home Assistant ein Ereignis aus, das die App zurücklesen kann.

Diese Tasten taugen aber nicht als Hauptweg. Am Testgerät zeigte sich: Die Tasten
erscheinen erst, wenn man den Finger auf der Mitteilung liegen lässt. Wer wie üblich
kurz antippt, sieht sie nie. Genau das wird ein Kind tun. Eine Routine, die auf langem
Drücken beruht, ist damit erledigt, bevor sie beginnt.

Was das Antippen tut, lässt sich dagegen bestimmen. Mit `url` in den Mitteilungsdaten
öffnet die App eine gewählte Seite statt der Startseite. Maßgeblich ist dabei der Pfad
des Seitenleisten-Eintrags, nicht der Ingress-Pfad: Das Add-on ist als Panel unter
`/e54108c7_schul_cockpit` registriert, während `/hassio/ingress/…` mit 404 antwortet.
Die registrierten Pfade liefert die Websocket-Abfrage `get_panels`.

Daraus folgen zwei Festlegungen. Der Web-Push-Weg wird nicht weiterverfolgt; die
Erinnerungen laufen über die Home-Assistant-App. Und die Mitteilung ist eine Tür, kein
Formular: Bestätigt wird auf einer Seite, die sich beim Antippen öffnet. Tasten in der
Mitteilung bleiben eine Zugabe für den, der lange drückt, und tragen nichts, worauf die
Routine angewiesen ist.

## Was die Forschung zu dieser Ausgangslage sagt

### Das Muster ist bekannt und behandelbar

Hohe Motivation bei gleichzeitig ausgeprägter Vergesslichkeit, Schwierigkeiten mit
Material und Planung, Rückmeldungen aus der Schule und eine sich verschärfende
elterliche Kontrolle sind ein häufig beschriebenes Zusammenspiel. Wenn das dauerhaft
und in mehreren Lebensbereichen auftritt, ist eine fachliche Abklärung sinnvoll. Diese
Einschätzung gehört zu Fachleuten, nicht in eine App, und dieses Dokument trifft
ausdrücklich keine Aussage über einzelne Kinder.

Für die Gestaltung ist die Abklärung nicht die Voraussetzung. Was bei
Organisationsschwierigkeiten hilft, ist unabhängig davon gut untersucht.

### Die passendste Studienlage: Organisationstraining

Das am besten untersuchte Vorgehen für genau dieses Problem heißt Homework,
Organization and Planning Skills. Es richtet sich an Jugendliche der Sekundarstufe I
und arbeitet an drei Dingen: Ordnung im Material, Notieren von Aufgaben und Terminen,
Planen der Erledigung. In einer randomisierten Studie mit 47 Schülern zeigten sich
gegenüber der Wartegruppe Effekte von d = 0,63 für Materialordnung, d = 0,85 für
Hausaufgabenerledigung und d = 1,05 für Planung. Eine größere Studie mit 280 Schülern
prüfte die Umsetzung durch Schulpersonal; die Sitzungen dauerten im Mittel unter zwanzig
Minuten.

Der Kern ist unspektakulär: eine kurze, immer gleiche Prüfroutine, jeden Tag, an
derselben Stelle, mit sichtbarem Ergebnis. Genau das kann eine App übernehmen.

Zwei Einzelheiten daraus sind wichtig, weil sie meiner ersten Fassung widersprechen.
Das Training beginnt mit äußerer Struktur und kleinen, unmittelbaren Verstärkern und
baut beides erst später ab. Und der Abbau erfolgt langsam, über Monate, nicht nach zwei
guten Wochen.

### Rückmeldung aus der Schule statt Beschwerdeanrufe

Die tägliche Rückmeldekarte ist eine seit Jahrzehnten untersuchte, aufwandsarme
Maßnahme: Die Lehrkraft bestätigt täglich in wenigen Sekunden drei bis fünf vorher
vereinbarte Punkte, zu Hause folgt eine kleine, verlässliche Anerkennung. Russell
Barkley bezeichnet dieses Vorgehen als eine der am besten untersuchten
niedrigschwelligen Maßnahmen, die Eltern einsetzen können. Als wirksamer Bestandteil
gilt dabei ausdrücklich die Rückmeldung zu Hause.

Für diese Familie ist der Nebeneffekt fast wichtiger als der Haupteffekt: Aus
unregelmäßigen Beschwerdeanrufen wird eine regelmäßige, sachliche Information. Die
Eltern erfahren am selben Tag, was fehlte, statt zwei Wochen später am Telefon. Und sie
haben gegenüber der Schule etwas vorzuweisen.

### Was aus der ersten Fassung bestehen bleibt

Wenn-Dann-Pläne bleiben der stärkste einzelne Hebel für das Erledigen: eine Metaanalyse
über 642 Prüfungen berichtet Effekte zwischen d = 0,27 und d = 0,66, die ältere
Metaanalyse von Gollwitzer und Sheeran d = 0,65. Wer festlegt, wann und wo genau etwas
passiert, tut es deutlich zuverlässiger.

Ebenso bleibt der Befund zur Elternrolle: Druck und Kontrolle gehen bei Jugendlichen mit
weniger erlebter Autonomie, mehr Trotz und geringerer selbstbestimmter Motivation
einher, autonomieunterstützendes Verhalten mit besserem Zeiteinsatz und mehr Ausdauer.
Die engmaschige Kontrolle, in die euch die Situation drängt, ist deshalb nicht nur
anstrengend, sie arbeitet gegen das Ziel. Sie ist aber auch keine Schuld: Sie entsteht,
weil sonst nichts trägt.

### Korrektur zu Belohnungen

In der ersten Fassung habe ich Belohnungen pauschal abgeraten, gestützt auf die
Metaanalyse von Deci, Koestner und Ryan. Dieser Befund gilt weiterhin, betrifft aber
das freiwillige Interesse an einer Tätigkeit, die jemand ohnehin gern tut. Hier geht es
um eine fehlende Fertigkeit, nicht um ein fehlendes Interesse. Die Trainings, die bei
dieser Ausgangslage wirken, arbeiten anfangs mit kleinen, sofortigen und verlässlichen
Verstärkern und bauen sie später ab.

Die Unterscheidung ist praktisch: kleine Anerkennung für die Routine (eingepackt,
notiert, abgegeben), nichts für Verständnis oder Noten, nichts, was mit dem Bruder
verglichen wird, und von Anfang an verabredet, dass es später ausläuft.

## Leitlinien

1. Die App erinnert, nicht die Eltern. Das ist der eigentliche Zweck.
2. Unterstützung im Moment des Vergessens, nicht im Rückblick.
3. Eine Mitteilung, ein Tippen, eine Seite. Was dort steht, muss ohne Navigation
   erledigt werden können. Jede zusätzliche Entscheidung kostet in dieser Lage mehr,
   als sie bringt.
4. Die Einstiegsseite richtet sich nach der Tageszeit: nach dem Unterricht das
   Notieren, abends das Packen und der Tagesabschluss, morgens das Fehlende. Wer die
   App öffnet, sieht das Anliegen des Moments, nicht eine Übersicht.
5. Der Abbau der Unterstützung dauert Monate und wird verabredet, nicht erschlichen.
6. Kein Vergleich zwischen den Geschwistern, an keiner Stelle.
7. Rückschläge kosten nichts. Keine Nullpunkte, keine gerissenen Serien.
8. Die App stellt Daten bereit und verhängt nichts. Strafen bleiben Sache der Familie
   und der Schule.

## Vorgehen

### Stufe 0: Zugang, diese Woche

Die Kinder nutzen das Schul-Cockpit künftig in der Home-Assistant-App statt als
Web-App vom Startbildschirm. Die Home-Assistant-App wird in der Bildschirmzeit unter
„Immer erlaubt" eingetragen. Danach ist zu prüfen, ob die App während einer Auszeit
wirklich erreichbar bleibt; erst diese Prüfung entscheidet, ob der Weg trägt.

Anschließend je Gerät eine Testnachricht mit Taste, und zwar zu einer Zeit, die niemanden
stört. Ohne diesen Nachweis ist jede weitere Stufe Spekulation.

Aufwand in der App: gering. Der Erinnerungsdienst berechnet die offenen Punkte bereits;
zu ersetzen ist der Versandweg.

### Stufe 1: Der Abend

Eine Mitteilung zu einer festen Zeit am Abend, die beim Antippen den Tagesabschluss
öffnet: die Punkte für morgen aus der vorhandenen Packliste und die fälligen Aufgaben,
je Zeile eine große Taste, sonst nichts auf der Seite.

Wer am Abend nicht abgeschlossen hat, bekommt am Morgen vor dem Aufbruch eine zweite,
kürzere Mitteilung. Wer abgeschlossen hat, bekommt sie nicht.

### Stufe 2: Der Moment nach dem Unterricht

Das wiederkehrende Grundproblem ist nicht nur das Vergessen der Erledigung, sondern
dass die Aufgabe gar nicht erst festgehalten wird. Nach der letzten Stunde eine
Mitteilung mit einer einzigen Frage: Gibt es Aufgaben, die noch nicht in der App
stehen? Ein Tippen öffnet eine Seite mit genau zwei Möglichkeiten, Kamera oder „nichts
Neues". Die Materialablage wertet das Foto bereits
heute aus und ordnet es Fach und Aufgabe zu.

### Stufe 3: Die Schule als Quelle statt als Anrufer

Eine tägliche Rückmeldung zu wenigen, vorher vereinbarten Punkten, zunächst für ein
einziges Fach oder eine einzige Lehrkraft, dort wo es am meisten weh tut. Die App hält
sie fest und zeigt die Woche. Ob das gelingt, hängt an der Schule, nicht an der
Software; deshalb steht es nach den Stufen, die ihr allein umsetzen könnt.

### Stufe 4: Übergabe

Erst wenn die Fehlerquote gesunken ist, wird die Unterstützung schrittweise
zurückgenommen: erst die zweite Mitteilung am Morgen, dann die abendliche, zuletzt die
feste Zeit zugunsten eines eigenen Plans. Jede Stufe wird beantragt, und ein
Rückschritt ist verabredet, nicht beschämend. Gerechnet wird in Monaten.

## Was das für die Eltern heißt

Die tägliche Nachfrage soll nicht aus Prinzip entfallen, sondern weil etwas anderes sie
ersetzt. Solange Stufe 0 und 1 nicht nachweislich laufen, wäre ein Rückzug fahrlässig.
Sobald sie laufen, ist der Rückzug die eigentliche Maßnahme.

Gegenüber der Schule ändert sich die Lage mit Stufe 3 am deutlichsten: Es gibt dann
eine belegte, gemeinsame Routine statt des Vorwurfs, zu Hause geschehe nichts.

## Offene Entscheidungen

Ob die Web-App auf den Kindergeräten entfernt wird oder als Notweg bestehen bleibt. Ob
die Einstiegsseite fest nach Tageszeit wechselt oder nur die oberste Karte tauscht. Zu
welcher Uhrzeit die abendliche Mitteilung kommt und wer sie festlegt. Ob es eine kleine
Anerkennung für die Routine gibt, welche, und wann sie ausläuft. Ob und mit welcher
Lehrkraft eine tägliche Rückmeldung versucht wird. Ob eine fachliche Abklärung gesucht
wird; davon hängt keine der oben genannten Stufen ab.

## Quellen

Die folgenden Arbeiten stützen einzelne Aussagen, nicht das Gesamtkonzept.

- [HOPS: randomisierte Studie mit Schulpersonal](https://pubmed.ncbi.nlm.nih.gov/25355991/), School Psychology Review.
- [Größere randomisierte Studie zu zwei kurzen Hausaufgaben- und Organisationsprogrammen](https://pubmed.ncbi.nlm.nih.gov/29172596/).
- [Anleitung zur täglichen Rückmeldekarte](https://ccf.fiu.edu/research/_assets/how_to_establish_a_school_drc.pdf), Center for Children and Families, Florida International University.
- [Dieselbe Anleitung im Toolkit der American Academy of Pediatrics](https://publications.aap.org/toolkits/book/337/chapter/5733253/How-to-Establish-a-School-Home-Daily-Report-Card).
- [Metaanalyse zu Wenn-Dann-Plänen über 642 Prüfungen](https://www.tandfonline.com/doi/abs/10.1080/10463283.2024.2334563).
- [Gollwitzer und Sheeran zu Implementation Intentions](https://cancercontrol.cancer.gov/sites/default/files/2020-06/goal_intent_attain.pdf).
- [Deci, Koestner und Ryan zu Belohnungen und intrinsischer Motivation](https://home.ubalt.edu/tmitch/642/articles%20syllabus/Deci%20Koestner%20Ryan%20meta%20IM%20psy%20bull%2099.pdf).
- [Reaktionen Jugendlicher auf elterliche Regulation](https://iris.unil.ch/bitstreams/d9d2552e-78aa-43d1-98d6-78e30999266a/download).
- [Autonomieunterstützende Elternbegleitung bei Hausaufgaben](https://link.springer.com/article/10.1007/s12310-026-09856-4).
- [Entwicklung des prospektiven Erinnerns im Jugendalter](https://pmc.ncbi.nlm.nih.gov/articles/PMC11521922/).
- [Aktionstasten in Mitteilungen der Home-Assistant-App](https://companion.home-assistant.io/docs/notifications/actionable-notifications/).
- [Geräte ohne iOS 26](https://www.techradar.com/phones/ios/ios-26-compatibility-does-your-iphone-support-it-heres-the-full-list-of-supported-devices).

Zu Streaks und zu natürlichen Konsequenzen liegen keine vergleichbar belastbaren
Quellen vor; beides bleibt außen vor.
