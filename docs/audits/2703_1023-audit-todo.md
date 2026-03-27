# 2703_1023 Audit TODO

**Bezug:** Restpunkte aus `2503_0943-audit-todo.md` + Findings aus `2703_1023-audit.md` + Run-Analyse  
**Zweck:** Umsetzungsdatei fuer verbleibende Architekturdefekte und Haertungen  
**Prinzip:** Jedes Finding hat eine klare Patch-Sequenz. Keine Umsetzung ohne Review.

---

## Statusuebersicht

| ID | Thema | Severity | Prioritaet | Status |
|---|---|---:|---:|---|
| P0-1 | `department_packages` Shape eindeutig machen | kritisch | P0 | Offen |
| P0-2 | Synthesis-Consumption fixen (report_segment, segments, confidences) | kritisch | P0 | Offen |
| P0-3 | Regressionstests auf Envelope-Shape | hoch | P0 | Offen |
| P0-4 | `build_report_package()` an Envelope-Semantik anpassen | hoch | P0 | Offen |
| P1-1 | `needs_contract_review` autoritativ verdrahten | mittel | P1 | Offen |
| P1-2 | Synthesis-Rollen in ROLE_MODEL_DEFAULTS eintragen | mittel | P1 | Offen |
| P1-3 | `input_artifacts` runtime-wirksam machen oder entfernen | mittel | P1 | Offen |
| P1-4 | `current_payload` Overwrite mit Regressionsschutz absichern | niedrig-mittel | P1 | Offen |
| P1-5 | Preflight-Ziel sauber trennen (core vs. runtime readiness) | niedrig-mittel | P1 | Offen |
| P2-1 | `CrossDomainStrategicAnalyst` vollstaendig entfernen | niedrig-mittel | P2 | Offen |
| P2-2 | Blocked-Artifact als Pydantic-Modell formalisieren | niedrig | P2 | Offen |
| P2-3 | DAG-Linter Phase-Kompatibilitaet pruefen | niedrig | P2 | Offen |
| P2-4 | Synthesis Extra-Felder bereinigen (Schema != Agent-Output) | niedrig | P2 | Offen |
| P2-5 | `_synthesis_admission` Marker durch Envelope-Konsum ersetzen | niedrig | P2 | Offen |
| P2-6 | Kanonische Dedup-Keys / Merge-Policy / StrEnum / mypy / CI | niedrig | P2 | Offen |

---

## P0-1 — `department_packages` Shape eindeutig machen

**Severity:** kritisch  
**Prioritaet:** P0

### Finding

`department_packages` hat je nach Kontext eine andere Shape:

| Stelle | Shape | Erwartet |
|--------|-------|----------|
| `supervisor_loop.py` | Admission-Envelope `{admission, raw_package, admitted_payload}` | Envelope |
| `ShortTermMemoryStore.store_department_package()` | Raw department package (via `lead.py`) | Raw |
| `follow_up.py` | Liest aus Run-Brain → raw | Raw |
| `synthesis_department.py` | Bekommt Envelopes, liest aber `package.get("report_segment")` | Raw erwartet, Envelope geliefert |
| `build_report_package()` | Liest `package.get("visual_focus")` | Raw erwartet, Envelope geliefert |

Das ist der zentrale Architekturdefekt: gleicher Name, unterschiedliche Shapes, unterschiedliche Semantik.

### Patch-Sequenz

1. **Entscheidung treffen:** Zwei getrennte Namen einfuehren:
   - `admission_envelopes` — Supervisor-Loop-Ergebnis mit Admission-Metadata
   - `raw_department_packages` — Department-Ergebnis ohne Admission-Wrapper (fuer Memory, Follow-up)
2. `supervisor_loop.py`: Return-Typ und interne Variable umbenennen
3. `pipeline_runner.py`: Beide Varianten korrekt konsumieren
4. `synthesis_department.py`: Explizit `raw_package` aus Envelope extrahieren
5. `build_report_package()`: Explizit `raw_package` oder `admitted_payload` lesen
6. `ShortTermMemoryStore`: Weiterhin raw Packages speichern (kein Envelope im Run-Brain)
7. Tests: Shape-Assertions fuer beide Varianten

### Akzeptanzkriterien
- Kein Code liest `department_packages` ohne zu wissen ob es Envelope oder Raw ist
- Zwei klar getrennte Variablen/Parameter
- Synthesis und Report lesen korrekt

---

## P0-2 — Synthesis-Consumption fixen

**Severity:** kritisch  
**Prioritaet:** P0

### Finding

`synthesis_department.py` liest Department-Packages im Raw-Format, bekommt aber Envelopes:

```python
# Erwartet:
package.get("report_segment")
# Bekommt (Envelope):
{"admission": {...}, "raw_package": {...}, "admitted_payload": {...}}
```

Betroffen:
- `read_report_segment()` → liest `report_segment` aus Envelope statt aus `raw_package`
- `available_segments` → zaehlt falsch
- `dept_confidences` → liest falsch
- `request_department_followup()` → schreibt `report_segment` direkt auf Envelope-Objekt (Shape-Mischen)

Ergebnis: Synthesis faellt faktisch auf den precomputed `synthesis_context` zurueck.

### Patch-Sequenz

1. `synthesis_department.py`: Envelope-Aufloesung einbauen — `pkg.get("raw_package", pkg)` vor jedem Zugriff
2. `request_department_followup()`: Follow-up-Ergebnis sauber in `raw_package` schreiben, nicht auf Envelope-Root
3. Tests mit Envelope-Shape statt Raw-Shape

### Akzeptanzkriterien
- `read_report_segment()` findet Segments aus Envelope-wrapped Packages
- `available_segments` zaehlt korrekt
- Follow-up-Updates verschmieren nicht die Envelope-Struktur

---

## P0-3 — Regressionstests auf Envelope-Shape

**Severity:** hoch  
**Prioritaet:** P0

### Finding

Die Synthesis-Integrationstests bauen `department_packages` im Legacy/Raw-Format auf. Dadurch bleibt der Envelope-Bug unentdeckt.

### Patch-Sequenz

1. `tests/integration/test_ag2_runtime.py`: Synthesis-Tests mit Envelope-Shape statt Raw-Shape
2. Neuer Test: `test_synthesis_reads_report_segment_from_envelope`
3. Neuer Test: `test_build_report_package_reads_visual_focus_from_envelope`

### Akzeptanzkriterien
- Tests brechen wenn Synthesis Envelopes nicht korrekt aufloest
- Kein Test baut department_packages im Raw-Format auf wenn der Runtime-Pfad Envelopes liefert

---

## P0-4 — `build_report_package()` an Envelope-Semantik anpassen

**Severity:** hoch  
**Prioritaet:** P0

### Finding

`build_report_package()` liest `package.get("visual_focus", [])` aus `department_packages`. Bekommt aber Envelopes → `visual_focus` ist leer.

### Patch-Sequenz

1. `src/orchestration/synthesis.py` → `build_report_package()`: Envelope-Aufloesung
2. Test: `test_report_package_visual_focus_from_envelope`

### Akzeptanzkriterien
- `department_visual_focus` ist korrekt befuellt

---

## P1-1 — `needs_contract_review` autoritativ verdrahten

**Herkunft:** F4 Restpunkt  
**Severity:** mittel  
**Prioritaet:** P1

### Finding

`needs_contract_review` Flag wird gesetzt, aber bei Critic-Approval geht der Pfad direkt in `lead_accepted()`.

### Patch-Sequenz

1. `src/agents/lead.py` → `review_research()`: Nach Critic-Approval pruefen ob `artifact.needs_contract_review == True`
2. Wenn ja: Nicht als accepted weiterleiten, sondern Judge eskalieren
3. Test: `test_needs_contract_review_triggers_judge_escalation`

### Akzeptanzkriterien
- Critic-Approval bei `needs_contract_review=True` fuehrt zu Judge-Eskalation

---

## P1-2 — Synthesis-Rollen in ROLE_MODEL_DEFAULTS eintragen

**Herkunft:** Audit Finding 10  
**Severity:** mittel  
**Prioritaet:** P1

### Finding

`SynthesisLead`, `SynthesisAnalyst`, `SynthesisCritic`, `SynthesisJudge` fehlen in `ROLE_MODEL_DEFAULTS` und `ROLE_STRUCTURED_MODEL_DEFAULTS`.

### Patch-Sequenz

1. `src/config/settings.py`: Alle vier Synthesis-Rollen eintragen
2. Test: `test_all_agent_specs_have_model_defaults`

### Akzeptanzkriterien
- Jede Rolle in `AGENT_SPECS` hat einen Eintrag in `ROLE_MODEL_DEFAULTS`

---

## P1-3 — `input_artifacts` runtime-wirksam machen oder entfernen

**Herkunft:** Audit Finding  
**Severity:** mittel  
**Prioritaet:** P1

### Finding

`input_artifacts` wird in `use_cases.py` definiert und in `Assignment` transportiert, aber nie operativ genutzt. Der Worker bekommt nur `current_sections`, nicht die deklarierten Input-Artifacts.

### Patch-Sequenz

**Option A — Runtime-wirksam machen:**
1. `lead.py` → `run_research()`: `input_artifacts` aus Assignment lesen
2. Relevante Sections aus `current_sections` filtern und als expliziten Input uebergeben
3. Worker erhaelt nur die deklarierten Inputs, nicht den gesamten Section-State

**Option B — Aus Contract entfernen:**
1. `use_cases.py`: `input_artifacts` Feld entfernen
2. `task_router.py`: `Assignment.input_artifacts` entfernen
3. Tests anpassen

### Akzeptanzkriterien
- Entweder: Worker erhaelt nur deklarierte Inputs
- Oder: Feld existiert nicht mehr und suggeriert keine falsche Disziplin

---

## P1-4 — `current_payload` Overwrite mit Regressionsschutz

**Herkunft:** Audit Finding 4  
**Severity:** niedrig-mittel  
**Prioritaet:** P1

### Finding

`lead.py` ueberschreibt `run_state.current_payload = dict(report["payload"])` nach jedem Worker-Run. Der Worker merged intern, aber es gibt keinen Regressionsschutz falls ein Worker unvollstaendig zurueckliefert.

### Patch-Sequenz

1. `lead.py`: Vor Overwrite pruefen ob der neue Payload mindestens die Felder des alten enthaelt
2. Oder: `deep_merge` statt Overwrite verwenden
3. Test: `test_current_payload_does_not_lose_fields_on_subsequent_task`

### Akzeptanzkriterien
- Ein zweiter Task-Run verliert keine Felder die der erste Task gesetzt hat

---

## P1-5 — Preflight-Ziel sauber trennen

**Herkunft:** Audit Finding 1  
**Severity:** niedrig-mittel  
**Prioritaet:** P1

### Finding

`preflight.py` vermischt zwei Ziele: leichter Core-Check (ohne AG2) und voller Runtime-Readiness-Check (mit AG2).

### Patch-Sequenz

1. `preflight.py`: Zwei Modi oder zwei Stufen
   - Stufe 1: Core (Packages, .env, API-Key, pure imports) — ohne AG2
   - Stufe 2: Runtime (AG2 importierbar, Streamlit erreichbar) — mit AG2
2. Stufe 1 muss auch ohne AG2-Installation durchlaufen

### Akzeptanzkriterien
- `python preflight.py --core` laeuft ohne AG2
- `python preflight.py` laeuft mit AG2

---

## P2-1 — `CrossDomainStrategicAnalyst` vollstaendig entfernen

**Herkunft:** Audit + F6  
**Severity:** niedrig-mittel  
**Prioritaet:** P2

### Finding

Geisterrolle die noch in Model-Defaults, Tool-Policy, Memory-Registry und Config-Summary haengt.

### Patch-Sequenz

1. `settings.py`: Aus ROLE_MODEL_DEFAULTS und ROLE_STRUCTURED_MODEL_DEFAULTS entfernen
2. `tool_policy.py`: Aus BASE_TOOL_POLICY und TASK_TOOL_OVERRIDES entfernen
3. `consolidation.py`: Aus MEMORY_ROLE_STATUS entfernen
4. `settings.py` → `summarize_runtime_models()`: Referenz entfernen
5. Test: `test_no_crossdomainstrategicanalyst_in_codebase`

### Akzeptanzkriterien
- Kein Code referenziert `CrossDomainStrategicAnalyst` mehr

---

## P2-2 — Blocked-Artifact als Pydantic-Modell formalisieren

**Herkunft:** F3 Architektur-Review  
**Severity:** niedrig  
**Prioritaet:** P2

### Patch-Sequenz

1. `src/orchestration/contracts.py` oder `src/models/schemas.py`: `BlockedSectionArtifact` Pydantic-Modell
2. `supervisor_loop.py` + `pipeline_runner.py`: Nutzen das Modell
3. Test: `test_blocked_artifact_has_canonical_schema`

---

## P2-3 — DAG-Linter Phase-Kompatibilitaet

**Herkunft:** F4 Restpunkt  
**Severity:** niedrig  
**Prioritaet:** P2

### Patch-Sequenz

1. `tests/smoke/test_preflight.py`: Test der Phase-Ordnung gegen Cross-Department-Dependencies prueft
2. Phase-Ordnung: `{Company, Market}` parallel → `Buyer` sequential → `Contact` sequential

---

## P2-4 — Synthesis Extra-Felder bereinigen

**Herkunft:** Audit  
**Severity:** niedrig  
**Prioritaet:** P2

### Finding

`finalize_synthesis()` schreibt Felder (`opportunity_assessment`, `negotiation_relevance`, `back_requests_issued`, `department_confidences`) die das Synthesis-Schema nicht definiert. Pydantic verwirft sie still.

### Patch-Sequenz

1. Entweder: Schema erweitern um die Felder die tatsaechlich gebraucht werden
2. Oder: Agent-Output auf Schema-konforme Felder beschraenken
3. Test: `test_synthesis_output_matches_schema`

---

## P2-5 — `_synthesis_admission` Marker durch Envelope-Konsum ersetzen

**Herkunft:** F3 Architektur-Review  
**Severity:** niedrig  
**Prioritaet:** P2

### Patch-Sequenz

1. `pipeline_runner.py`: Admission aus Envelope lesen statt aus Marker-Feld
2. `supervisor_loop.py`: Marker-Injection entfernen
3. Wird durch P0-1 moeglicherweise obsolet

---

## P2-6 — Sammel-Haertungen

**Herkunft:** Diverse Follow-ups aus F5/F7/F8/F10  
**Severity:** niedrig  
**Prioritaet:** P2

Einzelpunkte:
- Kanonische Dedup-Keys pro Sammlung (F5) — Sources bereits URL-basiert in `snapshot()`, Worker-Reports noch nicht
- Merge-Konflikt-Policy strict-Mode (F5)
- StrEnum statt frozenset fuer Vokabular (F7)
- mypy/pyright Typ-Check-Step (F10)
- CI-Pipeline explizit festziehen (F8)
- AGENT_SPECS semantisch rahmen (F9)
- Drawio-Diagramm aktualisieren (F9)
- `definitions.py` Shim entfernen (F1)

---

## Bearbeitungsreihenfolge

### Phase 1 — P0 (Shape-Konsistenz)
1. P0-1 — department_packages Shape eindeutig machen
2. P0-2 — Synthesis-Consumption fixen
3. P0-3 — Regressionstests auf Envelope-Shape
4. P0-4 — build_report_package() fixen

### Phase 2 — P1 (Contract-Haertung)
5. P1-1 — needs_contract_review verdrahten
6. P1-2 — Synthesis-Rollen in Defaults
7. P1-3 — input_artifacts entscheiden
8. P1-4 — current_payload Regressionsschutz
9. P1-5 — Preflight trennen

### Phase 3 — P2 (Bereinigung)
10. P2-1 — CrossDomainStrategicAnalyst entfernen
11. P2-2 — Blocked-Artifact Modell
12. P2-3 — DAG-Linter Phase-Compat
13. P2-4 — Synthesis Extra-Felder
14. P2-5 — Synthesis Marker → Envelope
15. P2-6 — Sammel-Haertungen
