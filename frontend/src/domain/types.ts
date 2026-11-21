// Types that mirror the API contract (SRS Section 8). No React and no fetch in this layer.

export type AnswerStatus = 'answered' | 'follow_up' | 'fallback' | 'error'

export type RouterName = 'banglabert' | 'tfidf' | 'llm' | 'context'

export type Channel = 'voice' | 'app' | 'sms'

/** A service as listed by GET /api/v1/services. */
export interface Service {
  id: string
  name_bn: string
  name_en: string
  office_bn: string
  sms_name: string
}

/** The short service object inside a chat answer. */
export interface ServiceBrief {
  id: string
  name_bn: string
  name_en: string
}

export interface Checklist {
  who: string
  papers: string[]
  fee: string
  where: string
  decision: string
}

export interface Citation {
  title: string
  source_url: string
  snippet: string
  chunk_id: string
}

/** Response of POST /api/v1/chat. */
export interface ChatResponse {
  conversation_id: string
  status: AnswerStatus
  service: ServiceBrief | null
  confidence: number
  router: RouterName | null
  speech_text: string
  display_text: string
  checklist: Checklist | null
  citations: Citation[]
  follow_up_question: string | null
  latency_ms: number
}

/** Body of POST /api/v1/chat. */
export interface ChatRequest {
  phone: string
  message: string
  channel?: 'app'
}

/** One stored message in GET /api/v1/conversations/{phone}. */
export interface HistoryMessage {
  role: 'user' | 'assistant'
  channel: Channel
  text: string
  service_id: string | null
  status: AnswerStatus | null
  created_at: string
}

export interface ChecklistRecord {
  service_id: string
  checklist: Checklist
  citations: Citation[]
  sms_sent: boolean
  created_at: string
}

/** Response of GET /api/v1/conversations/{phone}. */
export interface HistoryResponse {
  phone: string
  messages: HistoryMessage[]
  checklists: ChecklistRecord[]
}

/** A message shown in the chat on screen. */
export type ChatMessage =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; answer: ChatResponse }
  | { id: string; role: 'error'; text: string }

/** The error JSON every endpoint returns: {"error": {"code", "message_bn", "message_en"}}. */
export class ApiError extends Error {
  readonly code: string
  readonly messageBn: string
  readonly status: number

  constructor(code: string, messageBn: string, status: number, messageEn = '') {
    super(messageEn || code)
    this.name = 'ApiError'
    this.code = code
    this.messageBn = messageBn
    this.status = status
  }
}
