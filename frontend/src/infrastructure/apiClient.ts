// ApiPort over fetch. Turns every failure into an ApiError with a Bangla message (FR-APP-08).

import type { ApiPort } from '../application/ports'
import { MSG } from '../domain/messages'
import {
  ApiError,
  type AdminQuestion,
  type AdminStats,
  type AnswerStatus,
  type ChatRequest,
  type ChatResponse,
  type HistoryResponse,
  type Service,
} from '../domain/types'

interface ErrorBody {
  error?: { code?: string; message_bn?: string; message_en?: string }
}

export function createApiClient(baseUrl: string, timeoutMs: number, adminToken = ''): ApiPort {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    let res: Response
    try {
      res = await fetch(`${baseUrl}${path}`, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...init.headers },
        signal: controller.signal,
      })
    } catch (err) {
      // Server down, no network, CORS blocked, or our timeout fired.
      const code = controller.signal.aborted ? 'TIMEOUT' : 'NETWORK'
      throw new ApiError(code, MSG.ERROR, 0, String(err))
    } finally {
      clearTimeout(timer)
    }

    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as ErrorBody
      throw new ApiError(
        body.error?.code ?? `HTTP_${res.status}`,
        body.error?.message_bn || MSG.ERROR,
        res.status,
        body.error?.message_en,
      )
    }
    return (await res.json()) as T
  }

  const phonePath = (phone: string) => `/api/v1/conversations/${encodeURIComponent(phone)}`
  const adminHeaders: Record<string, string> = adminToken ? { 'X-Admin-Token': adminToken } : {}

  return {
    chat: (body: ChatRequest) =>
      request<ChatResponse>('/api/v1/chat', {
        method: 'POST',
        body: JSON.stringify({ channel: 'app', ...body }),
      }),
    listServices: () => request<Service[]>('/api/v1/services'),
    getHistory: (phone: string, limit = 50) =>
      request<HistoryResponse>(`${phonePath(phone)}?limit=${limit}`),
    deleteHistory: async (phone: string) =>
      (await request<{ deleted: boolean }>(phonePath(phone), { method: 'DELETE' })).deleted,
    adminStats: () => request<AdminStats>('/api/v1/admin/stats', { headers: adminHeaders }),
    adminQuestions: async (options: { status?: AnswerStatus; limit?: number } = {}) => {
      const query = new URLSearchParams({ limit: String(options.limit ?? 20) })
      if (options.status) query.set('status', options.status)
      const body = await request<{ questions: AdminQuestion[] }>(`/api/v1/admin/questions?${query}`, {
        headers: adminHeaders,
      })
      return body.questions
    },
  }
}
