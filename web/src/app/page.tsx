'use client'

import { useCallback, useEffect, useState } from 'react'
import { Sun, Moon, Loader2, ArrowLeft, AlertCircle, Sparkles, FileSearch, Github } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import UploadZone from '@/components/UploadZone'
import ModelSelector from '@/components/ModelSelector'
import CompareView from '@/components/CompareView'
import SamplePicker from '@/components/SamplePicker'
import {
  listModels,
  listSamples,
  uploadFile,
  processJob,
  getJobStatus,
  getOCRResults,
  RecModel,
  OCRResult,
  SampleMeta,
} from '@/lib/api'

type Stage = 'idle' | 'uploading' | 'processing' | 'ready' | 'error'

export default function Page() {
  const { theme, toggleTheme } = useTheme()

  const [stage, setStage] = useState<Stage>('idle')
  const [error, setError] = useState<string | null>(null)

  const [models, setModels] = useState<RecModel[]>([])
  const [selectedModelId, setSelectedModelId] = useState<string>('stage2c')

  const [file, setFile] = useState<File | null>(null)
  const [sample, setSample] = useState<SampleMeta | null>(null)  // 사전 업로드된 시연 샘플
  const [samples, setSamples] = useState<SampleMeta[]>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [stageMessage, setStageMessage] = useState('')
  const [ocr, setOcr] = useState<OCRResult | null>(null)
  const [pendingAutoRun, setPendingAutoRun] = useState<SampleMeta | null>(null)
  const [autoRunArmed, setAutoRunArmed] = useState(false)

  useEffect(() => {
    const saved = typeof window !== 'undefined' ? localStorage.getItem('kow.modelId') : null
    listModels()
      .then((data) => {
        setModels(data.models)
        const valid = new Set(data.models.map((m) => m.id))
        if (saved && valid.has(saved)) setSelectedModelId(saved)
        else if (data.default && valid.has(data.default)) setSelectedModelId(data.default)
      })
      .catch(() => setError('서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.'))

    listSamples()
      .then((list) => {
        setSamples(list)
        // ?s=<샘플id> — 링크 공유·시연용
        const want = new URLSearchParams(window.location.search).get('s')
        const found = want ? list.find((x) => x.id === want) : null
        if (found) setPendingAutoRun(found)
      })
      .catch(() => {})
  }, [])


  const handleModelChange = useCallback((id: string) => {
    setSelectedModelId(id)
    try { localStorage.setItem('kow.modelId', id) } catch {}
  }, [])

  const handleFile = useCallback((f: File) => {
    setFile(f)
    setSample(null)        // 업로드 새 파일 → 샘플 선택 해제 (배타)
    setError(null)
    setStage('idle')
  }, [])

  const handlePickSample = useCallback((s: SampleMeta) => {
    setSample(s)
    setFile(null)          // 샘플 선택 → 업로드 파일 해제
    setError(null)
    setStage('idle')
    // 추천 모델이 명시되어 있으면 자동 선택
    if (s.recommended_model) {
      setSelectedModelId(s.recommended_model)
      try { localStorage.setItem('kow.modelId', s.recommended_model) } catch {}
    }
  }, [])

  const startOCR = useCallback(async () => {
    setError(null); setOcr(null); setProgress(0)

    if (file) {
      setStageMessage('파일 업로드')
      setStage('uploading')
      try {
        const { job_id } = await uploadFile(file)
        setJobId(job_id)
        setStageMessage('인식 시작')
        await processJob(job_id, selectedModelId)
        setStage('processing')
      } catch (e: any) {
        setError(e?.message || String(e))
        setStage('error')
      }
      return
    }

    if (sample) {
      setStageMessage('인식 시작')
      setStage('processing')
      setJobId(sample.job_id)
      try {
        await processJob(sample.job_id, selectedModelId)
      } catch (e: any) {
        setError(e?.message || String(e))
        setStage('error')
      }
      return
    }
  }, [file, sample, selectedModelId])

  // 딥링크 → 선택 → 자동 실행
  useEffect(() => {
    if (!pendingAutoRun) return
    handlePickSample(pendingAutoRun)
    setPendingAutoRun(null)
    setAutoRunArmed(true)
  }, [pendingAutoRun, handlePickSample])

  useEffect(() => {
    if (!autoRunArmed || !sample) return
    setAutoRunArmed(false)
    void startOCR()
  }, [autoRunArmed, sample, startOCR])

  useEffect(() => {
    if (stage !== 'processing' || !jobId) return
    let cancelled = false
    const tick = async () => {
      try {
        const s = await getJobStatus(jobId)
        if (cancelled) return
        setProgress(s.progress_percent || 0)
        setStageMessage(s.sub_stage || s.message || '텍스트 인식 중')
        if (s.status === 'completed') {
          const data = await getOCRResults(jobId)
          if (cancelled) return
          setOcr(data)
          setStage('ready')
        } else if (s.status === 'failed' || s.status === 'cancelled') {
          setError(s.message || '인식에 실패했습니다.')
          setStage('error')
        }
      } catch (e: any) {
        if (cancelled) return
        console.warn('status poll:', e?.message)
      }
    }
    tick()
    const id = setInterval(tick, 1500)
    return () => { cancelled = true; clearInterval(id) }
  }, [stage, jobId])

  const reset = useCallback(() => {
    setStage('idle'); setFile(null); setSample(null); setJobId(null)
    setProgress(0); setStageMessage(''); setOcr(null); setError(null)
  }, [])

  // 인식 시작 버튼이 카드 아래라 누를 때쯤엔 페이지가 내려가 있다. 화면만 바뀌고
  // 스크롤은 그대로라 결과가 중간부터 보임
  useEffect(() => {
    if (stage === 'ready' || stage === 'idle') {
      window.scrollTo({ top: 0, behavior: 'auto' })
    }
  }, [stage])

  const inBusy = stage === 'uploading' || stage === 'processing'

  return (
    <div className="relative min-h-screen flex flex-col bg-background-light dark:bg-background-dark">
      <div className="pointer-events-none absolute inset-0 overflow-hidden -z-0">
        <div className="absolute -top-40 -right-20 h-[500px] w-[500px] rounded-full bg-primary/[0.08] blur-3xl dark:bg-primary/[0.12]" />
        <div className="absolute -bottom-40 -left-20 h-[400px] w-[400px] rounded-full bg-accent-purple/[0.06] blur-3xl dark:bg-accent-purple/[0.08]" />
      </div>

      {/* ===== 헤더 ===== */}
      <header className="relative z-10 flex flex-shrink-0 items-center justify-between border-b border-border-light/60 dark:border-border-dark/60 bg-surface-light/80 dark:bg-surface-dark/80 backdrop-blur-xl px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/[0.12] text-primary">
            <FileSearch className="h-[18px] w-[18px]" strokeWidth={2} />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold tracking-tight text-text-primary-light dark:text-text-primary-dark">
              Searchable PDF Generator
            </span>
            <span className="text-[10px] uppercase tracking-[0.16em] text-text-secondary-light dark:text-text-secondary-dark">
              Document Intelligence
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {stage === 'ready' && (
            <button
              type="button"
              onClick={reset}
              className="flex items-center gap-1.5 rounded-lg border border-border-light dark:border-border-dark bg-surface-light dark:bg-surface-dark px-3 py-1.5 text-sm font-medium text-text-primary-light dark:text-text-primary-dark hover:border-primary/40 hover:text-primary transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              다른 파일
            </button>
          )}
          <a
            href="https://github.com/dnss1/searchable-pdf-generator"
            target="_blank"
            rel="noopener noreferrer"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-border-light dark:border-border-dark bg-surface-light dark:bg-surface-dark text-text-secondary-light dark:text-text-secondary-dark hover:text-text-primary-light dark:hover:text-text-primary-dark transition-colors"
            aria-label="GitHub 저장소"
          >
            <Github className="h-4 w-4" />
          </a>
          <button
            type="button"
            onClick={toggleTheme}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-border-light dark:border-border-dark bg-surface-light dark:bg-surface-dark text-text-secondary-light dark:text-text-secondary-dark hover:text-text-primary-light dark:hover:text-text-primary-dark transition-colors"
            aria-label="테마 전환"
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </header>

      {/* ===== 본문 ===== */}
      <main className="relative z-10 flex flex-1 min-h-0 flex-col">
        {stage === 'ready' && ocr ? (
          <div className="flex-1 min-h-0 animate-fade-in">
            <CompareView jobId={jobId!} ocr={ocr} />
          </div>
        ) : (
          <div className="flex flex-1 items-start justify-center px-6 py-10">
            <div className="w-full max-w-3xl space-y-8 animate-fade-in">
              {/* 헤드라인 */}
              <div className="space-y-3 text-center">
                <div className="inline-flex items-center gap-1.5 rounded-full border border-border-light/70 dark:border-border-dark/70 bg-surface-light/60 dark:bg-surface-dark/60 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-text-secondary-light dark:text-text-secondary-dark">
                  <Sparkles className="h-3 w-3 text-primary" />
                  <span>다국어 혼재 한국어 문서 OCR</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-text-primary-light dark:text-text-primary-dark leading-tight">
                  이미지 문서를 검색 가능한 PDF로
                </h2>
                <p className="text-base text-text-secondary-light dark:text-text-secondary-dark max-w-xl mx-auto leading-relaxed">
                  OCR로 인식한 텍스트를 원본 위에 <span className="font-medium text-text-primary-light dark:text-text-primary-dark">투명 레이어</span>로 얹습니다.
                  화질은 그대로 두고 검색·복사·추출만 가능해집니다.
                </p>
              </div>

              {/* 카드형 폼 */}
              <div className="rounded-2xl border border-border-light/70 dark:border-border-dark/70 bg-surface-light/70 dark:bg-surface-dark/70 backdrop-blur-sm shadow-soft p-6 space-y-6">
                {/* 업로드 영역 */}
                <UploadZone onFile={handleFile} disabled={inBusy} readOnly />

                {/* 샘플 그리드 */}
                <SamplePicker
                  samples={samples}
                  selectedId={sample?.id ?? null}
                  onPick={handlePickSample}
                  disabled={inBusy}
                />

                {/* 선택된 샘플 표시 */}
                {sample && (
                  <div className="flex items-center justify-between rounded-xl border border-primary/40 bg-primary/[0.06] px-4 py-2.5">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
                        <Sparkles className="h-3.5 w-3.5" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
                          {sample.label}
                        </p>
                        <p className="text-[11px] text-text-secondary-light dark:text-text-secondary-dark">
                          시연 샘플 · 인식 시작을 누르면 즉시 처리됩니다
                        </p>
                      </div>
                    </div>
                    {!inBusy && (
                      <button
                        type="button"
                        onClick={() => setSample(null)}
                        className="text-xs text-text-secondary-light hover:text-accent-red dark:text-text-secondary-dark transition-colors"
                      >
                        해제
                      </button>
                    )}
                  </div>
                )}

                {/* 선택된 업로드 파일 표시 */}
                {file && (
                  <div className="flex items-center justify-between rounded-xl border border-border-light dark:border-border-dark bg-surface-alt-light/50 dark:bg-surface-alt-dark/50 px-4 py-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary text-[10px] font-bold tracking-tight">
                        {(file.name.split('.').pop() || '?').toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
                          {file.name}
                        </p>
                        <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
                          {(file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                    {!inBusy && (
                      <button
                        type="button"
                        onClick={() => setFile(null)}
                        className="text-xs text-text-secondary-light hover:text-accent-red dark:text-text-secondary-dark transition-colors"
                      >
                        제거
                      </button>
                    )}
                  </div>
                )}

                {/* 모델 선택 */}
                {models.length > 0 && (
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary-light dark:text-text-secondary-dark">
                        인식 모델
                      </h3>
                      <span className="text-[11px] text-text-secondary-light dark:text-text-secondary-dark">
                        학위연구 최종 모델 고정
                      </span>
                    </div>
                    <ModelSelector
                      models={models}
                      selectedId={selectedModelId}
                      onChange={handleModelChange}
                      disabled={inBusy}
                    />
                  </div>
                )}

                {/* CTA */}
                <button
                  type="button"
                  disabled={(!file && !sample) || inBusy}
                  onClick={startOCR}
                  className={`
                    relative flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-sm font-semibold transition-all overflow-hidden
                    ${(!file && !sample) || inBusy
                      ? 'cursor-not-allowed bg-surface-alt-light text-text-secondary-light dark:bg-surface-alt-dark dark:text-text-secondary-dark'
                      : 'bg-primary text-white hover:bg-primary-dark shadow-soft hover:shadow-soft-lg'
                    }
                  `}
                >
                  {inBusy ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>{stageMessage || '처리 중'}{progress > 0 ? ` · ${Math.round(progress)}%` : ''}</span>
                    </>
                  ) : (
                    <span>인식 시작</span>
                  )}
                </button>

                {/* 진행 바 */}
                {inBusy && (
                  <div className="-mt-2 space-y-2">
                    <div className="h-1 w-full overflow-hidden rounded-full bg-surface-alt-light dark:bg-surface-alt-dark">
                      <div
                        className="h-full rounded-full bg-primary transition-all duration-300"
                        style={{ width: `${Math.max(2, progress)}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* 에러 */}
                {error && (
                  <div className="flex items-start gap-2 rounded-lg border border-accent-red/30 bg-accent-red/5 px-4 py-3 text-sm text-accent-red">
                    <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    <div className="flex-1">{error}</div>
                    {stage === 'error' && (
                      <button type="button" onClick={reset} className="text-xs underline">
                        다시 시도
                      </button>
                    )}
                  </div>
                )}
              </div>

              <p className="text-center text-[11px] leading-relaxed text-text-secondary-light/70 dark:text-text-secondary-dark/70">
                결과는 모두 사전 계산된 값입니다. 브라우저에서 모델을 돌리지 않습니다.
                <br />
                전정운 · OCR / Document AI
              </p>
            </div>
          </div>
        )}
      </main>

    </div>
  )
}
