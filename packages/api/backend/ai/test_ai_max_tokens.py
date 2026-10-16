"""Audit T3 AI-01 (2026-09-02): vision max_tokens hard cap.

The ``_ai_chat_vision`` path previously passed the caller-supplied
``max_tokens`` straight to the Anthropic SDK, letting any caller force
Opus 4.5 to emit up to its model limit. The fix clamps the value to
[1, 4096] regardless of caller input. This test verifies the clamp by
exercising the public helper indirectly.
"""
from __future__ import annotations


import pytest


@pytest.fixture
def reload_module(monkeypatch):
    """Force-reload the module so env-mutation tests pick up changes."""
    import sys

    for m in list(sys.modules):
        if m.endswith("provider_strategy") or m.endswith("routers.ai"):
            del sys.modules[m]
    yield
    for m in list(sys.modules):
        if m.endswith("provider_strategy") or m.endswith("routers.ai"):
            del sys.modules[m]


def test_vision_max_tokens_clamped_to_ceiling(monkeypatch, reload_module):
    """Passing max_tokens=999999 must clamp to 4096 inside the helper."""
    monkeypatch.setenv("ANTHROPIC_OPT_IN", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

    # Import after env is set; the helper reads env at import-time only
    # for the opt-in check, not at call time.
    from packages.api.backend.ai import provider_strategy as _ps

    captured = {}

    class _FakeMessages:
        def create(self, **kwargs):
            captured["max_tokens"] = kwargs.get("max_tokens")
            class _Resp:
                content = [type("X", (), {"text": "ok"})()]
            return _Resp()

    class _FakeAnthropic:
        def __init__(self, api_key=None):
            pass
        class _Messages:
            pass
        messages = _FakeMessages()

    monkeypatch.setattr(_ps, "_anthropic_key", lambda: "sk-test-fake")
    # Patch the lazy import inside the function.
    import sys
    import types
    fake = types.ModuleType("anthropic")
    fake.Anthropic = _FakeAnthropic
    sys.modules["anthropic"] = fake

    # Provide a one-pixel PNG so the path is exercised.
    import base64
    png_b64 = base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
        b"\xff?\x00\x05\xfe\x02\xfe\xa3z\xd9\xa7\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode("ascii")

    _ps._ai_chat_vision("sys", "user", png_b64, "image/png", max_tokens=999_999)
    assert captured["max_tokens"] == 4096, (
        f"expected ceiling 4096, got {captured['max_tokens']!r}"
    )


def test_vision_max_tokens_low_clamped_to_one(monkeypatch, reload_module):
    """max_tokens=1 is the minimum — caller can ask for less, but the
    helper guarantees the request is at least 1 token. Anything between
    1 and the ceiling passes through unclamped."""
    monkeypatch.setenv("ANTHROPIC_OPT_IN", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

    from packages.api.backend.ai import provider_strategy as _ps

    captured = {}

    class _FakeMessages:
        def create(self, **kwargs):
            captured["max_tokens"] = kwargs.get("max_tokens")
            class _Resp:
                content = [type("X", (), {"text": "ok"})()]
            return _Resp()

    class _FakeAnthropic:
        def __init__(self, api_key=None):
            pass
        messages = _FakeMessages()

    import sys
    import types
    fake = types.ModuleType("anthropic")
    fake.Anthropic = _FakeAnthropic
    sys.modules["anthropic"] = fake
    monkeypatch.setattr(_ps, "_anthropic_key", lambda: "sk-test-fake")

    import base64
    png_b64 = base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
        b"\xff?\x00\x05\xfe\x02\xfe\xa3z\xd9\xa7\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode("ascii")

    _ps._ai_chat_vision("sys", "user", png_b64, "image/png", max_tokens=1)
    assert captured["max_tokens"] == 1


def test_vision_max_tokens_in_range_unchanged(monkeypatch, reload_module):
    """max_tokens=512 is in range — passes through unchanged."""
    monkeypatch.setenv("ANTHROPIC_OPT_IN", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

    from packages.api.backend.ai import provider_strategy as _ps

    captured = {}

    class _FakeMessages:
        def create(self, **kwargs):
            captured["max_tokens"] = kwargs.get("max_tokens")
            class _Resp:
                content = [type("X", (), {"text": "ok"})()]
            return _Resp()

    class _FakeAnthropic:
        def __init__(self, api_key=None):
            pass
        messages = _FakeMessages()

    import sys
    import types
    fake = types.ModuleType("anthropic")
    fake.Anthropic = _FakeAnthropic
    sys.modules["anthropic"] = fake
    monkeypatch.setattr(_ps, "_anthropic_key", lambda: "sk-test-fake")

    import base64
    png_b64 = base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
        b"\xff?\x00\x05\xfe\x02\xfe\xa3z\xd9\xa7\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode("ascii")

    _ps._ai_chat_vision("sys", "user", png_b64, "image/png", max_tokens=512)
    assert captured["max_tokens"] == 512
