// What the app needs from the outside world. Hooks use these interfaces only;
// infrastructure/ provides the real implementations, main.tsx plugs them in.

import type {
  AdminQuestion,
  AdminStats,
  AnswerStatus,
  ChatRequest,
  ChatResponse,
  HistoryResponse,
  Service,
} from '../domain/types'

/** The Ek Call HTTP API (SRS Section 8). Every method throws ApiError on failure. */
export interface ApiPort {
  chat(request: ChatRequest): Promise<ChatResponse>
  listServices(): Promise<Service[]>
  getHistory(phone: string, limit?: number): Promise<HistoryResponse>
  deleteHistory(phone: string): Promise<boolean>
  /** Admin dashboard (FR-ADM-01, 02). Sends X-Admin-Token when one is configured. */
  adminStats(): Promise<AdminStats>
  adminQuestions(options?: { status?: AnswerStatus; limit?: number }): Promise<AdminQuestion[]>
}

/** Where the phone number of this browser is kept (FR-APP-01). */
export interface SessionStorePort {
  loadPhone(): string | null
  savePhone(phone: string): void
  clearPhone(): void
}

export interface Ports {
  api: ApiPort
  session: SessionStorePort
}
