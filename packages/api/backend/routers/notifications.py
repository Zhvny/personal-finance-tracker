import hmac
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from packages.api.backend.core.websocket_manager import manager
from packages.api.backend.security.core import _get_api_key, _is_dev_mode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["Notifications"])

_LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}

@router.websocket("/notifications/{client_id}")
async def websocket_notifications(websocket: WebSocket, client_id: str, token: Optional[str] = Query(None)):
    """
    WebSocket endpoint for real-time task status updates (authenticated).

    SECURITY: dev-mode bypass hanya berlaku untuk koneksi loopback —
    jaringan lain selalu wajib token meskipun dev mode aktif.
    """
    client_host = websocket.client.host if websocket.client else ""
    is_loopback = (
        client_host in _LOOPBACK
        or client_host.startswith("::ffff:127.")
    )

    if not (_is_dev_mode() and is_loopback):
        api_key = _get_api_key()
        # Allow token from query param, Authorization header, or Sec-WebSocket-Protocol header
        auth_header = websocket.headers.get("authorization") or websocket.headers.get("sec-websocket-protocol")
        effective_token = token
        if not effective_token and auth_header:
            effective_token = auth_header.replace("Bearer ", "").strip()

        if not api_key or not effective_token or not hmac.compare_digest(effective_token, api_key):
            logger.warning(
                f"[security] Unauthorized WebSocket connection attempt "
                f"for client_id={client_id} from {client_host}"
            )
            await websocket.close(code=1008) # 1008: Policy Violation / Unauthorized
            return

    await manager.connect(websocket, client_id)
    try:
        while True:
            # We mostly push server -> client, but we need to keep the connection open
            # and handle potential pings or client messages.
            data = await websocket.receive_text()
            # Simple heartbeat/echo for testing
            if data == "ping":
                await manager.send_personal_message({"type": "pong"}, client_id)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)

