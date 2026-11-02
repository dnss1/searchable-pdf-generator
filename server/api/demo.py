"""
Demo samples: the documents of the pre-built "테스트 세션". Each one is already
processed, so the dashboard links straight to its editor page.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from demo.sample_registry import get_sample, list_samples
from demo.seed import job_id_for

router = APIRouter()


@router.get("/demo/samples")
async def get_demo_samples():
    """Pre-processed samples and the job id each one is installed under"""
    return [
        {
            "sample_id": s.sample_id,
            "job_id": job_id_for(s),
            "title": s.title,
            "description": s.description,
            "filename": s.input_path.name,
            "page_count": s.page_count,
            "thumbnail_url": f"/api/demo/samples/{s.sample_id}/input",
        }
        for s in list_samples()
    ]


@router.get("/demo/samples/{sample_id}/input")
async def get_sample_input(sample_id: str):
    """A sample's original file (used as the dashboard thumbnail)"""
    sample = get_sample(sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    return FileResponse(path=str(sample.input_path))
