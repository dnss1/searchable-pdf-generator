'use client'

import { SampleMeta, getPageImageUrl } from '@/lib/api'
import { Check, FileText, Plus, Pencil, Trash2 } from 'lucide-react'

interface SamplePickerProps {
  samples: SampleMeta[]
  selectedId: string | null
  onPick: (s: SampleMeta) => void
  onAddClick?: () => void
  onEdit?: (s: SampleMeta) => void
  onDelete?: (s: SampleMeta) => void
  disabled?: boolean
}

/** 시연용 샘플 그리드. 카드 = 페이지 1 썸네일 + 라벨 + 짧은 설명 + 추천 모델 칩 */
export default function SamplePicker({
  samples,
  selectedId,
  onPick,
  onAddClick,
  onEdit,
  onDelete,
  disabled = false,
}: SamplePickerProps) {
  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary-light dark:text-text-secondary-dark">
          시연용 샘플
          {samples.length > 0 && (
            <span className="ml-2 rounded-full bg-surface-alt-light dark:bg-surface-alt-dark px-1.5 py-0.5 text-[10px] font-normal normal-case text-text-secondary-light dark:text-text-secondary-dark">
              {samples.length}
            </span>
          )}
        </h3>
        {onAddClick && (
          <button
            type="button"
            onClick={onAddClick}
            disabled={disabled}
            className="inline-flex items-center gap-1 rounded-md border border-border-light dark:border-border-dark px-2 py-1 text-[11px] font-medium text-text-secondary-light dark:text-text-secondary-dark hover:border-primary/40 hover:text-primary transition-colors disabled:opacity-50"
          >
            <Plus className="h-3 w-3" />
            샘플 추가
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {samples.map((s) => {
          const selected = s.id === selectedId
          const thumbUrl = getPageImageUrl(s.job_id, 1)
          return (
            <button
              key={s.id}
              type="button"
              disabled={disabled}
              onClick={() => onPick(s)}
              className={`
                group relative flex flex-col overflow-hidden rounded-xl border text-left transition-all
                ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-primary/50 hover:shadow-soft'}
                ${selected
                  ? 'border-primary ring-2 ring-primary/30 shadow-soft'
                  : 'border-border-light dark:border-border-dark bg-surface-light dark:bg-surface-dark'
                }
              `}
            >
              {/* 썸네일 영역 (3:4 비율) */}
              <div className="relative w-full bg-gray-100 dark:bg-gray-800 overflow-hidden" style={{ aspectRatio: '3 / 4' }}>
                <img
                  src={thumbUrl}
                  alt={s.label}
                  className="absolute inset-0 h-full w-full object-cover"
                  draggable={false}
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                  loading="lazy"
                />
                <div className="absolute inset-0 flex items-center justify-center text-text-secondary-light/40 -z-0">
                  <FileText className="h-8 w-8" />
                </div>

                {/* 선택 표시 */}
                {selected && (
                  <div className="absolute top-2 right-2 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-white shadow-soft z-10">
                    <Check className="h-3.5 w-3.5" strokeWidth={3} />
                  </div>
                )}

                {/* 수정/삭제 (hover 시) */}
                {!selected && onEdit && onDelete && (
                  <div className="absolute top-1.5 right-1.5 z-10 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); onEdit(s) }}
                      className="flex h-6 w-6 items-center justify-center rounded-md bg-black/60 backdrop-blur-sm text-white hover:bg-black/80 cursor-pointer"
                      title="수정"
                      aria-label="수정"
                    >
                      <Pencil className="h-3 w-3" />
                    </span>
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(s) }}
                      className="flex h-6 w-6 items-center justify-center rounded-md bg-black/60 backdrop-blur-sm text-white hover:bg-accent-red/90 cursor-pointer"
                      title="삭제"
                      aria-label="삭제"
                    >
                      <Trash2 className="h-3 w-3" />
                    </span>
                  </div>
                )}

                {/* 추천 모델 칩 */}
                {s.recommended_model && (
                  <div className="absolute bottom-2 left-2 rounded-md bg-black/70 backdrop-blur-sm px-1.5 py-0.5 font-mono text-[9px] font-bold text-white z-10">
                    {s.recommended_model === 'paddle_ch' ? 'Base_ch' : s.recommended_model === 'stage2c' ? 'Babel_kr' : s.recommended_model}
                  </div>
                )}
              </div>

              {/* 라벨 / 설명 */}
              <div className="flex-1 px-3 py-2 space-y-0.5">
                <div
                  className={`text-xs font-semibold leading-tight ${
                    selected ? 'text-primary' : 'text-text-primary-light dark:text-text-primary-dark'
                  }`}
                >
                  {s.label}
                </div>
                {s.description && (
                  <p className="text-[10px] leading-tight text-text-secondary-light dark:text-text-secondary-dark line-clamp-2">
                    {s.description}
                  </p>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
