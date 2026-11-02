"""
Registry of pre-processed demo samples.

Layout of one sample (see demo_samples/README.md):

    demo_samples/<sample_id>/
        sample.json            title, description, input file name
        input/<file>           the original document
        result/searchable.pdf  searchable PDF produced by the private engine
        result/ocr.json        OCR JSON produced by the private engine
        result/pages/          optional page images (page_0001.png, ...)
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from config import Config

logger = logging.getLogger(__name__)

SAMPLE_META = "sample.json"


@dataclass
class DemoSample:
    sample_id: str
    root: Path
    title: str
    description: str
    input_path: Path
    page_count: int
    extra: Dict = field(default_factory=dict)

    @property
    def result_pdf(self) -> Path:
        return self.root / "result" / "searchable.pdf"

    @property
    def result_json(self) -> Path:
        return self.root / "result" / "ocr.json"

    @property
    def result_pages_dir(self) -> Path:
        return self.root / "result" / "pages"


def _load_sample(sample_dir: Path) -> Optional[DemoSample]:
    meta_path = sample_dir / SAMPLE_META
    if not meta_path.exists():
        return None
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        input_path = sample_dir / "input" / meta["input_file"]
        result_pdf = sample_dir / "result" / "searchable.pdf"
        result_json = sample_dir / "result" / "ocr.json"
        missing = [p.name for p in (input_path, result_pdf, result_json) if not p.exists()]
        if missing:
            logger.warning(f"Demo sample '{sample_dir.name}' skipped, missing: {missing}")
            return None

        page_count = meta.get("page_count")
        if not page_count:
            with open(result_json, 'r', encoding='utf-8') as f:
                page_count = json.load(f).get("page_count", 1)

        return DemoSample(
            sample_id=sample_dir.name,
            root=sample_dir,
            title=meta.get("title") or input_path.name,
            description=meta.get("description", ""),
            input_path=input_path,
            page_count=int(page_count),
            extra=meta,
        )
    except Exception as e:
        logger.warning(f"Demo sample '{sample_dir.name}' could not be loaded: {e}")
        return None


def list_samples() -> List[DemoSample]:
    """All valid samples, sorted by folder name."""
    root = Config.DEMO_SAMPLES_DIR
    if not root.exists():
        return []
    samples = []
    for sample_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        sample = _load_sample(sample_dir)
        if sample:
            samples.append(sample)
    return samples


def get_sample(sample_id: str) -> Optional[DemoSample]:
    return next((s for s in list_samples() if s.sample_id == sample_id), None)
