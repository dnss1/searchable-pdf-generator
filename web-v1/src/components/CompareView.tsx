'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { OCRResult, getPageImageUrl, getProcessedPdfUrl } from '@/lib/api'
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Maximize2, Copy, Check, Download } from 'lucide-react'

interface CompareViewProps {
  jobId: string
  ocr: OCRResult
}

/**
 * 신뢰도 → 색상 매핑
 *  0.9+ : 초록 (good)
 *  0.7-0.9: 노랑 (fair)
 *  < 0.7: 빨강 (poor)
 */
function confidenceColor(c: number | null | undefined): {
  border: string
  bg: string
  text: string
  dot: string
  label: 'good' | 'fair' | 'poor'
} {
  const v = c ?? 0
  if (v >= 0.9) return { border: 'rgba(34, 197, 94, 0.95)', bg: 'rgba(34, 197, 94, 0.08)', text: 'rgb(22, 163, 74)', dot: 'rgb(34, 197, 94)', label: 'good' }
  if (v >= 0.7) return { border: 'rgba(234, 179, 8, 0.95)', bg: 'rgba(234, 179, 8, 0.08)', text: 'rgb(202, 138, 4)', dot: 'rgb(234, 179, 8)', label: 'fair' }
  return { border: 'rgba(239, 68, 68, 0.95)', bg: 'rgba(239, 68, 68, 0.08)', text: 'rgb(220, 38, 38)', dot: 'rgb(239, 68, 68)', label: 'poor' }
}

export default function CompareView({ jobId, ocr }: CompareViewProps) {
  const [pageIdx, setPageIdx] = useState(0)
  const [zoom, setZoom] = useState(1.0)
  const [fitToWidth, setFitToWidth] = useState(true)
  const [hoveredLine, setHoveredLine] = useState<number | null>(null)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [allCopied, setAllCopied] = useState(false)

  const leftScrollRef = useRef<HTMLDivElement>(null)
  const rightScrollRef = useRef<HTMLDivElement>(null)
  const syncRef = useRef<'left' | 'right' | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const lineListRef = useRef<HTMLDivElement>(null)

  const page = ocr.pages[pageIdx]
  const imageUrl = useMemo(() => getPageImageUrl(jobId, page?.page_number || 1), [jobId, page?.page_number])
  // 미리 만들어 둔 searchable PDF 를 그대로 내려준다
  const pdfUrl = useMemo(() => getProcessedPdfUrl(jobId), [jobId])

  // fit-to-width: 패널 너비에 맞춰 자동 zoom 계산
  const [autoZoom, setAutoZoom] = useState(1.0)
  useEffect(() => {
    if (!fitToWidth || !page) return
    const calc = () => {
      const w = containerRef.current?.clientWidth || 0
      // 좌우 패널 50% 씩, 내부 패딩 24px 감안
      const panelWidth = (w / 2) - 24
      if (panelWidth > 0 && page.width > 0) {
        setAutoZoom(panelWidth / page.width)
      }
    }
    calc()
    window.addEventListener('resize', calc)
    return () => window.removeEventListener('resize', calc)
  }, [fitToWidth, page])

  const effectiveZoom = fitToWidth ? autoZoom : zoom

  // 좌우 스크롤 동기화
  useEffect(() => {
    const left = leftScrollRef.current
    const right = rightScrollRef.current
    if (!left || !right) return
    const onScrollL = () => {
      if (syncRef.current === 'right') return
      syncRef.current = 'left'
      right.scrollTop = left.scrollTop
      right.scrollLeft = left.scrollLeft
      requestAnimationFrame(() => { syncRef.current = null })
    }
    const onScrollR = () => {
      if (syncRef.current === 'left') return
      syncRef.current = 'right'
      left.scrollTop = right.scrollTop
      left.scrollLeft = right.scrollLeft
      requestAnimationFrame(() => { syncRef.current = null })
    }
    left.addEventListener('scroll', onScrollL)
    right.addEventListener('scroll', onScrollR)
    return () => {
      left.removeEventListener('scroll', onScrollL)
      right.removeEventListener('scroll', onScrollR)
    }
  }, [])

  const copy = async (text: string, key: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedKey(key)
      setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 1200)
    } catch (e) {
      console.warn('copy failed', e)
    }
  }

  const copyAll = async () => {
    if (!page) return
    const text = page.lines.map((l) => l.text).join('\n')
    try {
      await navigator.clipboard.writeText(text)
      setAllCopied(true)
      setTimeout(() => setAllCopied(false), 1400)
    } catch (e) {
      console.warn('copy failed', e)
    }
  }

  // 라인 리스트에서 hover 시 동일 인덱스 bbox 강조 / 클릭 시 해당 bbox로 scroll
  const scrollToLine = (idx: number) => {
    setHoveredLine(idx)
    const right = rightScrollRef.current
    if (!right || !page) return
    const line = page.lines[idx]
    if (!line) return
    const [x1, y1, x2, y2] = line.bbox
    const centerX = ((x1 + x2) / 2) * effectiveZoom
    const centerY = ((y1 + y2) / 2) * effectiveZoom
    right.scrollTo({
      top: Math.max(0, centerY - right.clientHeight / 2),
      left: Math.max(0, centerX - right.clientWidth / 2),
      behavior: 'smooth',
    })
  }

  if (!page) {
    return (
      <div className="flex h-full items-center justify-center text-text-secondary-light dark:text-text-secondary-dark">
        OCR 결과가 비어있습니다.
      </div>
    )
  }

  const totalPages = ocr.pages.length
  const scaledW = page.width * effectiveZoom
  const scaledH = page.height * effectiveZoom

  // 신뢰도 통계 (전체 페이지 라인 기반)
  const stats = useMemo(() => {
    let good = 0, fair = 0, poor = 0
    for (const l of page.lines) {
      const c = l.confidence ?? 0
      if (c >= 0.9) good++
      else if (c >= 0.7) fair++
      else poor++
    }
    return { good, fair, poor }
  }, [page.lines])

  return (
    <div className="flex h-full flex-col">
      {/* 컨트롤 바 */}
      <div className="flex flex-shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border-light dark:border-border-dark bg-surface-light dark:bg-surface-dark px-4 py-2">
        {/* 좌: 페이지 네비 */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled={pageIdx <= 0}
            onClick={() => setPageIdx((p) => Math.max(0, p - 1))}
            className="rounded-lg p-1.5 text-text-secondary-light dark:text-text-secondary-dark hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-30"
            aria-label="이전 페이지"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="px-2 text-sm font-medium tabular-nums text-text-primary-light dark:text-text-primary-dark">
            {pageIdx + 1} / {totalPages}
          </span>
          <button
            type="button"
            disabled={pageIdx >= totalPages - 1}
            onClick={() => setPageIdx((p) => Math.min(totalPages - 1, p + 1))}
            className="rounded-lg p-1.5 text-text-secondary-light dark:text-text-secondary-dark hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-30"
            aria-label="다음 페이지"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        {/* 중: 줌 */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => { setFitToWidth(false); setZoom((z) => Math.max(0.25, z - 0.15)) }}
            className="rounded-lg p-1.5 text-text-secondary-light dark:text-text-secondary-dark hover:bg-black/5 dark:hover:bg-white/10"
            title="축소"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <span className="px-2 text-xs tabular-nums w-12 text-center text-text-secondary-light dark:text-text-secondary-dark">
            {Math.round(effectiveZoom * 100)}%
          </span>
          <button
            type="button"
            onClick={() => { setFitToWidth(false); setZoom((z) => Math.min(3.0, z + 0.15)) }}
            className="rounded-lg p-1.5 text-text-secondary-light dark:text-text-secondary-dark hover:bg-black/5 dark:hover:bg-white/10"
            title="확대"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setFitToWidth((f) => !f)}
            className={`ml-1 rounded-lg p-1.5 transition-colors ${
              fitToWidth
                ? 'bg-primary/10 text-primary'
                : 'text-text-secondary-light dark:text-text-secondary-dark hover:bg-black/5 dark:hover:bg-white/10'
            }`}
            title="너비에 맞추기"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
        </div>

        {/* 우: 신뢰도 칩 + PDF */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 text-[11px]">
            <Stat dot="rgb(34, 197, 94)" label="High" count={stats.good} />
            <Stat dot="rgb(234, 179, 8)" label="Mid" count={stats.fair} />
            <Stat dot="rgb(239, 68, 68)" label="Low" count={stats.poor} />
          </div>
          {pdfUrl && (
            <a
              href={pdfUrl}
              download
              className="flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/[0.07] px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary hover:text-white"
              title="원본 위에 투명 텍스트 레이어를 얹은 PDF — 열어서 Ctrl+F로 검색해 보세요"
            >
              <Download className="h-3.5 w-3.5" />
              Searchable PDF
            </a>
          )}
        </div>
      </div>

      {/* 비교 + 라인 리스트 (vertical split) */}
      <div className="flex flex-1 min-h-0 flex-col">
        {/* 상단: 좌우 비교 — 화면의 약 60%로 고정. 이미지가 화면 절반 이상을 안 잡도록. */}
        <div
          ref={containerRef}
          className="grid h-[60%] min-h-[280px] flex-shrink-0 grid-cols-2 gap-3 bg-background-light p-3 dark:bg-background-dark"
        >
          {/* 좌: 원본 */}
          <PanelFrame label="원본" panelRef={leftScrollRef}>
            <div style={{ width: scaledW, height: scaledH }} className="relative">
              <img
                src={imageUrl}
                alt={`page ${pageIdx + 1}`}
                className="absolute inset-0 h-full w-full object-fill select-none"
                draggable={false}
              />
            </div>
          </PanelFrame>

          {/* 우: OCR 인식 결과 + bbox 시각화 */}
          <PanelFrame
            label="인식 결과"
            panelRef={rightScrollRef}
            badge={page.is_multi_column ? '더블 컬럼' : undefined}
          >
            <div style={{ width: scaledW, height: scaledH }} className="relative bg-white">
              {/* 컬럼 경계선 (multi-column일 때만) */}
              {page.is_multi_column && page.column_boundary != null && (
                <>
                  <div
                    className="absolute pointer-events-none"
                    style={{
                      left: page.column_boundary * effectiveZoom - 0.5,
                      top: 0,
                      width: 1,
                      height: scaledH,
                      borderLeft: '1.5px dashed rgba(99, 102, 241, 0.55)',
                    }}
                  />
                  <div
                    className="absolute pointer-events-none rounded bg-indigo-500/80 text-white px-1.5 py-[1px] font-mono text-[9px] font-semibold leading-none whitespace-nowrap"
                    style={{
                      left: page.column_boundary * effectiveZoom - 24,
                      top: 4,
                    }}
                  >
                    컬럼 경계
                  </div>
                </>
              )}
              {page.lines.map((line, i) => {
                const [x1, y1, x2, y2] = line.bbox
                const w = (x2 - x1) * effectiveZoom
                const h = (y2 - y1) * effectiveZoom
                const left = x1 * effectiveZoom
                const top = y1 * effectiveZoom
                const isVertical = h >= w * 1.5
                const conf = line.confidence ?? 0
                const color = confidenceColor(conf)
                const isHover = hoveredLine === i

                return (
                  <div key={i}>
                    {/* bbox 경계선 (신뢰도 색) */}
                    <div
                      className="absolute pointer-events-none transition-all duration-150"
                      style={{
                        left, top, width: w, height: h,
                        border: `${isHover ? 2 : 1.2}px solid ${color.border}`,
                        backgroundColor: isHover ? color.bg.replace('0.08', '0.18') : color.bg,
                        boxShadow: isHover ? `0 0 0 3px ${color.bg.replace('0.08', '0.20')}` : undefined,
                      }}
                    />
                    {/* 인식된 텍스트 (bbox 안에 배치) */}
                    <div
                      onMouseEnter={() => setHoveredLine(i)}
                      onMouseLeave={() => setHoveredLine((h) => (h === i ? null : h))}
                      onClick={() => {
                        const item = lineListRef.current?.querySelector(`[data-line-idx="${i}"]`) as HTMLElement | null
                        item?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                      }}
                      className="ocr-bbox-text absolute overflow-hidden text-black cursor-pointer"
                      style={{
                        left, top, width: w, height: h,
                        fontSize: isVertical ? `${Math.max(8, w * 0.7)}px` : `${Math.max(8, h * 0.65)}px`,
                        writingMode: isVertical ? 'vertical-rl' : 'horizontal-tb',
                        textOrientation: isVertical ? 'upright' : 'mixed',
                        lineHeight: 1,
                      }}
                      title={`신뢰도 ${(conf * 100).toFixed(1)}%`}
                    >
                      {line.text}
                    </div>
                    {/* 신뢰도 라벨 — bbox 좌상단 위 (외부) */}
                    {w > 24 && h > 14 && (
                      <div
                        className="absolute pointer-events-none px-1 py-[1px] rounded-sm font-mono text-[9px] font-bold leading-none whitespace-nowrap"
                        style={{
                          left,
                          top: Math.max(0, top - 13),
                          backgroundColor: color.border,
                          color: 'white',
                        }}
                      >
                        {(conf * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </PanelFrame>
        </div>

        {/* 하단: 라인 리스트 */}
        <div className="flex flex-1 min-h-0 flex-col border-t border-border-light dark:border-border-dark bg-surface-light dark:bg-surface-dark">
          <div className="flex flex-shrink-0 items-center justify-between border-b border-border-light/60 dark:border-border-dark/60 px-4 py-2">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-text-primary-light dark:text-text-primary-dark">
                인식된 텍스트
              </h3>
              <span className="rounded-full bg-surface-alt-light dark:bg-surface-alt-dark px-2 py-0.5 text-[10px] font-medium text-text-secondary-light dark:text-text-secondary-dark">
                {page.lines.length} 라인
              </span>
            </div>
            <button
              type="button"
              onClick={copyAll}
              className="flex items-center gap-1.5 rounded-lg border border-border-light dark:border-border-dark bg-surface-light dark:bg-surface-alt-dark/50 px-3 py-1 text-xs font-medium text-text-primary-light dark:text-text-primary-dark hover:border-primary/40 hover:text-primary transition-colors"
            >
              {allCopied ? <Check className="h-3 w-3 text-accent-green" /> : <Copy className="h-3 w-3" />}
              {allCopied ? '복사됨' : '전체 복사'}
            </button>
          </div>
          <div ref={lineListRef} className="flex-1 min-h-0 overflow-auto">
            <ul className="divide-y divide-border-light/40 dark:divide-border-dark/40">
              {page.lines.map((line, i) => {
                const conf = line.confidence ?? 0
                const color = confidenceColor(conf)
                const isHover = hoveredLine === i
                const key = `${pageIdx}:${i}`
                const col = (line.column || '').toLowerCase()
                const colBadge = col === 'left' ? { label: 'L', cls: 'bg-blue-500/15 text-blue-600 dark:text-blue-300' }
                  : col === 'right' ? { label: 'R', cls: 'bg-purple-500/15 text-purple-600 dark:text-purple-300' }
                  : null
                return (
                  <li
                    key={i}
                    data-line-idx={i}
                    onMouseEnter={() => setHoveredLine(i)}
                    onMouseLeave={() => setHoveredLine((h) => (h === i ? null : h))}
                    onClick={() => scrollToLine(i)}
                    className={`group flex items-center gap-3 px-4 py-2 cursor-pointer transition-colors ${
                      isHover ? 'bg-primary/5 dark:bg-primary/10' : 'hover:bg-surface-alt-light/50 dark:hover:bg-surface-alt-dark/30'
                    }`}
                  >
                    <span className="w-7 flex-shrink-0 text-right font-mono text-[11px] text-text-secondary-light dark:text-text-secondary-dark tabular-nums">
                      {i + 1}
                    </span>
                    {colBadge && (
                      <span
                        className={`flex-shrink-0 inline-flex h-5 w-5 items-center justify-center rounded font-mono text-[10px] font-bold ${colBadge.cls}`}
                        title={`${col} 컬럼`}
                      >
                        {colBadge.label}
                      </span>
                    )}
                    <span
                      className="flex flex-shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-mono font-semibold tabular-nums"
                      style={{ backgroundColor: color.bg, color: color.text }}
                    >
                      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color.dot }} />
                      {(conf * 100).toFixed(1)}%
                    </span>
                    <span
                      className="flex-1 select-text text-sm text-text-primary-light dark:text-text-primary-dark break-all"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {line.text}
                    </span>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); copy(line.text, key) }}
                      className={`flex-shrink-0 rounded-md p-1.5 transition-all ${
                        copiedKey === key
                          ? 'bg-accent-green/10 text-accent-green'
                          : 'opacity-0 group-hover:opacity-100 text-text-secondary-light dark:text-text-secondary-dark hover:bg-black/5 dark:hover:bg-white/10'
                      }`}
                      title="복사"
                    >
                      {copiedKey === key ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

function Stat({ dot, label, count }: { dot: string; label: string; count: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-alt-light dark:bg-surface-alt-dark/50 px-2 py-0.5 text-text-secondary-light dark:text-text-secondary-dark">
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: dot }} />
      <span className="font-medium tabular-nums">{count}</span>
      <span className="text-[10px] uppercase tracking-wide opacity-70">{label}</span>
    </span>
  )
}

function PanelFrame({
  label,
  badge,
  children,
  panelRef,
}: {
  label: string
  badge?: string
  children: React.ReactNode
  panelRef: React.RefObject<HTMLDivElement>
}) {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border-light dark:border-border-dark bg-surface-light dark:bg-surface-dark shadow-soft">
      <div className="flex flex-shrink-0 items-center justify-between border-b border-border-light/60 dark:border-border-dark/60 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary-light dark:text-text-secondary-dark">
        <span>{label}</span>
        {badge && (
          <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-300 normal-case">
            {badge}
          </span>
        )}
      </div>
      <div ref={panelRef} className="flex-1 overflow-auto bg-gray-50 dark:bg-gray-900/50">
        <div className="p-3 inline-block">{children}</div>
      </div>
    </div>
  )
}
