// src/lib/api/endpoints.ts
import { api, ApiResponse } from "./client";

// ✅ Define all response types
export interface HistoryResponse {
  analyses: any[];
  chats: any[];
  pagination?: {
    page: number;
    limit: number;
    total: number;
    pages: number;
  };
}

export interface DeleteResponse {
  message: string;
}

export interface ExportResponse {
  user: {
    id: string;
    email: string;
    name: string;
    createdAt: string;
  };
  analyses: any[];
  chatHistory: any[];
  payments: any[];
  exportedAt: string;
}

export interface ProfileResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login: string;
}

// ✅ Use explicit type annotations
export const userApi = {
  getProfile: (): Promise<ApiResponse<ProfileResponse>> =>
    api.get<ProfileResponse>("/user/profile"),

  updateProfile: (data: {
    name?: string;
    email?: string;
  }): Promise<ApiResponse<ProfileResponse>> =>
    api.put<ProfileResponse>("/user/profile", data),

  getHistory: (params?: {
    type?: string;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<HistoryResponse>> =>
    api.get<HistoryResponse>("/user/history", params),

  deleteData: (): Promise<ApiResponse<DeleteResponse>> =>
    api.delete<DeleteResponse>("/user/data"),

  exportData: (): Promise<ApiResponse<ExportResponse>> =>
    api.get<ExportResponse>("/user/export"),
};

// ============================================================
// ADMIN ENDPOINTS
// ============================================================

export const adminApi = {
  getAnalytics: () => api.get("/admin/analytics"),
  getUsers: (params?: {
    page?: number;
    limit?: number;
    search?: string;
    role?: string;
  }) => api.get("/admin/users", params),
  getUser: (id: string) => api.get(`/admin/users/${id}`),
  updateUser: (id: string, data: any) => api.put(`/admin/users/${id}`, data),
  deleteUser: (id: string) => api.delete(`/admin/users/${id}`),
  getPaymentLogs: (params?: {
    page?: number;
    limit?: number;
    status?: string;
  }) => api.get("/admin/payments/logs", params),
  getContactMessages: (params?: { status?: string }) =>
    api.get("/admin/contact", params),
  updateContactMessage: (data: { id: string; status: string }) =>
    api.put("/admin/contact", data),
};

// ============================================================
// ANALYSIS ENDPOINTS
// ============================================================

export const analysisApi = {
  getAnalysis: (id: string) => api.get(`/analysis/${id}`),
  getSummary: (id: string) => api.get(`/analysis/${id}/summary`),
  upload: (formData: FormData) => api.upload("/upload", formData),
};

// ============================================================
// PAYMENT ENDPOINTS
// ============================================================

export const paymentApi = {
  initiate: (data: {
    analysisId: string;
    phoneNumber: string;
    amount: number;
  }) => api.post("/payment/initiate", data),
  getStatus: (id: string) => api.get(`/payment/status/${id}`),
};

// ============================================================
// REPORT ENDPOINTS
// ============================================================

export const reportApi = {
  generate: (id: string, format?: string) =>
    api.get(`/report/${id}`, { format }),
  email: (data: { email: string; analysisId: string }) =>
    api.post("/report/email", data),
};

// ============================================================
// HEALTH ENDPOINT
// ============================================================

export const healthApi = {
  check: () => api.get("/health"),
};
