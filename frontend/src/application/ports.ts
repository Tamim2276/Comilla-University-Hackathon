// What the app needs from the outside world. Hooks use these interfaces only;
// infrastructure/ provides the real implementations, main.tsx plugs them in.

import type { ChatRequest, ChatResponse, HistoryResponse, Service } from '../domain/types'

/** The Ek Call HTTP API (SRS Section 8). Every method throws ApiError on failure. */
export interface ApiPort {
  chat(request: ChatRequest): Promise<ChatResponse>
  listServices(): Promise<Service[]>
  getHistory(phone: string, limit?: number): Promise<HistoryResponse>
  deleteHistory(phone: string): Promise<boolean>
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
