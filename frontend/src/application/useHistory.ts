// Use case: show the past checklists of this phone number, from the app and from calls (FR-APP-05).

import { useCallback, useEffect, useState } from 'react'
import { MSG } from '../domain/messages'
import { ApiError, type ChecklistRecord } from '../domain/types'
import { usePorts } from './portsContext'

export interface History {
  /** Newest first, as the API returns them. */
  checklists: ChecklistRecord[]
  /** service id -> Bangla service name (from GET /api/v1/services). */
  serviceNames: Record<string, string>
  loading: boolean
  /** Bangla error message, or null. */
  error: string | null
  reload(): void
}

export function useHistory(phone: string): History {
  const { api } = usePorts()
  const [checklists, setChecklists] = useState<ChecklistRecord[]>([])
  const [serviceNames, setServiceNames] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false // ignore a late answer after the page was left or reloaded
    setLoading(true)
    setError(null)
    Promise.all([api.getHistory(phone), api.listServices().catch(() => [])])
      .then(([history, services]) => {
        if (cancelled) return
        setChecklists(history.checklists)
        setServiceNames(Object.fromEntries(services.map((s) => [s.id, s.name_bn])))
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.messageBn : MSG.ERROR)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [api, phone, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  return { checklists, serviceNames, loading, error, reload }
}
