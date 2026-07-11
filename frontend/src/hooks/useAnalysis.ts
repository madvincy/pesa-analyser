/**
 * React hook for fetching and managing analysis data.
 * Optimized to prevent excessive requests and stop when complete.
 */

import { AnalysisResponse, analysisService } from "@/services/analysisService";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

interface UseAnalysisOptions {
  autoFetch?: boolean;
  enableWebSocket?: boolean;
  onComplete?: (data: AnalysisResponse) => void;
  onError?: (error: any) => void;
  onProgress?: (progress: number) => void;
  pollInterval?: number;
  maxWebSocketRetries?: number;
  wsReconnectDelay?: number;
}

interface UseAnalysisResult {
  data: AnalysisResponse | null;
  loading: boolean;
  error: any;
  progress: number;
  wsConnected: boolean;
  isComplete: boolean;
  refetch: () => Promise<void>;
  exportPDF: () => Promise<Blob>;
  exportCSV: () => Promise<Blob>;
  emailReport: (email: string) => Promise<void>;
}

export function useAnalysis(
  analysisId: string,
  options: UseAnalysisOptions = {},
): UseAnalysisResult {
  const {
    autoFetch = true,
    enableWebSocket = true,
    onComplete,
    onError,
    onProgress,
    pollInterval = 5000,
    maxWebSocketRetries = 2,
    wsReconnectDelay = 3000,
  } = options;

  // ─── State ──────────────────────────────────────────────────────────────
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<any>(null);
  const [progress, setProgress] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);

  // ─── Refs for preventing duplicate requests ────────────────────────────
  const isFetchingRef = useRef(false);
  const hasFetchedRef = useRef(false);
  const fetchCountRef = useRef(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);
  const wsRetryCountRef = useRef(0);
  const isConnectingRef = useRef(false);
  const analysisIdRef = useRef(analysisId);
  const initialFetchDoneRef = useRef(false);
  const isCompleteRef = useRef(false);

  // ─── Store callbacks in refs ──────────────────────────────────────────
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);
  const onProgressRef = useRef(onProgress);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    onProgressRef.current = onProgress;
  }, [onProgress]);

  // ─── Cleanup ──────────────────────────────────────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    analysisIdRef.current = analysisId;
    isCompleteRef.current = false;

    return () => {
      mountedRef.current = false;
      cleanupWebSocket();
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [analysisId]);

  // ─── Cleanup WebSocket ────────────────────────────────────────────────
  const cleanupWebSocket = useCallback(() => {
    isConnectingRef.current = false;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    if (wsRef.current) {
      try {
        if (
          wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING
        ) {
          wsRef.current.close(1000, "Cleanup");
        }
      } catch (e) {
        // Ignore close errors
      }
      wsRef.current = null;
    }
  }, []);

  // ─── Stop all polling and WebSocket connections ──────────────────────
  const stopAllUpdates = useCallback(() => {
    console.log("🛑 Stopping all updates (analysis complete)");
    cleanupWebSocket();
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setWsConnected(false);
  }, [cleanupWebSocket]);

  // ─── Fetch Data (with deduplication) ─────────────────────────────────
  const fetchData = useCallback(
    async (silent: boolean = false) => {
      // ✅ STOP: Don't fetch if already complete
      if (isCompleteRef.current) {
        console.log("⏭️ Skipping fetch - analysis already complete");
        return;
      }

      // Prevent concurrent fetches
      if (isFetchingRef.current) {
        console.log("⏭️ Skipping fetch - already in progress");
        return;
      }

      const currentAnalysisId = analysisIdRef.current;
      if (!currentAnalysisId) {
        setLoading(false);
        return;
      }

      // Limit fetch attempts
      if (fetchCountRef.current > 50) {
        console.warn("⚠️ Too many fetch attempts, stopping");
        return;
      }

      try {
        isFetchingRef.current = true;
        fetchCountRef.current += 1;

        if (!silent) {
          setLoading(true);
        }

        console.log(
          `📡 Fetching analysis ${currentAnalysisId} (attempt ${fetchCountRef.current})`,
        );

        const result = await analysisService.getAnalysis(currentAnalysisId);

        if (!mountedRef.current) return;

        setData(result);
        setProgress(result.progress || 100);
        hasFetchedRef.current = true;

        // ✅ CHECK: If status is completed, stop all updates
        if (result.status === "completed") {
          console.log("✅ Analysis completed - stopping all updates");
          setIsComplete(true);
          isCompleteRef.current = true;
          setProgress(100);

          // 🛑 STOP ALL UPDATES - No more polling or WebSocket
          stopAllUpdates();

          if (onCompleteRef.current) {
            onCompleteRef.current(result);
          }
          // Reset fetch count on success
          fetchCountRef.current = 0;
        }
      } catch (err: any) {
        if (!mountedRef.current) return;

        // Don't set error for 404 - just log
        if (err.status === 404) {
          console.warn("⚠️ Analysis not found (yet)");
        } else {
          setError(err);
          if (onErrorRef.current) {
            onErrorRef.current(err);
          }
        }
      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
        isFetchingRef.current = false;
      }
    },
    [stopAllUpdates],
  );

  // ─── WebSocket Setup ──────────────────────────────────────────────────
  const setupWebSocket = useCallback(() => {
    const currentAnalysisId = analysisIdRef.current;

    // ✅ STOP: Don't setup WebSocket if already complete
    if (isCompleteRef.current) {
      console.log("⏭️ Skipping WebSocket - analysis already complete");
      return;
    }

    // Don't setup if WebSocket is disabled or already connecting
    if (!enableWebSocket || !currentAnalysisId || isConnectingRef.current) {
      return;
    }

    // Check retry limit
    if (wsRetryCountRef.current >= maxWebSocketRetries) {
      console.warn(
        `⚠️ WebSocket retry limit reached (${maxWebSocketRetries}) - using polling`,
      );
      // Start polling once
      if (!pollTimeoutRef.current) {
        const poll = () => {
          if (!mountedRef.current || isCompleteRef.current) {
            if (pollTimeoutRef.current) {
              clearTimeout(pollTimeoutRef.current);
              pollTimeoutRef.current = null;
            }
            return;
          }
          fetchData(true);
          if (!isCompleteRef.current && mountedRef.current) {
            pollTimeoutRef.current = setTimeout(poll, pollInterval);
          }
        };
        pollTimeoutRef.current = setTimeout(poll, pollInterval);
      }
      return;
    }

    // Close existing connection
    if (wsRef.current) {
      cleanupWebSocket();
    }

    // ✅ FIX: Try to get WebSocket URL with authentication
    const wsUrl = analysisService.getWebSocketUrl(currentAnalysisId);
    isConnectingRef.current = true;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      // Set a connection timeout
      const connectionTimeout = setTimeout(() => {
        if (wsRef.current && wsRef.current.readyState !== WebSocket.OPEN) {
          console.warn("⚠️ WebSocket connection timeout");
          try {
            wsRef.current.close();
          } catch (e) {
            // Ignore
          }
          wsRetryCountRef.current += 1;
          isConnectingRef.current = false;
          // Start polling on timeout
          if (!pollTimeoutRef.current) {
            const poll = () => {
              if (!mountedRef.current || isCompleteRef.current) {
                if (pollTimeoutRef.current) {
                  clearTimeout(pollTimeoutRef.current);
                  pollTimeoutRef.current = null;
                }
                return;
              }
              fetchData(true);
              if (!isCompleteRef.current && mountedRef.current) {
                pollTimeoutRef.current = setTimeout(poll, pollInterval);
              }
            };
            pollTimeoutRef.current = setTimeout(poll, pollInterval);
          }
        }
      }, 5000);

      ws.onopen = () => {
        clearTimeout(connectionTimeout);
        if (!mountedRef.current) return;
        setWsConnected(true);
        isConnectingRef.current = false;
        wsRetryCountRef.current = 0;
        console.log("✅ WebSocket connected");
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;

        try {
          const message = JSON.parse(event.data);
          console.log("📨 WebSocket message:", message.type || message.status);

          switch (message.type || message.status) {
            case "progress":
              if (message.progress !== undefined) {
                setProgress(message.progress);
                if (onProgressRef.current) {
                  onProgressRef.current(message.progress);
                }
              }
              break;

            case "stage_complete":
              const stageProgress = {
                basic_summary: 25,
                category_breakdown: 50,
                behavior_metrics: 75,
                insights: 90,
              };
              const newProgress =
                stageProgress[message.stage as keyof typeof stageProgress] ||
                50;
              setProgress(newProgress);
              if (onProgressRef.current) {
                onProgressRef.current(newProgress);
              }
              break;

            case "completed":
              console.log("✅ WebSocket: Analysis completed");
              setIsComplete(true);
              isCompleteRef.current = true;
              setProgress(100);

              // 🛑 STOP ALL UPDATES
              stopAllUpdates();

              // Fetch final data once
              fetchData(true);
              break;

            case "failed":
              const errorMsg = message.error || "Analysis failed";
              setError({ message: errorMsg });
              if (onErrorRef.current) {
                onErrorRef.current({ message: errorMsg });
              }
              break;

            case "queued":
              setProgress(0);
              if (onProgressRef.current) {
                onProgressRef.current(0);
              }
              break;
          }
        } catch (e) {
          console.error("Failed to parse WebSocket message:", e);
        }
      };

      // ✅ FIX: Handle errors gracefully - don't retry immediately
      ws.onerror = (event) => {
        clearTimeout(connectionTimeout);
        if (!mountedRef.current) return;
        console.warn("⚠️ WebSocket error:", event);
        setWsConnected(false);
        isConnectingRef.current = false;
        wsRetryCountRef.current += 1;
        // Use exponential backoff for reconnection
        if (!isCompleteRef.current) {
          attemptReconnect();
        }
      };

      ws.onclose = (event) => {
        clearTimeout(connectionTimeout);
        if (!mountedRef.current) return;
        console.log(`🔌 WebSocket closed: ${event.code} - ${event.reason}`);
        setWsConnected(false);
        isConnectingRef.current = false;
        // Don't reconnect for normal closure or if complete
        if (event.code !== 1000 && !isCompleteRef.current) {
          wsRetryCountRef.current += 1;
          attemptReconnect();
        } else if (event.code === 1000) {
          // Normal closure - don't retry
          console.log("WebSocket closed normally");
        }
      };
    } catch (err) {
      console.error("Failed to setup WebSocket:", err);
      isConnectingRef.current = false;
      // Start polling on error
      if (!pollTimeoutRef.current) {
        const poll = () => {
          if (!mountedRef.current || isCompleteRef.current) {
            if (pollTimeoutRef.current) {
              clearTimeout(pollTimeoutRef.current);
              pollTimeoutRef.current = null;
            }
            return;
          }
          fetchData(true);
          if (!isCompleteRef.current && mountedRef.current) {
            pollTimeoutRef.current = setTimeout(poll, pollInterval);
          }
        };
        pollTimeoutRef.current = setTimeout(poll, pollInterval);
      }
    }
  }, [
    enableWebSocket,
    fetchData,
    cleanupWebSocket,
    maxWebSocketRetries,
    wsReconnectDelay,
    pollInterval,
    stopAllUpdates,
  ]);

  // ─── Reconnection Logic ──────────────────────────────────────────────
  const attemptReconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    // ✅ STOP: Don't reconnect if complete
    if (isCompleteRef.current || !mountedRef.current) {
      return;
    }

    if (wsRetryCountRef.current >= maxWebSocketRetries) {
      console.warn(`⚠️ Max WebSocket retries reached - using polling`);
      // Start polling
      if (!pollTimeoutRef.current) {
        const poll = () => {
          if (!mountedRef.current || isCompleteRef.current) {
            if (pollTimeoutRef.current) {
              clearTimeout(pollTimeoutRef.current);
              pollTimeoutRef.current = null;
            }
            return;
          }
          fetchData(true);
          if (!isCompleteRef.current && mountedRef.current) {
            pollTimeoutRef.current = setTimeout(poll, pollInterval);
          }
        };
        pollTimeoutRef.current = setTimeout(poll, pollInterval);
      }
      return;
    }

    // Exponential backoff
    const delay = Math.min(
      30000,
      wsReconnectDelay * Math.pow(2, wsRetryCountRef.current),
    );
    console.log(
      `🔄 Reconnecting in ${delay}ms (attempt ${wsRetryCountRef.current + 1}/${maxWebSocketRetries})`,
    );

    reconnectTimeoutRef.current = setTimeout(() => {
      if (!mountedRef.current || isCompleteRef.current) return;
      if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
        setupWebSocket();
      }
    }, delay);
  }, [
    setupWebSocket,
    wsReconnectDelay,
    maxWebSocketRetries,
    fetchData,
    pollInterval,
  ]);

  // ─── Main Effect ──────────────────────────────────────────────────────
  useEffect(() => {
    const currentAnalysisId = analysisIdRef.current;
    if (!currentAnalysisId) return;

    // Reset state when analysisId changes
    if (hasFetchedRef.current) {
      hasFetchedRef.current = false;
      setIsComplete(false);
      isCompleteRef.current = false;
      setData(null);
      setError(null);
      setProgress(0);
      wsRetryCountRef.current = 0;
      initialFetchDoneRef.current = false;
      fetchCountRef.current = 0;
    }

    // Only fetch once on mount/change
    if (!initialFetchDoneRef.current && autoFetch) {
      initialFetchDoneRef.current = true;
      fetchData(false);
    }

    // Delay WebSocket connection to avoid resource contention
    const wsTimer = setTimeout(() => {
      if (
        enableWebSocket &&
        !isCompleteRef.current &&
        initialFetchDoneRef.current
      ) {
        setupWebSocket();
      }
    }, 2000);

    return () => {
      clearTimeout(wsTimer);
    };
  }, [analysisId, autoFetch, enableWebSocket, fetchData, setupWebSocket]);

  // ─── Refetch ──────────────────────────────────────────────────────────
  const refetch = useCallback(async () => {
    // Reset complete state to allow refetch
    setIsComplete(false);
    isCompleteRef.current = false;
    initialFetchDoneRef.current = true;
    hasFetchedRef.current = false;
    fetchCountRef.current = 0;

    // Clear any existing polling
    stopAllUpdates();

    await fetchData(false);
  }, [fetchData, stopAllUpdates]);

  // ─── Export Handlers ──────────────────────────────────────────────────
  const exportPDF = useCallback(async (): Promise<Blob> => {
    return analysisService.exportPDF(analysisIdRef.current);
  }, []);

  const exportCSV = useCallback(async (): Promise<Blob> => {
    return analysisService.exportCSV(analysisIdRef.current);
  }, []);

  const emailReport = useCallback(async (email: string): Promise<void> => {
    await analysisService.emailReport({
      email,
      analysis_id: analysisIdRef.current,
    });
  }, []);

  // ─── Memoized Result ──────────────────────────────────────────────────
  const result = useMemo(
    () => ({
      data,
      loading,
      error,
      progress,
      wsConnected,
      isComplete,
      refetch,
      exportPDF,
      exportCSV,
      emailReport,
    }),
    [
      data,
      loading,
      error,
      progress,
      wsConnected,
      isComplete,
      refetch,
      exportPDF,
      exportCSV,
      emailReport,
    ],
  );

  return result;
}
