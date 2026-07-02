// src/lib/api/client.ts
import { getSession } from "next-auth/react";

export interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  message?: string;
  status: number;
}

export interface ApiError {
  message: string;
  status: number;
  errors?: Record<string, string[]>;
}

interface ExtendedSession {
  user?: {
    id: string;
    name?: string | null;
    email?: string | null;
    image?: string | null;
    role?: string;
    createdAt?: string | Date;
  };
  accessToken?: string;
  jwt?: any;
  provider?: string;
}

class ApiClient {
  private baseUrl: string;
  private defaultHeaders: Record<string, string>;

  constructor() {
    this.baseUrl =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    this.defaultHeaders = {
      "Content-Type": "application/json",
    };
  }

  private async getHeaders(): Promise<HeadersInit> {
    const session = (await getSession()) as ExtendedSession | null;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (session) {
      const token = session.accessToken || session.jwt || null;
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    return headers;
  }

  private async handleResponse<T>(response: Response): Promise<ApiResponse<T>> {
    const contentType = response.headers.get("content-type");

    if (contentType?.includes("text/html")) {
      const text = await response.text();
      return {
        error: "API returned HTML instead of JSON.",
        status: response.status,
      };
    }

    let data: any;
    try {
      data = await response.json();
    } catch (e) {
      return {
        error: "Invalid JSON response from server",
        status: response.status,
      };
    }

    if (!response.ok) {
      return {
        error: data.message || data.error || "An error occurred",
        status: response.status,
        data,
      };
    }

    return {
      data: data as T,
      status: response.status,
      message: data.message,
    };
  }

  // ✅ Fix: Make these methods properly typed
  async get<T>(
    endpoint: string,
    params?: Record<string, any>,
  ): Promise<ApiResponse<T>> {
    const url = new URL(`${this.baseUrl}${endpoint}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    try {
      const headers = await this.getHeaders();
      const response = await fetch(url.toString(), {
        method: "GET",
        headers,
        credentials: "include",
      });

      return this.handleResponse<T>(response);
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : "Network error",
        status: 500,
      };
    }
  }

  async post<T>(endpoint: string, body?: any): Promise<ApiResponse<T>> {
    try {
      const headers = await this.getHeaders();
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: "POST",
        headers,
        body: body ? JSON.stringify(body) : undefined,
        credentials: "include",
      });

      return this.handleResponse<T>(response);
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : "Network error",
        status: 500,
      };
    }
  }

  async put<T>(endpoint: string, body?: any): Promise<ApiResponse<T>> {
    try {
      const headers = await this.getHeaders();
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: "PUT",
        headers,
        body: body ? JSON.stringify(body) : undefined,
        credentials: "include",
      });

      return this.handleResponse<T>(response);
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : "Network error",
        status: 500,
      };
    }
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    try {
      const headers = await this.getHeaders();
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: "DELETE",
        headers,
        credentials: "include",
      });

      return this.handleResponse<T>(response);
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : "Network error",
        status: 500,
      };
    }
  }

  async upload<T>(
    endpoint: string,
    formData: FormData,
  ): Promise<ApiResponse<T>> {
    try {
      const session = (await getSession()) as ExtendedSession | null;
      const headers: Record<string, string> = {};

      if (session) {
        const token = session.accessToken || session.jwt || null;
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
      }

      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: "POST",
        headers,
        body: formData,
        credentials: "include",
      });

      return this.handleResponse<T>(response);
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : "Network error",
        status: 500,
      };
    }
  }
}

export const apiClient = new ApiClient();

// ✅ Fix: Use function overloads or proper typing
export const api = {
  get: <T>(
    endpoint: string,
    params?: Record<string, any>,
  ): Promise<ApiResponse<T>> => apiClient.get<T>(endpoint, params),
  post: <T>(endpoint: string, body?: any): Promise<ApiResponse<T>> =>
    apiClient.post<T>(endpoint, body),
  put: <T>(endpoint: string, body?: any): Promise<ApiResponse<T>> =>
    apiClient.put<T>(endpoint, body),
  delete: <T>(endpoint: string): Promise<ApiResponse<T>> =>
    apiClient.delete<T>(endpoint),
  upload: <T>(endpoint: string, formData: FormData): Promise<ApiResponse<T>> =>
    apiClient.upload<T>(endpoint, formData),
};

export const getAuthToken = async (): Promise<string | null> => {
  const session = (await getSession()) as ExtendedSession | null;
  if (!session) return null;
  return session.accessToken || session.jwt || null;
};
