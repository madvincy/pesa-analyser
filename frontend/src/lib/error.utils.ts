// src/lib/error-utils.ts
import { ApiError } from "./api/client";

export function getErrorMessage(
  error: string | ApiError | null | undefined,
): string {
  if (!error) return "An unknown error occurred";

  if (typeof error === "string") {
    return error;
  }

  return error.message || "An unknown error occurred";
}

export function getErrorStatus(
  error: string | ApiError | null | undefined,
): number {
  if (!error) return 500;

  if (typeof error === "string") {
    return 500;
  }

  return error.status || 500;
}
