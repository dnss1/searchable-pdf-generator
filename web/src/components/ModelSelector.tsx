'use client'

import { RecModel } from '@/lib/api'
import { Check } from 'lucide-react'

interface ModelSelectorProps {
  models: RecModel[]
  selectedId: string
  onChange: (id: string) => void
  disabled?: boolean
}

export default function ModelSelector({ models, selectedId, onChange, disabled = false }: ModelSelectorProps) {
  return (
    <div className={`grid gap-2 ${models.length > 1 ? 'sm:grid-cols-2' : ''}`}>
      {models.map((m) => {
        const selected = m.id === selectedId
        const fixed = models.length === 1   // 하나뿐이면 고정
        return (
          <button
            key={m.id}
            type="button"
            disabled={disabled || fixed}
            onClick={() => onChange(m.id)}
            className={`
              group relative flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-left transition-all
              ${disabled ? 'opacity-50 cursor-not-allowed' : fixed ? 'cursor-default' : 'cursor-pointer'}
              ${selected
                ? 'border-primary bg-primary/[0.07] ring-1 ring-primary/30'
                : 'border-border-light bg-surface-light hover:border-primary/30 dark:border-border-dark dark:bg-surface-dark/60'
              }
            `}
          >
            {/* 체크 아이콘 자리 (선택 시) */}
            <div
              className={`mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full transition-colors ${
                selected
                  ? 'bg-primary text-white'
                  : 'border border-border-light dark:border-border-dark'
              }`}
            >
              {selected && <Check className="h-2.5 w-2.5" strokeWidth={3.5} />}
            </div>

            <div className="min-w-0">
              <div
                className={`font-mono text-sm font-semibold tracking-tight ${
                  selected ? 'text-primary' : 'text-text-primary-light dark:text-text-primary-dark'
                }`}
              >
                {m.label}
              </div>
              {m.description && (
                <div className="mt-0.5 text-[11px] text-text-secondary-light dark:text-text-secondary-dark">
                  {m.description}
                </div>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}
