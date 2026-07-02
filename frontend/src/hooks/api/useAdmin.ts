import { useApi, useApiMutation } from './useApi'
import { adminApi } from '@/lib/api/endpoints'

export function useAdminAnalytics() {
  return useApi(() => adminApi.getAnalytics())
}

export function useAdminUsers(params?: { page?: number; limit?: number; search?: string; role?: string }) {
  return useApi(() => adminApi.getUsers(params))
}

export function useAdminUser(id: string) {
  return useApi(() => adminApi.getUser(id), { enabled: !!id })
}

export function useUpdateUser() {
  return useApiMutation(({ id, data }: { id: string; data: any }) =>
    adminApi.updateUser(id, data)
  )
}

export function useDeleteUser() {
  return useApiMutation((id: string) => adminApi.deleteUser(id))
}

export function usePaymentLogs(params?: { page?: number; limit?: number; status?: string }) {
  return useApi(() => adminApi.getPaymentLogs(params))
}

export function useContactMessages(params?: { status?: string }) {
  return useApi(() => adminApi.getContactMessages(params))
}

export function useUpdateContactMessage() {
  return useApiMutation((data: { id: string; status: string }) =>
    adminApi.updateContactMessage(data)
  )
}
