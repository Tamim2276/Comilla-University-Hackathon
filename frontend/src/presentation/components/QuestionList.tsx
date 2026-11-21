// Logged questions on the admin dashboard: recent activity and the unanswered ones (SRS 3.4).
// A list, not a wide table, so it fits a 360 px phone. Status is always a word, never colour alone.

import { UI } from '../../domain/messages'
import type { AdminQuestion, AnswerStatus } from '../../domain/types'
import { bnDateTime, bnSeconds } from '../format'

const STATUS: Record<AnswerStatus, { label: string; className: string }> = {
  answered: { label: UI.statusAnswered, className: 'bg-bd-green-soft text-bd-green' },
  follow_up: { label: UI.statusFollowUp, className: 'bg-gray-100 text-gray-700' },
  fallback: { label: UI.statusFallback, className: 'bg-bd-red-soft text-bd-red-dark' },
  error: { label: UI.statusError, className: 'bg-bd-red-soft text-bd-red-dark' },
}

export function QuestionList({
  title,
  rows,
  empty,
}: {
  title: string
  rows: AdminQuestion[]
  empty: string
}) {
  return (
    <section className="rounded-2xl bg-white p-4 shadow-sm">
      <h2 className="mb-2 text-lg font-bold text-bd-green">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-gray-600">{empty}</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {rows.map((q, i) => {
            const status = STATUS[q.status] ?? STATUS.error
            return (
              <li key={`${q.created_at}-${i}`} className="py-2">
                <p className="break-words">{q.text}</p>
                <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-gray-600">
                  <span className={`rounded-full px-2 py-0.5 font-bold ${status.className}`}>{status.label}</span>
                  {q.service_name_bn && <span>{q.service_name_bn}</span>}
                  <span>· {q.channel === 'voice' ? UI.channelVoice : UI.channelApp}</span>
                  {q.latency_ms > 0 && (
                    <span>
                      · {bnSeconds(q.latency_ms)} {UI.secondsShort}
                    </span>
                  )}
                  <span>· {bnDateTime(q.created_at)}</span>
                  {q.is_demo && (
                    <span className="rounded-full border border-gray-300 px-2 py-0.5">{UI.demoBadge}</span>
                  )}
                </p>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
