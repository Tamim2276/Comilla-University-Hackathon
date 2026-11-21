// SessionStorePort over localStorage. Storage can be blocked (private mode, some in-app browsers),
// so every call is guarded and the app keeps working without it.

import type { SessionStorePort } from '../application/ports'

const PHONE_KEY = 'ekcall.phone'

export function createLocalSessionStore(): SessionStorePort {
  return {
    loadPhone() {
      try {
        return window.localStorage.getItem(PHONE_KEY)
      } catch {
        return null
      }
    },
    savePhone(phone) {
      try {
        window.localStorage.setItem(PHONE_KEY, phone)
      } catch {
        // not saved: the user types the number again next time
      }
    },
    clearPhone() {
      try {
        window.localStorage.removeItem(PHONE_KEY)
      } catch {
        // nothing to clear
      }
    },
  }
}
