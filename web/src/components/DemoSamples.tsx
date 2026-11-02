'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { FileText, FlaskConical, History, Play } from 'lucide-react'
import { apiFetch, V1_URL } from '@/lib/api'

interface DemoSample {
  sample_id: string
  job_id: string
  title: string
  description: string
  filename: string
  page_count: number
  thumbnail_url: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5015'
const IMAGE_EXT = /\.(png|jpe?g)$/i

/**
 * Demo build: the documents of the read-only "테스트 세션". They are already
 * processed, so "체험하기" opens the result in the editor directly.
 */
export default function DemoSamples() {
  const router = useRouter()
  const [samples, setSamples] = useState<DemoSample[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiFetch(`${API_URL}/api/demo/samples`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then(setSamples)
      .catch(() => setError(true))
  }, [])

  return (
    <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg p-6">
      <div className="flex items-start gap-3">
        <FlaskConical className="w-6 h-6 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">데모 버전 (체험 전용)</h2>
            <a
              href={V1_URL}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-gray-800"
            >
              <History className="w-4 h-4" />
              이전 버전(v1) 보기
            </a>
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300 mt-1">
            OCR 처리가 끝난 샘플 문서로 결과 화면을 체험할 수 있습니다. <b>체험하기</b>를 누르면 텍스트 레이어와 정확도 시각화가
            켜진 편집기가 열립니다. 상단의 <b>데이터</b>로 JSON·XML을, <b>내보내기</b>로 PDF·TXT·XML·Excel을 받아 볼 수 있습니다.
            업로드와 OCR 실행은 지원하지 않습니다.
          </p>

          {error && (
            <p className="text-sm text-red-600 dark:text-red-400 mt-3">샘플 목록을 불러오지 못했습니다. 백엔드가 실행 중인지 확인하세요.</p>
          )}
          {samples && samples.length === 0 && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-3">
              등록된 샘플이 없습니다. <code>demo_samples/</code>에 샘플을 추가하세요(README 참고).
            </p>
          )}
          {samples && samples.length > 0 && (
            <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
              {samples.map((s) => (
                <li
                  key={s.sample_id}
                  className="flex gap-3 p-3 rounded-lg bg-white dark:bg-gray-800 border border-amber-200 dark:border-amber-800"
                >
                  <div className="w-16 h-20 shrink-0 rounded border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 overflow-hidden flex items-center justify-center">
                    {IMAGE_EXT.test(s.filename) ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={`${API_URL}${s.thumbnail_url}`} alt="" className="w-full h-full object-cover object-top" />
                    ) : (
                      <FileText className="w-6 h-6 text-gray-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0 flex flex-col justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium text-gray-900 dark:text-white truncate" title={s.title}>{s.title}</p>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {s.page_count}쪽{s.description ? ` · ${s.description}` : ''}
                      </p>
                    </div>
                    <button
                      onClick={() => router.push(`/editor/${s.job_id}`)}
                      className="self-start flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-amber-500 hover:bg-amber-600 text-white font-medium"
                    >
                      <Play className="w-4 h-4" />
                      체험하기
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
