// App settings read from Vite env variables (frontend/.env). Only this file reads import.meta.env.

const DEFAULT_API_URL = 'http://localhost:8000'

function trimSlash(url: string): string {
  return url.replace(/\/+$/, '')
}

export const config = {
  /** Backend base URL without a trailing slash, e.g. http://localhost:8000 */
  apiUrl: trimSlash(import.meta.env.VITE_API_URL || DEFAULT_API_URL),
  /** How long the app waits for one answer before showing an error (the first answer can be slow). */
  requestTimeoutMs: 60_000,
  /** Sent as X-Admin-Token on admin requests (FR-ADM-05). It is part of the built app, so it only
   *  keeps casual visitors out of the dashboard during the demo; it is not a real login. */
  adminToken: (import.meta.env.VITE_ADMIN_TOKEN as string | undefined) ?? '',
} as const
