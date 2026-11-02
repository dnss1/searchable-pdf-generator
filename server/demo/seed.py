"""
Build the demo state at server startup.

Every start resets the runtime data and creates one read-only session
("테스트 세션") whose documents are the pre-processed samples, already in the
completed state. Job ids are derived from the sample id, so editor URLs stay
the same across restarts.
"""
import json
import logging
import shutil
import uuid
from datetime import datetime

from config import Config
from database import Base, Job, Session, SessionDocument, SessionLocal, User, engine
from demo.sample_registry import DemoSample, list_samples
from models.job import JobStatus
from utils.db_helper import update_job_ocr_results
from utils.job_manager import STATUS_DIR

logger = logging.getLogger(__name__)

DEMO_SESSION_ID = "demo-test-session"
DEMO_SESSION_NAME = "테스트 세션"
_JOB_NAMESPACE = uuid.UUID("6f1c2a52-3c0e-4f0a-9d8e-2b7a1d5c9e40")


def job_id_for(sample: DemoSample) -> str:
    return str(uuid.uuid5(_JOB_NAMESPACE, sample.sample_id))


def _reset_runtime_data():
    for directory in (Config.RAW_DIR, Config.PROCESSED_DIR, Config.DEBUG_DIR, Config.TEMP_DIR,
                      Config.DATA_DIR / "edit_logs"):
        shutil.rmtree(directory, ignore_errors=True)
    Config.ensure_directories()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _install_outputs(sample: DemoSample, job_id: str):
    """Copy the sample's input and stored results into the job's paths."""
    raw_dir = Config.RAW_DIR / job_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / sample.input_path.name
    shutil.copy2(sample.input_path, raw_path)

    pdf_path = Config.PROCESSED_DIR / f"{job_id}.pdf"
    shutil.copy2(sample.result_pdf, pdf_path)
    if sample.result_pages_dir.exists():
        shutil.copytree(sample.result_pages_dir, Config.PROCESSED_DIR / f"{job_id}_pages")

    with open(sample.result_json, 'r', encoding='utf-8') as f:
        ocr_data = json.load(f)
    ocr_data["job_id"] = job_id
    json_path = Config.PROCESSED_DIR / f"{job_id}_ocr.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(ocr_data, f, ensure_ascii=False, indent=2)
    return raw_path, pdf_path, json_path, ocr_data


def seed_demo_state(job_manager):
    """Reset runtime data and create the demo session with completed jobs."""
    _reset_runtime_data()
    samples = list_samples()
    now = datetime.now()

    db = SessionLocal()
    try:
        db.add(User(user_id=Config.DEFAULT_USER_ID, username=Config.DEFAULT_USER_NAME,
                    email=Config.DEFAULT_USER_EMAIL))
        db.add(Session(session_id=DEMO_SESSION_ID, user_id=Config.DEFAULT_USER_ID,
                       session_name=DEMO_SESSION_NAME,
                       description="미리 처리해 둔 샘플 문서로 결과 화면을 체험하는 세션입니다."))
        db.commit()

        for order, sample in enumerate(samples):
            job_id = job_id_for(sample)
            raw_path, pdf_path, json_path, ocr_data = _install_outputs(sample, job_id)
            pages = ocr_data.get("pages", [])
            db.add(Job(
                job_id=job_id,
                user_id=Config.DEFAULT_USER_ID,
                original_filename=sample.input_path.name,
                file_type=sample.input_path.suffix.lstrip('.').lower(),
                file_size_bytes=raw_path.stat().st_size,
                status="completed",
                progress_percent=100.0,
                current_page=len(pages),
                total_pages=len(pages),
                is_double_column=any(p.get("is_multi_column") for p in pages),
                raw_file_path=str(raw_path),
                pdf_file_path=str(pdf_path),
                ocr_json_path=str(json_path),
                created_at=now,
                started_at=now,
                completed_at=now,
            ))
            db.add(SessionDocument(session_id=DEMO_SESSION_ID, job_id=job_id, order=order, is_selected=False))
            db.commit()
            update_job_ocr_results(job_id, ocr_data=ocr_data, pdf_path=str(pdf_path), ocr_json_path=str(json_path))

            # In-memory status (and its status file) for the editor's status polling
            (STATUS_DIR / f"{job_id}.json").unlink(missing_ok=True)
            job_manager.create_job(job_id=job_id, filename=sample.input_path.name, user_id=Config.DEFAULT_USER_ID)
            job_manager.update_job(job_id, status=JobStatus.COMPLETED, progress_percent=100.0,
                                   current_page=len(pages), total_pages=len(pages),
                                   message="미리 처리해 둔 결과입니다.",
                                   pdf_url=f"/files/processed/{job_id}.pdf")
    finally:
        db.close()

    logger.info(f"Demo session '{DEMO_SESSION_NAME}' ready with {len(samples)} document(s)")
    return samples
