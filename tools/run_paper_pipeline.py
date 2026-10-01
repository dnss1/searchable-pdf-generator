"""
논문 평가와 같은 설정으로 추론해서 fixture 생성.
설정은 research/scripts/evaluation/evaluate_full.py 기준.

    # paddleocr 2.10.0 환경
    python tools/run_paper_pipeline.py \
        --image page.png --rec-dir /path/to/stage2c \
        --id a1-digital --title "A1 · 디지털 고딕" \
        --source "자체 구축 평가셋 수록 페이지" --tags 디지털 고딕
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web" / "public"

PAPER_SETTINGS = dict(
    use_angle_cls=False,
    det_limit_side_len=2000,
    det_db_thresh=0.3,
    det_db_box_thresh=0.3,
    det_db_unclip_ratio=1.8,
    rec_image_shape="3, 48, 1280",
)


def to_rect(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return [min(xs), min(ys), max(xs), max(ys)]


def infer_columns(lines, page_width, gap_ratio=0.06):
    mid = page_width / 2
    band = page_width * gap_ratio
    crossing = sum(1 for l in lines if l["bbox"][0] < mid - band and l["bbox"][2] > mid + band)
    if crossing > len(lines) * 0.15:
        return [0] * len(lines), False, None
    return [0 if l["bbox"][0] < mid else 1 for l in lines], True, round(mid)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True, nargs="+", help="페이지 이미지 (쪽 순서대로)")
    ap.add_argument("--rec-dir", required=True, help="인식 모델 디렉토리 (stage2c 등)")
    ap.add_argument("--dict", help="문자 사전 (기본: <rec-dir>/ppocrv5_dict.txt)")
    ap.add_argument("--id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", default="")
    ap.add_argument("--source", required=True, help="문서 출처와 이용 근거")
    ap.add_argument("--filename", help="화면에 표시할 원본 파일명")
    ap.add_argument("--model", default="stage2c")
    ap.add_argument("--tags", nargs="*", default=[])
    ap.add_argument("--vertical", action="store_true")
    ap.add_argument("--max-side", type=int, default=1600,
                    help="저장할 페이지 이미지 긴 변 상한 px (0이면 원본)")
    args = ap.parse_args()

    try:
        from paddleocr import PaddleOCR
        from PIL import Image, ImageOps
    except ImportError as e:
        sys.exit(f"의존성이 없습니다: {e}\n논문 평가에 쓴 환경(paddleocr 2.10.0)에서 실행하세요.")

    rec_dir = Path(args.rec_dir)
    dict_path = Path(args.dict) if args.dict else rec_dir / "ppocrv5_dict.txt"
    ocr = PaddleOCR(rec_model_dir=str(rec_dir), rec_char_dict_path=str(dict_path),
                    show_log=False, **PAPER_SETTINGS)

    out_dir = ROOT / "assets" / args.id
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = []

    for n, img_path in enumerate(args.image, start=1):
        result = ocr.ocr(img_path, cls=False)
        entries = result[0] if result and result[0] else []

        im = ImageOps.exif_transpose(Image.open(img_path))
        w0, h0 = im.size
        scale = 1.0
        if args.max_side and max(w0, h0) > args.max_side:
            scale = args.max_side / max(w0, h0)
            im = im.resize((round(w0 * scale), round(h0 * scale)), Image.LANCZOS)
        img_name = f"p{n:03d}.jpg"
        im.convert("RGB").save(out_dir / img_name, "JPEG", quality=88, optimize=True)
        W, H = im.size

        lines = []
        for entry in entries:
            if not entry:
                continue
            poly, (text, conf) = entry[0], entry[1]
            text = (text or "").strip()
            if not text:
                continue
            x0, y0, x1, y1 = to_rect(poly)
            lines.append({
                "text": text,
                "bbox": [round(x0 * scale), round(y0 * scale),
                         round(x1 * scale), round(y1 * scale)],
                "confidence": round(float(conf), 3),
                "column": None,
                "layout_type": "text",
                **({"direction": "vertical"} if args.vertical else {}),
            })

        if args.vertical:
            lines.sort(key=lambda l: (-l["bbox"][2], l["bbox"][1]))
            multi, boundary = False, None
        else:
            cols, multi, boundary = infer_columns(lines, W)
            for l, c in zip(lines, cols):
                l["column"] = c
            lines.sort(key=lambda l: (l["column"] if multi else 0, l["bbox"][1], l["bbox"][0]))
        for i, l in enumerate(lines):
            l["order"] = i

        pages.append({
            "page_number": n,
            "image": f"assets/{args.id}/{img_name}",
            "width": W, "height": H,
            "is_multi_column": bool(multi),
            "column_boundary": boundary,
            "lines": lines,
        })
        avg = sum(l["confidence"] for l in lines) / max(len(lines), 1)
        print(f"  {n}쪽: {len(lines)}라인  평균 {avg:.3f}  {W}x{H}  {'2단' if multi else '1단'}")

    fixture = {
        "id": args.id, "title": args.title, "description": args.description,
        "source": args.source, "confidence_source": "model",
        "model": args.model, "tags": args.tags,
        "pipeline": "paper-eval",     # 어느 설정으로 뽑았는지 표시
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
        "id": args.id, "title": args.title, "description": args.description,
        "tags": args.tags, "recommended_model": args.model,
        "filename": args.filename or Path(args.image[0]).name,
        "fixture": f"fixtures/{args.id}.json",
    }]
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"fixtures/{args.id}.json 생성")


if __name__ == "__main__":
    main()
