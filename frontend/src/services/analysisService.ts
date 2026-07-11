/**
 * Analysis service for fetching and managing analysis data.
 * Handles authentication via session tokens.
 */

import { getSession } from "next-auth/react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface AnalysisResponse {
  id: string;
  status: string;
  file_name?: string;
  created_at?: string;
  completed_at?: string;
  total_income?: number;
  total_expenses?: number;
  net_cash_flow?: number;
  average_balance?: number;
  total_fees?: number;
  total_transactions?: number;
  health_score?: number;
  savings_rate?: number;
  burn_rate_daily?: number;
  fee_pct?: number;
  fuliza_total?: number;
  fuliza_count?: number;
  betting_total?: number;
  betting_pct?: number;
  p2p_total?: number;
  p2p_count?: number;
  income_count?: number;
  expense_count?: number;
  top_income_source?: string;
  income_concentration?: number;
  income_change?: number;
  expenses_change?: number;
  monthly_data?: any[];
  category_data?: any[];
  trend_data?: any[];
  insights?: string[];
  warnings?: string[];
  recommendations?: string[];
  top_category?: string;
  top_category_amount?: number;
  top_category_percent?: number;
  highest_transaction?: number;
  highest_transaction_date?: string;
  health_breakdown?: Record<string, number>;
  day_of_week_spend?: any[];
  salary_day?: number | null;
  recurring_payments?: any[];
  anomalies?: any[];
  fuliza_cycles?: {
    cycle_count: number;
    same_day_repayment_rate: number;
  };
  income_analysis?: {
    loan_disbursement_warning: boolean;
  };
  top_depositors?: any[];
  top_creditors?: any[];
  progress?: number;
}

export interface ExportOptions {
  format: "pdf" | "csv";
}

export interface EmailOptions {
  email: string;
  analysis_id: string;
}

class AnalysisService {
  private baseUrl: string;

  constructor(baseUrl: string = "") {
    // Remove trailing slash if present
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  /**
   * Get authentication headers from session
   */
  private async getAuthHeaders(): Promise<HeadersInit> {
    const headers: HeadersInit = {};

    try {
      const session = await getSession();

      if (!session?.user) {
        console.warn("⚠️ No session found for API request");
        return headers;
      }

      // Add Authorization header if access token exists
      if (session.accessToken) {
        headers["Authorization"] = `Bearer ${session.accessToken}`;
      }

      // Add user identification headers (matching Next.js API route)
      if (session.user.id) {
        // Validate UUID format
        const uuidRegex =
          /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        if (uuidRegex.test(session.user.id)) {
          headers["X-User-ID"] = session.user.id;
        }
      }

      if (session.user.email) {
        headers["X-User-Email"] = session.user.email;
      }

      if (session.user.name) {
        headers["X-User-Name"] = session.user.name;
      }

      // Add any additional session headers
      if (session.user.role) {
        headers["X-User-Role"] = session.user.role;
      }
    } catch (error) {
      console.error("Failed to get session for auth headers:", error);
    }

    return headers;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
  ): Promise<T> {
    // Ensure endpoint starts with /
    const normalizedEndpoint = endpoint.startsWith("/")
      ? endpoint
      : `/${endpoint}`;
    const url = `${this.baseUrl}${normalizedEndpoint}`;

    // Get auth headers
    const authHeaders = await this.getAuthHeaders();

    const response = await fetch(url, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
        ...options.headers,
      },
    });

    // Handle specific status codes
    if (response.status === 401) {
      throw {
        status: 401,
        message: "Your session has expired. Please sign in again.",
        code: "UNAUTHORIZED",
      };
    }

    if (response.status === 403) {
      throw {
        status: 403,
        message: "You don't have permission to access this resource.",
        code: "FORBIDDEN",
      };
    }

    if (response.status === 404) {
      throw {
        status: 404,
        message: "Resource not found.",
        code: "NOT_FOUND",
      };
    }

    if (!response.ok) {
      let errorData: any = {};
      try {
        errorData = await response.json();
      } catch {
        // If response is not JSON, use status text
      }

      throw {
        status: response.status,
        message:
          errorData.detail ||
          errorData.message ||
          errorData.error ||
          `HTTP ${response.status}`,
        data: errorData,
        code: errorData.code || "UNKNOWN_ERROR",
      };
    }

    return response.json();
  }

  /**
   * Fetch analysis data by ID
   */
  async getAnalysis(analysisId: string): Promise<AnalysisResponse> {
    return this.request<AnalysisResponse>(`/results/${analysisId}`);
  }

  /**
   * Get analysis status
   */
  async getAnalysisStatus(
    analysisId: string,
  ): Promise<{ status: string; progress?: number }> {
    return this.request<{ status: string; progress?: number }>(
      `/results/${analysisId}/status`,
    );
  }

  /**
   * Export analysis as PDF
   */
  async exportPDF(analysisId: string): Promise<Blob> {
    const endpoint = `/reports/report/${analysisId}?format=pdf`;
    const url = `${this.baseUrl}${endpoint}`;

    const authHeaders = await this.getAuthHeaders();

    const response = await fetch(url, {
      credentials: "include",
      headers: authHeaders,
    });

    if (!response.ok) {
      let errorData: any = {};
      try {
        errorData = await response.json();
      } catch {
        // If response is not JSON, use status text
      }

      throw {
        status: response.status,
        message: errorData.detail || `Export failed: ${response.status}`,
      };
    }

    return response.blob();
  }

  /**
   * Export analysis as CSV
   */
  async exportCSV(analysisId: string): Promise<Blob> {
    const endpoint = `/reports/report/${analysisId}?format=csv`;
    const url = `${this.baseUrl}${endpoint}`;

    const authHeaders = await this.getAuthHeaders();

    const response = await fetch(url, {
      credentials: "include",
      headers: authHeaders,
    });

    if (!response.ok) {
      let errorData: any = {};
      try {
        errorData = await response.json();
      } catch {
        // If response is not JSON, use status text
      }

      throw {
        status: response.status,
        message: errorData.detail || `Export failed: ${response.status}`,
      };
    }

    return response.blob();
  }

  /**
   * Email report
   */
  async emailReport(
    options: EmailOptions,
  ): Promise<{ success: boolean; message: string }> {
    return this.request<{ success: boolean; message: string }>(
      "/reports/report/email",
      {
        method: "POST",
        body: JSON.stringify(options),
      },
    );
  }

  /**
   * Get WebSocket URL for real-time updates
   */
  getWebSocketUrl(analysisId: string): string {
    const protocol =
      typeof window !== "undefined" && window.location.protocol === "https:"
        ? "wss:"
        : "ws:";
    const host = typeof window !== "undefined" ? window.location.host : "";

    // WebSocket connections can use token as query parameter
    // or rely on cookies (if same domain)
    return `${protocol}//${host}/api/v1/results/ws/${analysisId}`;
  }

  /**
   * Get WebSocket URL with authentication token
   */
  async getAuthenticatedWebSocketUrl(analysisId: string): Promise<string> {
    try {
      const session = await getSession();
      const token = session?.accessToken;

      const baseUrl = this.getWebSocketUrl(analysisId);
      if (token) {
        return `${baseUrl}?token=${encodeURIComponent(token)}`;
      }
      return baseUrl;
    } catch (error) {
      console.error("Failed to get authenticated WebSocket URL:", error);
      return this.getWebSocketUrl(analysisId);
    }
  }
}

// Singleton instance
export const analysisService = new AnalysisService(
  process.env.NEXT_PUBLIC_API_URL || "",
);
