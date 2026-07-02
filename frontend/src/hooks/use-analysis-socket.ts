// src/hooks/use-analysis-socket.ts
"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useRef, useState } from "react";

export type AnalysisStatus =
  | "idle"
  | "connecting"
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "not_found";

interface AnalysisSocketState {
  status: AnalysisStatus;
  progress?: number;
  message?: string;
  analysis?: any;
  error?: string;
}

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "wss://your-api-domain.com";
const POLL_INTERVAL_MS = 4000;
const MAX_RECONNECT_ATTEMPTS = 3;

export function useAnalysisSocket(fileId: string | null) {
  const { data: session } = useSession();
  const [state, setState] = useState<AnalysisSocketState>({ status: "idle" });
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectAttempts = useRef(0);
  const settledRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) clearInterval(pollTimer.current);
    pollTimer.current = null;
  }, []);

  const pollStatus = useCallback(async () => {
    if (!fileId) return;
    try {
      const res = await fetch(`/api/analysis/${fileId}/status`, {
        credentials: "include",
      });
      if (!res.ok) return; // transient — retry next tick, don't surface an error
      const data = await res.json();

      if (data.status === "completed") {
        settledRef.current = true;
        setState({ status: "completed", analysis: data.analysis });
        stopPolling();
      } else if (data.status === "failed") {
        settledRef.current = true;
        setState({
          status: "failed",
          error: data.error_message ?? "Analysis failed.",
        });
        stopPolling();
      } else {
        setState((prev) => ({
          ...prev,
          status: "processing",
          message: "Still working on it…",
        }));
      }
    } catch {
      // network hiccup — keep polling quietly, this is not a fatal error
    }
  }, [fileId, stopPolling]);

  const startPolling = useCallback(() => {
    stopPolling();
    pollStatus();
    pollTimer.current = setInterval(pollStatus, POLL_INTERVAL_MS);
  }, [pollStatus, stopPolling]);

  const connectSocket = useCallback(() => {
    if (!fileId || !session?.accessToken || settledRef.current) return;

    setState((prev) => ({
      ...prev,
      status: prev.status === "idle" ? "connecting" : prev.status,
    }));

    const ws = new WebSocket(
      `${WS_BASE}/ws/analysis/${fileId}?token=${encodeURIComponent(session.accessToken)}`,
    );
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setState({
          status: data.status,
          progress: data.progress,
          message: data.message,
          analysis: data.analysis,
          error: data.error,
        });
        if (data.status === "completed" || data.status === "failed") {
          settledRef.current = true;
          ws.close();
        }
      } catch {
        /* ignore malformed frame */
      }
    };

    ws.onclose = () => {
      if (settledRef.current) return;
      if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts.current += 1;
        setTimeout(connectSocket, 1000 * reconnectAttempts.current);
      } else {
        startPolling(); // e.g. corporate proxy blocking WS — fall back gracefully
      }
    };
  }, [fileId, session?.accessToken, startPolling]);

  useEffect(() => {
    if (!fileId) return;
    settledRef.current = false;
    connectSocket();
    return () => {
      wsRef.current?.close();
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId]);

  return state;
}
