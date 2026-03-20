"""Export pipeline results to artifacts directory."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts"


def export_run(
    run_id: str,
    chat_result,
    pipeline_data: dict | None = None,
    run_meta_extra: dict | None = None,
) -> Path:
    """Extract and save structured results from the group chat."""
    run_dir = ARTIFACTS_DIR / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save full chat history
    messages = []
    if hasattr(chat_result, "chat_history"):
        messages = chat_result.chat_history
    elif isinstance(chat_result, dict):
        messages = chat_result.get("chat_history", [])

    (run_dir / "chat_history.json").write_text(
        json.dumps(messages, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Save run metadata
    meta = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_messages": len(messages),
    }
    if run_meta_extra:
        meta.update(run_meta_extra)
    (run_dir / "run_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if pipeline_data is not None:
        (run_dir / "pipeline_data.json").write_text(
            json.dumps(pipeline_data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    return run_dir
