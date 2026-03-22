# Implementation Plan — Architektur-Erweiterung

Besprochene Änderungen:
- Jedes Department produziert einen vollständigen **Domain Report Segment** (nicht nur Rohdaten)
- Neues **Contact Intelligence Department** (nach Buyer Department)
- **Strategic Synthesis Department** als echte AG2-Gruppe (ersetzt Python-Funktionen)
- **Unified Question Router** auf Supervisor-Ebene (für Synthesis-Rückfragen UND UI-Follow-up)
- **Department Mini-Run** für gezielte Nachschärfungen

---

## Phase 1 — Schema Foundation
> Neue Pydantic-Modelle, auf die alle weiteren Phasen aufbauen

- [x] `ContactPerson` Modell (`name, firma, rolle_titel, funktion, senioritaet, standort, quelle, confidence, relevance_reason, suggested_outreach_angle`)
- [x] `ContactIntelligenceSection` Modell (`contacts, prioritized_contacts, coverage_summary, narrative_summary, open_questions, sources`)
- [x] `DomainReportSegment` Modell (gemeinsames Basis-Schema für alle Department Reports: `narrative_summary, confidence, key_findings, open_questions, sources`)
- [x] `BackRequest` Modell (`department, type: clarify|strengthen|expand|resolve_contradiction, subject, context`)
- [x] `DepartmentPackage` um `report_segment: DomainReportSegment` erweitern
- [x] `PipelineData` um `contact_intelligence: ContactIntelligenceSection` erweitern
- [x] `validate_pipeline_data` und `empty_pipeline_data` aktualisieren

**Datei:** `src/models/schemas.py`

---

## Phase 2 — Contact Intelligence Department
> Neues Department, gleiches AG2-Muster wie Company/Market/Buyer

- [x] Tasks in `STANDARD_TASK_BACKLOG` hinzufügen (`contact_discovery`, `contact_qualification`) — `assignee: "ContactDepartment"`
- [x] `ContactDepartment` in `DEPARTMENT_RESEARCHERS` registrieren — `task_router.py`
- [x] Department-Konfiguration in `lead.py` hinzufügen: `_DEPARTMENT_PREFIX`, `_VISUAL_FOCUS`, `_CLASSIFICATION_FRAME`, `_INVESTIGATION_FOCUS`, `_TASK_GUIDANCE_TEMPLATES`
- [x] Agent Specs in `definitions.py` registrieren (`ContactLead`, `ContactResearcher`, `ContactCritic`, `ContactJudge`, `ContactCodingSpecialist`, `ContactDepartment`)
- [x] `create_runtime_agents()` in `definitions.py` erweitern
- [x] `supervisor_loop.py`: Contact Intelligence sequenziell nach Buyer Department ausführen (benötigt Buyer Output als Kontext)

**Dateien:** `src/app/use_cases.py`, `src/orchestration/task_router.py`, `src/agents/lead.py`, `src/agents/definitions.py`, `src/orchestration/supervisor_loop.py`

---

## Phase 3 — Department Report Segments
> Jeder Department Lead schreibt am Ende einen strukturierten Report-Abschnitt

- [x] `finalize_package()` in `lead.py` erweitern: produziert `DomainReportSegment` mit `narrative_summary` (vom Lead-LLM geschrieben), `key_findings`, `confidence`
- [x] `DepartmentPackage` trägt jetzt `report_segment` im Output
- [x] `DepartmentRuntime.run()` gibt `report_segment` im Package mit zurück

**Datei:** `src/agents/lead.py`

---

## Phase 4 — Strategic Synthesis Department (AG2)
> Ersetzt die Python-Funktionen `build_synthesis_from_memory`, `build_quality_review`

- [x] Neue Datei `src/agents/synthesis_department.py` mit AG2 GroupChat:
  - `SynthesisLead` — orchestriert, hat Tools: `read_report_segment`, `request_department_followup`, `finalize_synthesis`
  - `SynthesisAnalyst` — führt die Domänen zusammen
  - `SynthesisCritic` — bewertet Vollständigkeit und Widersprüche
  - `SynthesisJudge` — Entscheider wenn Critic ablehnt
- [x] Tool `read_report_segment(department)` — liest `report_segment` aus dem Department Package
- [x] Tool `request_department_followup(department, type, subject, context)` — delegiert an Question Router
- [x] Tool `finalize_synthesis(summary)` — produziert `SynthesisReport` → TERMINATE
- [x] Tasks in `STANDARD_TASK_BACKLOG`: `liquisto_opportunity_assessment`, `negotiation_relevance` → `assignee` von `CrossDomainStrategicAnalyst` auf `SynthesisDepartment` ändern
- [x] Agent Specs in `definitions.py` registrieren

**Dateien:** `src/agents/synthesis_department.py` (neu), `src/app/use_cases.py`, `src/agents/definitions.py`

---

## Phase 5 — Unified Question Router
> Ein Mechanismus für Synthesis-Rückfragen UND UI-Follow-up

- [x] `route_follow_up()` in `supervisor.py` auf alle Departments erweitern (inkl. `ContactDepartment`, `SynthesisDepartment`)
- [x] `route_question(question, run_id, source: "synthesis"|"user_ui")` als neue Methode auf `SupervisorAgent`
- [x] `follow_up.py`: Handler für `ContactDepartment` hinzufügen
- [x] `follow_up.py`: Handler für `SynthesisDepartment` hinzufügen

**Dateien:** `src/agents/supervisor.py`, `src/orchestration/follow_up.py`

---

## Phase 6 — Department Mini-Run
> Departments können gezielt für Nachschärfungen reaktiviert werden

- [x] `run_followup(question, context, brief, memory_store, on_message)` auf `DepartmentRuntime` hinzufügen
- [x] `DepartmentLeadAgent.run_followup()` implementieren: single-task Assignment aus der Frage ableiten, fokussierten GroupChat starten, ergänztes `report_segment` zurückgeben
- [x] `SynthesisDepartment` ruft Mini-Run via `request_department_followup` Tool auf

**Dateien:** `src/orchestration/department_runtime.py`, `src/agents/lead.py`

---

## Phase 7 — Pipeline Integration
> Alle Departments + Synthesis korrekt verdrahtet

- [x] `supervisor_loop.py`: Contact Intelligence nach Buyer Department einfügen
- [x] `supervisor_loop.py`: `SynthesisDepartment` als AG2-Run statt Python-Funktionen
- [x] `pipeline_runner.py`: `build_synthesis_from_memory`, `build_quality_review` entfernen, durch SynthesisDepartment-Output ersetzen
- [x] `definitions.py`: `SynthesisDepartment` in `create_runtime_agents()` eintragen
- [x] `memory/consolidation.py`: Contact Intelligence und Synthesis Department Patterns hinzufügen

**Dateien:** `src/orchestration/supervisor_loop.py`, `src/pipeline_runner.py`, `src/agents/definitions.py`, `src/memory/consolidation.py`

---

## Phase 8 — UI Follow-up
> Mitarbeiter kann via Run ID Folgefragen stellen

- [x] `ui/app.py`: Run ID Eingabe + Follow-up Frage Formular
- [x] `ui/app.py`: Antwort-Anzeige mit Department-Attribution und Evidence
- [x] `ui/app.py`: Contact Intelligence Ergebnisse in eigener Tab-Sektion anzeigen

**Datei:** `ui/app.py`

---

## Legende

| Symbol | Bedeutung |
|---|---|
| `[ ]` | Ausstehend |
| `[x]` | Abgeschlossen |
| `[~]` | In Arbeit |
| `[!]` | Blockiert / Problem |
