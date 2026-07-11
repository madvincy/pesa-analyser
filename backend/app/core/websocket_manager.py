"""
WebSocket connection manager with graceful failure handling.
"""

import asyncio
import logging
from typing import Dict, Set, Optional, List

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
        self._lock = asyncio.Lock()
        self._max_connections_per_analysis = 10
        self._max_total_connections = 100

    async def connect(self, file_id: str, websocket: WebSocket) -> bool:
        """
        Connect a WebSocket with rate limiting and connection limits.
        Returns True if connected, False if rejected.
        """
        async with self._lock:
            # Clean up stale connections first
            await self._cleanup_stale_connections()

            # Check total connection limit
            total_connections = await self._get_total_connections()
            if total_connections >= self._max_total_connections:
                logger.warning(
                    f"⚠️ Max total connections reached: {self._max_total_connections}"
                )
                try:
                    await websocket.close(code=1008, reason="Server at capacity")
                except Exception:
                    pass
                return False

            # Check per-analysis connection limit
            if file_id in self._connections:
                if (
                    len(self._connections[file_id])
                    >= self._max_connections_per_analysis
                ):
                    logger.warning(
                        f"⚠️ Max connections for analysis {file_id}: {self._max_connections_per_analysis}"
                    )
                    try:
                        await websocket.close(
                            code=1008, reason="Too many connections for this analysis"
                        )
                    except Exception:
                        pass
                    return False

            # Accept the connection
            try:
                await websocket.accept()
            except Exception as e:
                logger.warning(f"Failed to accept WebSocket: {e}")
                return False

            # Store the connection
            self._connections.setdefault(file_id, set()).add(websocket)
            logger.info(
                f"🔌 WS connected: {file_id} "
                f"({len(self._connections[file_id])} client(s))"
            )
            return True

    def disconnect(self, file_id: str, websocket: WebSocket) -> None:
        """Disconnect a WebSocket."""
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
        Never raises exceptions — all failures are logged and ignored.
        """
        # ✅ FIX: Check if there are any connections first
        if file_id not in self._connections:
            return

        # Clean up stale connections
        await self._cleanup_stale_connections()

        # Check again after cleanup
        if file_id not in self._connections:
            return

        # Get a copy of the connections set to avoid modification during iteration
        connections = list(self._connections.get(file_id, set()))

        if not connections:
            return

        disconnected = []
        for ws in connections:
            try:
                await ws.send_json(payload)
            except Exception as e:
                # Log at debug level - WebSocket failure is not critical
                logger.debug(f"WS send failed for {file_id}: {e}")
                disconnected.append(ws)

        # Remove disconnected clients
        for ws in disconnected:
            self.disconnect(file_id, ws)

    async def broadcast(self, file_id: str, payload: dict) -> None:
        """Alias for send_status."""
        await self.send_status(file_id, payload)

    async def close_all(self, file_id: str) -> None:
        """Close all connections for a file_id."""
        conns = self._connections.get(file_id)
        if conns:
            for ws in list(conns):
                try:
                    await ws.close(code=1000, reason="Analysis complete")
                except Exception:
                    pass
            del self._connections[file_id]
            logger.info(f"🔌 Closed all connections for {file_id}")

    async def _cleanup_stale_connections(self) -> None:
        """Remove closed or dead connections."""
        stale_ids = []
        for file_id, connections in self._connections.items():
            active = set()
            for ws in connections:
                try:
                    # Check if connection is still active
                    if hasattr(ws, "client_state"):
                        if ws.client_state.name not in ["CLOSED", "DISCONNECTED"]:
                            active.add(ws)
                    else:
                        # If we can't check state, assume it's active
                        active.add(ws)
                except Exception:
                    # If checking fails, connection is likely dead
                    pass

            if active:
                self._connections[file_id] = active
            else:
                stale_ids.append(file_id)

        for file_id in stale_ids:
            del self._connections[file_id]
            logger.debug(f"🧹 Cleaned up stale connections for {file_id}")

    async def _get_total_connections(self) -> int:
        """Get total active WebSocket connections."""
        total = 0
        for connections in self._connections.values():
            total += len(connections)
        return total

    def get_connection_count(self, file_id: str) -> int:
        """Get the number of connections for a file_id."""
        return len(self._connections.get(file_id, set()))

    def get_total_connection_count(self) -> int:
        """Get the total number of connections across all file_ids."""
        total = 0
        for connections in self._connections.values():
            total += len(connections)
        return total

    async def health_check(self) -> Dict[str, any]:
        """Get connection health information."""
        await self._cleanup_stale_connections()
        return {
            "total_connections": await self._get_total_connections(),
            "analysis_count": len(self._connections),
            "max_total_connections": self._max_total_connections,
            "max_per_analysis": self._max_connections_per_analysis,
            "analyses": {aid: len(conns) for aid, conns in self._connections.items()},
        }


# Singleton instance
manager = ConnectionManager()
