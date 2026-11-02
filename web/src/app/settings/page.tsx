'use client'

import Sidebar from '@/components/Sidebar'

export default function SettingsPage() {
  return (
    <div className="relative flex min-h-screen w-full bg-background-light dark:bg-background-dark">
      <Sidebar />

      <main className="flex-1 p-6 lg:p-10">
        <div className="w-full max-w-4xl mx-auto">
          <div className="flex flex-col gap-2 mb-8">
            <h1 className="text-text-primary-light dark:text-text-primary-dark text-3xl font-bold leading-tight tracking-tight">
              설정
            </h1>
            <p className="text-text-secondary-light dark:text-text-secondary-dark text-base font-normal leading-normal">
              OCR 처리 및 성능 설정
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700">
            <p className="text-gray-900 dark:text-white font-medium">데모 버전에서는 설정 화면을 제공하지 않습니다.</p>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
              이 버전은 OCR 엔진 없이 미리 처리해 둔 결과를 보여 줍니다. 인식 모델, 검출·렌더링 파라미터, 전처리 옵션 같은
              처리 설정은 전체 시스템에서만 바꿀 수 있습니다.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
