"""
backend/ai/provider_strategy.py Ã¢â‚¬â€ AI Provider Strategy
=======================================================
Single source of truth for:
  - Provider detection & selection  (_detect_provider)
  - Unified text chat               (_ai_chat)
  - Unified vision chat             (_ai_chat_vision)
  - Rule engine lazy-loader         (_load_rule_engine)
  - All provider-state globals      (_PROVIDER_OVERRIDE, _OLLAMA_*, etc.)

Architecture Ã¢â‚¬â€ Strategy pattern:
  Provider selection is encapsulated here. No route handler ever talks to
  Anthropic or Ollama directly; they call _ai_chat / _ai_chat_vision instead.

Imported by:
  - backend/routers/ai.py            (route handlers)
  - backend/behavioral/data_aggregator.py  (indirectly, via _load_rule_engine)

Step 6 of the api_server.py God-Object split.

Sub-modules (extracted for cohesion):
  - token_caps.py        Ã¢â‚¬â€ _OLLAMA_TOKEN_CAPS, _ollama_token_cap
  - json_repair.py       Ã¢â‚¬â€ _repair_truncated_json, _strip_json_fences
  - prompt_templates.py  Ã¢â‚¬â€ _RECEIPT_SYSTEM, _INSIGHTS_SYSTEM, prompt helpers
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error as _urlerr
import urllib.request as _urlreq
from pathlib import Path

from fastapi import HTTPException

from packages.api.backend.ai.token_caps import _ollama_token_cap

logger = logging.getLogger("finance_tracker")

# Ã¢â€â‚¬Ã¢â€â‚¬ Path to rule engine Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
_HERE = Path(__file__).resolve().parent  # backend/ai/
_RULE_ENGINE_PATH = _HERE / "ai_rule_engine.py"
_RECEIPT_PARSER_PATH = _HERE / "receipt_parser.py"

# Ã¢â€â‚¬Ã¢â€â‚¬ Rule engine lazy-loader Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
_rule_engine = None
_receipt_parser_mod = None

def _load_rule_engine():
    """Lazy-load the rule-based insight engine. Returns module or None on failure."""
    global _rule_engine
    if _rule_engine is not None:
        return _rule_engine
    try:
        import importlib.util as _ilu

        spec = _ilu.spec_from_file_location("ai_rule_engine", str(_RULE_ENGINE_PATH))
        mod = _ilu.module_from_spec(spec)
        sys.modules["ai_rule_engine"] = mod  # register BEFORE exec so dataclasses resolve
        spec.loader.exec_module(mod)
        _rule_engine = mod
        return mod
    except Exception:
        return None


def _load_receipt_parser():
    """Lazy-load the standalone receipt parser module. Returns module or None on failure.
    Extracted from ai_rule_engine.py in R1 (2026-09-05) so receipt parsing can
    evolve independently of the 9-analyzer insight engine.
    """
    global _receipt_parser_mod
    if _receipt_parser_mod is not None:
        return _receipt_parser_mod
    try:
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("receipt_parser", str(_RECEIPT_PARSER_PATH))
        mod  = _ilu.module_from_spec(spec)
        sys.modules["receipt_parser"] = mod
        spec.loader.exec_module(mod)
        _receipt_parser_mod = mod
        return mod
    except Exception:
        return None


# ── Provider state globals ───────────────────────────────────────────────────
_PROVIDER_OVERRIDE:     str | None = None   # "claude" | "gemini" | "ollama" | "rules" | None (auto)
_OLLAMA_MODEL_CACHE:    str | None = None   # cached best Ollama model name
_OLLAMA_MODEL_OVERRIDE: str | None = None   # force specific model e.g. "qwen2.5:7b"
_GEMINI_MODEL_OVERRIDE: str | None = None   # force specific gemini model
_OLLAMA_CACHE_TIME:     float = 0.0         # epoch seconds when cache was last set
_OLLAMA_CACHE_TTL:      float = 30.0        # seconds before re-checking Ollama
_OLLAMA_OOM_BLACKLIST:  set[str] = set()    # models that OOM-crashed this session


# ── Token caps ───────────────────────────────────────────────────────────────
# Keeps latency / RAM acceptable on 6 GB devices.
_OLLAMA_TOKEN_CAPS: dict[str, int] = {
    "satgeze/ornith-9b-1m:q2_k": 1024,
    "satgeze/ornith-9b-1m": 1024,
    "satgeze": 1024,
    "ornith": 1024,
    "qwen2.5":   768,
    "phi3":      768,
    "tinyllama": 768,
    "llama3.2":  768,
    "llama3.1":  768,
    "llama3":    768,
    "gemma2":    768,
    "mistral":   768,
}

def _ollama_token_cap(model: str, requested: int) -> int:
    """Return min(requested, model-specific cap). Looks up by exact name or base name."""
    if model in _OLLAMA_TOKEN_CAPS:
        return min(requested, _OLLAMA_TOKEN_CAPS[model])
    base = model.split(":")[0]
    cap  = _OLLAMA_TOKEN_CAPS.get(base, 512)
    return min(requested, cap)


# ── Provider detection helpers ───────────────────────────────────────────────

def _anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if "," in key:
        return key.split(",")[0].strip()
    return key


def _gemini_key() -> str:
    # Check for both standard and Vite-prefixed keys
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("VITE_GEMINI_API_KEY") or ""
    key = key.strip()
    if "," in key:
        return key.split(",")[0].strip()
    return key


def _ollama_base() -> str:
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def _ollama_available() -> tuple[bool, str]:
    """
    Check if Ollama is running and return (available, best_auto_model).
    Preference order: satgeze/ornith-9b-1m:q2_k > qwen2.5 > phi3 > tinyllama > llama3.2 > gemma2 > mistral > llama3.1 > llama3.
    Model override is handled by _detect_provider(), not here.
    Results are cached for _OLLAMA_CACHE_TTL seconds.
    """
    import time

    global _OLLAMA_MODEL_CACHE, _OLLAMA_CACHE_TIME
    if _OLLAMA_MODEL_CACHE and (time.time() - _OLLAMA_CACHE_TIME) < _OLLAMA_CACHE_TTL:
        return True, _OLLAMA_MODEL_CACHE
    try:
        req = _urlreq.Request(f"{_ollama_base()}/api/tags", method="GET")
        with _urlreq.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        available = data.get("models", [])
        if not available:
            return False, ""
        cloud_names = {m["name"] for m in available if m.get("remote_model")}
        PREF = [
            "qwen3:8b-q4_K_M",
            "qwen3",
            "qwen2.5",
            "phi3",
            "tinyllama",
            "llama3.2",
            "gemma2",
            "mistral",
            "llama3.1",
            "llama3",
            "satgeze/ornith-9b-1m:q2_k",
            "satgeze/ornith-9b-1m",
            "ornith"
        ]
        model_names = [m["name"] for m in available if m["name"] not in cloud_names]
        safe_names  = [n for n in model_names if n not in _OLLAMA_OOM_BLACKLIST]
        safe_bases  = [n.split(":")[0] for n in safe_names]
        if not safe_names:
            return False, ""
        chosen_full = None
        for p in PREF:
            if p in safe_names:
                chosen_full = p
                break
            base = p.split(":")[0]
            if base in safe_bases:
                chosen_full = safe_names[safe_bases.index(base)]
                break
        if not chosen_full:
            chosen_full = safe_names[0]
        _OLLAMA_MODEL_CACHE = chosen_full
        _OLLAMA_CACHE_TIME = time.time()
        return True, chosen_full
    except Exception:
        return False, ""


def _resolve_ollama_model() -> tuple[bool, str]:
    """Resolve actual model, respecting _OLLAMA_MODEL_OVERRIDE or environment variables."""
    env_override = os.environ.get("OLLAMA_MODEL_OVERRIDE") or os.environ.get("OLLAMA_DEFAULT_MODEL")
    if env_override and env_override.strip():
        return True, env_override.strip()
    if _OLLAMA_MODEL_OVERRIDE:
        return True, _OLLAMA_MODEL_OVERRIDE
    ok, auto_model = _ollama_available()
    if not ok:
        return False, ""
    return True, auto_model


def _detect_provider() -> dict:
    """
    Returns {"provider": "claude"|"gemini"|"ollama"|"rules", "model": str, "vision": bool, "reason": str}

    Strict fallback chain (always):
      1. Cloud AI  : Claude (ANTHROPIC_API_KEY + anthropic SDK)
      2. Cloud AI  : Gemini (GEMINI_API_KEY + google.generativeai SDK)
      3. Local LLM : Ollama (ollama serve aktif)
      4. Local Py  : Rules  (pure-Python bilingual engine, always available)

    Override dapat mem-pin preferred provider, tapi jika tidak tersedia
    chain tetap dilanjutkan ke langkah berikutnya.
    """
    global _PROVIDER_OVERRIDE

    # Resolve effective override: runtime (_PROVIDER_OVERRIDE) beats env var
    _env_prov = (os.environ.get("PROVIDER_OVERRIDE") or "").strip().lower()
    _effective_override = _PROVIDER_OVERRIDE or (_env_prov if _env_prov else None)

    # Inner helpers: each returns a provider dict or None
    def _try_claude(ctx: str):
        key = _anthropic_key()
        if not key:
            return None
        try:
            import anthropic  # noqa: F401
        except ImportError:
            logger.warning("ANTHROPIC_API_KEY tersedia tapi 'anthropic' SDK belum ter-install.")
            return None
        return {"provider": "claude", "model": "claude-opus-4-5", "vision": True,
                "reason": f"Claude aktif ({ctx})"}

    def _try_gemini(ctx: str):
        key = _gemini_key()
        if not key:
            return None
        try:
            import google.generativeai  # noqa: F401
        except ImportError:
            logger.warning("GEMINI_API_KEY tersedia tapi 'google-generativeai' SDK belum ter-install.")
            return None
        mdl = _GEMINI_MODEL_OVERRIDE or "gemini-2.5-flash"
        return {"provider": "gemini", "model": mdl, "vision": True,
                "reason": f"Gemini aktif ({ctx})"}

    def _try_ollama(ctx: str):
        ok, mdl = _resolve_ollama_model()
        if not ok:
            return None
        return {"provider": "ollama", "model": mdl, "vision": False,
                "reason": f"Ollama aktif - {mdl} ({ctx})"}

    def _rules(ctx: str):
        return {"provider": "rules", "model": "rule-engine-v1", "vision": False,
                "reason": f"Offline Rule Engine ({ctx})"}

    # Override: "rules" — langsung ke local
    if _effective_override == "rules":
        return _rules("manual override")

    # Override: "ollama" — Ollama -> Rules (tanpa cloud)
    if _effective_override == "ollama":
        return (_try_ollama("PROVIDER_OVERRIDE=ollama") or
                _rules("Ollama tidak tersedia"))

    # Override: "gemini" — Gemini -> Ollama -> Rules
    if _effective_override == "gemini":
        return (_try_gemini("manual override") or
                _try_ollama("Gemini tidak tersedia - fallback") or
                _rules("Gemini & Ollama tidak tersedia"))

    # Override: "claude" — Claude -> Gemini -> Ollama -> Rules
    if _effective_override == "claude":
        return (_try_claude("manual override") or
                _try_gemini("Claude tidak tersedia - fallback") or
                _try_ollama("Cloud AI tidak tersedia - fallback") or
                _rules("Semua cloud & Ollama tidak tersedia"))

    # Auto-detect: Cloud -> Ollama -> Rules
    return (_try_claude("auto-detect") or
            _try_gemini("auto-detect") or
            _try_ollama("auto-detect") or
            _rules("semua provider tidak tersedia - offline mode"))

def _ai_chat(system: str, user: str, max_tokens: int = 2048) -> str:
    """
    Send a text prompt to the active provider. Returns raw response text.
    Raises HTTPException 503 if no provider is available.
    """
    info = _detect_provider()

    if info["provider"] == "claude":
        try:
            import anthropic as _ant
        except ImportError:
            raise HTTPException(503, "Anthropic SDK belum terinstall: pip install anthropic")
        client = _ant.Anthropic(api_key=_anthropic_key())
        msg = client.messages.create(
            model=info["model"],
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()

    if info["provider"] == "gemini":
        try:
            import google.generativeai as genai
        except ImportError:
            raise HTTPException(503, "Google Generative AI SDK belum terinstall: pip install google-generativeai")
        genai.configure(api_key=_gemini_key())
        model = genai.GenerativeModel(info["model"])
        # Gemini 1.5 doesn't have a direct 'system' parameter in generate_content,
        # but we can use System Instruction or just prepend to user message.
        # For simplicity and compatibility with older Gemini models, we prepend.
        prompt = f"{system}\n\nUSER: {user}"
        response = model.generate_content(prompt)
        return response.text.strip()

    if info["provider"] == "ollama":
        capped = _ollama_token_cap(info["model"], max_tokens)
        payload = json.dumps(
            {
                "model": info["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"num_predict": capped, "temperature": 0.3},
            }
        ).encode()
        req = _urlreq.Request(
            f"{_ollama_base()}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        logger.info(f"[ollama] Ã¢â€ â€™ POST {_ollama_base()}/api/chat  model={info['model']}  num_predict={capped}")
        try:
            with _urlreq.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            content = data["message"]["content"].strip()
            logger.info(f"[ollama] Ã¢â€ Â 200 OK  model={info['model']}  reply_len={len(content)}")
            return content
        except _urlerr.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:300]
            except Exception:
                pass
            logger.warning(f"[ollama] Ã¢â€ Â HTTP {e.code}  model={info['model']}  body={body[:120]}")
            if e.code == 400 and "does not support chat" in body.lower():
                gen_payload = json.dumps(
                    {
                        "model": info["model"],
                        "prompt": f"{system}\n\n{user}",
                        "stream": False,
                        "options": {"num_predict": capped, "temperature": 0.3},
                    }
                ).encode()
                gen_req = _urlreq.Request(
                    f"{_ollama_base()}/api/generate",
                    data=gen_payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                logger.info(f"[ollama] POST {_ollama_base()}/api/generate (chat unsupported) model={info['model']}")
                try:
                    with _urlreq.urlopen(gen_req, timeout=120) as gresp:
                        gdata = json.loads(gresp.read())
                    gcontent = (gdata.get("response") or "").strip()
                    if gcontent:
                        logger.info(f"[ollama] 200 OK (generate) model={info['model']} reply_len={len(gcontent)}")
                        return gcontent
                except Exception as gexc:  # noqa: BLE001
                    logger.warning(f"[ollama] generate fallback failed: {gexc}")
            if e.code == 404:
                global _OLLAMA_MODEL_OVERRIDE, _OLLAMA_MODEL_CACHE
                _OLLAMA_MODEL_OVERRIDE = None
                _OLLAMA_MODEL_CACHE = None
                _ok, fallback = _ollama_available()
                if _ok and fallback:
                    payload2 = json.dumps(
                        {
                            "model": fallback,
                            "messages": [
                                {"role": "system", "content": system},
                                {"role": "user", "content": user},
                            ],
                            "stream": False,
                            "options": {"num_predict": _ollama_token_cap(fallback, max_tokens), "temperature": 0.3},
                        }
                    ).encode()
                    req2 = _urlreq.Request(
                        f"{_ollama_base()}/api/chat",
                        data=payload2,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    try:
                        with _urlreq.urlopen(req2, timeout=120) as resp2:
                            data2 = json.loads(resp2.read())
                        return data2["message"]["content"].strip()
                    except Exception:
                        pass
                raise HTTPException(
                    503, f"Model '{info['model']}' tidak ditemukan. Pull dulu: ollama pull {info['model']}"
                )
            if e.code == 500:
                is_oom = "memory" in body.lower() or "out of memory" in body.lower()
                if is_oom:
                    _OLLAMA_OOM_BLACKLIST.add(info["model"])
                    _OLLAMA_MODEL_CACHE = None
                    logger.warning(
                        f"[ollama] OOM on '{info['model']}' Ã¢â‚¬â€ blacklisted. Trying lighter modelÃ¢â‚¬Â¦"
                    )
                    ok2, next_model = _ollama_available()
                    if ok2 and next_model:
                        logger.info(f"[ollama] Retrying with lighter model: {next_model}")
                        payload_retry = json.dumps(
                            {
                                "model": next_model,
                                "messages": [
                                    {"role": "system", "content": system},
                                    {"role": "user", "content": user},
                                ],
                                "stream": False,
                                "options": {
                                    "num_predict": _ollama_token_cap(next_model, max_tokens),
                                    "temperature": 0.3,
                                },
                            }
                        ).encode()
                        req_retry = _urlreq.Request(
                            f"{_ollama_base()}/api/chat",
                            data=payload_retry,
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        try:
                            with _urlreq.urlopen(req_retry, timeout=120) as resp_retry:
                                data_retry = json.loads(resp_retry.read())
                            content_retry = data_retry["message"]["content"].strip()
                            logger.info(
                                f"[ollama] Ã¢â€ Â 200 OK (retry) model={next_model}  reply_len={len(content_retry)}"
                            )
                            return content_retry
                        except Exception as retry_err:
                            logger.warning(f"[ollama] Retry with {next_model} also failed: {retry_err}")
                    raise HTTPException(
                        503,
                        f"Ollama: semua model kehabisan RAM (terakhir: '{info['model']}'). "
                        f"Gunakan Rule Engine, atau pull model ringan: "
                        f"ollama pull qwen2.5:7b  /  ollama pull phi3:mini  /  ollama pull tinyllama",
                    )
                raise HTTPException(503, f"Ollama error Ã¢â‚¬â€ model '{info['model']}': {body[:200]}")
            raise HTTPException(503, f"Ollama tidak dapat dihubungi: HTTP {e.code} Ã¢â‚¬â€ {body}")
        except _urlerr.URLError as e:
            raise HTTPException(503, f"Ollama tidak dapat dihubungi: {e}")

    raise HTTPException(503, info["reason"])


def _ai_chat_vision(system: str, user_text: str, image_b64: str, media_type: str, max_tokens: int = 1024) -> str:
    """
    Send an image + text prompt. Claude supports native vision.
    Ollama: OCR via pytesseract if available, else text-only fallback.
    Rules: OCR sentinel JSON returned for the receipt parser.
    """
    info = _detect_provider()

    if info["provider"] == "claude":
        try:
            import anthropic as _ant
        except ImportError:
            raise HTTPException(503, "Anthropic SDK belum terinstall: pip install anthropic")
        client = _ant.Anthropic(api_key=_anthropic_key())
        msg = client.messages.create(
            model=info["model"],
            max_tokens=max_tokens,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
        )
        return msg.content[0].text.strip()

    if info["provider"] == "gemini":
        try:
            import base64 as _b64
            import io as _io

            import google.generativeai as genai
            import PIL.Image as _PIL_Image
        except ImportError:
            raise HTTPException(503, "Google Generative AI SDK / PIL belum terinstall: pip install google-generativeai Pillow")

        genai.configure(api_key=_gemini_key())
        model = genai.GenerativeModel(info["model"])

        img_bytes = _b64.b64decode(image_b64)
        img = _PIL_Image.open(_io.BytesIO(img_bytes))

        # Prepend system prompt for Gemini
        prompt = f"{system}\n\nUSER: {user_text}"
        response = model.generate_content([prompt, img])
        return response.text.strip()

    if info["provider"] == "ollama":
        extracted_text = ""
        try:
            import base64 as _b64
            import io

            import PIL.Image
            import pytesseract
            img_bytes = _b64.b64decode(image_b64)
            img = PIL.Image.open(io.BytesIO(img_bytes))
            extracted_text = pytesseract.image_to_string(img, lang="ind+eng")
        except Exception:
            pass
        context = (
            f"Berikut teks yang berhasil diekstrak dari gambar struk:\n\n{extracted_text}\n\n"
            if extracted_text.strip()
            else "Gambar struk tidak dapat diekstrak teksnya. Gunakan nilai default yang masuk akal.\n\n"
        )
        return _ai_chat(system, context + user_text, max_tokens)

    if info["provider"] == "rules":
        extracted_text = ""
        try:
            import base64 as _b64
            import io

            import PIL.Image
            import pytesseract
            img_bytes = _b64.b64decode(image_b64)
            img = PIL.Image.open(io.BytesIO(img_bytes))
            extracted_text = pytesseract.image_to_string(img, lang="ind+eng")
        except Exception:
            pass
        return json.dumps({"_rule_ocr_text": extracted_text or ""})

    raise HTTPException(503, info["reason"])


# â”€â”€ JSON repair / fence-stripping â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _repair_truncated_json(raw: str) -> str:
    """Repair truncated JSON from LLM token cutoff. Also unwraps [{...}] â†’ {...}."""
    import json as _json

    def _unwrap(s):
        s = s.strip()
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].strip()
            if inner.startswith("{"):
                return inner
        return s

    try:
        parsed = _json.loads(raw)
        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
            return _json.dumps(parsed[0])
        return raw
    except _json.JSONDecodeError:
        pass

    repaired = raw.rstrip()
    stack, in_string, escape_next = [], False, False
    for ch in repaired:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    stack.pop()
    if in_string:
        repaired += '"'
    close_map = {"{": "}", "[": "]"}
    for opener in reversed(stack):
        repaired += close_map.get(opener, "}")
    repaired = _unwrap(repaired)
    try:
        _json.loads(repaired)
        return repaired
    except _json.JSONDecodeError:
        return raw


def _strip_json_fences(raw: str) -> str:
    """Remove markdown code fences and leading/trailing garbage from LLM output."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    first_brace = next((i for i, ch in enumerate(raw) if ch in "{["), -1)
    if first_brace > 0:
        raw = raw[first_brace:]
    last_brace = next((i for i in range(len(raw) - 1, -1, -1) if raw[i] in "}]"), -1)
    if 0 <= last_brace < len(raw) - 1:
        raw = raw[:last_brace + 1]
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if inner.startswith("{"):
            raw = inner
    return raw


# â”€â”€ Prompt templates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_RECEIPT_SYSTEM = """
Kamu adalah asisten keuangan expert yang membaca dokumen keuangan dengan akurasi 100%.
Tugasmu: ekstrak SEMUA informasi transaksi dari gambar dengan TEPAT mengikuti data yang tertulis.

Jawab HANYA dalam format JSON berikut (tanpa markdown, tanpa komentar, tanpa penjelasan):
{
  "merchant": "nama toko/merchant/bank yang tertera di struk",
  "date": "YYYY-MM-DD",
  "amount": 0,
  "currency": "IDR",
  "type": "expense|income|transfer",
  "category": "food|transport|housing|entertainment|health|shopping|education|investment|salary|freelance|transfer|other",
  "payment_method": "cash|bank-transfer|credit-card|debit-card|e-wallet|qris",
  "confidence": 0.95,
  "items": [
    {"name": "nama item", "qty": 1, "unit_price": 0, "total": 0}
  ],
  "notes": "informasi tambahan relevan (nomor ref, no rekening tujuan, dll)",
  "ai_analysis": "1-2 kalimat insight singkat berbasis data di struk ini (Bahasa Indonesia)"
}

ATURAN EKSTRAKSI JUMLAH (WAJIB IKUTI):
- "amount" = TOTAL yang benar-benar dibayar/diterima (setelah diskon, setelah pajak)
- Jika ada kolom TOTAL, GRAND TOTAL, JUMLAH BAYAR, NOMINAL → gunakan nilai tertinggi akhir
- Jika ada SUBTOTAL + PPN/Pajak → amount = SUBTOTAL + PPN (bukan subtotal saja)
- Jika ada DISKON/DISC → amount = harga setelah diskon
- Untuk mutasi rekening: amount = nilai transfer/debet/kredit yang tercantum
- JANGAN gunakan subtotal sebagai amount jika ada total yang lebih besar

ATURAN MERCHANT:
- Gunakan nama yang tertera persis di struk, bukan terjemahan
- Untuk struk ATM/Mobile Banking: merchant = nama bank (e.g. "BCA", "BRI", "Mandiri")
- Untuk struk belanja: merchant = nama toko/restoran yang tertera
- Untuk bukti transfer: merchant = nama pengirim atau penerima yang relevan

ATURAN TANGGAL:
- Format: YYYY-MM-DD (e.g. 2026-08-13)
- Jika ada format Indonesia (13 Agustus 2026, 13/08/2026, 13-08-2026) → konversi ke YYYY-MM-DD
- Jika tanggal tidak ditemukan → gunakan hari ini

ATURAN KATEGORI:
- food: restoran, warung, kafe, delivery makanan, supermarket, minimarket, grocery
- transport: SPBU/BBM, parkir, toll, ojek, taxi, kereta, bus, grab/gojek transport
- housing: listrik, air, internet, WiFi, sewa, kos, kontrakan, PLN, PDAM
- entertainment: game, streaming, bioskop, hobi, musik
- health: apotek, klinik, RS, dokter, obat, vitamin
- shopping: fashion, elektronik, gadget, perabot, marketplace (Shopee/Tokopedia/Lazada)
- education: kursus, buku, sekolah, kampus, beasiswa
- investment: saham, reksa dana, crypto, tabungan investasi
- salary: gaji, THR, bonus, tunjangan (income type)
- freelance: project, client payment, invoice
- transfer: pindah buku, top up, withdraw, transfer antar rekening
- other: tidak termasuk kategori di atas

ATURAN PAYMENT METHOD:
- cash: bayar tunai, uang tunai
- bank-transfer: transfer bank, pindah buku, ATM transfer
- credit-card: kartu kredit, CC, credit
- debit-card: kartu debit, ATM debit
- e-wallet: OVO, GoPay, ShopeePay, DANA, LinkAja, Jenius
- qris: QRIS, QR code payment

ATURAN TYPE:
- expense: pembelian, pembayaran, pengeluaran, debet
- income: penerimaan uang, gaji, transfer masuk, kredit
- transfer: top up e-wallet, transfer antar rekening sendiri, penarikan tunai (withdraw)

ATURAN CONFIDENCE:
- 0.95-1.0: semua data terbaca jelas dan lengkap
- 0.75-0.94: sebagian besar data jelas, 1-2 field perlu konfirmasi
- 0.50-0.74: gambar blur/miring, beberapa field tidak pasti
- 0.0-0.49: gambar sangat buruk, data sebagian besar asumsi

CATATAN PENTING:
- Baca SEMUA teks di gambar sebelum menjawab
- Jangan mengarang data yang tidak ada di gambar
- Untuk struk panjang dengan banyak item, daftarkan semua di "items"
- "notes" isi dengan no. referensi transaksi, no. kartu (4 digit terakhir), atau info penting lainnya
""".strip()

_INSIGHTS_SYSTEM = """
Kamu adalah financial advisor AI personal untuk pengguna aplikasi manajemen keuangan ini.
Kamu berbicara SEPERTI seorang teman yang paham betul kondisi keuangan pengguna — memakai kata "kamu",
merujuk profil aktifnya, dan selalu mengacu angka nyata dari blok DATA di bawah. Empatik tapi jujur.

Tugasmu: analisis DATA KEUANGAN PENGGUNA (blok di user message) dan berikan insight yang:
  - SESUAI DENGAN KEADAAN SEBENARNYA (angka harus persis dari data, tidak mengarang, tidak menutupi defisit)
  - DETAILED (setiap poin menyebut nominal/angka transaksi/kategori/month-to-month yang ada di data)
  - PERSONAL (untuk profil aktif pengguna, disesuaikan goals & pola impulsif yang terdata)

PERIODE ANALISIS:
- Cek bulan yang tertulis di judul blok DATA (baris "DATA KEUANGAN PENGGUNA — <bulan>"). Itulah periode analisis.
- Jika ada CATATAN PENTING tentang fallback bulan, patuhi: "bulan ini" berarti bulan yang dipakai analisis.
- Jangan pernah berasumsi periode selain yang tertulis di DATA.

Jawab HANYA dalam format JSON berikut (tanpa markdown, tanpa teks lain):
{
  "fbs_score": 0,
  "overall_assessment": "1-2 kalimat ringkasan kondisi keuanganmu berdasarkan angka aktual: total pemasukan, total pengeluaran, surplus/defisit, dan satu fakta menonjol",
  "score_interpretation": "penjelasan mengapa skor FBS bernilai angka tersebut, merujuk angka nyata (saving rate, budget compliance, pertumbuhan pengeluaran, stabilitas income)",
  "top_risk": "risiko paling kritis yang terdeteksi dari data DENGAN ANGKA KONKRET (contoh: 'defisit Rp X' atau 'kategori Y naik +Z%') — jika tidak ada risiko serius, tetap sebutkan risiko terkecil yang jujur",
  "biggest_win": "hal positif terbesar dari data bulan ini dengan angka konkret, atau null jika jujur tidak ada",
  "spending_pattern": "pola dominan pengeluaranmu berdasarkan kategori & metode pembayaran yang terdata, sebutkan kategori terbesar dan %-nya",
  "impulse_analysis": "analisis perilaku impulsif berdasarkan Impulse Index dan daftar transaksi impulsif teratas (jika tersedia), atau jelaskan bahwa tidak ada tanda impulsif berlebih",
  "lifestyle_inflation_verdict": "verdict apakah terjadi lifestyle inflation berdasar perbandingan MoM dan tren 3 bulan yang tersedia — jujur: 'ya', 'tidak', atau 'tidak cukup data'",
  "recommendations": [
    {"priority": "high", "action": "tindakan spesifik dengan angka target (kategori, nominal, tenggat)", "reason": "alasan dengan referensi data aktual", "impact": "dampak kuantitatif jika dilakukan"},
    {"priority": "medium", "action": "tindakan spesifik dengan angka target (kategori, nominal, tenggat)", "reason": "alasan dengan referensi data aktual", "impact": "dampak kuantitatif jika dilakukan"},
    {"priority": "low", "action": "tindakan spesifik dengan angka target (kategori, nominal, tenggat)", "reason": "alasan dengan referensi data aktual", "impact": "dampak kuantitatif jika dilakukan"}
  ],
  "next_month_forecast": "prediksi konkret bulan depan berdasarkan tren aktual: perkirakan pengeluaran/pemasukan dan apakah defisit bisa tertutup",
  "motivational_note": "pesan motivasi personal 1 kalimat yang relevan dengan kondisi & profil aktif pengguna (bukan template umum)"
}

ATURAN WAJIB — VIOLATIONS = FAIL:
1. "fbs_score": gunakan skor FBS yang ada di DATA jika tersedia; jika tidak, hitung 0-100 dari:
   saving_rate (40%), budget_compliance (20%), expense_growth (20%), income_stability (20%).
2. Semua nilai dalam Bahasa Indonesia kecuali istilah teknis keuangan.
3. Setiap insight WAJIB menyebut angka spesifik yang benar-benar ada di DATA (Rp, %, jumlah transaksi, dst).
   DILARANG membuat angka yang tidak ada di DATA.
4. Defisit (pengeluaran > pemasukan) WAJIB dikatakan secara terbuka di overall_assessment & top_risk,
   beserta nominalnya. Jangan mengelak, jangan menyebutnya surplus.
5. Transfer masuk (pindah dana sendiri) BUKAN pemasukan — jangan dihitung sebagai income dalam analisis.
6. Rekomendasi WAJIB spesifik: bukan "kurangi pengeluaran" tapi "kurangi {kategori} dari Rp X ke Rp Y".
7. Jumlah rekomendasi boleh 2-4, urutkan berdasarkan urgensi untuk kondisi nyata pengguna.
8. Format angka: "Rp 1.500.000" (bukan 1500000 atau Rp1.5jt).
9. biggest_win boleh null jika jujur tidak ada hal positif dari data.
10. Jika DATA benar-benar kosong (tidak ada transaksi sama sekali): sampaikan itu dengan jujur,
    beri saran membangun untuk mulai mencatat, dan JANGAN mengarang angka.
""".strip()

_INSIGHTS_SYSTEM_SMALL = """You are a personal finance assistant. The user message contains REAL financial data for a specific month. Output ONLY a single JSON object. No array. No markdown. No explanation. No text before or after the JSON.

Output exactly this structure (fill in real values only, based strictly on the numbers in the data):
{"overall_assessment":"one sentence summary using the real income/expense totals and whether surplus or DEFISIT","top_risk":"biggest real risk found with the real amount/percentage","biggest_win":"best real positive thing or null","recommendations":[{"priority":"high","action":"specific action with real target numbers","reason":"data-based reason","impact":"expected result"},{"priority":"medium","action":"specific action with real target numbers","reason":"data-based reason","impact":"expected result"}],"motivational_note":"one sentence encouragement for this user"}

Rules: Use Bahasa Indonesia for all values. Reference the month label shown in the data. Be honest: if expenses exceed income, say DEFISIT with the real amount; never claim a surplus that is not in the data. Do NOT invent numbers. Start your response with { and end with }.""".strip()

# Models known to be too small for the full schema
_SMALL_MODELS = {"tinyllama", "phi3", "gemma2", "llama3.2:1b", "llama3.2"}


def _insights_system_for(model: str) -> str:
    """Return the appropriate system prompt based on model capability."""
    base = model.split(":")[0].lower()
    return _INSIGHTS_SYSTEM_SMALL if base in _SMALL_MODELS else _INSIGHTS_SYSTEM


def _insights_tokens_for(model: str, default: int = 768) -> int:
    """Return token budget for insights generation. Never below 640."""
    base = model.split(":")[0].lower()
    cap  = _OLLAMA_TOKEN_CAPS.get(base, default)
    return max(cap, 640)

