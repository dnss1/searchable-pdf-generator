/**
 * 정적 데모용 데이터 레이어.
 * 원래는 FastAPI 백엔드를 호출하던 파일 — fixture 를 읽도록 바꾸고 시그니처는 유지.
 */

export interface RecModel {
  id: string
  label: string
  description?: string
}

export interface OCRLine {
  text: string
  bbox: [number, number, number, number]
  confidence?: number | null
  column?: 'left' | 'right' | string | null
  reading_order?: number | null
  char_confidences?: number[] | null
  direction?: 'horizontal' | 'vertical' | null
}

export interface OCRPage {
  page_number: number
  width: number
  height: number
  lines: OCRLine[]
  is_multi_column?: boolean
  column_boundary?: number | null
}

export interface LayoutPageSummary {
  page_number: number
  is_double_column?: boolean
  column_boundary?: number | null
  layout_type?: string
}

export interface OCRResult {
  job_id: string
  page_count: number
  total_bboxes: number
  pages: OCRPage[]
  layout_summary?: {
    has_double_column?: boolean
    double_column_pages?: number
    dominant_layout?: string
    pages?: LayoutPageSummary[]
  } | null
  /** 정적 데모 전용 메타 */
  source?: string
  confidence_source?: 'model' | 'simulated'
  writing_direction?: 'horizontal' | 'vertical'
}

export interface JobStatus {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress_percent?: number
  current_page?: number
  total_pages?: number
  message?: string
  sub_stage?: string
}

export interface SampleMeta {
  id: string
  job_id: string
  filename: string
  label: string
  description?: string
  recommended_model?: string | null
  created_at?: string
  tags?: string[]
}

interface Fixture extends OCRResult {
  id: string
  title: string
  description?: string
  model?: string
  tags?: string[]
  pdf?: string
  pages: (OCRPage & { image: string })[]
}

const fixtureCache = new Map<string, Fixture>()
const processStartedAt = new Map<string, number>()

const STAGES: { ms: number; label: string }[] = [
  { ms: 420, label: '파일 업로드' },
  { ms: 620, label: '페이지 이미지 변환' },
  { ms: 780, label: '레이아웃 감지' },
  { ms: 900, label: '텍스트 영역 검출' },
  { ms: 1250, label: '문자 인식' },
  { ms: 520, label: '읽기 순서 정렬' },
  { ms: 560, label: '텍스트 레이어 생성' },
]
const TOTAL_MS = STAGES.reduce((a, s) => a + s.ms, 0)

async function loadJSON<T>(path: string): Promise<T> {
  const res = await fetch(path, { cache: 'no-store' })
  if (!res.ok) throw new Error(`${path} 를 불러오지 못했습니다 (${res.status})`)
  return res.json()
}

async function loadFixture(id: string): Promise<Fixture> {
  const cached = fixtureCache.get(id)
  if (cached) return cached
  const fx = await loadJSON<Fixture>(`fixtures/${id}.json`)
  fixtureCache.set(id, fx)
  return fx
}

/* ------------------------------------------------------------------ 목록 */

export async function listModels(): Promise<{ default: string; models: RecModel[] }> {
  return {
    default: 'stage2c',
    models: [
      { id: 'stage2c', label: 'Babel_kr', description: '다국어 혼재 한국어 문서 특화 · stage2c' },
    ],
  }
}

export async function listSamples(): Promise<SampleMeta[]> {
  const idx = await loadJSON<{ samples: any[] }>('fixtures/index.json')
  await Promise.all(idx.samples.map((s) => loadFixture(s.id).catch(() => null)))
  return idx.samples.map((s) => ({
    id: s.id,
    job_id: s.id, // 여기선 fixture id 가 곧 job id
    filename: s.filename ?? `${s.id}.pdf`,
    label: s.title ?? s.label ?? s.id,
    description: s.description,
    recommended_model: s.recommended_model ?? null,
    tags: s.tags ?? [],
  }))
}

/* ------------------------------------------------------------------ 처리 */

export async function uploadFile(_file: File): Promise<{ job_id: string; filename: string }> {
  throw new Error(
    '이 데모는 업로드를 받지 않습니다. 모델과 서버 코드를 공개하지 않기 위해 ' +
      '미리 처리해 둔 결과만 보여줍니다. 아래 시연용 샘플을 선택해 주세요.'
  )
}

export async function processJob(jobId: string, _modelId: string): Promise<unknown> {
  processStartedAt.set(jobId, Date.now())
  void loadFixture(jobId).catch(() => {}) // 연출 도는 동안 미리 받아 둠
  return { job_id: jobId, status: 'processing' }
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const started = processStartedAt.get(jobId)
  if (!started) return { job_id: jobId, status: 'queued', progress_percent: 0 }

  const elapsed = Date.now() - started
  let acc = 0
  let label = STAGES[STAGES.length - 1].label
  for (const s of STAGES) {
    acc += s.ms
    if (elapsed < acc) {
      label = s.label
      break
    }
  }

  if (elapsed >= TOTAL_MS) {
    try {
      await loadFixture(jobId)
    } catch (e: any) {
      return { job_id: jobId, status: 'failed', message: e?.message ?? '결과를 불러오지 못했습니다.' }
    }
    return { job_id: jobId, status: 'completed', progress_percent: 100, sub_stage: '완료' }
  }

  return {
    job_id: jobId,
    status: 'processing',
    progress_percent: Math.min(99, Math.round((elapsed / TOTAL_MS) * 100)),
    sub_stage: label,
  }
}

export async function getOCRResults(jobId: string): Promise<OCRResult> {
  const fx = await loadFixture(jobId)
  const pages = fx.pages.map((p) => ({
    page_number: p.page_number,
    width: p.width,
    height: p.height,
    is_multi_column: p.is_multi_column,
    column_boundary: p.column_boundary ?? null,
    lines: [...p.lines].sort(
      (a: any, b: any) => (a.order ?? a.reading_order ?? 0) - (b.order ?? b.reading_order ?? 0)
    ),
  }))
  return {
    job_id: jobId,
    page_count: pages.length,
    total_bboxes: pages.reduce((a, p) => a + p.lines.length, 0),
    pages,
    layout_summary: {
      has_double_column: pages.some((p) => p.is_multi_column),
      double_column_pages: pages.filter((p) => p.is_multi_column).length,
    },
    source: fx.source,
    confidence_source: fx.confidence_source,
    writing_direction: fx.writing_direction,
  }
}

/* ------------------------------------------------------------------ 파일 */

export function getPageImageUrl(jobId: string, pageNum: number): string {
  const fx = fixtureCache.get(jobId)
  const page = fx?.pages.find((p) => p.page_number === pageNum) ?? fx?.pages[0]
  return page?.image ?? ''
}

export function getRawFileUrl(jobId: string, _filename: string): string {
  return getPageImageUrl(jobId, 1)
}

export function getProcessedPdfUrl(jobId: string): string {
  return fixtureCache.get(jobId)?.pdf ?? ''
}

export const SAMPLE_ADMIN_ENABLED = false

export async function createSample(_input: {
  file: File
  label: string
  description?: string
  recommendedModel?: string | null
}): Promise<SampleMeta> {
  throw new Error('정적 데모에서는 샘플을 추가할 수 없습니다.')
}

export async function updateSample(_id: string, _patch: Partial<SampleMeta>): Promise<SampleMeta> {
  throw new Error('정적 데모에서는 샘플을 수정할 수 없습니다.')
}

export async function deleteSample(_id: string): Promise<void> {
  throw new Error('정적 데모에서는 샘플을 삭제할 수 없습니다.')
}
