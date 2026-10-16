"""
backend/ai/token_caps.py â€” Ollama token-cap helpers.

Keeps latency / RAM acceptable on 6 GB devices by capping max_tokens
per model family. Imported by provider_strategy and routers/ai.
"""

_OLLAMA_TOKEN_CAPS: dict[str, int] = {
    "satgeze/ornith-9b-1m:q2_k": 1024,
    "satgeze/ornith-9b-1m": 1024,
    "satgeze": 1024,
    "ornith": 1024,
    "qwen2.5": 768,
    "phi3": 768,
    "tinyllama": 768,
    "llama3.2": 768,
    "llama3.1": 768,
    "llama3": 768,
    "gemma2": 768,
    "mistral": 768,
}


def _ollama_token_cap(model: str, requested: int) -> int:
    """Return min(requested, model-specific cap). Looks up by exact name or base name."""
    if model in _OLLAMA_TOKEN_CAPS:
        return min(requested, _OLLAMA_TOKEN_CAPS[model])
    base = model.split(":")[0]
    cap = _OLLAMA_TOKEN_CAPS.get(base, 512)
    return min(requested, cap)
