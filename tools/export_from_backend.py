"""
운영 백엔드에서 결과만 받아 fixture 로 굽는다. 모델·서버 코드는 안 건드림.

원본 파일은 없고 백엔드에만 결과가 남은 문서용 보조 도구다.
**논문과 같은 결과가 필요하면 run_paper_pipeline.py 를 쓸 것** — 서비스 설정은
속도 위주라 긴 라인이 뭉개진다.

    python tools/export_from_backend.py --list
    python tools/export_from_backend.py --job <job_id> \
        --id my-doc --title "표시할 이름" --source "출처와 이용 근거" --vertical

가져오는 것: /api/ocr-results 의 좌표·텍스트·신뢰도, /api/page-image 의 이미지.

⚠️ 공개 저장소다. --source 는 필수. 제3자 저작물·고객사 문서·재배포 금지
   데이터(AI Hub, 국립국어원)는 올리지 말 것.
"""
import argparse
import io
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web" / "public"
DEFAULT_API = "http://127.0.0.1:5015/api"


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get_bytes(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read(), r.headers.get("Content-Type", "")


def cmd_list(api):
    samples = get_json(f"{api}/samples").get("samples", [])
    if not samples:
        print("등록된 샘플이 없습니다.")
        return
    print(f"{'sample_id':38} {'job_id':38} 파일명")
    print("-" * 100)
    for s in samples:
        print(f"{s['id']:38} {s['job_id']:38} {s['filename']}")
        if s.get("label"):
            print(f"{'':77}{s['label']}")
    print("\n권리 확인 후 --job 또는 --sample 로 내보내세요.")


def normalize_image(raw: bytes, max_side: int):
    """웹에 올릴 수 있는 형태로.

    서버가 Content-Type 을 image/jpeg 라고 하면서 WebP 를 보낼 때가 있어서
    헤더 말고 실제 바이트로 포맷을 본다. JPEG/PNG 아니면 JPEG 로 변환.
    긴 변이 max_side 넘으면 축소 — 좌표도 같이 줄여야 하니 최종 크기를 같이 반환.
    """
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow 가 없어 이미지 변환을 건너뜁니다 (pip install pillow)", file=sys.stderr)
        return raw, ".png", 1.0

    from PIL import ImageOps

    im = Image.open(io.BytesIO(raw))
    fmt = (im.format or "").upper()
    # 휴대폰 사진 EXIF 회전. 백엔드가 펴고 나서 좌표를 잡으니 여기서도 펴야 안 어긋남
    rotated = ImageOps.exif_transpose(im)
    changed = rotated.size != im.size
    im = rotated

    w, h = im.size
    if max_side and max(w, h) > max_side:
        k = max_side / max(w, h)
        im = im.resize((round(w * k), round(h * k)), Image.LANCZOS)

    if not changed and im.size == (w, h) and fmt in ("JPEG", "PNG"):
        return raw, ".jpg" if fmt == "JPEG" else ".png", im.size

    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=86, optimize=True)
    return buf.getvalue(), ".jpg", im.size


def to_rect(bbox):
    if not bbox:
        return None
    if isinstance(bbox[0], (int, float)) and len(bbox) == 4:
        x0, y0, x1, y1 = bbox
    else:
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    return [round(min(x0, x1)), round(min(y0, y1)), round(max(x0, x1)), round(max(y0, y1))]


def export(args):
    api = args.api.rstrip("/")
    job = args.job

    if args.sample:
        found = next((s for s in get_json(f"{api}/samples").get("samples", [])
                      if s["id"] == args.sample), None)
        if not found:
            sys.exit(f"샘플을 찾을 수 없습니다: {args.sample}")
        job = found["job_id"]
        args.title = args.title or found.get("label") or found["filename"]
        args.description = args.description or found.get("description")
        args.model = args.model or found.get("recommended_model")

    if not job:
        sys.exit("--job 또는 --sample 이 필요합니다.")

    result = get_json(f"{api}/ocr-results/{job}")
    out_dir = ROOT / "assets" / args.id
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = []
    for sp in result.get("pages", []):
        n = sp.get("page_number", len(pages) + 1)
        raw, _ctype = get_bytes(f"{api}/page-image/{job}/{n}")
        raw, ext, (img_w, img_h) = normalize_image(raw, args.max_side)
        # 좌표는 백엔드 페이지 기준. 최종 이미지 크기에 맞춰 x/y 따로 스케일
        sx = img_w / (sp.get("width") or img_w)
        sy = img_h / (sp.get("height") or img_h)
        if abs(sx / sy - 1) > 0.05:
            print(f"  ⚠️ {n}쪽 가로·세로 비율이 어긋납니다 "
                  f"(백엔드 {sp.get('width')}x{sp.get('height')} → 이미지 {img_w}x{img_h})",
                  file=sys.stderr)
        img_name = f"p{n:03d}{ext}"
        (out_dir / img_name).write_bytes(raw)

        lines = []
        for ln in sp.get("lines", []):
            rect = to_rect(ln.get("bbox"))
            text = (ln.get("text") or "").strip()
            if not rect or not text:
                continue
            rect = [round(rect[0] * sx), round(rect[1] * sy),
                    round(rect[2] * sx), round(rect[3] * sy)]
            item = {
                "text": text,
                "bbox": rect,
                "confidence": round(float(ln.get("confidence") or 0), 3),
                "column": ln.get("column"),
                "layout_type": ln.get("layout_type") or "text",
            }
            if ln.get("reading_order") is not None:
                item["order"] = ln["reading_order"]
            cc = ln.get("char_confidences") or ln.get("char_conf")
            if cc and len(cc) == len(text):
                item["char_confidences"] = [round(float(c), 3) for c in cc]
            if args.vertical:
                item["direction"] = "vertical"
            lines.append(item)

        if any("order" not in l for l in lines):
            if args.vertical:                       # 세로쓰기는 오른쪽 단부터
                lines.sort(key=lambda l: (-l["bbox"][2], l["bbox"][1]))
            else:
                col = {l["column"] for l in lines if l["column"] is not None}
                lines.sort(key=lambda l: (str(l["column"]) if col else "", l["bbox"][1], l["bbox"][0]))
            for i, l in enumerate(lines):
                l["order"] = i
        else:
            lines.sort(key=lambda l: l["order"])

        pages.append({
            "page_number": n,
            "image": f"assets/{args.id}/{img_name}",
            "width": img_w,
            "height": img_h,
            "is_multi_column": bool(sp.get("is_multi_column")),
            "column_boundary": sp.get("column_boundary"),
            "lines": lines,
        })

    fixture = {
        "id": args.id,
        "title": args.title,
        "description": args.description or "",
        "source": args.source,
        "confidence_source": "model",
        "model": args.model or "stage2c",
        "tags": args.tags or [],
        "pdf": f"assets/{args.id}/searchable.pdf",
        "pages": pages,
    }
    if args.vertical:
        fixture["writing_direction"] = "vertical"

    (ROOT / "fixtures" / f"{args.id}.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1), encoding="utf-8")

    idx_path = ROOT / "fixtures" / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"samples": []}
    idx["samples"] = [s for s in idx["samples"] if s["id"] != args.id] + [{
        "id": args.id, "title": args.title,
        "description": args.description or "",
        "tags": args.tags or [],
        "recommended_model": fixture["model"],
        "filename": args.filename or f"{args.id}.pdf",
        "fixture": f"fixtures/{args.id}.json",
    }]
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")

    total = sum(len(p["lines"]) for p in pages)
    print(f"fixtures/{args.id}.json — {len(pages)}쪽 / {total}라인")
    print(f"이미지 → assets/{args.id}/")
    print(f"다음: python tools/make_searchable_pdf.py --fixture fixtures/{args.id}.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default=DEFAULT_API, help=f"백엔드 API 주소 (기본 {DEFAULT_API})")
    ap.add_argument("--list", action="store_true", help="등록된 샘플 목록만 보기")
    ap.add_argument("--job", help="job_id 로 직접 내보내기")
    ap.add_argument("--sample", help="sample_id 로 내보내기")
    ap.add_argument("--id", help="fixture id (영문 소문자·하이픈)")
    ap.add_argument("--title", help="목록에 표시할 이름")
    ap.add_argument("--description")
    ap.add_argument("--filename", help="화면에 표시할 원본 파일명")
    ap.add_argument("--source", help="문서 출처와 이용 근거 — 공개 저장소이므로 필수")
    ap.add_argument("--model", help="인식 모델 id (stage2c / paddle_ch)")
    ap.add_argument("--tags", nargs="*", help="샘플 카드에 표시할 태그")
    ap.add_argument("--vertical", action="store_true", help="세로쓰기 문서")
    ap.add_argument("--max-side", type=int, default=1600,
                    help="페이지 이미지 긴 변 상한 px (0이면 원본 유지, 기본 1600)")
    args = ap.parse_args()

    if args.list:
        cmd_list(args.api.rstrip("/"))
        return
    if not args.id or not args.source:
        ap.error("--id 와 --source 가 필요합니다. (--list 로 먼저 확인하세요)")
    if not args.title and not args.sample:
        ap.error("--title 이 필요합니다. (--sample 을 쓰면 백엔드 라벨을 가져옵니다)")
    export(args)


if __name__ == "__main__":
    main()
