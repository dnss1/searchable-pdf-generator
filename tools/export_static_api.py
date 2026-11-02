"""
Generate the static API used by the GitHub Pages build of the v2 demo.

Starts the demo server in-process (FastAPI TestClient), which seeds the
"테스트 세션" from demo_samples/, then saves every response the web UI reads
under web/public/demo-api/<request path>. JSON responses are stored as
"<path>.json"; files (PDF, TXT, XML, Excel, ZIP, images) keep their path.
web/src/lib/api.ts reads them back when NEXT_PUBLIC_STATIC_DEMO=1.

    pip install -r server/requirements.txt
    python tools/export_static_api.py
"""
import json
import re
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SERVER = REPO / "server"
OUT = REPO / "web" / "public" / "demo-api"
ALL_FORMATS = ["pdf", "txt", "xml", "json", "excel"]

sys.path.insert(0, str(SERVER))
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402  (server/main.py)


def clean_json(text: str, renames: dict) -> str:
    # one public URL for processed PDFs, no cache-busting timestamps
    text = re.sub(r'"/files/processed/', '"/api/files/processed/', text)
    text = re.sub(r'\?v=\d+', '', text)
    for old, new in renames.items():
        text = text.replace(old, new)
    return text


def save_json(path: str, data, renames=None):
    target = OUT / f"{path.lstrip('/')}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    target.write_text(clean_json(text, renames or {}), encoding="utf-8")


def save_file(path: str, content: bytes):
    target = OUT / path.lstrip('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def get(client, path, **params):
    r = client.get(path, params=params)
    r.raise_for_status()
    return r


def run_session_export(client, session_id, kind, body, stable_id):
    """Start a session export, wait for it, and store it under a fixed export id."""
    r = client.post(f"/api/sessions/{session_id}/export-{kind}", json=body) if body else \
        client.post(f"/api/sessions/{session_id}/export-{kind}")
    r.raise_for_status()
    started = r.json()
    export_id = started["export_id"]
    for _ in range(600):
        status = get(client, f"/api/sessions/export-status/{export_id}").json()
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)
    if status["status"] != "completed":
        raise RuntimeError(f"session export-{kind} failed: {status}")
    download = get(client, f"/api/sessions/export-download/{export_id}").content
    renames = {export_id: stable_id}
    save_json(f"/api/sessions/{session_id}/export-{kind}", started, renames)
    save_json(f"/api/sessions/export-status/{stable_id}", status, renames)
    save_file(f"/api/sessions/export-download/{stable_id}", download)


def main_export():
    shutil.rmtree(OUT, ignore_errors=True)
    with TestClient(main.app) as client:
        # samples (thumbnail URLs get the file extension so static hosting sends an image type)
        samples = get(client, "/api/demo/samples").json()
        for s in samples:
            ext = Path(s["filename"]).suffix.lower()
            image = get(client, s["thumbnail_url"]).content
            s["thumbnail_url"] = f"{s['thumbnail_url']}{ext}"
            save_file(s["thumbnail_url"], image)
        save_json("/api/demo/samples", samples)

        sessions = get(client, "/api/sessions").json()
        save_json("/api/sessions", sessions)
        for session in sessions:
            sid = session["session_id"]
            save_json(f"/api/sessions/{sid}", get(client, f"/api/sessions/{sid}").json())
        save_json("/api/sessions/stats/overview", get(client, "/api/sessions/stats/overview").json())

        save_json("/api/jobs", get(client, "/api/jobs", user_id="user001", limit=100).json())
        save_json("/api/jobs/statistics/summary", get(client, "/api/jobs/statistics/summary", user_id="user001").json())

        for s in samples:
            job = s["job_id"]
            save_json(f"/api/jobs/{job}", get(client, f"/api/jobs/{job}").json())
            save_json(f"/api/status/{job}", get(client, f"/api/status/{job}").json())
            save_json(f"/api/ocr-results/{job}", get(client, f"/api/ocr-results/{job}").json())
            save_json(f"/api/export/{job}/statistics", get(client, f"/api/export/{job}/statistics").json())
            save_file(f"/api/download-json/{job}", get(client, f"/api/download-json/{job}").content)
            save_file(f"/api/files/processed/{job}.pdf", get(client, f"/api/files/processed/{job}.pdf").content)
            for fmt in ("txt", "xml", "excel", "all"):
                save_file(f"/api/export/{job}/{fmt}", get(client, f"/api/export/{job}/{fmt}").content)
            r = client.post(f"/api/export/{job}/multi", json={"formats": ALL_FORMATS, "as_zip": True})
            r.raise_for_status()
            save_file(f"/api/export/{job}/multi.zip", r.content)

        # session-level exports need the documents selected
        for session in sessions:
            sid = session["session_id"]
            job_ids = [d["job_id"] for d in session["documents"]]
            client.patch(f"/api/sessions/{sid}/selection", json={"job_ids": job_ids, "is_selected": True}).raise_for_status()
            run_session_export(client, sid, "multi", {"formats": ALL_FORMATS, "as_zip": True}, f"{sid}-multi")
            run_session_export(client, sid, "merged", None, f"{sid}-merged")

    # nothing from the local machine may end up in the public site
    leaks = [str(p.relative_to(OUT)) for p in OUT.rglob("*.json")
             if re.search(r'[A-Za-z]:\\\\|[A-Za-z]:/|/home/|/Users/', p.read_text(encoding="utf-8"))]
    if leaks:
        raise SystemExit(f"Local paths found in: {leaks}")

    files = [p for p in OUT.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files) / 1e6
    print(f"Wrote {len(files)} files ({size:.1f} MB) to {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main_export()
