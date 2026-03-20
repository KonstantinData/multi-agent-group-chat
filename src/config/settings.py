"""Runtime configuration."""
from __future__ import annotations

import os
from typing import Any

from autogen import LLMConfig
from dotenv import load_dotenv

load_dotenv()

STRUCTURED_OUTPUT_MODELS = (
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
)


def _supports_structured_outputs(model: str) -> bool:
    return any(model == prefix or model.startswith(f"{prefix}-") for prefix in STRUCTURED_OUTPUT_MODELS)


def get_llm_config(response_format: Any | None = None) -> LLMConfig:
    preferred_model = os.environ.get("LLM_MODEL", "gpt-4")
    structured_model = os.environ.get("STRUCTURED_LLM_MODEL", "gpt-4o-mini")
    max_tokens = os.environ.get("LLM_MAX_TOKENS", "1400")

    model = preferred_model
    if response_format is not None and not _supports_structured_outputs(preferred_model):
        model = structured_model

    llm_kwargs: dict[str, Any] = {
        "model": model,
        "api_key": os.environ["OPENAI_API_KEY"],
    }
    if max_tokens:
        llm_kwargs["max_tokens"] = int(max_tokens)

    return LLMConfig(llm_kwargs, response_format=response_format)
