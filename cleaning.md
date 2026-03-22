# Cleaning Candidates

This file lists repository content that is no longer needed for the current
runtime architecture or can be removed safely as generated residue.

The list is split into:
- safe removals from the codebase
- safe deletions of generated/local artifacts
- optional consolidations where one file is enough but both are still valid

## 1. Safe Codebase Removals

These files are not referenced by the current runtime, UI, tests, or README and
can be removed.

### Unused domain dataclasses

- `src/domain/briefing.py`
  Old standalone briefing dataclass. The runtime now uses schema-backed
  `pipeline_data`, department packages, and `report_package`.
- `src/domain/buyers.py`
  Old buyer-path dataclass layer. Not used by the department runtime.
- `src/domain/decisions.py`
  Old opportunity-assessment dataclass. Not used by the current synthesis flow.
- `src/domain/evidence.py`
  Old evidence-record dataclass. The runtime now uses structured dict payloads
  and Pydantic schemas.
- `src/domain/findings.py`
  Old generic finding dataclass. Not referenced by the current pipeline.
- `src/domain/market.py`
  Old market-signal dataclass. Not referenced by the current pipeline.

### Unused memory/model helpers

- `src/memory/models.py`
  Contains dataclasses that are not imported by the active runtime.

### Unused compatibility wrapper

- `src/tools/__init__.py`
  Compatibility wrapper package with no active imports.
- `src/tools/research.py`
  Backward-compatibility helper exporting underscored aliases only. Not used by
  the current runtime.

## 2. Safe Generated/Local Deletions

These are generated artifacts or cache output and can be deleted without
changing the runtime architecture.

### Temporary PDF/image output

- `tmp/pdfs/professional_briefing.pdf`
- `tmp/pdfs/professional_briefing.png`
- `tmp/pdfs/ims_gear_briefing_1.png`
- `tmp/pdfs/ims_gear_briefing_2.png`
- `tmp/pdfs/ims_gear_briefing_3.png`
- `tmp/pdfs/ims_gear_briefing_4.png`
- `tmp/pdfs/ims_gear_briefing_5.png`

### Generated test artifacts

- `artifacts/test/test_report_DE.pdf`
- `artifacts/test/test_report_EN.pdf`

### Generated caches

- `__pycache__/`
- `.pytest_cache/`
- `ui/__pycache__/`
- `src/__pycache__/`

### Resettable runtime memory

- `artifacts/memory/long_term_memory.json`
  Remove only if you want to reset the accumulated strategy memory. This is not
  required for code cleanup, but it is safe if a clean runtime state is desired.

## 3. Optional Consolidations

These are not strictly dead files, but one copy would be enough.

### Architecture diagram duplication

- `docs/runtime_architecture.drawio`
- `docs/updated_runtime_architecture.drawio`

The repo can keep both, but the current implementation is already aligned to the
target architecture. If you want a single source of truth, keep one canonical
runtime diagram and remove or archive the other.

### Secondary process note

- `Develop-MD.md`

This file is now only a checklist. The actual architecture definition already
lives in:
- `README.md`
- `docs/target_runtime_architecture.md`
- `docs/updated_runtime_architecture.drawio`

If you want leaner docs, this checklist can be removed.

### Convenience launcher layer

- `launcher.py`
- `start_streamlit.bat`

These are still usable convenience wrappers, but the runtime itself does not
depend on them. If the team prefers a single startup path via direct Streamlit
or a task runner, these can be removed.

## 4. Recommended Cleanup Order

1. Remove the unused `src/domain/*` dataclass files listed above.
2. Remove `src/memory/models.py`.
3. Remove the unused `src/tools/*` compatibility wrapper.
4. Delete generated `tmp/pdfs/*` and `artifacts/test/*`.
5. Decide whether to keep one or both runtime Drawio files.
6. Optionally remove `Develop-MD.md` and the launcher wrappers.
