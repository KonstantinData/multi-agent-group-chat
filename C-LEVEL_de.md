# Liquisto Department Runtime — Executive Overview

## Was ist das?

Ein KI-gestütztes Recherchesystem, das automatisiert Pre-Meeting-Briefings
für Liquisto-Kundengespräche erstellt. Eingabe: Firmenname und Webdomain.
Ergebnis: ein strukturiertes Briefing-Dokument als PDF (Deutsch + Englisch),
das in wenigen Minuten liefert, wofür ein Analyst mehrere Stunden braucht.

## Welches Problem löst es?

Vor jedem Erstgespräch mit einem potenziellen Kunden muss ein Liquisto-Kollege
verstehen:

- Was macht das Unternehmen, was verkauft oder produziert es?
- Gibt es wirtschaftlichen Druck, Überbestände, Restrukturierung?
- Welche Güter, Materialien oder Assets sind sichtbar?
- Wer sind die Wettbewerber und potenziellen Abnehmer?
- Welche konkreten Ansprechpartner gibt es bei den Abnehmern?
- Wo liegt die plausibelste Liquisto-Opportunity — Bestandsmonetarisierung,
  Repurposing/Kreislaufwirtschaft, oder Analytics/Entscheidungsunterstützung?
- Welche Verhandlungshebel und nächsten Schritte ergeben sich?

Dieses System beantwortet alle diese Fragen automatisch und liefert ein
druckfertiges Briefing mit Quellenangaben.

## Wie funktioniert es?

Das System arbeitet wie eine interne Research-Abteilung mit spezialisierten
Teams. Jedes Team hat einen Leiter, einen Researcher, einen Kritiker und bei
Bedarf weitere Spezialisten. Die Teams arbeiten nacheinander:

```
Eingabe: Firmenname + Webdomain
    │
    ▼
┌─────────────────────────────────────────────┐
│  Supervisor — Auftragsklärung & Steuerung   │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐   ┌─────────┐   ┌─────────┐
│Company │   │ Market  │   │ Buyer   │
│  Team  │   │  Team   │   │  Team   │
└───┬────┘   └────┬────┘   └────┬────┘
    │              │              │
    │              │              ▼
    │              │        ┌──────────┐
    │              │        │ Contact  │
    │              │        │  Team    │
    │              │        └────┬─────┘
    ▼              ▼             ▼
┌─────────────────────────────────────────────┐
│  Strategische Synthese — Gesamtbewertung    │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Report Writer — PDF-Briefing (DE + EN)     │
└─────────────────────────────────────────────┘
```

### Die vier Research-Teams

| Team | Aufgabe |
|------|---------|
| **Company** | Unternehmensprofil, Produkte, wirtschaftliche Lage, Asset-Scope |
| **Market** | Marktsituation, Nachfragetrends, Repurposing-Potenzial, Analytics-Signale |
| **Buyer** | Wettbewerber, Abnehmer, Monetarisierungs- und Redeployment-Pfade |
| **Contact** | Ansprechpartner bei priorisierten Abnehmerfirmen mit Outreach-Vorschlägen |

Jedes Team recherchiert eigenständig im Internet, bewertet die Ergebnisse
intern durch einen Kritiker, und liefert ein geprüftes Ergebnispaket ab.
Der Supervisor steuert den Ablauf, interpretiert aber keine Fachinhalte.

### Strategische Synthese

Nach Abschluss aller Teams bewertet eine Synthese-Einheit die Ergebnisse
übergreifend: Wo liegt die stärkste Liquisto-Opportunity? Welche Risiken
bestehen? Welche konkreten nächsten Schritte sind sinnvoll?

## Was kommt am Ende raus?

### PDF-Briefing (Deutsch + Englisch)

Ein professionelles Dokument mit:

- **Key Facts** — Branche, Umsatz, Mitarbeiter, Standort
- **Executive Summary** — Gesamteinschätzung in einem Absatz
- **Liquisto Opportunity** — Bewertung der drei Servicebereiche (Bestandsmonetarisierung, Repurposing, Analytics) mit Relevanz-Einstufung
- **Unternehmensprofil** — Produkte, Assets, wirtschaftliche Lage
- **Markt- & Nachfragekontext** — Trends, Überkapazitäten, Nachfrageausblick
- **Käufer- & Redeployment-Landschaft** — Wettbewerber, Abnehmer, Dienstleister, branchenübergreifende Käufer mit Relevanz-Bewertung
- **Kontakt-Intelligence** — Priorisierte Ansprechpartner mit Funktion, Seniorität und konkretem Outreach-Vorschlag
- **Risiken & nächste Schritte**
- **Quellenanhang**

### Qualitätsbewertung

Jedes Briefing enthält einen Research-Readiness-Score (0–100), der anzeigt,
wie belastbar die Ergebnisse sind. Briefings unter einem Schwellenwert werden
als „nicht verwendbar" markiert.

### Follow-up-Fragen

Nach einem abgeschlossenen Run können über die Benutzeroberfläche gezielte
Nachfragen gestellt werden. Das System routet die Frage automatisch an das
zuständige Team und beantwortet sie aus dem gespeicherten Recherche-Kontext.

## Benutzeroberfläche

Eine Web-Oberfläche (Streamlit) ermöglicht:

- Neuen Run starten (Firmenname + Domain eingeben)
- Live-Fortschritt über alle Pipeline-Schritte verfolgen
- Abgeschlossene Runs laden und durchsuchen
- Ergebnisse pro Team einsehen
- Synthese und Report-Paket prüfen
- Follow-up-Fragen stellen
- PDF-Briefings herunterladen (DE + EN)

## Kosten pro Run

Das System nutzt OpenAI-Sprachmodelle (GPT-4.1 und GPT-4.1-mini).
Die Kosten pro Briefing hängen von der Komplexität des Zielunternehmens ab.

| Modell | Rolle | Preis (Input / Output pro 1M Tokens) |
|--------|-------|--------------------------------------|
| gpt-4.1 | Teamleiter, Kritiker, Richter, Synthese | $2.00 / $8.00 |
| gpt-4.1-mini | Researcher, Coding-Spezialisten, Report Writer | $0.40 / $1.60 |

Typische Kosten pro vollständigem Briefing: **$0.10 – $0.80 USD**,
abhängig von Recherche-Tiefe und Anzahl der Revisionsschleifen.
Die tatsächlichen Kosten werden pro Run erfasst und in der UI angezeigt.

## Lernfähigkeit

Das System speichert nach jedem erfolgreichen Run wiederverwendbare
Arbeitsmuster — z.B. welche Suchstrategien gut funktioniert haben oder
welche Review-Heuristiken zu besseren Ergebnissen geführt haben.
Es speichert **keine** unverifizierten Unternehmensfakten als dauerhafte
Wahrheit.

## Technische Voraussetzungen

- Python 3.11+
- OpenAI API Key
- Keine eigene Infrastruktur nötig — läuft lokal auf einem Laptop oder Server
- Keine Datenbank — alle Ergebnisse werden als JSON-Dateien gespeichert

## Status

Das System ist funktionsfähig und produziert vollständige Briefings.
Jeder Run wird unter `artifacts/runs/<run_id>/` archiviert und ist
jederzeit nachvollziehbar.
