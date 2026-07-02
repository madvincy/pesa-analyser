// src/hooks/useHistoryData.ts
import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

export interface HistoryData {
  analyses: any[];
  chats: any[];
  pagination?: {
    page: number;
    limit: number;
    total: number;
    pages: number;
  };
}

interface HistoryResponse {
  analyses: any[];
  chats: any[];
  pagination?: {
    page: number;
    limit: number;
    total: number;
    pages: number;
  };
}

interface UseHistoryDataOptions {
  type?: string;
  page?: number;
  limit?: number;
}

function normalizeAnalysis(analysis: any) {
  return {
    ...analysis,
    id: analysis.id,
    fileName:
      analysis.fileName ||
      analysis.file_name ||
      analysis.filename ||
      "Untitled analysis",
    createdAt:
      analysis.createdAt || analysis.created_at || analysis.created || null,
    status: analysis.status || "pending",
  };
}

function normalizeChat(chat: any) {
  return {
    ...chat,
    id: chat.id,
    message: chat.message || chat.content || chat.prompt || "No message",
    createdAt: chat.createdAt || chat.created_at || chat.created || null,
  };
}

function normalizeHistoryData(
  data: HistoryResponse | null | undefined,
): HistoryData {
  if (!data) {
    return { analyses: [], chats: [] };
  }

  return {
    analyses: (data.analyses || []).map(normalizeAnalysis),
    chats: (data.chats || []).map(normalizeChat),
    pagination: data.pagination,
  };
}

export function useHistoryData(options: UseHistoryDataOptions = {}) {
  const { status } = useSession();
  const { type = "all", page = 1, limit = 10 } = options;

  const [history, setHistory] = useState<HistoryData>({
    analyses: [],
    chats: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refetch = useCallback(async () => {
    if (status === "unauthenticated") {
      setHistory({ analyses: [], chats: [] });
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
      });
      if (type && type !== "all") {
        params.set("type", type);
      }

      const response = await fetch(`/api/user/history?${params.toString()}`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || "Failed to fetch history");
      }

      setHistory(normalizeHistoryData(payload));
    } catch (err) {
      console.error("Failed to load history", err);
      setHistory({ analyses: [], chats: [] });
      setError(
        err instanceof Error ? err : new Error("Failed to fetch history"),
      );
    } finally {
      setLoading(false);
    }
  }, [status, type, page, limit]);

  useEffect(() => {
    if (status === "loading") return;
    void refetch();
  }, [status, refetch]);

  return {
    history,
    loading,
    error,
    refetch,
  };
}
