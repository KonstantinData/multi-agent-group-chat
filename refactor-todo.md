# Refactor TODO — Drawio → Code Alignment

Ziel: Die drei Drawio-Dateien sind die Architektur-Wahrheit.
Jede Abweichung zwischen Drawio und Code muss geschlossen werden.

Quellen:
- `docs/updated_runtime_architecture.drawio` — Gesamtarchitektur
- `docs/company_department_run.drawio` — Company Department Ablauf
- `docs/company_department_storage.drawio` — Company Department Speicherung

---

## 1. CompanyLead: „classifies goods" ist Lead-owned ✅

**Drawio sagt:**
> CompanyLead: "builds investigation plan · **classifies goods** · owns domain package · calls finalize_package()"

**Code heute:**
Die Güterklassifikation (made vs distributed vs held-in-stock) passiert im
Worker (`worker.py`, Task `product_asset_scope`). Der Lead sieht das Ergebnis
erst als fertigen Worker-Report. Die Klassifikation ist generisch
(„Automotive components appears likely to matter...") statt ein echtes
Domain-Urteil.

**Fix:**
- Nach dem Worker-Report für `product_asset_scope` führt der Lead einen
  eigenen Klassifikationsschritt durch.
- Der Lead nimmt die Researcher-Rohdaten und wendet den Classification Frame
  (`made_vs_distributed_vs_held_in_stock`) an, bevor er das Ergebnis in den
  Payload schreibt.
- Implementierung in `lead.py`: entweder im `finalize_package()` oder als
  separater Post-Research-Schritt nach dem Worker-Report.
- Der Worker liefert weiterhin die Rohdaten (welche Güter sichtbar sind).
- Die Einordnung „made / distributed / held-in-stock" macht der Lead (gpt-4.1).

**Dateien:** `src/agents/lead.py`
**Priorität:** Hoch — Architektur-Kernverantwortung falsch zugeordnet

---

## 2. Synthesis: `contact_intelligence` fehlt als Input ✅

**Drawio sagt:**
> Supervisor → Synthesis: "4 approved packages"
> build_synthesis_from_memory() liest alle 4 Sections

**Code heute:**
`build_synthesis_context()` in `synthesis.py` nimmt nur 3 Parameter:
`company_profile`, `industry_analysis`, `market_network`. Der Parameter
`contact_intelligence` fehlt komplett. Auch der Aufruf in `supervisor_loop.py`
übergibt nur 3 Sections.

**Fix:**
- `build_synthesis_context()` um Parameter `contact_intelligence` erweitern.
- Aufruf in `supervisor_loop.py` anpassen:
  `contact_intelligence=sections.get("contact_intelligence", {})`.
- Contact-Daten in die Synthesis-Logik einbauen: verified contacts, buyer
  contacts, coverage quality in die Opportunity-Bewertung einfließen lassen.

**Dateien:** `src/orchestration/synthesis.py`, `src/orchestration/supervisor_loop.py`
**Priorität:** Hoch — Synthesis ignoriert ein ganzes Department

---

## 3. `build_quality_review`: ContactDepartment fehlt in `validated_agents` ✅

**Drawio sagt:**
> 4 Domain Departments liefern an Synthesis

**Code heute:**
`build_quality_review()` in `synthesis.py` hardcoded:
```python
"validated_agents": ["Supervisor", "CompanyDepartment", "MarketDepartment", "BuyerDepartment", ...]
```
`ContactDepartment` fehlt in der Liste.

**Fix:**
- `ContactDepartment` in die `validated_agents`-Liste aufnehmen.

**Dateien:** `src/orchestration/synthesis.py`
**Priorität:** Mittel — Kosmetisch, aber irreführend für Downstream-Konsumenten

---

## 4. `assess_research_readiness`: Contact-Section nicht bewertet ✅

**Drawio sagt:**
> 4 approved packages → Synthesis → research_readiness score 0–100

**Code heute:**
`assess_research_readiness()` in `synthesis.py` bewertet nur 3 Sections
(company_profile=35, industry_analysis=25, market_network=20, quality=20).
Contact Intelligence hat keinen Score-Anteil.

**Fix:**
- Score-Gewichtung auf 4 Sections umverteilen, z.B.:
  company_profile=30, industry_analysis=20, market_network=15,
  contact_intelligence=15, quality=20.
- Contact-Section prüfen: mindestens 1 verified contact oder coverage_quality
  != "n/v" für Punkte.

**Dateien:** `src/orchestration/synthesis.py`
**Priorität:** Mittel — Readiness-Score bildet Contact-Qualität nicht ab

---

## 5. `shared_search_cache` in `supervisor_loop.py` wird nicht genutzt ✅

**Drawio sagt (implizit):**
> Departments teilen sich einen Search-Cache innerhalb eines Runs

**Code heute:**
`supervisor_loop.py` deklariert `shared_search_cache: dict = {}` (Zeile ~68),
übergibt ihn aber **nicht** an die Department-Runtimes. Die tatsächliche
Cache-Sharing passiert in `definitions.py` → `create_runtime_agents()`, wo
ein eigener `shared_search_cache` erstellt wird.

**Fix:**
- Entweder die tote Variable in `supervisor_loop.py` entfernen (Cache lebt
  korrekt in `definitions.py`), oder den Cache aus `supervisor_loop.py`
  durchreichen und in `definitions.py` entfernen.
- Entscheidung: `definitions.py` ist der richtige Ort (einmal pro Run
  erstellt). Die Variable in `supervisor_loop.py` entfernen.

**Dateien:** `src/orchestration/supervisor_loop.py`
**Priorität:** Niedrig — Toter Code, kein Laufzeitfehler

---

## 6. `economic_commercial_situation`: Cache-Reuse verhindert neue Suchen ✅

**Drawio sagt:**
> CompanyResearcher: "run_research() · OpenAI web_search_preview · fetch_page()"

**Code heute:**
Der shared search cache bewirkt, dass `economic_commercial_situation` alle
seine Queries bereits gecacht findet (von `company_fundamentals`), weil die
Queries identisch sind (`build_company_queries` + 2 Zusatz-Queries). Die
gecachten Ergebnisse enthalten aber keine wirtschaftlichen Signale. Der Worker
denkt, er hat gesucht, hat aber keine relevanten Daten.

**Fix:**
- `_build_queries()` in `worker.py`: für `economic_commercial_situation`
  **eigene** Queries generieren, die sich nicht mit `company_fundamentals`
  überlappen. Fokus auf: revenue trends, restructuring, inventory stress,
  financial pressure, layoffs, M&A.
- Alternativ: die 2 Zusatz-Queries (`revenue growth demand`,
  `inventory excess restructuring`) als **einzige** Queries verwenden,
  nicht zusätzlich zu `build_company_queries()`.

**Dateien:** `src/agents/worker.py`
**Priorität:** Hoch — Task produziert systematisch leere Ergebnisse

---

## 7. `peer_companies`: LLM-Synthese extrahiert keine konkreten Firmennamen ✅

**Drawio sagt:**
> BuyerDepartment → market_network: "MarketNetwork schema · peers · buyers · gaps"

**Code heute:**
Der Worker-LLM-Prompt ist generisch ("Return JSON with keys: payload_updates,
facts..."). Er gibt dem LLM keine Anweisung, konkrete Firmennamen aus den
Suchergebnissen zu extrahieren. Ergebnis: `peer_competitors.companies` bleibt
leer oder enthält nur Search-Title-Fragmente aus dem Fallback.

**Fix:**
- LLM-Synthese-Prompt in `worker.py` → `_llm_synthesis()` für
  `market_network`-Tasks spezifischer machen: explizit verlangen, dass
  Firmennamen, Städte, Länder und Relevanz aus den Suchergebnissen
  extrahiert werden.
- Alternativ: Task-spezifische Prompt-Erweiterungen im System-Prompt
  basierend auf `target_section` und `task_key`.

**Dateien:** `src/agents/worker.py`
**Priorität:** Hoch — Buyer Department liefert systematisch leere Peer-Listen

---

## 8. Contact Department: Cascade-Failure bei leeren `buyer_candidates` ✅

**Drawio sagt:**
> buyer_output → contact_lead: "buyer_candidates"
> ContactLead: "reads buyer_candidates from market_network"

**Code heute:**
`supervisor_loop.py` übergibt `buyer_candidates` aus
`buyer_package.get("accepted_points", [])`. Wenn BuyerDepartment keine
konkreten Firmennamen liefert (Bug #7), sind `buyer_candidates` leer.
ContactDepartment fällt auf industry-scoped Queries zurück, findet aber
keine spezifischen Kontakte.

**Fix:**
- Primär: Bug #7 fixen (peer_companies liefert echte Firmennamen).
- Sekundär: `supervisor_loop.py` sollte `buyer_candidates` aus
  `section_payload.peer_competitors.companies` + 
  `section_payload.downstream_buyers.companies` extrahieren, nicht aus
  `accepted_points` (das sind Prosa-Strings, keine Firmennamen).
- Tertiär: ContactDepartment-Fallback verbessern — wenn keine
  buyer_candidates, dann aus dem company_profile die Industrie und
  Produktkeywords nehmen und gezielt nach Einkäufern in dieser Branche
  suchen.

**Dateien:** `src/orchestration/supervisor_loop.py`, `src/agents/worker.py`
**Priorität:** Hoch — Kontakt-Ergebnisse sind systematisch leer

---

## 9. Critic→Lead Rejection: Retry produziert kein besseres Ergebnis ✅

**Drawio sagt:**
> Critic → Lead: "approved / revision"
> Lead → Supervisor: request_supervisor_revision
> Supervisor: retry=true → Researcher re-runs

**Code heute:**
Wenn der Critic rejected und der Supervisor retry=true entscheidet, wird
`run_research()` erneut aufgerufen. Aber: die `revision_request` enthält
nur die Critic-Feedback-Punkte. Der Worker-LLM-Prompt nutzt diese nicht
effektiv — er bekommt das gleiche Evidence-Pack und produziert das gleiche
Ergebnis. Die Retry-Schleife ist funktional wirkungslos.

**Fix:**
- `_llm_synthesis()` in `worker.py`: wenn `revision_request` vorhanden,
  die rejected_points und feedback_to_worker explizit in den LLM-Prompt
  einbauen als "You must specifically address these gaps: ...".
- Alternativ: der CodingSpecialist wird bei method_issue=true aktiviert
  und liefert query_overrides — sicherstellen, dass dieser Pfad auch bei
  inhaltlichen (nicht nur methodischen) Lücken genutzt wird.

**Dateien:** `src/agents/worker.py`
**Priorität:** Mittel — Retry existiert, ist aber wirkungslos

---

## 10. `completed_but_not_usable` Status zu strikt ✅

**Drawio sagt:**
> assess_research_readiness() → score 0–100 + usable flag

**Code heute:**
`assess_research_readiness()` setzt `usable = score >= 70 AND evidence_health
in {high, medium}`. Wenn Company + Market + Monetization substantiv sind,
aber Contacts und Peers leer, wird der Run als `completed_but_not_usable`
markiert — obwohl ein brauchbares Briefing möglich wäre.

**Fix:**
- Readiness-Score differenzierter gestalten (siehe #4).
- `usable`-Schwelle senken oder nach Kern-Sections (Company + Market)
  vs. optionalen Sections (Contact) gewichten.
- Alternativ: Zwischenstatus `completed_partial` einführen, der signalisiert
  dass ein Briefing möglich ist, aber Lücken hat.

**Dateien:** `src/orchestration/synthesis.py`, `src/pipeline_runner.py`
**Priorität:** Mittel — Brauchbare Runs werden als unbrauchbar markiert

---

## 11. LTM-Strategien verursachen Cache-Pollution (entschärft durch #6)

**Drawio sagt:**
> Strategy Memory (LTM): "reusable search and classification patterns"
> LTM → Researcher: "patterns"

**Code heute:**
LTM speichert Query-Patterns aus vorherigen Runs. Diese werden dem Researcher
als `role_memory` mitgegeben. Problem: wenn LTM-Queries identisch mit den
Standard-Queries sind, werden sie im shared cache gefunden, aber die gecachten
Ergebnisse passen nicht zum aktuellen Task (z.B. company_fundamentals-Cache
wird für economic_situation wiederverwendet).

**Fix:**
- LTM-Strategien sollten **keine rohen Queries** speichern, sondern
  Query-**Muster** (z.B. "für economic_situation, suche nach: {company}
  + restructuring/layoffs/inventory write-down").
- Worker sollte LTM-Patterns als Inspiration für Query-Generierung nutzen,
  nicht als direkte Query-Overrides.
- Kurzfristig: Bug #6 fixen (eigene Queries für economic_situation)
  entschärft das Problem.

**Dateien:** `src/agents/worker.py`, `src/memory/long_term.py`
**Priorität:** Niedrig — wird durch #6 entschärft

---

## 12. `build_synthesis_context`: executive_summary erwähnt nur 3 Departments ✅

**Code heute:**
```python
"The briefing is based on approved company, market, and buyer department packages."
```
Contact Department fehlt im Text.

**Fix:**
- Text anpassen: "...approved company, market, buyer, and contact department
  packages."

**Dateien:** `src/orchestration/synthesis.py`
**Priorität:** Niedrig — Kosmetisch

---

## 13. `build_report_package`: Contact-Section nicht in `recommended_sections` ✅

**Code heute:**
```python
"recommended_sections": [
    "Executive summary",
    "Company snapshot",
    "Market and operational signals",
    "Buyer and redeployment paths",
    "Liquisto opportunity assessment",
    "Negotiation relevance and next steps",
    "Evidence appendix",
]
```
Kein Abschnitt für Contact Intelligence.

**Fix:**
- "Contact intelligence and outreach angles" nach "Buyer and redeployment
  paths" einfügen.

**Dateien:** `src/orchestration/synthesis.py`
**Priorität:** Niedrig — Report-Struktur unvollständig

---

## 14. `company_department_run.drawio`: Subtitle und GroupChatManager aktualisiert ✅

Bereits erledigt in dieser Session:
- Subtitle: `speaker_selection="auto"` → `custom state-machine speaker selector`
- Lead-Box: „classifies goods" ergänzt
- GroupChatManager-Box: state-machine statt auto

---

## 15. `company_department_storage.drawio`: 4 Departments aktualisiert ✅

Bereits erledigt in dieser Session:
- `build_synthesis_from_memory()`: `contact_intelligence` als 4. Section
- `build_report_package()`: „alle 3" → „alle 4"

---

## Zusammenfassung nach Priorität

### Erledigt ✅

| # | Aufgabe | Dateien |
|---|---------|---------|
| 1 | CompanyLead: classifies goods Lead-owned | `lead.py`, `schemas.py` |
| 2 | Synthesis: contact_intelligence als Input | `synthesis.py`, `supervisor_loop.py`, `pipeline_runner.py` |
| 3 | quality_review: ContactDepartment in validated_agents | `synthesis.py` |
| 4 | research_readiness: Contact-Score einbauen | `synthesis.py`, `pipeline_runner.py` |
| 5 | shared_search_cache tote Variable entfernen | `supervisor_loop.py` |
| 6 | economic_situation: eigene Queries | `worker.py` |
| 7 | peer_companies: LLM extrahiert Firmennamen | `worker.py` |
| 8 | Contact cascade: buyer_candidates aus companies extrahieren | `supervisor_loop.py` |
| 9 | Retry: revision_request im LLM-Prompt nutzen | `worker.py` |
| 10 | completed_but_not_usable zu strikt → completed_partial | `synthesis.py`, `pipeline_runner.py` |
| 11 | LTM Cache-Pollution (entschärft durch #6) | — |
| 12 | executive_summary Text: 4 Departments | `synthesis.py` |
| 13 | recommended_sections: Contact einfügen | `synthesis.py` |
| 14 | company_department_run.drawio aktualisiert | — |
| 15 | company_department_storage.drawio aktualisiert | — |
