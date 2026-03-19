"""Runtime configuration."""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


def get_llm_config() -> dict:
    return {
        "config_list": [
            {
                "model": os.environ.get("LLM_MODEL", "gpt-4"),
                "api_key": os.environ["OPENAI_API_KEY"],
            }
        ]
    }
