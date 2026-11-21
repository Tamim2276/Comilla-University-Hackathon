// Top bar: the flag in miniature, the app name, and an optional action on the right.

import type { ReactNode } from 'react'
import { UI } from '../../domain/messages'

export function FlagMark({ size = 'md' }: { size?: 'md' | 'lg' }) {
  const box = size === 'lg' ? 'h-20 w-28 rounded-md' : 'h-8 w-12 rounded'
  const disc = size === 'lg' ? 'h-11 w-11' : 'h-4 w-4'
  return (
    <div className={`flex shrink-0 items-center justify-center bg-bd-green ${box}`} aria-hidden="true">
      <div className={`rounded-full bg-bd-red ${disc}`} />
    </div>
  )
}

export function AppHeader({ right }: { right?: ReactNode }) {
  return (
    <header className="sticky top-0 z-10 bg-bd-green text-white shadow">
      <div className="mx-auto flex min-h-14 w-full max-w-2xl items-center gap-3 px-4 py-2">
        <div className="rounded bg-white p-0.5">
          <FlagMark />
        </div>
        <div className="min-w-0 flex-1 leading-tight">
          <p className="text-xl font-bold">{UI.appName}</p>
          <p className="text-sm text-white/80">{UI.appNameEn}</p>
        </div>
        {right}
      </div>
    </header>
  )
}
