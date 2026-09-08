"""The one place a model is called. Backend is read from the environment so the
local Ollama path can be swapped without touching callers. Local is the supported
path and needs no API key."""

import os


def complete(prompt: str, system: str) -> str:
    backend = os.environ.get("FACTLEDGER_LLM_BACKEND", "ollama")
    if backend == "ollama":
        return _ollama_complete(prompt, system)
    raise ValueError(f"unknown FACTLEDGER_LLM_BACKEND: {backend}")


def _ollama_complete(prompt: str, system: str) -> str:
    import ollama

    model = os.environ.get("FACTLEDGER_LLM_MODEL", "qwen2.5:7b-instruct")
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        format="json",
        options={"temperature": 0},
    )
    return response["message"]["content"]
