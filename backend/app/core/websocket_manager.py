import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    In-process registry of WebSocket clients watching a given analysis file_id.

    NOTE: this is per-process / per-worker. It works fine for a single
    Uvicorn worker. If you scale to multiple workers or instances behind a
    load balancer, a client connected to worker A will never see a push
    sent from worker B's background task. In that case, swap this for
    Redis pub/sub: PUBLISH on send_status(), SUBSCRIBE per file_id on
    connect(). You already have `redis_client` available in this project.
    """

    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, file_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(file_id, set()).add(websocket)
        logger.info(
            f"🔌 WS connected: {file_id} "
            f"({len(self._connections[file_id])} client(s))"
        )

    def disconnect(self, file_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(file_id)
        if conns and websocket in conns:
            conns.remove(websocket)
            if not conns:
                del self._connections[file_id]
        logger.info(f"🔌 WS disconnected: {file_id}")

    async def send_status(self, file_id: str, payload: dict) -> None:
        """
        Push a status payload to every client watching file_id.
        Safe to call even if nobody is connected — it's just a no-op then.
        """
        for ws in list(self._connections.get(file_id, set())):
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.warning(f"WS send failed for {file_id}, dropping client: {e}")
                self.disconnect(file_id, ws)


manager = ConnectionManager()