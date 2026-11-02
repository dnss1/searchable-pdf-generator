# demo_samples

데모에서 보여 줄, 미리 처리해 둔 결과를 넣는 폴더입니다. 샘플 하나는 폴더 하나입니다.

```
demo_samples/<sample_id>/
├── sample.json            # 제목, 설명, 입력 파일 이름, SHA-256
├── input/<원본 파일>       # 원본 문서 (대시보드 썸네일로도 쓰임)
└── result/
    ├── searchable.pdf     # 전체 시스템이 만든 검색 가능한 PDF
    ├── ocr.json           # 전체 시스템이 만든 OCR 결과
    └── pages/             # (선택) 페이지 이미지 page_0001.png ...
```

`sample.json` 예시:

```json
{
  "title": "KCI 논문 2단 레이아웃",
  "description": "2단 본문과 표",
  "input_file": "paper.pdf",
  "sha256": "4ab526bb…",
  "page_count": 25
}
```

- 서버가 시작할 때 모든 샘플을 "테스트 세션"에 처리 완료 상태로 넣습니다. 새 샘플은 서버를 다시 시작하면 반영됩니다.
- `page_count`가 없으면 `ocr.json`에서 읽습니다. `sha256`은 기록용입니다.

직접 만들기보다 `tools/make_demo_sample.py`로 전체 시스템의 처리 결과를 옮기는 것을 권장합니다(루트 README 참고).
공개 저장소에 올리는 문서는 공개해도 되는 자료인지 먼저 확인하세요.
