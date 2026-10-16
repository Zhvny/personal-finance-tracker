"""
backend/ai/json_repair.py â€” JSON repair and fence-stripping for LLM output.
"""


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
        raw = raw[: last_brace + 1]
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if inner.startswith("{"):
            raw = inner
    return raw
