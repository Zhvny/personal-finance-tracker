"""
alpha-gateway :8444 — public entry of the Alpha microservice platform.

Builds an exact (method, path) -> downstream route table from each service's
/openapi.json at startup, then reverse-proxies. No hardcoded path list, so
route drift cannot silently misroute.

WebSocket /ws/* is transparently proxied to ALPHA_WS_UPSTREAM (default:
platform :8450). If a second service ever exposes WS, promote this to a
path-based WS route table.
"""

import asyncio
import os
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress

import httpx
import uvicorn
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from services.runtime.bootstrap import _setup_logging
from services.runtime.service_token import inject_service_token

logger = _setup_logging("alpha-gateway")

DEFAULT_DOWNSTREAMS = {
    "platform": "http://localhost:8450",
    "ledger": "http://localhost:8451",
    "portfolio": "http://localhost:8452",
    "market": "http://localhost:8453",
    "insights": "http://localhost:8454",
    "engagement": "http://localhost:8455",
}

WS_UPSTREAM = os.getenv(
    "ALPHA_WS_UPSTREAM",
    "http://platform:8450" if os.getenv("ENVIRONMENT", "").lower() == "production" else DEFAULT_DOWNSTREAMS["platform"],
)


def _ws_routes() -> list[tuple[str, str]]:
    """Path-prefix -> WS upstream mapping.

    Audit A-M03: previously the gateway proxied every /ws/* connection
    to a single upstream. Now operators can route WS by prefix. The
    list is matched in order; the first prefix match wins. Format:
    ``ALPHA_WS_ROUTES="notifications=http://platform:8450,realtime=http://insights:8454"``.
    An unprefixed request (e.g. ``/ws/``) falls back to ``WS_UPSTREAM``.
    """
    raw = os.getenv("ALPHA_WS_ROUTES", "").strip()
    if not raw:
        return []
    out: list[tuple[str, str]] = []
    for pair in raw.split(","):
        prefix, _, url = pair.strip().partition("=")
        if prefix and url:
            out.append((prefix.strip().lstrip("/"), url.strip().rstrip("/")))
    return out


def _resolve_ws_upstream(path: str) -> str:
    """Pick a WS upstream based on path prefix; fall back to WS_UPSTREAM."""
    for prefix, url in _ws_routes():
        if path == prefix or path.startswith(prefix + "/"):
            return url
    return WS_UPSTREAM


HOP_BY_HOP = {"host", "content-length", "connection", "keep-alive", "transfer-encoding", "te", "upgrade"}


class _RateLimitExceeded(Exception):
    """Raised by the gateway rate limiter so the middleware can return 429."""

    def __init__(self, retry_after: int, ip: str, limit: int) -> None:
        super().__init__(f"rate limit exceeded for {ip}")
        self.retry_after = retry_after
        self.ip = ip
        self.limit = limit


# In-memory sliding-window rate limiter, per-IP. Per-process state
# (audit A-H05): multi-replica deployments effectively multiply the
# limit by N replicas. A Redis-backed INCR+EXPIRE limiter is the
# upgrade path; see services/runtime/service_token.py for the same
# pattern. Set ALPHA_GATEWAY_RATE_LIMIT=0 to disable.
LOOPBACK_IPS = {"127.0.0.1", "::1", "localhost", "testclient"}
LOOPBACK_RATE_LIMIT_MULTIPLIER = 2
_RATE_WINDOW_SECS = 60
_RATE_STORE: dict[str, deque] = defaultdict(lambda: deque())


def _effective_client_ip(request: Request) -> str:
    """XFF-aware client IP resolution (mirrors packages.api.backend.security.core).

    Only trusts X-Forwarded-For when the direct connection comes from a
    private/loopback proxy. Prevents IP spoofing behind ingress.
    """
    direct = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return direct
    direct_normalized = direct.replace("::ffff:", "", 1) if direct.startswith("::ffff:") else direct
    is_private_proxy = (
        direct_normalized in LOOPBACK_IPS
        or direct_normalized.startswith("10.")
        or direct_normalized.startswith("192.168.")
        or direct_normalized.startswith("172.16.")
        or direct_normalized.startswith("172.17.")
        or direct_normalized.startswith("172.18.")
        or direct_normalized.startswith("172.19.")
        or direct_normalized.startswith("172.2")
        or direct_normalized.startswith("172.30.")
        or direct_normalized.startswith("172.31.")
    )
    return forwarded.split(",")[0].strip() if is_private_proxy else direct


def _gateway_rate_limit() -> int:
    raw = os.getenv("ALPHA_GATEWAY_RATE_LIMIT", "300")
    if not raw.isdigit():
        return 300
    return int(raw)


def _check_rate_limit(request: Request) -> None:
    """Sliding-window IP rate limit. Returns silently if disabled."""
    limit = _gateway_rate_limit()
    if limit <= 0:
        return
    ip = _effective_client_ip(request)
    effective = limit * LOOPBACK_RATE_LIMIT_MULTIPLIER if ip in LOOPBACK_IPS else limit
    now = time.time()
    window = _RATE_STORE[ip]
    while window and window[0] < now - _RATE_WINDOW_SECS:
        window.popleft()
    if len(window) >= effective:
        raise _RateLimitExceeded(retry_after=_RATE_WINDOW_SECS, ip=ip, limit=effective)
    window.append(now)


def _downstreams() -> dict[str, str]:
    raw = os.getenv("ALPHA_GATEWAY_TARGETS")
    if not raw:
        return DEFAULT_DOWNSTREAMS
    out = {}
    for pair in raw.split(","):
        name, _, url = pair.strip().partition("=")
        if name and url:
            out[name] = url.rstrip("/")
    return out or DEFAULT_DOWNSTREAMS


async def _build_route_table(client: httpx.AsyncClient, downstreams: dict[str, str]) -> dict[tuple[str, str], str]:
    table: dict[tuple[str, str], str] = {}
    for name, base_url in downstreams.items():
        try:
            resp = await client.get(f"{base_url}/openapi.json", timeout=5)
            resp.raise_for_status()
            spec = resp.json()
            for path, methods in spec.get("paths", {}).items():
                for method in methods:
                    if method.lower() in ("get", "post", "put", "patch", "delete", "options", "head"):
                        table[(method.upper(), path)] = base_url
            logger.info(f"Route table: {name} contributed {len(spec.get('paths', {}))} paths.")
        except Exception as e:
            logger.warning(f"openapi.json unavailable from {name} ({base_url}): {e}")
    return table


async def _check_ws_auth(ws: WebSocket) -> str | None:
    """Bearer check for WS handshake, equivalent to HTTP ``verify_api_key``.

    The HTTP dependency is reused directly (it only needs ``.headers`` /
    ``.client`` / ``.query_params``, all present on ``WebSocket``). Scope:
    every token passing ``verify_api_key`` holds at least ``read`` scope
    (master key = admin, ``user_`` session = read), so this equals
    ``require_scope("read")``. Returns the token, or ``None`` on failure.
    """
    auth = ws.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token:
        token = ws.query_params.get("token") or ws.query_params.get("api_key") or ""
    try:
        from packages.api.backend.security.core import verify_api_key

        return await verify_api_key(token or None, ws)  # type: ignore[arg-type]
    except Exception as e:
        logger.warning(f"WS auth rejected: {type(e).__name__}: {e}")
        return None


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.client = httpx.AsyncClient(timeout=60)
        # Internal gateway → downstream calls must carry the service token,
        # otherwise the downstreams' IP deny-list rejects bridge-network
        # callers (openapi route-table build + /health aggregation below).
        from services.runtime.service_token import get_service_token

        app.state.client.headers["X-Service-Token"] = get_service_token()
        downstreams = _downstreams()
        table = {}
        for attempt in range(30):
            table = await _build_route_table(app.state.client, downstreams)
            if len(set(table.values())) == len(downstreams):
                break
            logger.info(f"Waiting for all downstream openapi.json (attempt {attempt + 1}/30)...")
            await asyncio.sleep(2)
        app.state.route_table = table
        app.state.ready = bool(table)
        logger.info(f"Gateway ready with {len(table)} exact routes.")

        # Start the rate-store sweeper (audit A-L03).
        async def _sweep_loop() -> None:
            while True:
                try:
                    await asyncio.sleep(300)
                    cutoff = time.time() - _RATE_WINDOW_SECS
                    empty: list[str] = []
                    for ip, window in list(_RATE_STORE.items()):
                        while window and window[0] < cutoff:
                            window.popleft()
                        if not window:
                            empty.append(ip)
                    for ip in empty:
                        _RATE_STORE.pop(ip, None)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"rate-store sweep failed: {e}")

        sweeper = asyncio.create_task(_sweep_loop())
        try:
            yield
        finally:
            sweeper.cancel()
            with suppress(asyncio.CancelledError):
                await sweeper
            await app.state.client.aclose()

    app = FastAPI(title="alpha-gateway", version="1.0.0", lifespan=lifespan)
    app.state.route_table = {}
    app.state.client = None
    app.state.ready = False

    # A-004: warn loudly at startup if prod has no shared rate-limit store.
    # The in-memory store multiplies the effective limit by N replicas.
    if (
        os.getenv("ENVIRONMENT", "").lower() == "production"
        and _gateway_rate_limit() > 0
        and not os.getenv("ALPHA_REDIS_URL")
    ):
        import logging

        logging.getLogger("alpha.gateway").error(
            "ALPHA_REDIS_URL is unset in prod — gateway rate limit is per-process only; "
            "with N replicas, the effective limit is N * ALPHA_GATEWAY_RATE_LIMIT. "
            "Configure ALPHA_REDIS_URL and switch to a Redis-backed limiter."
        )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # Skip rate limiting for the public health probes (used by
        # orchestrators and the downstream-aggregating /health route
        # which polls every 30s in the startup loop).
        if request.url.path in ("/health", "/health/live", "/health/ready", "/openapi.json"):
            return await call_next(request)
        try:
            _check_rate_limit(request)
        except _RateLimitExceeded as exc:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded: {exc.limit}/min"},
                headers={"Retry-After": str(exc.retry_after)},
            )
        return await call_next(request)

    @app.get("/health/live", include_in_schema=False)
    async def gateway_live():
        return {"status": "ok", "service": "alpha-gateway"}

    @app.get("/health", tags=["System"])
    async def gateway_health():
        if not app.state.ready:
            return JSONResponse(status_code=503, content={"status": "starting", "service": "alpha-gateway"})
        matrix = {}
        for name, base in _downstreams().items():
            try:
                r = await app.state.client.get(f"{base}/health/live", timeout=3)
                matrix[name] = "up" if r.status_code == 200 else f"http_{r.status_code}"
            except Exception:
                matrix[name] = "down"
        healthy = [v == "up" for v in matrix.values()]
        status = "ok" if all(healthy) else ("degraded" if any(healthy) else "unhealthy")
        code = 200 if status == "ok" else 503
        return JSONResponse(
            status_code=code, content={"status": status, "service": "alpha-gateway", "downstream": matrix}
        )

    @app.websocket("/ws/{path:path}")
    async def ws_proxy(ws: WebSocket, path: str):
        if await _check_ws_auth(ws) is None:
            await ws.close(code=4401)
            return
        await ws.accept()
        upstream_base = _resolve_ws_upstream(path)
        query = ws.url.query
        target = f"{upstream_base.replace('http', 'ws', 1)}/ws/{path}"
        if query:
            target += f"?{query}"
        try:
            async with websockets.connect(target, max_size=None) as upstream:

                async def client_to_upstream():
                    while True:
                        msg = await ws.receive()
                        if msg["type"] == "websocket.disconnect":
                            return
                        if msg.get("text") is not None:
                            await upstream.send(msg["text"])
                        elif msg.get("bytes") is not None:
                            await upstream.send(msg["bytes"])

                async def upstream_to_client():
                    async for message in upstream:
                        if isinstance(message, str):
                            await ws.send_text(message)
                        else:
                            await ws.send_bytes(message)

                done, pending = await asyncio.wait(
                    [asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
        except (WebSocketDisconnect, websockets.ConnectionClosed):
            pass
        except Exception as e:
            logger.warning(f"WS proxy error /ws/{path}: {e}")
        finally:
            with suppress(Exception):
                await ws.close()

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def proxy(path: str, request: Request):
        # Correlation ID: pakai yang dikirim klien, kalau tidak ada generate.
        # Diteruskan ke downstream, dicatat di log, dan di-echo di response
        # (termasuk error) supaya satu request bisa dilacak lintas service.
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        candidates = [
            (request.method, "/" + path),
            (request.method, "/" + path.rstrip("/")),
            (request.method, "/" + path + "/"),
        ]
        target_base = None
        for key in candidates:
            target_base = app.state.route_table.get(key)
            if target_base:
                break
        if not target_base:
            # honey: known_roots sengaja tidak disertakan — tidak membocorkan
            # topologi rute internal ke pemanggil anonim (SECURITY-AUDIT F-2).
            return JSONResponse(
                status_code=404,
                content={"detail": f"No route for '{request.method} /{path}'"},
                headers={"x-request-id": request_id},
            )
        headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
        headers["x-request-id"] = request_id
        # SECURITY: strip ?token=/api_key dari query sebelum forward upstream —
        # kredensial di URL bocor ke log akses/proxy; auth lewat header.
        params = dict(request.query_params)
        for _secret in ("token", "api_key"):
            params.pop(_secret, None)
        # Stamp the shared service token so downstreams can verify this
        # request came through the gateway. The token is auto-generated
        # in dev if ALPHA_SERVICE_TOKEN is unset; production must set it.
        inject_service_token(headers)
        body = await request.body()
        try:
            upstream = await app.state.client.request(
                request.method,
                f"{target_base}/{path}",
                params=params,
                headers=headers,
                content=body,
            )
        except httpx.RequestError as e:
            safe_path = path.replace("\n", " ").replace("\r", " ")
            logger.warning(f"[{request_id}] {request.method} /{safe_path} -> {target_base} gagal: {e}")
            return JSONResponse(
                status_code=502,
                # honey: detail error lengkap hanya di log — jangan bocorkan host internal.
                content={"detail": "Upstream unavailable.", "request_id": request_id},
                headers={"x-request-id": request_id},
            )
        resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP}
        resp_headers.setdefault("x-request-id", request_id)
        if upstream.status_code >= 500:
            logger.warning(f"[{request_id}] {request.method} /{path} -> {upstream.status_code} dari {target_base}")
        return Response(content=upstream.content, status_code=upstream.status_code, headers=resp_headers)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("ALPHA_GATEWAY_PORT", "8444"))
    # Selaras dengan S-3: default loopback; docker setel HOST=0.0.0.0 eksplisit.
    host = os.getenv("HOST", "127.0.0.1")
    print(f"\n[*] alpha-gateway on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
