# Codebase Audit — Liquisto Department Runtime

**Datum**: 2025-01  
**Scope**: Vollständiger Architektur- und Code-Audit aller Quelldateien  
**Repository**: `multi-agent-intel-pipeline`

---

## 1  Architektur-Stärken

Das System ist architektonisch solide aufgebaut. Die folgenden Designentscheidungen sind gut durchdacht und konsequent umgesetzt:

- **Klare Drei-Ebenen-Trennung** (Control / Research / Synthesis) — der Supervisor interpretiert keine Domain-Fakten, Departments arbeiten autonom.
- **Explizite Artifact-Contracts** (CHG-01/CHG-05) — `TaskArtifact`, `TaskReviewArtifact`, `TaskDecisionArtifact` ersetzen lose Dicts und machen jeden Versuch nachvollziehbar.
- **Guardrail-only Speaker Selector** (CHG-04) — kein versteckter State-Machine-Workflow, der Lead steuert die Konversation durch explizites Agent-Addressing.
- **Department-Autonomie** (CHG-03) — kein `supervisor`-Parameter in der Department-Schnittstelle, der Lead entscheidet Retry/Judge/Coding autonom.
- **Finalization from Stored Decisions** (CHG-07) — `finalize_package` re-judged nie Tasks, die bereits eine Decision haben.
- **Run Brain Persistence** (CHG-02/CHG-08) — vollständige Artifact-History pro Department wird serialisiert und ist für Follow-ups rehydrierbar.
- **Company-Name Scrubbing** (CHG-09) — Long-Term Memory enthält nur strukturelle Patterns, keine kundenspezifischen Fakten.
- **Parallele Execution** — Company + Market laufen parallel via `ThreadPoolExecutor`, Buyer → Contact sequentiell (korrekte Dependency).
- **Deterministische Critic + Judge** — keine LLM-Calls in der Review/Decision-Schicht, reproduzierbare Qualitätsgates.
- **Shared Search Cache** — run-level Cache über alle Departments hinweg vermeidet redundante API-Calls.

---

## 2  Dokumentations-Drift

### 2.1  AGENTS.md — VERALTET

`AGENTS.md` enthält mehrere faktisch falsche Aussagen, die nicht mehr dem Codebase-Stand entsprechen:

| Zeile / Abschnitt | Behauptung in AGENTS.md | Tatsächlicher Stand |
|---|---|---|
| Department Group Structure | Lead-Tool: `finalize_package`, `request_supervisor_revision` | `request_supervisor_revision` existiert nicht mehr (CHG-03). Lead hat nur `finalize_package`. |
| Department Group Structure | Speaker selection: "custom state-machine `speaker_selection_method`" | Guardrail-only Selector (CHG-04), kein State-Machine. |
| Supervisor ↔ Department Boundary | "The Supervisor is passed as a reference to `DepartmentLeadAgent.run()`" | Kein `supervisor`-Parameter in `run()` (CHG-03). |
| Supervisor ↔ Department Boundary | "The Lead calls `supervisor.decide_revision()` as a Python method call" | `decide_revision()` wird nie aus dem Department aufgerufen. |
| Key File Map | `src/agents/strategic_analyst.py` | Datei existiert nicht. |
| Key File Map | `src/tools/research.py` | Datei existiert nicht. Verzeichnis `src/tools/` existiert nicht. |
| Runtime Flow | "Departments run sequentially: Company → Market → Buyer → Contact" | Company + Market laufen parallel (ThreadPoolExecutor). |
| Key File Map | Fehlende Einträge | `contracts.py`, `speaker_selector.py`, `run_context.py`, `pricing.py`, `registry.py` fehlen. |

### 2.2  docs/target_runtime_architecture.md — KORREKT

Einziges Architektur-Dokument, das den tatsächlichen Codebase-Stand widerspiegelt. Alle CHG-01 bis CHG-09 Refactors sind korrekt dokumentiert.

### 2.3  README.md — AKTUALISIERT

Wurde im Rahmen dieses Audits vollständig neu geschrieben und entspricht dem aktuellen Stand.

---

## 3  Code-Level Findings

### 3.1  Strukturelle Issues

#### F-01: `_dedup_safe` / `_dedup` — 6× dupliziert

Identische JSON-basierte Deduplizierungslogik existiert in 6 separaten Dateien:

| Datei | Funktionsname |
|---|---|
| `src/agents/lead.py` | `_dedup()` (Modul-Level) |
| `src/agents/worker.py` | `_dedup_list()` (Instanzmethode) |
| `src/orchestration/follow_up.py` | `_dedup_safe()` |
| `src/orchestration/synthesis.py` | `_dedup_safe()` |
| `src/memory/consolidation.py` | `_dedup_safe()` |
| `src/exporters/pdf_report.py` | `_dedup_safe()` |

**Empfehlung**: Einmal in `src/utils.py` definieren, überall importieren.

**Severity**: Low — funktional korrekt, aber Wartungsrisiko bei Divergenz.

#### F-02: `ReportWriterAgent` — Dead Code

[`src/agents/report_writer.py`](src/agents/report_writer.py) enthält nur `__init__` mit `model_name` und `allowed_tools`. Keine Methoden, keine Logik. Die Klasse wird in `create_runtime_agents()` instanziiert (`definitions.py` L65), aber nirgends aufgerufen.

Die tatsächliche Report-Generierung erfolgt über:
- `build_report_package()` in `src/orchestration/synthesis.py`
- `generate_pdf_report()` in `src/exporters/pdf_report.py`

**Empfehlung**: Entweder mit Logik füllen oder entfernen und den `ReportWriter`-Eintrag in `AGENT_SPECS` als rein visuellen Marker kennzeichnen.

**Severity**: Low — kein Laufzeitfehler, aber irreführend.

#### F-03: `CrossDomainStrategicAnalyst` — Phantom-Rolle

`CrossDomainStrategicAnalyst` existiert in:
- `ROLE_MODEL_DEFAULTS` und `ROLE_STRUCTURED_MODEL_DEFAULTS` in [`settings.py`](src/config/settings.py)
- `run_context.retrieved_role_strategies` in [`pipeline_runner.py`](src/pipeline_runner.py) (L107)

Es gibt aber keinen Agent, keine Klasse, und keine Datei mit diesem Namen. Die Synthesis-Rollen heißen `SynthesisLead`, `SynthesisAnalyst`, `SynthesisCritic`, `SynthesisJudge`.

**Empfehlung**: Alle `CrossDomainStrategicAnalyst`-Referenzen durch die tatsächlichen Synthesis-Rollennamen ersetzen oder entfernen.

**Severity**: Low — verursacht keinen Fehler (Fallback auf Default-Model), aber irreführend.

#### F-04: Synthesis-Rollen fehlen in `ROLE_MODEL_DEFAULTS`

[`settings.py`](src/config/settings.py) enthält keine Einträge für:
- `SynthesisLead`
- `SynthesisAnalyst`
- `SynthesisCritic`
- `SynthesisJudge`

Diese Rollen existieren in `AGENT_SPECS` (`definitions.py`) und werden in `synthesis_department.py` als AG2-Agents instanziiert. Ohne Eintrag in `ROLE_MODEL_DEFAULTS` fallen sie auf `DEFAULT_MODEL` (`gpt-4.1-mini`) zurück.

**Empfehlung**: Explizite Einträge hinzufügen — mindestens `SynthesisLead` und `SynthesisJudge` sollten `gpt-4.1` verwenden.

**Severity**: Medium — Synthesis-Qualität könnte unter dem schwächeren Default-Model leiden.

### 3.2  Robustheit / Edge Cases

#### F-05: `run_supervisor_loop` — Return-Type-Annotation falsch

[`supervisor_loop.py`](src/orchestration/supervisor_loop.py) L52:
```python
def run_supervisor_loop(...) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, str]]]:
```

Die Funktion gibt tatsächlich ein 5-Tupel zurück (L240):
```python
return sections, department_packages, messages, completed_backlog, department_timings
```

Der Caller in `pipeline_runner.py` (L117) entpackt korrekt 5 Werte — die Annotation ist nur falsch, nicht der Code.

**Empfehlung**: Annotation auf 5-Tupel korrigieren.

**Severity**: Low — kein Laufzeitfehler, aber irreführend für Tooling und Entwickler.

#### F-06: `_extract_pipeline_data` — Dead Code

[`pipeline_runner.py`](src/pipeline_runner.py) L63–79: Die Funktion `_extract_pipeline_data()` wird nirgends aufgerufen. Die Pipeline baut `pipeline_data` direkt aus `sections` und `assemble_section()` (L140–155).

**Empfehlung**: Entfernen.

**Severity**: Low — toter Code, kein Laufzeiteffekt.

#### F-07: `build_initial_assignments()` — 3× pro Run aufgerufen

[`task_router.py`](src/orchestration/task_router.py) ruft `build_standard_backlog()` bei jedem Call auf. Die Funktion wird 3× pro Run aufgerufen:
1. `build_initial_assignments(brief)` direkt in `supervisor_loop.py`
2. `build_department_assignments(brief)` → ruft intern `build_initial_assignments()` auf
3. `build_synthesis_assignments(brief)` → ruft intern `build_initial_assignments()` auf

Jeder Call iteriert über den gesamten Backlog und baut alle Assignments neu.

**Empfehlung**: Einmal berechnen, Ergebnis cachen oder als Parameter durchreichen.

**Severity**: Low — Performance-Impact minimal (12 Tasks, keine I/O), aber unnötige Arbeit.

#### F-08: Unused Import in `supervisor_loop.py`

[`supervisor_loop.py`](src/orchestration/supervisor_loop.py) L20:
```python
from src.orchestration.synthesis import build_synthesis_context, build_quality_review
```

`build_synthesis_context` wird in `supervisor_loop.py` importiert, aber nur in der Synthesis-Sektion verwendet, die den Import aus `pipeline_runner.py` nutzt. `build_quality_review` wird lokal verwendet (L218).

**Empfehlung**: Prüfen ob `build_synthesis_context` hier tatsächlich gebraucht wird oder nur in `pipeline_runner.py`.

**Severity**: Info — kein Laufzeiteffekt.

### 3.3  Schema / Contract Gaps

#### F-09: `output_schema_key` — nie enforced

`Assignment.output_schema_key` wird aus `use_cases.py` durchgereicht, aber nirgends zur Laufzeit validiert. Der Worker schreibt in `target_section`, nicht in `output_schema_key`.

**Empfehlung**: Entweder zur Laufzeit validieren (Worker-Output gegen Schema prüfen) oder das Feld als rein dokumentarisch kennzeichnen.

**Severity**: Low — kein Fehler, aber das Feld suggeriert eine Validierung, die nicht stattfindet.

#### F-10: `depends_on` und `input_artifacts` — nie enforced

`Assignment.depends_on` und `Assignment.input_artifacts` werden aus `use_cases.py` durchgereicht, aber nirgends zur Laufzeit geprüft. Die tatsächliche Dependency-Steuerung erfolgt über:
- Hardcoded `_PARALLEL_BATCH` / `_SEQUENTIAL_AFTER` in `supervisor_loop.py`
- `evaluate_run_conditions()` für `run_condition`-Strings

**Empfehlung**: Entweder die Felder zur Laufzeit nutzen (generische Dependency-Resolution) oder als rein dokumentarisch kennzeichnen.

**Severity**: Low — die Execution-Order ist korrekt hardcoded, aber die Contract-Felder sind irreführend.

### 3.4  Performance / Cost

#### F-11: Kein Token-Tracking auf AG2-GroupChat-Ebene

Token-Budgets (`SOFT_TOKEN_BUDGET`, `HARD_TOKEN_CAP`) werden nur zwischen Departments geprüft (`supervisor_loop.py` L200–210), nicht innerhalb eines Department-GroupChats. Ein einzelner Department-Run könnte theoretisch das gesamte Budget verbrauchen.

**Empfehlung**: Token-Tracking auch innerhalb des GroupChats implementieren (z.B. über einen Callback auf dem GroupChatManager).

**Severity**: Medium — bei teuren Departments (Contact mit vielen Buyer-Candidates) könnte das Budget überschritten werden.

#### F-12: `worker.py` — Umfangreiche Task-spezifische Prompt-Logik

[`worker.py`](src/agents/worker.py) enthält ~15 task-spezifische `if task_key == "..."` Blöcke in `_llm_synthesis()` und `_fallback_synthesis()`. Diese Logik wächst linear mit jedem neuen Task.

**Empfehlung**: Task-spezifische Prompt-Templates in eine separate Konfiguration auslagern (z.B. `TASK_PROMPT_EXTENSIONS` Dict).

**Severity**: Low — funktional korrekt, aber Wartbarkeit leidet bei wachsendem Task-Katalog.

---

## 4  Offene Design-Entscheidungen

### D-01: Synthesis Selector — Hybrid-Ansatz

Der Synthesis-Selector in [`speaker_selector.py`](src/orchestration/speaker_selector.py) behält einen leichtgewichtigen `synthesis_step`-State (`start` → `read` → `critique` → `decide` → `finalize`), obwohl die Department-Selectors rein guardrail-basiert sind.

**Begründung**: Die Read-before-Critique-Semantik erfordert eine minimale Sequenzierung (der Analyst muss alle Segmente lesen, bevor der Critic reviewed).

**Entscheidung**: Akzeptabel als bewusster Hybrid. Dokumentieren, dass dies eine Ausnahme vom Guardrail-only-Prinzip ist.

### D-02: Follow-up — Wann neue Recherche?

`answer_follow_up()` setzt `requires_additional_research=True` wenn `unresolved_points` existieren, aber `DepartmentRuntime.run_followup()` wird nur aufgerufen, wenn der UI-Layer dies explizit triggert.

**Entscheidung**: Die aktuelle Implementierung ist konservativ (kein automatischer Re-Research). Für V2 könnte ein automatischer Trigger sinnvoll sein.

### D-03: `max_round` Berechnung

`max_round = len(assignments) * 15` ist ein fester Multiplikator. Bei 3 Tasks pro Department = 45 Rounds. Das ist großzügig, aber bei komplexen Retry-Chains mit Coding-Support könnte es knapp werden.

**Entscheidung**: Monitoring der tatsächlichen Round-Nutzung pro Run empfohlen. Fallback-Package-Logik (`_build_fallback_package`) fängt den Fall ab.

---

## 5  Priorisierte Next Steps

### P0 — Sofort (Korrektheit)

| # | Maßnahme | Aufwand |
|---|---|---|
| P0-1 | `run_supervisor_loop` Return-Type-Annotation auf 5-Tupel korrigieren (F-05) | 1 Zeile |
| P0-2 | Synthesis-Rollen in `ROLE_MODEL_DEFAULTS` + `ROLE_STRUCTURED_MODEL_DEFAULTS` ergänzen (F-04) | 8 Zeilen |

### P1 — Kurzfristig (Hygiene)

| # | Maßnahme | Aufwand |
|---|---|---|
| P1-1 | `AGENTS.md` aktualisieren oder durch Verweis auf `target_runtime_architecture.md` ersetzen (2.1) | 30 min |
| P1-2 | `_extract_pipeline_data()` entfernen (F-06) | 1 min |
| P1-3 | `CrossDomainStrategicAnalyst`-Referenzen bereinigen (F-03) | 10 min |
| P1-4 | `ReportWriterAgent` entweder mit Logik füllen oder als Stub dokumentieren (F-02) | 15 min |

### P2 — Mittelfristig (Wartbarkeit)

| # | Maßnahme | Aufwand |
|---|---|---|
| P2-1 | `_dedup_safe` in `src/utils.py` zentralisieren (F-01) | 30 min |
| P2-2 | `build_initial_assignments()` einmal berechnen, Ergebnis cachen (F-07) | 20 min |
| P2-3 | Task-spezifische Prompt-Templates aus `worker.py` extrahieren (F-12) | 2h |
| P2-4 | `output_schema_key` / `depends_on` / `input_artifacts` entweder enforced oder als dokumentarisch markieren (F-09, F-10) | 1h |

### P3 — Langfristig (Robustheit)

| # | Maßnahme | Aufwand |
|---|---|---|
| P3-1 | Intra-Department Token-Tracking implementieren (F-11) | 4h |
| P3-2 | Generische Dependency-Resolution aus `depends_on`-Feld statt hardcoded Execution-Order | 8h |

---

## 6  Zusammenfassung

Das Repository ist architektonisch gut strukturiert und die CHG-01 bis CHG-09 Refactors sind konsequent umgesetzt. Die Hauptprobleme sind:

1. **Dokumentations-Drift** — `AGENTS.md` ist signifikant veraltet und enthält faktisch falsche Aussagen.
2. **Phantom-Referenzen** — `CrossDomainStrategicAnalyst` und `ReportWriterAgent` existieren als Referenzen ohne funktionale Implementierung.
3. **Fehlende Model-Defaults** — Synthesis-Rollen fallen auf das schwächere Default-Model zurück.
4. **Code-Duplikation** — `_dedup_safe` in 6 Dateien.

Keines dieser Issues verursacht Laufzeitfehler. Die Pipeline funktioniert korrekt. Die Findings betreffen Wartbarkeit, Dokumentationsgenauigkeit und potenzielle Qualitätseinbußen bei der Synthesis-Schicht.
