// One message in the chat: the user's question, an answer from Ek Call, or an error (FR-APP-02, 08).
// The checklist card and the source list are added in D1-R5.

import { UI } from '../../domain/messages'
import type { ChatMessage, ChatResponse } from '../../domain/types'
import { RichText } from './RichText'
import { PlayAnswerButton } from './voice/PlayAnswerButton'

function ServiceTag({ name }: { name: string }) {
  return (
    <span className="inline-block rounded-full bg-bd-green-soft px-3 py-1 text-sm font-bold text-bd-green">
      {name}
    </span>
  )
}

function AnswerBubble({ answer }: { answer: ChatResponse }) {
  if (answer.status === 'follow_up') {
    // The agent needs one more detail before it can answer; the user simply replies below.
    return (
      <div className="rounded-2xl rounded-tl-sm border-2 border-bd-red bg-bd-red-soft p-4">
        <p className="mb-1 text-base font-bold text-bd-red-dark">{UI.followUpLabel}</p>
        <p className="text-lg font-bold">{answer.follow_up_question || answer.display_text}</p>
        <div className="mt-2">
          <PlayAnswerButton text={answer.speech_text} />
        </div>
      </div>
    )
  }

  const isFallback = answer.status !== 'answered'
  return (
    <div
      className={`rounded-2xl rounded-tl-sm bg-white p-4 shadow-sm ${isFallback ? 'border-2 border-gray-300' : ''}`}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {answer.service && !isFallback && <ServiceTag name={answer.service.name_bn} />}
        {isFallback && <span className="text-sm font-bold text-gray-600">{UI.fallbackLabel}</span>}
      </div>
      <RichText text={answer.display_text || answer.speech_text} />
      <div className="mt-2">
        <PlayAnswerButton text={answer.speech_text} />
      </div>
    </div>
  )
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-bd-green px-4 py-3 text-white break-words">
          <span className="sr-only">{UI.you}: </span>
          {message.text}
        </div>
      </div>
    )
  }

  if (message.role === 'error') {
    return (
      <div className="flex justify-start" role="alert">
        <div className="max-w-[90%] rounded-2xl rounded-tl-sm border-2 border-bd-red-dark bg-bd-red-soft px-4 py-3 text-bd-red-dark">
          {message.text}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[95%]">
        <AnswerBubble answer={message.answer} />
      </div>
    </div>
  )
}

export function ThinkingBubble() {
  return (
    <div className="flex justify-start" role="status" aria-live="polite">
      <div className="flex items-center gap-3 rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm">
        <span className="flex gap-1" aria-hidden="true">
          <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-bd-green [animation-delay:-0.3s]" />
          <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-bd-green [animation-delay:-0.15s]" />
          <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-bd-red" />
        </span>
        <span className="text-gray-600">{UI.thinking}</span>
      </div>
    </div>
  )
}
