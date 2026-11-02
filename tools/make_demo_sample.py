"""
Package a job processed by the full (private) OCR system as a demo sample.

Only output files are copied: the uploaded input, the searchable PDF, the OCR
JSON and the page images. No engine code or model is involved.

Examples
--------
List completed jobs in the private system's data folder:

    python tools/make_demo_sample.py --source-data D:/path/to/ocr_gen/data --list

Create demo_samples/<id>/ from one job:

    python tools/make_demo_sample.py --source-data D:/path/to/ocr_gen/data \
        --job 1b11b782-95f6-4899-be7c-30d324325647 --id kci-paper \
        --title "KCI 논문 2단 레이아웃" --description "2단 본문과 표"
"""
import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Korean file names must not crash the Windows console (cp949)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def list_jobs(data_dir: Path):
    db_path = data_dir / "ocr_gen.db"
    processed = data_dir / "processed"
    rows = []
    if db_path.exists():
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT job_id, original_filename, status, total_pages, created_at FROM jobs ORDER BY created_at"
            ).fetchall()
        finally:
            con.close()
    print(f"{'job_id':36}  {'pages':>5}  {'ready':5}  created              filename")
    for job_id, filename, status, pages, created in rows:
        ready = (processed / f"{job_id}_ocr.json").exists() and (processed / f"{job_id}.pdf").exists()
        if status != "completed":
            continue
        print(f"{job_id:36}  {pages or 0:>5}  {'yes' if ready else 'no':5}  {str(created)[:19]:19}  {filename}")


def original_filename(data_dir: Path, job_id: str):
    """Uploaded files are stored under a random name; the real name is in the DB."""
    db_path = data_dir / "ocr_gen.db"
    if not db_path.exists():
        return None
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT original_filename FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    finally:
        con.close()
    # folder uploads store "folder/file.jpg"; keep only the file name
    return Path(row[0].replace("\\", "/")).name if row and row[0] else None


def shrink_pdf(src: Path, dst: Path, scale: float, quality: int):
    """Re-encode the page images of a searchable PDF as smaller JPEGs.

    Only the background images change; the invisible text layer (text,
    positions, fonts) is left untouched, so search and copy behave the same.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(src)
    done = set()
    for page in doc:
        for img in page.get_images(full=True):
            xref, smask = img[0], img[1]
            if xref in done or smask:
                continue
            done.add(xref)
            pix = fitz.Pixmap(doc, xref)
            if pix.alpha:
                pix = fitz.Pixmap(pix, 0)
            if pix.n > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            if scale < 1:
                pix = fitz.Pixmap(pix, max(1, int(pix.width * scale)), max(1, int(pix.height * scale)))
            page.replace_image(xref, stream=pix.tobytes("jpeg", jpg_quality=quality))
    doc.save(dst, garbage=4, deflate=True)
    doc.close()


def make_sample(data_dir: Path, job_id: str, sample_id: str, title: str, description: str,
                out_root: Path, use_final: bool, force: bool, with_pages: bool,
                shrink: str, scale: float, quality: int):
    raw_files = sorted(p for p in (data_dir / "raw" / job_id).glob("*") if p.is_file())
    processed = data_dir / "processed"
    pdf = processed / (f"{job_id}_final.pdf" if use_final else f"{job_id}.pdf")
    ocr_json = processed / f"{job_id}_ocr.json"
    pages = processed / f"{job_id}_pages"

    missing = []
    if not raw_files:
        missing.append(f"raw/{job_id}/<input>")
    for p in (pdf, ocr_json):
        if not p.exists():
            missing.append(str(p.relative_to(data_dir)))
    if missing:
        sys.exit(f"Missing files for job {job_id}: {missing}")

    target = out_root / sample_id
    if target.exists():
        if not force:
            sys.exit(f"{target} already exists (use --force to replace)")
        shutil.rmtree(target)

    input_file = raw_files[0]
    input_name = original_filename(data_dir, job_id) or input_file.name
    (target / "input").mkdir(parents=True)
    (target / "result").mkdir()
    shutil.copy2(input_file, target / "input" / input_name)

    result_pdf = target / "result" / "searchable.pdf"
    pdf_mb = pdf.stat().st_size / 1e6
    if shrink == "always" or (shrink == "auto" and pdf_mb > 25):
        shrink_pdf(pdf, result_pdf, scale, quality)
        print(f"  searchable.pdf: {pdf_mb:.1f} MB -> {result_pdf.stat().st_size / 1e6:.1f} MB "
              f"(page images scaled x{scale}, JPEG q{quality}; text layer unchanged)")
    else:
        shutil.copy2(pdf, result_pdf)

    with open(ocr_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["job_id"] = sample_id
    with open(target / "result" / "ocr.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if with_pages and pages.exists():
        shutil.copytree(pages, target / "result" / "pages")

    meta = {
        "title": title or Path(input_name).stem,
        "description": description,
        "input_file": input_name,
        "sha256": sha256_of(input_file),
        "page_count": data.get("page_count", 1),
        "packaged_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(target / "sample.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    size_mb = sum(p.stat().st_size for p in target.rglob("*") if p.is_file()) / 1e6
    print(f"Created {target} ({meta['page_count']} pages, {size_mb:.1f} MB)")
    if size_mb > 50:
        print("  Note: GitHub rejects files over 100 MB and warns above 50 MB.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-data", required=True, type=Path, help="data/ folder of the full OCR system")
    parser.add_argument("--list", action="store_true", help="list completed jobs and exit")
    parser.add_argument("--job", help="job_id to package")
    parser.add_argument("--id", dest="sample_id", help="sample folder name (letters, digits, '-')")
    parser.add_argument("--title", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "demo_samples", help="samples root")
    parser.add_argument("--use-final", action="store_true", help="use <job>_final.pdf (after editor export)")
    parser.add_argument("--force", action="store_true", help="replace an existing sample folder")
    parser.add_argument("--with-pages", action="store_true",
                        help="also copy rendered page PNGs (large; the web UI does not need them)")
    parser.add_argument("--shrink-pdf", choices=["auto", "always", "never"], default="auto",
                        help="re-encode page images of the searchable PDF (auto: only if > 25 MB)")
    parser.add_argument("--scale", type=float, default=0.5, help="image scale when shrinking (default 0.5)")
    parser.add_argument("--quality", type=int, default=80, help="JPEG quality when shrinking (default 80)")
    args = parser.parse_args()

    if args.list:
        list_jobs(args.source_data)
        return
    if not args.job or not args.sample_id:
        parser.error("--job and --id are required (or use --list)")
    make_sample(args.source_data, args.job, args.sample_id, args.title, args.description,
                args.out, args.use_final, args.force, args.with_pages,
                args.shrink_pdf, args.scale, args.quality)


if __name__ == "__main__":
    main()
