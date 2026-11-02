"""
OCR API (demo build, read-only).

The documents of the demo session are installed at startup from pre-processed
samples (demo/seed.py). The endpoints the editor reads from keep the same paths
and response shapes as the full system. Uploading and running OCR are not part
of this build: the OCR engine, the searchable-PDF text layer generator and the
layout/reading-order logic are not included.
"""
import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import Config
from models.job import JobResponse
from models.ocr import PDFExportRequest
from utils.job_manager import JobManager

logger = logging.getLogger(__name__)

router = APIRouter()

job_manager = JobManager()


@router.get("/page-image/{job_id}/{page_number}")
async def get_page_image(job_id: str, page_number: int):
    """Get a specific page image for rendering"""
    image_path = Config.PROCESSED_DIR / f"{job_id}_pages" / f"page_{page_number:04d}.png"
    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Page {page_number} image not found")
    return FileResponse(path=str(image_path), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"})


@router.post("/export/{job_id}")
async def export_with_smart_tools(job_id: str, payload: PDFExportRequest):
    """
    Return the final PDF.

    The full system re-renders the edited text layer and Smart Tool drawings
    into a new PDF. That renderer is not included and the demo stores nothing,
    so the pre-processed searchable PDF is returned as is.
    """
    source_pdf = Config.PROCESSED_DIR / f"{job_id}.pdf"
    if not source_pdf.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    timestamp = int(time.time() * 1000)
    return {
        "message": "Export completed",
        "pdf_url": f"/api/files/processed/{job_id}.pdf?v={timestamp}",
        "json_url": f"/api/download-json/{job_id}?v={timestamp}",
        "demo_notice": "데모 버전에서는 편집 내용이 저장되거나 PDF에 반영되지 않습니다. 처리 결과 PDF를 그대로 내려받습니다.",
    }


@router.get("/status/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """Get job status from file or database (non-blocking)"""
    from database import SessionLocal, Job as DBJob

    file_status = JobManager.read_status_from_file(job_id)
    if file_status and file_status.get("status") == "processing":
        raw_file_url = None
        if file_status.get("filename"):
            raw_file_url = f"/files/raw/{job_id}/{file_status['filename']}"
        return JobResponse(
            job_id=file_status["job_id"],
            filename=file_status.get("filename"),
            status=file_status.get("status", "unknown"),
            progress_percent=file_status.get("progress_percent", 0),
            current_page=file_status.get("current_page", 0),
            total_pages=file_status.get("total_pages", 0),
            message=file_status.get("message"),
            sub_stage=file_status.get("sub_stage"),
            pdf_url=file_status.get("pdf_url"),
            raw_file_url=raw_file_url,
        )

    memory_job = job_manager.get_job(job_id)
    if memory_job:
        raw_file_url = f"/files/raw/{job_id}/{memory_job.filename}" if memory_job.filename else None
        status_str = memory_job.status.value if hasattr(memory_job.status, 'value') else memory_job.status
        return JobResponse(
            job_id=memory_job.job_id,
            filename=memory_job.filename,
            status=status_str,
            progress_percent=memory_job.progress_percent,
            current_page=memory_job.current_page,
            total_pages=memory_job.total_pages,
            message=memory_job.message,
            sub_stage=memory_job.sub_stage,
            pdf_url=memory_job.pdf_url,
            raw_file_url=raw_file_url,
        )

    db = SessionLocal()
    try:
        db_job = db.query(DBJob).filter_by(job_id=job_id).first()
        if not db_job:
            raise HTTPException(status_code=404, detail="Job not found")

        raw_file_url = f"/files/raw/{job_id}/{db_job.original_filename}" if db_job.original_filename else None
        pdf_url = None
        if db_job.pdf_file_path:
            pdf_url = f"/files/processed/{Path(db_job.pdf_file_path).name}?v={int(time.time() * 1000)}"

        return JobResponse(
            job_id=db_job.job_id,
            filename=db_job.original_filename,
            status=db_job.status,
            progress_percent=db_job.progress_percent,
            current_page=db_job.current_page,
            total_pages=db_job.total_pages,
            message=db_job.error_message,
            sub_stage=None,
            pdf_url=pdf_url,
            raw_file_url=raw_file_url,
            created_at=db_job.created_at.isoformat() if db_job.created_at else None,
            completed_at=db_job.completed_at.isoformat() if db_job.completed_at else None,
            processing_time_seconds=db_job.processing_time_seconds,
            total_text_blocks=db_job.total_text_blocks,
            average_confidence=db_job.average_confidence,
            is_double_column=db_job.is_double_column,
        )
    finally:
        db.close()


@router.get("/ocr-results/{job_id}")
async def get_ocr_results(job_id: str):
    """Get OCR results for a job"""
    ocr_json_path = Config.PROCESSED_DIR / f"{job_id}_ocr.json"
    if not ocr_json_path.exists():
        raise HTTPException(status_code=404, detail="OCR results not found")
    with open(ocr_json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@router.get("/download-json/{job_id}")
async def download_json(job_id: str):
    """Download OCR results as JSON file"""
    ocr_json_path = Config.PROCESSED_DIR / f"{job_id}_ocr.json"
    if not ocr_json_path.exists():
        raise HTTPException(status_code=404, detail="OCR results not found")
    return FileResponse(path=str(ocr_json_path), filename=f"{job_id}_ocr.json", media_type="application/json")


@router.post("/save-edits/{job_id}")
async def save_ocr_edits(job_id: str, payload: dict):
    """
    Accept the editor's autosave without storing anything.

    The full system logs edits for fine-tuning and rewrites the OCR JSON. The
    demo is read-only, so edits live only in the visitor's browser.
    """
    from datetime import datetime

    if not (Config.PROCESSED_DIR / f"{job_id}_ocr.json").exists():
        raise HTTPException(status_code=404, detail="OCR results not found")
    edits = payload.get('edits', [])
    return {
        "status": "success",
        "message": f"데모 버전: 수정 {len(edits)}건은 이 브라우저에서만 유지되고 저장되지 않습니다.",
        "saved_at": datetime.now().isoformat(),
    }
