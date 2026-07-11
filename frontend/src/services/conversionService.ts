/**
 * Conversion service for managing PDF to CSV/Excel conversions.
 * Handles authentication via session tokens.
 */

import { getSession } from "next-auth/react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface FileResult {
  file_name: string;
  status: "completed" | "failed";
  transaction_count: number;
  error?: string | null;
}

export interface ConversionStatistics {
  total_transactions: number;
  total_income: number;
  total_expenses: number;
  net_flow: number;
}

export interface ConversionResponse {
  conversion_id: string;
  status: "completed" | "partial" | "failed";
  total_files: number;
  processed_files: number;
  failed_files: number;
  total_transactions: number;
  total_income: number;
  total_expenses: number;
  net_flow: number;
  format: string;
  payment_reference?: string;
  payment_amount: number;
  expires_at: string;
  download_url: string;
  file_results: FileResult[];
  statistics: ConversionStatistics;
}

export interface BulkConversionResponse {
  conversion_id: string;
  status: string;
  total_files: number;
  processed_files: number;
  failed_files: number;
  total_transactions: number;
  total_amount: number;
  payment_reference?: string;
  payment_amount: number;
  expires_at: string;
  download_url?: string;
  file_results: FileResult[];
}

export interface ConversionHistoryItem {
  id: string;
  file_name: string;
  file_count: number;
  transaction_count: number;
  total_amount: number;
  payment_reference?: string;
  payment_amount?: number;
  status: string;
  expires_at?: string;
  created_at?: string;
}

export interface ConversionHistoryResponse {
  total: number;
  skip: number;
  limit: number;
  conversions: ConversionHistoryItem[];
}

export interface ConversionStats {
  total_conversions: number;
  total_transactions: number;
  total_amount: number;
  monthly_conversions: number;
  last_30_days: number;
}

export interface PricingResponse {
  file_count: number;
  price: number;
  price_per_file: number;
  currency: string;
  base_price: number;
  bulk_price: number;
  bulk_threshold: number;
  bulk_extra_price: number;
}

export interface ConversionAnalytics {
  conversion_id: string;
  file_name: string;
  file_count: number;
  transaction_count: number;
  total_amount: number;
  payment_reference?: string;
  payment_amount: number;
  status: string;
  created_at?: string;
  expires_at?: string;
  statistics: ConversionStatistics;
  transactions: any[];
  files: string[];
}

export interface SearchFilters {
  category?: string;
  merchant?: string;
  date_from?: string;
  date_to?: string;
  min_amount?: number;
  max_amount?: number;
}

export interface SearchRequest {
  query: string;
  filters?: SearchFilters;
  page?: number;
  size?: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

export interface SearchResult {
  id: string;
  file_name: string;
  file_type: string;
  transaction_count: number;
  total_income: number;
  total_expenses: number;
  net_flow: number;
  upload_date: string;
  categories: string[];
  merchants: string[];
  score: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  page: number;
  size: number;
  total_pages: number;
  aggregations: {
    total_income: number;
    total_expenses: number;
    net_flow: number;
    by_month: { month: string; count: number }[];
    by_category: { name: string; count: number }[];
    by_merchant: { name: string; count: number }[];
  };
}

export interface PasswordRemoveResponse {
  success: boolean;
  message?: string;
}

// ─── Local Storage Helpers ──────────────────────────────────────────────────

interface LocalConversionRecord {
  fileId: string;
  fileName: string;
  uploadedAt: string;
  conversionFormat?: string;
  transactionCount?: number;
  totalAmount?: number;
}

/**
 * Store conversion record in localStorage
 */
function storeConversionInLocalStorage(record: LocalConversionRecord): void {
  try {
    const key = `conversion_${record.fileId}`;
    localStorage.setItem(key, JSON.stringify(record));

    // Update the conversions list
    const listKey = "conversion_history_list";
    let history: string[] = [];
    try {
      const existing = localStorage.getItem(listKey);
      if (existing) {
        history = JSON.parse(existing);
      }
    } catch {
      // Ignore parse errors
    }

    // Add to history if not already present
    if (!history.includes(record.fileId)) {
      history.unshift(record.fileId);
      // Keep only last 100 records
      if (history.length > 100) {
        history = history.slice(0, 100);
      }
      localStorage.setItem(listKey, JSON.stringify(history));
    }
  } catch (error) {
    console.error("Failed to store conversion in localStorage:", error);
  }
}

/**
 * Get conversion record from localStorage
 */
function getConversionFromLocalStorage(
  fileId: string,
): LocalConversionRecord | null {
  try {
    const key = `conversion_${fileId}`;
    const data = localStorage.getItem(key);
    if (data) {
      return JSON.parse(data);
    }
    return null;
  } catch (error) {
    console.error("Failed to get conversion from localStorage:", error);
    return null;
  }
}

/**
 * Get all conversion history from localStorage
 */
function getConversionHistoryFromLocalStorage(): LocalConversionRecord[] {
  try {
    const listKey = "conversion_history_list";
    const history: string[] = JSON.parse(localStorage.getItem(listKey) || "[]");

    const records: LocalConversionRecord[] = [];
    for (const id of history) {
      const record = getConversionFromLocalStorage(id);
      if (record) {
        records.push(record);
      }
    }
    return records;
  } catch (error) {
    console.error("Failed to get conversion history from localStorage:", error);
    return [];
  }
}

/**
 * Clear expired conversions from localStorage
 */
function clearExpiredConversionsFromLocalStorage(): void {
  try {
    const listKey = "conversion_history_list";
    const history: string[] = JSON.parse(localStorage.getItem(listKey) || "[]");

    const now = Date.now();
    const expiryMs = 24 * 60 * 60 * 1000; // 24 hours

    const validIds: string[] = [];
    for (const id of history) {
      const record = getConversionFromLocalStorage(id);
      if (record) {
        const uploadTime = new Date(record.uploadedAt).getTime();
        if (now - uploadTime < expiryMs) {
          validIds.push(id);
        } else {
          // Remove expired record
          localStorage.removeItem(`conversion_${id}`);
        }
      }
    }

    localStorage.setItem(listKey, JSON.stringify(validIds));
  } catch (error) {
    console.error("Failed to clear expired conversions:", error);
  }
}

// ─── Service Class ──────────────────────────────────────────────────────────

class ConversionService {
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

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
  ): Promise<T> {
    const normalizedEndpoint = endpoint.startsWith("/")
      ? endpoint
      : `/${endpoint}`;
    const url = `${this.baseUrl}${normalizedEndpoint}`;

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

    if (response.status === 410) {
      throw {
        status: 410,
        message: "This conversion has expired. Please convert again.",
        code: "EXPIRED",
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

  private async requestBlob(
    endpoint: string,
    options: RequestInit = {},
  ): Promise<Blob> {
    const normalizedEndpoint = endpoint.startsWith("/")
      ? endpoint
      : `/${endpoint}`;
    const url = `${this.baseUrl}/${normalizedEndpoint}`;

    const authHeaders = await this.getAuthHeaders();

    const response = await fetch(url, {
      ...options,
      credentials: "include",
      headers: {
        ...authHeaders,
        ...options.headers,
      },
    });

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

    if (response.status === 410) {
      throw {
        status: 410,
        message: "This conversion has expired. Please convert again.",
        code: "EXPIRED",
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
        message: errorData.detail || `HTTP ${response.status}`,
        code: errorData.code || "UNKNOWN_ERROR",
      };
    }

    return response.blob();
  }

  // ─── Conversion Endpoints ────────────────────────────────────────────────

  /**
   * Convert PDF files to CSV or Excel
   */
  async convertFiles(
    files: File[],
    format: "csv" | "excel" = "csv",
    password?: string,
    paymentReference?: string,
    paymentAmount?: number,
  ): Promise<ConversionResponse> {
    const formData = new FormData();

    files.forEach((file) => {
      formData.append("files", file);
    });

    formData.append("format", format);

    if (password) {
      formData.append("password", password);
    }

    if (paymentReference) {
      formData.append("payment_reference", paymentReference);
    }

    if (paymentAmount !== undefined && paymentAmount > 0) {
      formData.append("payment_amount", paymentAmount.toString());
    }

    const authHeaders = await this.getAuthHeaders();

    const response = await fetch(`${this.baseUrl}/converter/convert`, {
      method: "POST",
      credentials: "include",
      headers: authHeaders,
      body: formData,
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
        message:
          errorData.detail ||
          errorData.message ||
          errorData.error ||
          `Conversion failed: ${response.status}`,
        data: errorData,
        code: errorData.code || "CONVERSION_FAILED",
      };
    }

    const result = await response.json();

    // Store in localStorage for history
    if (result.conversion_id) {
      files.forEach((file) => {
        storeConversionInLocalStorage({
          fileId: result.conversion_id,
          fileName: file.name,
          uploadedAt: new Date().toISOString(),
          conversionFormat: format,
          transactionCount: result.total_transactions || 0,
          totalAmount: result.total_income || 0,
        });
      });
    }

    return result;
  }

  /**
   * Download converted file
   */
  async downloadConversion(conversionId: string): Promise<Blob> {
    return this.requestBlob(`converter/download/${conversionId}`);
  }

  /**
   * Download conversion with filename extraction from headers
   */
  async downloadConversionWithFilename(
    conversionId: string,
  ): Promise<{ blob: Blob; filename: string }> {
    const endpoint = `converter/download/${conversionId}`;
    const url = `${this.baseUrl}/${endpoint}`;

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
        message: errorData.detail || `Download failed: ${response.status}`,
        code: errorData.code || "DOWNLOAD_FAILED",
      };
    }

    const blob = await response.blob();

    // Extract filename from Content-Disposition header
    const contentDisposition = response.headers.get("Content-Disposition");
    let filename = `converted_statement.${blob.type.includes("csv") ? "csv" : "xlsx"}`;

    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(
        /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/,
      );
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1].replace(/['"]/g, "");
      }
    }

    return { blob, filename };
  }

  /**
   * Remove password from PDF
   */
  async removePassword(file: File, password: string): Promise<Blob> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("password", password);

    const authHeaders = await this.getAuthHeaders();

    const response = await fetch(`${this.baseUrl}/converter/remove-password`, {
      method: "POST",
      credentials: "include",
      headers: authHeaders,
      body: formData,
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
        message:
          errorData.detail ||
          errorData.message ||
          "Failed to remove password from PDF",
        code: errorData.code || "PASSWORD_REMOVE_FAILED",
      };
    }

    return response.blob();
  }

  /**
   * Get conversion history
   */
  async getHistory(
    skip: number = 0,
    limit: number = 50,
  ): Promise<ConversionHistoryResponse> {
    try {
      // Try to get from API first
      return await this.request<ConversionHistoryResponse>(
        `converter/history?skip=${skip}&limit=${limit}`,
      );
    } catch (error) {
      // If API fails, fall back to localStorage
      console.warn("API history failed, using localStorage fallback:", error);

      const records = getConversionHistoryFromLocalStorage();
      const total = records.length;
      const conversions = records.slice(skip, skip + limit).map((record) => ({
        id: record.fileId,
        file_name: record.fileName,
        file_count: 1,
        transaction_count: record.transactionCount || 0,
        total_amount: record.totalAmount || 0,
        status: "completed",
        created_at: record.uploadedAt,
      }));

      return {
        total,
        skip,
        limit,
        conversions,
      };
    }
  }

  /**
   * Get conversion statistics
   */
  async getStats(): Promise<ConversionStats> {
    return this.request<ConversionStats>("converter/stats");
  }

  /**
   * Get conversion analytics
   */
  async getAnalytics(conversionId: string): Promise<ConversionAnalytics> {
    return this.request<ConversionAnalytics>(
      `converter/analytics/${conversionId}`,
    );
  }

  /**
   * Get conversion pricing
   */
  async getPricing(fileCount: number = 1): Promise<PricingResponse> {
    return this.request<PricingResponse>(
      `converter/pricing?file_count=${fileCount}`,
    );
  }

  /**
   * Search transactions with filters
   */
  async searchTransactions(
    searchRequest: SearchRequest,
  ): Promise<SearchResponse> {
    return this.request<SearchResponse>("converter/search", {
      method: "POST",
      body: JSON.stringify({
        query: searchRequest.query || "",
        filters: searchRequest.filters || {},
        page: searchRequest.page || 1,
        size: searchRequest.size || 20,
        sort_by: searchRequest.sort_by || "upload_date",
        sort_order: searchRequest.sort_order || "desc",
      }),
    });
  }

  /**
   * Get transaction search suggestions (autocomplete)
   */
  async getSearchSuggestions(query: string): Promise<string[]> {
    try {
      const result = await this.searchTransactions({
        query,
        size: 5,
        page: 1,
      });

      // Extract unique file names and categories as suggestions
      const suggestions = new Set<string>();

      result.results.forEach((item) => {
        if (item.file_name) suggestions.add(item.file_name);
        item.categories.forEach((cat) => suggestions.add(cat));
        item.merchants.forEach((merchant) => suggestions.add(merchant));
      });

      return Array.from(suggestions).slice(0, 10);
    } catch (error) {
      console.error("Failed to get search suggestions:", error);
      return [];
    }
  }

  /**
   * Get conversion status by ID
   */
  async getConversionStatus(conversionId: string): Promise<{
    status: string;
    progress?: number;
    file_results?: FileResult[];
    total_transactions?: number;
  }> {
    try {
      // Use the analytics endpoint for status check
      const analytics = await this.getAnalytics(conversionId);
      return {
        status: analytics.status,
        file_results: [],
        total_transactions: analytics.transaction_count,
      };
    } catch (error) {
      // If analytics fails, try the download endpoint as a fallback
      // This is a lightweight way to check if conversion exists and is ready
      try {
        const response = await this.request<{
          exists: boolean;
          expires_at?: string;
        }>(`converter/check/${conversionId}`);
        return {
          status: response.exists ? "completed" : "not_found",
        };
      } catch {
        return { status: "not_found" };
      }
    }
  }

  /**
   * Batch convert multiple files with progress tracking
   */
  async batchConvert(
    files: File[],
    format: "csv" | "excel" = "csv",
    onProgress?: (processed: number, total: number) => void,
    password?: string,
  ): Promise<ConversionResponse> {
    // Split files into chunks of 10 for better performance
    const chunkSize = 10;
    const chunks: File[][] = [];

    for (let i = 0; i < files.length; i += chunkSize) {
      chunks.push(files.slice(i, i + chunkSize));
    }

    let allResults: FileResult[] = [];
    let totalTransactions = 0;
    let totalIncome = 0;
    let totalExpenses = 0;
    let processedCount = 0;
    let conversionId = `batch_${Date.now()}`;

    for (const chunk of chunks) {
      const response = await this.convertFiles(
        chunk,
        format,
        password,
        undefined,
        undefined,
      );

      processedCount += chunk.length;
      allResults = allResults.concat(response.file_results);
      totalTransactions += response.total_transactions;
      totalIncome += response.total_income;
      totalExpenses += response.total_expenses;
      conversionId = response.conversion_id || conversionId;

      if (onProgress) {
        onProgress(processedCount, files.length);
      }
    }

    // Return a combined response
    return {
      conversion_id: conversionId,
      status: allResults.every((r) => r.status === "completed")
        ? "completed"
        : "partial",
      total_files: files.length,
      processed_files: allResults.filter((r) => r.status === "completed")
        .length,
      failed_files: allResults.filter((r) => r.status === "failed").length,
      total_transactions: totalTransactions,
      total_income: totalIncome,
      total_expenses: totalExpenses,
      net_flow: totalIncome - totalExpenses,
      format,
      payment_amount: 0,
      expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
      download_url: "",
      file_results: allResults,
      statistics: {
        total_transactions: totalTransactions,
        total_income: totalIncome,
        total_expenses: totalExpenses,
        net_flow: totalIncome - totalExpenses,
      },
    };
  }

  /**
   * Validate file before upload
   */
  validateFile(file: File): { valid: boolean; error?: string } {
    const validExtensions = [".pdf", ".csv", ".xls", ".xlsx"];
    const maxSize = 50 * 1024 * 1024; // 50 MB

    const extension = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");

    if (!validExtensions.includes(extension)) {
      return {
        valid: false,
        error: `Invalid file type. Supported: ${validExtensions.join(", ")}`,
      };
    }

    if (file.size > maxSize) {
      return {
        valid: false,
        error: "File size exceeds 50 MB limit",
      };
    }

    return { valid: true };
  }

  /**
   * Validate multiple files
   */
  validateFiles(files: File[]): {
    valid: File[];
    invalid: { file: File; error: string }[];
  } {
    const valid: File[] = [];
    const invalid: { file: File; error: string }[] = [];

    for (const file of files) {
      const result = this.validateFile(file);
      if (result.valid) {
        valid.push(file);
      } else {
        invalid.push({ file, error: result.error! });
      }
    }

    return { valid, invalid };
  }

  /**
   * Get file type information
   */
  getFileInfo(file: File): {
    extension: string;
    type: "pdf" | "csv" | "excel" | "unknown";
    icon: string;
    color: string;
  } {
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");

    if (ext === ".pdf") {
      return {
        extension: ext,
        type: "pdf",
        icon: "FileText",
        color: "text-red-500",
      };
    }
    if (ext === ".csv") {
      return {
        extension: ext,
        type: "csv",
        icon: "FileJson",
        color: "text-blue-500",
      };
    }
    if ([".xls", ".xlsx"].includes(ext)) {
      return {
        extension: ext,
        type: "excel",
        icon: "FileSpreadsheet",
        color: "text-green-500",
      };
    }

    return {
      extension: ext,
      type: "unknown",
      icon: "File",
      color: "text-gray-500",
    };
  }

  /**
   * Check if PDF is password protected
   */
  async isPdfEncrypted(file: File): Promise<boolean> {
    try {
      const { PDFDocument } = await import("pdf-lib");
      const buffer = await file.arrayBuffer();
      await PDFDocument.load(buffer, { ignoreEncryption: false });
      return false;
    } catch (e) {
      const msg = e instanceof Error ? e.message.toLowerCase() : "";
      if (
        msg.includes("encrypt") ||
        msg.includes("password") ||
        msg.includes("decrypt")
      ) {
        return true;
      }
      return false;
    }
  }

  /**
   * Format file size for display
   */
  formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  /**
   * Get WebSocket URL for real-time conversion progress
   */
  getWebSocketUrl(conversionId: string): string {
    const protocol =
      typeof window !== "undefined" && window.location.protocol === "https:"
        ? "wss:"
        : "ws:";
    const host = typeof window !== "undefined" ? window.location.host : "";

    return `${protocol}//${host}converter/ws/${conversionId}`;
  }

  /**
   * Get authenticated WebSocket URL
   */
  async getAuthenticatedWebSocketUrl(conversionId: string): Promise<string> {
    try {
      const session = await getSession();
      const token = session?.accessToken;

      const baseUrl = this.getWebSocketUrl(conversionId);
      if (token) {
        return `${baseUrl}?token=${encodeURIComponent(token)}`;
      }
      return baseUrl;
    } catch (error) {
      console.error("Failed to get authenticated WebSocket URL:", error);
      return this.getWebSocketUrl(conversionId);
    }
  }

  /**
   * Clear expired conversions from local storage
   */
  clearExpiredConversions(): void {
    clearExpiredConversionsFromLocalStorage();
  }

  /**
   * Get local conversion history (fallback when API is unavailable)
   */
  getLocalHistory(): LocalConversionRecord[] {
    return getConversionHistoryFromLocalStorage();
  }

  /**
   * Store conversion in local storage
   */
  storeLocalConversion(record: LocalConversionRecord): void {
    storeConversionInLocalStorage(record);
  }
}

// ─── Singleton Instance ─────────────────────────────────────────────────────

export const conversionService = new ConversionService(
  process.env.NEXT_PUBLIC_API_URL || "",
);

// ─── React Hooks ────────────────────────────────────────────────────────────

import { useCallback, useEffect, useState } from "react";

/**
 * Hook for using conversion service with state management
 */
export function useConversion() {
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [conversion, setConversion] = useState<ConversionResponse | null>(null);

  const convert = useCallback(
    async (
      files: File[],
      format: "csv" | "excel" = "csv",
      password?: string,
    ) => {
      setIsLoading(true);
      setError(null);
      setProgress(0);

      try {
        const result = await conversionService.convertFiles(
          files,
          format,
          password,
        );
        setConversion(result);
        setProgress(100);
        return result;
      } catch (err: any) {
        setError(err.message || "Conversion failed");
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const download = useCallback(async (conversionId: string) => {
    try {
      const { blob, filename } =
        await conversionService.downloadConversionWithFilename(conversionId);

      // Create download link
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      return { blob, filename };
    } catch (err: any) {
      setError(err.message || "Download failed");
      throw err;
    }
  }, []);

  const reset = useCallback(() => {
    setConversion(null);
    setProgress(0);
    setError(null);
    setIsLoading(false);
  }, []);

  return {
    convert,
    download,
    reset,
    isLoading,
    progress,
    error,
    conversion,
  };
}

/**
 * Hook for fetching conversion history
 */
export function useConversionHistory(limit: number = 50) {
  const [history, setHistory] = useState<ConversionHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(
    async (skip: number = 0) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await conversionService.getHistory(skip, limit);
        setHistory(response.conversions);
        setTotal(response.total);
        return response;
      } catch (err: any) {
        setError(err.message || "Failed to load history");
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [limit],
  );

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return {
    history,
    total,
    isLoading,
    error,
    refresh: fetchHistory,
  };
}

/**
 * Hook for fetching conversion stats
 */
export function useConversionStats() {
  const [stats, setStats] = useState<ConversionStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await conversionService.getStats();
      setStats(response);
      return response;
    } catch (err: any) {
      setError(err.message || "Failed to load stats");
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return {
    stats,
    isLoading,
    error,
    refresh: fetchStats,
  };
}

/**
 * Hook for file management with validation
 */
export function useFileManagement() {
  const [files, setFiles] = useState<File[]>([]);
  const [errors, setErrors] = useState<{ file: File; error: string }[]>([]);

  const addFiles = useCallback((newFiles: File[]) => {
    const { valid, invalid } = conversionService.validateFiles(newFiles);

    if (invalid.length > 0) {
      setErrors(invalid);
    }

    setFiles((prev) => [...prev, ...valid]);
    return { valid, invalid };
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const clearFiles = useCallback(() => {
    setFiles([]);
    setErrors([]);
  }, []);

  const getTotalSize = useCallback(() => {
    return files.reduce((acc, file) => acc + file.size, 0);
  }, [files]);

  const getFileInfo = useCallback((file: File) => {
    return conversionService.getFileInfo(file);
  }, []);

  const formatSize = useCallback((bytes: number) => {
    return conversionService.formatFileSize(bytes);
  }, []);

  return {
    files,
    errors,
    addFiles,
    removeFile,
    clearFiles,
    getTotalSize,
    getFileInfo,
    formatSize,
    fileCount: files.length,
    totalSize: getTotalSize(),
  };
}
