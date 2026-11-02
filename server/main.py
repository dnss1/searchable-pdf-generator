"""
FastAPI demo server for Searchable PDF Generator v2.

The OCR engine is not included. At startup the runtime data is reset and a
read-only "테스트 세션" is created from the pre-processed samples in
demo_samples/ (see demo/seed.py). Requests that would upload, create, change
or delete anything are rejected.
"""
import logging
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import Config
from api import ocr, storage, drive, jobs, sessions, export, demo
from demo.seed import seed_demo_state

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Searchable PDF Generator v2 Demo API",
    description="Demo build: read-only, pre-processed OCR results (no OCR engine included)",
    version="2.0.0-demo"
)

# Write requests the read-only demo still accepts. None of them change stored data:
# autosave is acknowledged without saving, exports only build download files,
# and the selection flag only drives the sidebar checkboxes.
WRITE_ALLOWED = [
    ("POST", re.compile(r"^/api/save-edits/[^/]+$")),
    ("POST", re.compile(r"^/api/export/[^/]+$")),
    ("POST", re.compile(r"^/api/export/[^/]+/multi$")),
    ("POST", re.compile(r"^/api/sessions/[^/]+/export-(merged|multi)$")),
    ("PATCH", re.compile(r"^/api/sessions/[^/]+/selection$")),
]
READ_ONLY_DETAIL = "데모 버전은 체험 전용입니다. 파일 업로드, 세션 생성·수정·삭제, OCR 실행은 지원하지 않습니다."


@app.middleware("http")
async def read_only_guard(request: Request, call_next):
    # Registered before CORSMiddleware so CORS stays the outer layer and the
    # 403 response still carries CORS headers for the browser.
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and not any(
        request.method == method and pattern.match(request.url.path) for method, pattern in WRITE_ALLOWED
    ):
        return JSONResponse(status_code=403, content={"detail": READ_ONLY_DETAIL})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr.router, prefix="/api", tags=["OCR"])
app.include_router(storage.router, prefix="/api", tags=["Storage"])
app.include_router(drive.router, tags=["Drive"])
app.include_router(jobs.router, prefix="/api", tags=["Jobs"])
app.include_router(sessions.router, prefix="/api", tags=["Sessions"])
app.include_router(export.router, tags=["Export"])
app.include_router(demo.router, prefix="/api", tags=["Demo"])

app.mount("/files/processed", StaticFiles(directory=str(Config.PROCESSED_DIR)), name="processed")


@app.on_event("startup")
async def startup_event():
    samples = seed_demo_state(ocr.job_manager)
    logger.info("=" * 60)
    logger.info(f"Searchable PDF Generator v2 demo API: http://{Config.BACKEND_HOST}:{Config.BACKEND_PORT}")
    logger.info(f"Demo session with {len(samples)} sample(s) from {Config.DEMO_SAMPLES_DIR}")
    for s in samples:
        logger.info(f"  - {s.sample_id}: {s.input_path.name} ({s.page_count} pages)")
    logger.info("=" * 60)


@app.get("/")
async def root():
    return {"name": "Searchable PDF Generator v2 Demo API", "version": "2.0.0-demo", "status": "running", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "demo (read-only)", "samples": len(demo.list_samples())}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=Config.BACKEND_HOST, port=Config.BACKEND_PORT, reload=False, log_level="info")
