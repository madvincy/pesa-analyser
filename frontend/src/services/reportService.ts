/**
 * Report service for generating, exporting, and emailing financial reports.
 * Handles authentication via session tokens.
 */

import { getSession } from "next-auth/react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface ReportData {
  id: string;
  file_name: string;
  statement_type?: string;
  total_income: number;
  total_expenses: number;
  net_cash_flow: number;
  average_balance: number;
  total_fees: number;
  total_transactions: number;
  monthly_data: any[];
  category_data: any[];
  trend_data: any[];
  insights: string[];
  warnings: string[];
  recommendations: string[];
  generated_at: string;
}

export interface ReportPreviewData {
  id: string;
  file_name: string;
  total_income: number;
  total_expenses: number;
  net_cash_flow: number;
  total_transactions: number;
  health_score?: number;
  insights: string[];
  warnings: string[];
  recommendations: string[];
  preview: boolean;
  generated_at: string;
}

export interface ExportOptions {
  format: "pdf" | "csv";
}

export interface EmailOptions {
  email: string;
  analysis_id: string;
}

export interface EmailResponse {
  message: string;
  email: string;
  analysis_id: string;
}

class ReportService {
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

      // Add user identification headers
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

      if (session.user.role) {
        headers["X-User-Role"] = session.user.role;
      }
    } catch (error) {
      console.error("Failed to get session for auth headers:", error);
    }

    return headers;
  }

  /**
   * Make authenticated request
   */
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

    if (response.status === 402) {
      throw {
        status: 402,
        message:
          "Payment required. Please complete payment to access this report.",
        code: "PAYMENT_REQUIRED",
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
        message: "Report not found.",
        code: "NOT_FOUND",
      };
    }

    if (response.status === 503) {
      throw {
        status: 503,
        message: "Email service is not configured. Please contact support.",
        code: "SERVICE_UNAVAILABLE",
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
   * Generate and download a report
   *
   * @param analysisId - The analysis ID
   * @param format - 'pdf' or 'csv'
   * @returns Blob containing the file
   *
   * @example
   * const blob = await reportService.downloadReport('123', 'pdf');
   * // Create download link
   * const url = URL.createObjectURL(blob);
   */
  async downloadReport(
    analysisId: string,
    format: "pdf" | "csv" = "pdf",
  ): Promise<Blob> {
    const endpoint = `/reports/${analysisId}?format=${format}`;
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
        code: errorData.code || "EXPORT_FAILED",
      };
    }

    return response.blob();
  }

  /**
   * Download and save report with automatic filename
   *
   * @param analysisId - The analysis ID
   * @param format - 'pdf' or 'csv'
   * @param customFilename - Optional custom filename
   *
   * @example
   * await reportService.downloadAndSave('123', 'pdf');
   */
  async downloadAndSave(
    analysisId: string,
    format: "pdf" | "csv" = "pdf",
    customFilename?: string,
  ): Promise<void> {
    const blob = await this.downloadReport(analysisId, format);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;

    // Use custom filename or generate one
    const filename =
      customFilename || `financial_report_${analysisId}.${format}`;
    a.download = filename;

    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }

  /**
   * Preview report data without generating a file
   *
   * @param analysisId - The analysis ID
   * @returns Report preview data
   *
   * @example
   * const preview = await reportService.previewReport('123');
   * console.log(preview.insights);
   */
  async previewReport(analysisId: string): Promise<ReportPreviewData> {
    return this.request<ReportPreviewData>(`/reports/preview/${analysisId}`);
  }

  /**
   * Email report to a user
   *
   * @param options - Email options containing email and analysis_id
   * @returns Success message
   *
   * @example
   * await reportService.emailReport({
   *   email: 'user@example.com',
   *   analysis_id: '123'
   * });
   */
  async emailReport(options: EmailOptions): Promise<EmailResponse> {
    return this.request<EmailResponse>(
      `/reports/email?email=${encodeURIComponent(options.email)}&analysis_id=${options.analysis_id}`,
      {
        method: "POST",
      },
    );
  }

  /**
   * Check if email service is configured
   *
   * @returns Boolean indicating if email service is available
   */
  async checkEmailService(): Promise<{
    configured: boolean;
    message?: string;
  }> {
    try {
      // This would be a health check endpoint
      // For now, we'll return a reasonable default
      return { configured: true };
    } catch (error) {
      return { configured: false, message: "Email service unavailable" };
    }
  }

  /**
   * Get the user's email from session (for pre-filling)
   */
  async getUserEmail(): Promise<string | null> {
    try {
      const session = await getSession();
      return session?.user?.email || null;
    } catch (error) {
      console.error("Failed to get user email:", error);
      return null;
    }
  }

  /**
   * Check if a report can be generated (checks payment status)
   *
   * @param analysisId - The analysis ID
   * @returns Boolean indicating if report is available
   */
  async isReportAvailable(analysisId: string): Promise<boolean> {
    try {
      const preview = await this.previewReport(analysisId);
      return !!preview?.id;
    } catch (error) {
      if (error instanceof Error) {
        // Payment required or not found
        if (error.message.includes("Payment required")) {
          return false;
        }
      }
      return false;
    }
  }

  /**
   * Get download URL for report (for direct links)
   *
   * @param analysisId - The analysis ID
   * @param format - 'pdf' or 'csv'
   * @returns Full URL for downloading
   */
  getDownloadUrl(analysisId: string, format: "pdf" | "csv" = "pdf"): string {
    return `${this.baseUrl}/reports/${analysisId}?format=${format}`;
  }

  /**
   * Open report in new tab for viewing
   *
   * @param analysisId - The analysis ID
   * @param format - 'pdf' or 'csv'
   */
  openReportInTab(analysisId: string, format: "pdf" | "csv" = "pdf"): void {
    const url = this.getDownloadUrl(analysisId, format);
    window.open(url, "_blank");
  }

  /**
   * Get WebSocket URL for real-time report generation updates
   *
   * @param analysisId - The analysis ID
   * @returns WebSocket URL
   */
  getWebSocketUrl(analysisId: string): string {
    const protocol =
      typeof window !== "undefined" && window.location.protocol === "https:"
        ? "wss:"
        : "ws:";
    const host = typeof window !== "undefined" ? window.location.host : "";

    return `${protocol}//${host}/api/reports/ws/${analysisId}`;
  }

  /**
   * Get authenticated WebSocket URL
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
export const reportService = new ReportService(
  process.env.NEXT_PUBLIC_API_URL || "",
);

// Export types for use in components
export type { ReportService };
