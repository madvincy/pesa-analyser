// src/hooks/api/useUser.ts
import { userApi } from "@/lib/api/endpoints";
import { useCallback } from "react";
import { useApi, useApiMutation } from "./useApi";

// ✅ Import types from endpoints
import type {
  DeleteResponse,
  ExportResponse,
  HistoryResponse,
  ProfileResponse,
} from "@/lib/api/endpoints";

export function useUserHistory(params?: {
  type?: string;
  page?: number;
  limit?: number;
}) {
  const fetchFn = useCallback(
    () => userApi.getHistory(params),
    [params?.type, params?.page, params?.limit],
  );
  return useApi<HistoryResponse>(fetchFn);
}

export function useUserProfile() {
  const fetchFn = useCallback(() => userApi.getProfile(), []);
  return useApi<ProfileResponse>(fetchFn);
}

export function useUpdateProfile() {
  return useApiMutation<ProfileResponse, { name?: string; email?: string }>(
    (data) => userApi.updateProfile(data),
  );
}

export function useDeleteUserData() {
  return useApiMutation<DeleteResponse, void>(() => userApi.deleteData());
}

// ✅ FIXED: was using useApi() -- the eager query hook that auto-fetches on
// mount, same as useUserProfile/useUserHistory. That's correct for passive
// display data, but export is a user-triggered action (the "Export All
// Data" button), so it was firing /user/export automatically on every page
// load. Switched to useApiMutation, matching useDeleteUserData's pattern --
// nothing runs until the returned trigger function is explicitly called.
export function useExportUserData() {
  return useApiMutation<ExportResponse, void>(() => userApi.exportData());
}
