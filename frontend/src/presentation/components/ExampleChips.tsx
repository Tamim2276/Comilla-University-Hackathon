// Example questions for the main services (FR-APP-07). Typed exactly like
// backend/data/questions/demo_questions.txt, so they hit the pre-warmed answer cache.

const EXAMPLES: { label: string; question: string }[] = [
  { label: 'বয়স্ক ভাতা', question: 'আমার বয়স ৬৭। আমি কি বয়স্ক ভাতা পাবো? কী কী লাগবে?' },
  { label: 'বিধবা ভাতা', question: 'বিধবা ভাতার জন্য কী লাগে?' },
  { label: 'এনআইডি সংশোধন', question: 'NID-te namer banan bhul, ki korbo?' },
  { label: 'জন্ম নিবন্ধন', question: 'জন্ম নিবন্ধন করতে কী কী কাগজ লাগে?' },
  { label: 'ই-পাসপোর্ট', question: 'ই-পাসপোর্ট করতে কত টাকা লাগে?' },
  { label: 'প্রতিবন্ধী ভাতা', question: 'প্রতিবন্ধী ভাতা পেতে কী কী কাগজ লাগে?' },
  { label: 'জমির নামজারি', question: 'জমির নামজারি করতে কী কী লাগে?' },
  { label: 'ট্রেড লাইসেন্স', question: 'ট্রেড লাইসেন্স করতে কী কী কাগজ লাগে?' },
]

export function ExampleChips({
  onPick,
  disabled,
  title,
}: {
  onPick: (question: string) => void
  disabled?: boolean
  title?: string
}) {
  return (
    <div>
      {title && <p className="mb-2 text-base font-bold text-bd-green">{title}</p>}
      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        {EXAMPLES.map((e) => (
          <button
            key={e.label}
            type="button"
            title={e.question}
            disabled={disabled}
            onClick={() => onPick(e.question)}
            className="min-h-12 shrink-0 rounded-full border-2 border-bd-green bg-white px-4 text-base font-bold text-bd-green hover:bg-bd-green-soft disabled:opacity-50"
          >
            {e.label}
          </button>
        ))}
      </div>
    </div>
  )
}
