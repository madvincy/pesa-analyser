// src/hooks/api/useApi.ts
import { ApiError, ApiResponse } from "@/lib/api/client";
import { useCallback, useEffect, useRef, useState } from "react";

interface UseApiOptions<T> {
  onSuccess?: (data: T) => void;
  onError?: (error: ApiError) => void;
  enabled?: boolean;
}

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
}

export function useApi<T>(
  fetchFn: () => Promise<ApiResponse<T>>,
  options: UseApiOptions<T> = {},
) {
  const { onSuccess, onError, enabled = true } = options;
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  const isMounted = useRef(true);
  const fetchFnRef = useRef(fetchFn);
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    fetchFnRef.current = fetchFn;
    onSuccessRef.current = onSuccess;
    onErrorRef.current = onError;
  }, [fetchFn, onSuccess, onError]);

  const execute = useCallback(async () => {
    if (!isMounted.current) return;

    setState((prev) => ({ ...prev, loading: true, error: null }));

    try {
      const response = await fetchFnRef.current();

      if (!isMounted.current) return;

      if (response.error) {
        const error: ApiError = {
          message: response.error,
          status: response.status,
        };
        setState({ data: null, loading: false, error });
        onErrorRef.current?.(error);
        return;
      }

      // Handle the case where data might be undefined
      const data = response.data !== undefined ? response.data : null;
      setState({ data, loading: false, error: null });
      onSuccessRef.current?.(data as T);
      return response;
    } catch (error) {
      if (!isMounted.current) return;

      const apiError: ApiError = {
        message: error instanceof Error ? error.message : "Unknown error",
        status: 500,
      };
      setState({ data: null, loading: false, error: apiError });
      onErrorRef.current?.(apiError);
      return { error: apiError, data: null };
    }
  }, []);

  useEffect(() => {
    if (enabled && isMounted.current) {
      execute();
    }

    return () => {
      isMounted.current = false;
    };
  }, [enabled, execute]);

  return {
    ...state,
    refetch: execute,
  };
}

export function useApiMutation<T, V = void>(
  mutationFn: (variables: V) => Promise<ApiResponse<T>>,
) {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  });
  const isMounted = useRef(true);
  const mutationFnRef = useRef(mutationFn);

  useEffect(() => {
    mutationFnRef.current = mutationFn;
  }, [mutationFn]);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  const mutate = useCallback(
    async (
      variables?: V,
    ): Promise<{ error: ApiError | null; data: T | null }> => {
      if (!isMounted.current) return { error: null, data: null };

      setState((prev) => ({ ...prev, loading: true, error: null }));

      try {
        const response = await mutationFnRef.current(variables as V);

        if (!isMounted.current) return { error: null, data: null };

        if (response.error) {
          const error: ApiError = {
            message: response.error,
            status: response.status,
          };
          setState({ data: null, loading: false, error });
          return { error, data: null };
        }

        // Handle the case where data might be undefined
        const data = response.data !== undefined ? response.data : null;
        setState({ data, loading: false, error: null });
        return { error: null, data };
      } catch (error) {
        if (!isMounted.current) return { error: null, data: null };

        const apiError: ApiError = {
          message: error instanceof Error ? error.message : "Unknown error",
          status: 500,
        };
        setState({ data: null, loading: false, error: apiError });
        return { error: apiError, data: null };
      }
    },
    [],
  );

  return {
    ...state,
    mutate,
  };
}
