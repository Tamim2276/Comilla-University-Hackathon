// Admin dashboard (FR-ADM-01, 02, 06; SRS 3.4; scenario S6). Refreshes itself every 10 s.
// The cluster view (D2-R5) is added below the chart in a later step.

import { useAdmin } from '../../application/useAdmin'
import { UI } from '../../domain/messages'
import { AppHeader } from '../components/AppHeader'
import { QuestionList } from '../components/QuestionList'
import { ServiceBarChart } from '../components/ServiceBarChart'
import { StatCard } from '../components/StatCard'
import { bnNumber, bnPercent, bnSeconds, bnTime } from '../format'

export function AdminPage() {
  const { stats, recent, unanswered, loading, error, unauthorized, updatedAt, refresh } = useAdmin()
  const voice = stats?.by_channel.voice ?? 0
  const app = stats?.by_channel.app ?? 0
  const channelTotal = voice + app

  return (
    <div className="flex min-h-svh flex-col">
      <AppHeader
        right={
          <button
            type="button"
            onClick={refresh}
            className="min-h-12 rounded-lg px-3 font-bold text-white hover:bg-bd-green-dark"
          >
            {UI.adminRefresh}
          </button>
        }
      />

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-4 px-4 py-4">
        <div>
          <h1 className="text-2xl font-bold text-bd-green">{UI.adminTitle}</h1>
          <p className="text-gray-600">
            {UI.adminSubtitle} · {UI.adminAutoRefresh}
            {updatedAt && (
              <span className="block text-sm">
                {UI.adminUpdated}: {bnTime(updatedAt)}
              </span>
            )}
          </p>
        </div>

        {error && (
          <p role="alert" className="rounded-2xl border-2 border-bd-red-dark bg-bd-red-soft p-4 text-bd-red-dark">
            {unauthorized ? UI.adminUnauthorized : error}
          </p>
        )}

        {loading && !stats && (
          <p role="status" className="rounded-2xl bg-white p-4 text-center text-gray-700 shadow-sm">
            {UI.adminLoading}
          </p>
        )}

        {stats && (
          <>
            <section className="grid grid-cols-2 gap-3 md:grid-cols-5" aria-label="KPI">
              <StatCard label={UI.kpiTotal} value={bnNumber(stats.total_questions)} />
              <StatCard label={UI.kpiAnswered} value={bnPercent(stats.answered_pct)} />
              <StatCard label={UI.kpiFallback} value={bnPercent(stats.fallback_pct)} />
              <StatCard label={UI.kpiLatency} value={bnSeconds(stats.avg_latency_ms)} unit={UI.secondsShort} />
              <StatCard label={UI.kpiCallsToday} value={bnNumber(stats.calls_today)} />
            </section>

            <div className="grid gap-4 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <ServiceBarChart data={stats.by_service} />
              </div>
              <section className="rounded-2xl bg-white p-4 shadow-sm">
                <h2 className="mb-3 text-lg font-bold text-bd-green">{UI.byChannelTitle}</h2>
                <div className="grid grid-cols-2 gap-3">
                  <StatCard label={UI.channelVoice} value={bnNumber(voice)} />
                  <StatCard label={UI.channelApp} value={bnNumber(app)} />
                </div>
                {channelTotal > 0 && (
                  <p className="mt-3 text-sm text-gray-600">
                    {UI.channelVoice} {bnPercent((100 * voice) / channelTotal)} · {UI.channelApp}{' '}
                    {bnPercent((100 * app) / channelTotal)}
                  </p>
                )}
              </section>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <QuestionList title={UI.unansweredTitle} rows={unanswered} empty={UI.noUnanswered} />
              <QuestionList title={UI.recentTitle} rows={recent} empty={UI.noQuestions} />
            </div>
          </>
        )}
      </main>
    </div>
  )
}
