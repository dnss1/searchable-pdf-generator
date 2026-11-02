'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, ClipboardPaste } from 'lucide-react'

interface UploadZoneProps {
  onFile: (file: File) => void
  disabled?: boolean
  readOnly?: boolean
}

const SUPPORTED = ['.pdf', '.png', '.jpg', '.jpeg']
const SUPPORTED_MIME = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg']

export default function UploadZone({ onFile, disabled = false, readOnly = false }: UploadZoneProps) {
  const [dragOver, setDragOver] = useState(false)
  const [pasteFlash, setPasteFlash] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const dragCounterRef = useRef(0)

  const validateAndSubmit = useCallback((file: File | undefined | null) => {
    if (!file) return
    const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
    const okByExt = SUPPORTED.includes(ext)
    const okByMime = SUPPORTED_MIME.includes(file.type)
    if (!okByExt && !okByMime) {
      setError(`지원하지 않는 형식입니다. ${SUPPORTED.join(', ')} 만 가능합니다.`)
      return
    }
    setError(null)
    onFile(file)
  }, [onFile])

  // 전역 클립보드 paste — 다른 input/textarea에 포커스가 있지 않을 때만 동작
  useEffect(() => {
    if (disabled || readOnly) return
    const onPaste = (e: ClipboardEvent) => {
      const target = e.target as HTMLElement | null
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return
      const items = e.clipboardData?.items
      if (!items) return
      for (const item of Array.from(items)) {
        if (item.kind === 'file') {
          const blob = item.getAsFile()
          if (!blob) continue
          // 클립보드 이미지는 파일명이 비어있는 경우가 많음 — 확장자 추정해서 보정
          const ext = blob.type === 'image/png' ? 'png' : blob.type === 'image/jpeg' ? 'jpg' : 'png'
          const fileName = blob.name && blob.name !== 'image.png'
            ? blob.name
            : `clipboard_${Date.now()}.${ext}`
          const renamed = new File([blob], fileName, { type: blob.type || 'image/png' })
          validateAndSubmit(renamed)
          setPasteFlash(true)
          window.setTimeout(() => setPasteFlash(false), 600)
          e.preventDefault()
          return
        }
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [disabled, readOnly, validateAndSubmit])

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation()
    dragCounterRef.current += 1
    if (e.dataTransfer.types.includes('Files')) setDragOver(true)
  }
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation()
    dragCounterRef.current -= 1
    if (dragCounterRef.current <= 0) { dragCounterRef.current = 0; setDragOver(false) }
  }
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation()
    e.dataTransfer.dropEffect = 'copy'
  }
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation()
    dragCounterRef.current = 0
    setDragOver(false)
    if (disabled || readOnly) return
    validateAndSubmit(e.dataTransfer.files?.[0])
  }

  return (
    <div
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={() => !disabled && !readOnly && inputRef.current?.click()}
      className={`
        relative cursor-pointer rounded-2xl border-2 border-dashed transition-all duration-300
        flex flex-col items-center justify-center gap-4 py-14 px-8
        ${disabled || readOnly ? 'cursor-default' : 'hover:border-primary/60 hover:bg-primary/[0.03]'}
        ${disabled ? 'opacity-50' : ''}
        ${dragOver
          ? 'border-primary bg-primary/10 scale-[1.01]'
          : 'border-border-light dark:border-border-dark bg-surface-light dark:bg-surface-dark/40'
        }
        ${pasteFlash ? 'ring-2 ring-primary/40' : ''}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept={SUPPORTED.join(',')}
        className="hidden"
        onChange={(e) => validateAndSubmit(e.target.files?.[0])}
        disabled={disabled}
      />

      <div
        className={`
          flex h-14 w-14 items-center justify-center rounded-2xl transition-colors
          ${dragOver ? 'bg-primary text-white' : 'bg-primary/10 text-primary'}
        `}
      >
        <Upload className="h-6 w-6" strokeWidth={2.2} />
      </div>

      <div className="text-center">
        <p className="text-base font-semibold text-text-primary-light dark:text-text-primary-dark">
          {readOnly ? '이 데모는 업로드를 받지 않습니다' : dragOver ? '여기에 놓으세요' : '파일을 끌어다 놓거나 클릭'}
        </p>
        {readOnly ? (
          <p className="mt-1.5 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
            모델과 서버 코드를 공개하지 않기 위해, 미리 처리해 둔 결과만 보여줍니다.
            <br />
            아래 <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">시연용 샘플</span>을 선택하세요.
          </p>
        ) : (
        <p className="mt-1.5 text-sm text-text-secondary-light dark:text-text-secondary-dark flex items-center justify-center gap-1.5">
          <ClipboardPaste className="h-3.5 w-3.5" />
          <span>또는 <kbd className="rounded border border-border-light dark:border-border-dark bg-surface-alt-light dark:bg-surface-alt-dark px-1.5 py-0.5 font-mono text-[11px] font-semibold">Ctrl</kbd> <kbd className="rounded border border-border-light dark:border-border-dark bg-surface-alt-light dark:bg-surface-alt-dark px-1.5 py-0.5 font-mono text-[11px] font-semibold">V</kbd> 로 붙여넣기</span>
        </p>
        )}
      </div>

      <div className="flex gap-1.5 text-[11px] text-text-secondary-light dark:text-text-secondary-dark">
        {SUPPORTED.map((ext) => (
          <span
            key={ext}
            className="rounded-md bg-surface-alt-light dark:bg-surface-alt-dark px-2 py-0.5 font-mono"
          >
            {ext}
          </span>
        ))}
      </div>

      {error && (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-md bg-accent-red/10 px-3 py-1.5 text-xs text-accent-red whitespace-nowrap">
          {error}
        </div>
      )}
    </div>
  )
}
