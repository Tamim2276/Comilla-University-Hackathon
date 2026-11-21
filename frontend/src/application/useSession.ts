// Use case: remember who is using the app, by phone number (FR-APP-01).

import { useCallback, useState } from 'react'
import { normalizePhone } from '../domain/phone'
import { usePorts } from './portsContext'

export interface Session {
  /** E.164 number (+8801XXXXXXXXX), or null before the user starts. */
  phone: string | null
  /** Normalises and saves the number. Returns false if it is not a valid BD mobile number. */
  start(rawPhone: string): boolean
  /** Forgets the number on this device. */
  end(): void
}

export function useSession(): Session {
  const { session } = usePorts()
  // A stored value is checked again, in case it was saved by an older version or edited by hand.
  const [phone, setPhone] = useState<string | null>(() => normalizePhone(session.loadPhone() ?? ''))

  const start = useCallback(
    (rawPhone: string) => {
      const e164 = normalizePhone(rawPhone)
      if (!e164) return false
      session.savePhone(e164)
      setPhone(e164)
      return true
    },
    [session],
  )

  const end = useCallback(() => {
    session.clearPhone()
    setPhone(null)
  }, [session])

  return { phone, start, end }
}
