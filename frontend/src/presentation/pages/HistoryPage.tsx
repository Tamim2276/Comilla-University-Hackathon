// History: past checklists for this phone number, newest first, from the app and from phone calls
// (FR-APP-05, SRS 3.3, scenario S5).

import { Link } from 'react-router-dom'
import { useHistory } from '../../application/useHistory'
import { UI } from '../../domain/messages'
import { localPhone } from '../../domain/phone'
import { AppHeader } from '../components/AppHeader'
import { ChecklistCard } from '../components/ChecklistCard'
import { ServiceTag } from '../components/ServiceTag'
import { SourceList } from '../components/SourceList'

const dateFormat = new Intl.DateTimeFormat('bn-BD', { dateStyle: 'medium', timeStyle: 'short' })

function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '' : dateFormat.format(date)
}

export function HistoryPage({ phone }: { phone: string }) {
  const { checklists, serviceNames, loading, error, reload } = useHistory(phone)

  return (
    <div className="flex min-h-svh flex-col">
      <AppHeader
        right={
          <Link
            to="/chat"
            className="flex min-h-12 items-center rounded-lg px-3 font-bold text-white hover:bg-bd-green-dark"
          >
            {UI.backToChat}
          </Link>
        }
      />

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-3 px-4 py-4">
        <div>
          <h1 className="text-2xl font-bold text-bd-green">{UI.historyTitle}</h1>
          <p className="text-gray-600">
            {localPhone(phone)} · {UI.historyEn}
          </p>
        </div>

        {loading && (
          <p role="status" className="rounded-2xl bg-white p-4 text-center text-gray-700 shadow-sm">
            {UI.historyLoading}
          </p>
        )}

        {!loading && error && (
          <div role="alert" className="rounded-2xl border-2 border-bd-red-dark bg-bd-red-soft p-4 text-bd-red-dark">
            <p>{error}</p>
            <button
              type="button"
              onClick={reload}
              className="mt-3 min-h-12 rounded-xl bg-bd-red px-5 font-bold text-white hover:bg-bd-red-dark"
            >
              {UI.historyRetry}
            </button>
          </div>
        )}

        {!loading && !error && checklists.length === 0 && (
          <p className="rounded-2xl bg-white p-4 text-center text-gray-700 shadow-sm">{UI.historyEmpty}</p>
        )}

        {!loading && !error && checklists.length > 0 && (
          <ul className="flex flex-col gap-3">
            {checklists.map((record, i) => (
              <li key={`${record.created_at}-${i}`}>
                <article className="rounded-2xl bg-white p-4 shadow-sm">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <ServiceTag name={serviceNames[record.service_id] ?? record.service_id} />
                    <span className="text-sm text-gray-600">{formatDate(record.created_at)}</span>
                    {record.sms_sent && (
                      <span className="rounded-full bg-bd-red-soft px-3 py-1 text-sm font-bold text-bd-red-dark">
                        {UI.smsSentBadge}
                      </span>
                    )}
                  </div>
                  <ChecklistCard checklist={record.checklist} />
                  {record.citations.length > 0 && (
                    <div className="mt-3">
                      <SourceList citations={record.citations} />
                    </div>
                  )}
                </article>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}
