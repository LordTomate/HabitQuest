# HabitQuest

Software-Entwurf, Coding-Guidelines und GitHub-Workflow

## Inhaltsverzeichnis

- [Setup](#setup)
1. [Konzeptionelle Beschreibung des Use-Cases](#1-konzeptionelle-beschreibung-des-use-cases)
   1. [Geplante Architektur und Klassen](#11-geplante-architektur-und-klassen)
   2. [Interaktion der Objekte](#12-interaktion-der-objekte)
   3. [Geplante Attribute und Methoden](#13-geplante-attribute-und-methoden)
2. [Coding-Guidelines](#2-coding-guidelines)
3. [Aufwandsschätzung](#3-aufwandsschätzung)
4. [Geplante Implementierung und Versionsverwaltung](#4-geplante-implementierung-und-versionsverwaltung)
   1. [Git-Workflow: dev / main](#41-git-workflow-dev--main)
   2. [Continuous Integration (CI)](#42-continuous-integration-ci)
5. [Fazit & Ausblick (Limitationen)](#5-fazit--ausblick-limitationen)

## Setup

Bevor der Code ausgeführt werden kann, sind folgende Schritte notwendig:

1. Virtuelle Umgebung erstellen und aktivieren:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Tkinter installieren. Es wird für die GUI benötigt, ist aber ein Systempaket und kein
   Python-Paket, das über pip installiert werden könnte:

   ```bash
   sudo apt-get install -y python3-tk
   ```

3. Anwendung starten:

   ```bash
   python ui.py
   ```

4. Tests ausführen:

   ```bash
   python -m unittest test_habit_quest.py
   ```

## 1 Konzeptionelle Beschreibung des Use-Cases

Das Ziel von HabitQuest ist es, sich täglich wiederholende Abläufe (Routinen) zu gamifizieren.
Dadurch soll ein Weg geschaffen werden, sich selbst durch spielerische Elemente wie Level und
Erfahrungspunkte (XP) langfristig zu motivieren.

In der Praxis sieht das so aus: Zunächst erstellt man als Nutzer mehrere Routinen (z. B. für
einen Trainingsplan wie Push, Pull und Legs). Öffnet man die Anwendung täglich, werden automatisch
die Aufgaben angezeigt, die am heutigen Zyklustag anstehen. Hakt man eine Aufgabe ab, gibt es
Erfahrungspunkte. Schafft man es, alle Aufgaben an einem Tag zu erledigen, steigt die „Streak"
(die Serie) an. Im Laufe der Zeit rotiert der Plan automatisch weiter, sodass man sich nicht jeden
Tag manuell überlegen muss, was eigentlich ansteht.

### 1.1 Geplante Architektur und Klassen

Bei der Konzeption ist es wichtig, dass das Softwaredesign modular bleibt. Daher wird die
grafische Benutzeroberfläche strikt von den eigentlichen Daten und Berechnungen getrennt:

- **Datenmodelle (`models.py`)**: Die Klassen `Routine`, `Category` und `UserProfile` werden als
  Python `dataclasses` umgesetzt. Das hält das Zustandsmodell übersichtlich und erspart viel
  redundanten Code (Boilerplate). `Routine` bündelt beispielsweise alle Infos zu einem
  Trainingsplan, damit sich diese Logik nicht in die UI einschleicht.
- **Geschäftslogik (`engine.py`)**: Das Herzstück der Architektur bildet die `HabitQuestEngine`.
  Sie ist für das Speichern und Laden der Daten sowie für die Mathematik hinter den Streaks und
  XP zuständig. Diese Trennung ist praktisch, weil sich die Engine so später leicht automatisiert
  testen lässt, ohne dass die GUI geladen werden muss. Abgeschlossene Aufgaben werden als `set`
  gespeichert, um effizient prüfen zu können, ob eine Aufgabe schon erledigt wurde, und doppelte
  Einträge von vornherein zu verhindern.
- **Benutzeroberfläche (`ui.py`)**: Die `HabitQuestApp` zeichnet lediglich das Fenster, fängt
  Mausklicks ab und reicht diese Befehle an die Engine weiter. Sie merkt sich selbst keine
  Spieldaten.

**Warum Tkinter?** Als UI-Framework wird Tkinter genutzt. Das passt gut, da es direkt in der
Python-Standardbibliothek enthalten ist, keine externen Installationen erfordert und völlig
ausreicht, um saubere Architektur-Konzepte wie MVC zu demonstrieren.

#### UML-Klassendiagramm der geplanten OOP-Architektur

```
HabitQuestEngine
  + profile: UserProfile
  + routines: dict
  + completed_today: set
  + get_default_data()
  + xp_for_level(level: int)
  + total_xp_to_reach_level(level: int)
  + check_new_day()
  + load_today_completions()
  + calc_xp_reward()
  + toggle_task(task_key: str)
  + save_data()
  + load_data()
  + get_all_today_task_keys()
  + claim_rest_day()

HabitQuestApp
  + engine: HabitQuestEngine
  + refresh_ui()
  + rebuild_tasks()

UserProfile
  + xp: int
  + level: int
  + streak: int
  + last_checked_date: str
  + last_all_done_date: str
  + last_completed_date: str
  + history: list
  + from_dict(data)

Routine
  + name: str
  + categories: list
  + day_index: int
  + paused: bool
  + to_dict()
  + from_dict(name, data)
```

Beziehungen: `HabitQuestApp` **nutzt** `HabitQuestEngine` (1:1); `HabitQuestEngine` **verwaltet**
`Routine` (1:*) und **besitzt** `UserProfile` (1:1).

### 1.2 Interaktion der Objekte

Die Architektur orientiert sich an einer strikten Trennung von Präsentation, Geschäftslogik und
Datenmodell. Das Zusammenspiel ist wie folgt geplant:

1. **Initialisierung**: Startet man die App, wird zuerst in `habit_quest.py` die
   `HabitQuestEngine` ins Leben gerufen, die sich über `load_data()` die Speicherstände holt. Erst
   danach startet die `HabitQuestApp` und bekommt die Engine übergeben.
2. **Echtzeit-Synchronisierung**: Die Methode `check_new_day()` prüft, wie viele Tage seit dem
   letzten Öffnen vergangen sind, und schiebt den Zyklus der Routinen entsprechend weiter.
3. **Event-Handling**: Klickt man auf eine Aufgabe, rechnet die UI nicht selbst, sondern delegiert
   dies an `engine.toggle_task(key)`.
4. **Statusänderung und Persistenz**: In `toggle_task()` ändert sich der Status, XP werden
   berechnet und am Ende wird sofort `save_data()` ausgelöst, um den Fortschritt zu sichern. Die
   UI zeichnet sich danach per `refresh_ui()` mit den neuen Werten neu.

Durch diesen Aufbau bleibt die Benutzeroberfläche komplett unabhängig. Das ist besonders
praktisch, weil sich so später problemlos die XP-Formel oder die Streak-Logik anpassen lässt, ohne
auch nur eine Zeile UI-Code anfassen zu müssen.

### 1.3 Geplante Attribute und Methoden

Hier ist ein kurzer Überblick über die vorgesehenen Bausteine, die den Fortschritt speichern und
verarbeiten:

**Wichtige Attribute (`UserProfile` & Engine)**

- `profile.xp`: Speichert die gesamten gesammelten Erfahrungspunkte.
- `profile.level`: Das aktuell erreichte Level.
- `profile.streak`: Wie viele Tage am Stück man diszipliniert war.
- `profile.last_checked_date`: Merkt sich, wann die App das letzte Mal gestartet wurde (wichtig
  für die Berechnung verpasster Tage).
- `completed_today`: Ein `set()` in der Engine, das die IDs der heute erledigten Aufgaben
  zwischenspeichert.

**Wichtige Methoden (`HabitQuestEngine`)**

- `xp_for_level(level)`: Eine Hilfsmethode, die berechnet, wie viele XP man für das nächste Level
  braucht.
- `check_new_day()`: Berechnet die Differenz in Tagen und verschiebt die Workout-Zyklen.
- `toggle_task(task_key)`: Ändert den Status einer Aufgabe (abgehakt / offen), berechnet XP und
  das Level.
- `save_data()` / `load_data()`: Kümmert sich um das Speichern. Das Schreiben in die JSON-Datei
  wird atomar (über eine temporäre Datei und `os.replace`) umgesetzt, damit der Speicherstand bei
  einem Programmabbruch nicht kaputtgeht.
- `claim_rest_day()`: Eine Funktion, mit der man sich einen Pausentag nehmen kann, ohne dass die
  Streak abreißt.

## 2 Coding-Guidelines

Damit der Code auch auf Dauer gut lesbar und wartbar bleibt, orientiert sich das Projekt an
folgenden Best Practices:

- **PEP 8 & DRY**: Einheitliche Namensgebung (snake_case für Variablen, PascalCase für Klassen)
  und Auslagerung doppelten Codes (WET-Prinzip vermeiden).
- **Dokumentation & Typisierung**: Alle öffentlichen Methoden werden mit Type Hints ausgestattet.
  Außerdem werden die Klassen mit Docstrings nach PEP 257 erklärt.
- **Robuste Validierung**: Werden Funktionen mit völlig falschen Parametern aufgerufen, sollen sie
  gezielt `ValueError` oder `TypeError` werfen.
- **SOLID-Architektur**: Ausrichtung am Single Responsibility Principle (SRP). Jede Klasse soll
  genau einen Zuständigkeitsbereich haben.
- **UI/UX-Trennung**: Wie schon erwähnt, wird die Darstellung der Fenster strikt von der Logik
  getrennt.

## 3 Aufwandsschätzung

Für die Umsetzung des Projekts bis zum finalen MVP-Status wird in etwa dieser zeitliche Aufwand
geschätzt:

| Phase / Modul   | Stunden | Details                                                              |
| ---------------- | ------- | --------------------------------------------------------------------- |
| Konzeption        | 3h      | Entwurf des Datenmodells, der Zyklen und der XP-Formeln.               |
| Implementierung   | 8h      | Programmieren der Geschäftslogik, des Speichersystems und der Berechnungen. |
| GUI               | 4h      | Aufbau des Fensters, Scrollbars und Styling in Tkinter.                |
| Tests             | 3h      | Schreiben von Modultests (Unittests), um die Logik abzusichern.        |
| Dokumentation     | 2h      | Erstellung und Layout dieses Konzeptdokuments.                         |
| **Gesamt**        | **20h** |                                                                         |

## 4 Geplante Implementierung und Versionsverwaltung

Um strukturiert arbeiten zu können und keine Code-Stände zu verlieren, wird ein klassischer
Git-Workflow mit den Branches `dev` und `main` genutzt.

### 4.1 Git-Workflow: dev / main

Da das Projekt allein entwickelt wird, wird auf komplexe Feature-Branches verzichtet und
stattdessen mit einem schlanken `dev`/`main`-Workflow gearbeitet:

- **dev-Branch**: Hier findet die eigentliche Arbeit statt. Neue Features oder Fixes wandern
  direkt dorthin.
- **main-Branch**: Hier liegt nur die absolut stabile, lauffähige Version. Erst wenn auf `dev`
  alles funktioniert, werden die Änderungen nach `main` gemerged.
- **Commit-Messages**: Änderungen werden über aussagekräftige Commit-Nachrichten gut
  nachvollziehbar dokumentiert.

### 4.2 Continuous Integration (CI)

Damit beim Zusammenführen der Branches keine Fehler entstehen, laufen die Testfälle automatisch im
Hintergrund ab:

1. Neue Funktionen werden direkt mit Unittests in `test_habit_quest.py` abgedeckt.
2. Bei jedem Push auf GitHub startet automatisch eine Action, die alle Tests durchlaufen lässt:

   ```bash
   python3 -m unittest test_habit_quest.py
   ```

Das gibt die Sicherheit, dass Änderungen keine bestehenden Berechnungen unbeabsichtigt
beeinträchtigen.

## 5 Fazit & Ausblick (Limitationen)

Dieses Konzept für HabitQuest erfüllt als Studienprojekt genau seinen Zweck: Es skizziert eine
saubere Softwarearchitektur, trennt Logik von UI und plant die praktische Umsetzung von
OOP-Prinzipien detailliert durch.

Natürlich bringt die Planung für ein Projekt dieser Größenordnung auch gewisse Limitationen mit
sich. Im ersten Wurf werden alle Daten lokal in einer einfachen JSON-Datei und nur für einen
einzelnen Nutzer gespeichert. Für einen potenziellen Einsatz in der Zukunft wäre es spannend, das
Projekt dahingehend zu erweitern, dass Profile in einer echten SQLite-Datenbank abgelegt werden.
Auch Themen wie Zeitzonen-Wechsel bei Reisen (wenn man z. B. einen Tag „verliert") deckt die
Basisversion noch nicht ab. Solche Features wären großartige Erweiterungen für eine künftige
Version 2.0.
