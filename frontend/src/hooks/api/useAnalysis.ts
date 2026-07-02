import { useApi, useApiMutation } from './useApi'
import { analysisApi } from '@/lib/api/endpoints'

export function useAnalysis(id: string) {
  return useApi(() => analysisApi.getAnalysis(id), { enabled: !!id })
}

export function useAnalysisSummary(id: string) {
  return useApi(() => analysisApi.getSummary(id), { enabled: !!id })
}

export function useUploadAnalysis() {
  return useApiMutation((formData: FormData) => analysisApi.upload(formData))
}
