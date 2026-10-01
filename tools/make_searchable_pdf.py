"""
fixture → Searchable PDF. 원본 이미지 위에 렌더 모드 3(invisible) 텍스트를 얹는다.

    python tools/make_searchable_pdf.py                       # fixtures/ 전부
    python tools/make_searchable_pdf.py --fixture fixtures/xx.json
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF 가 필요합니다:  pip install pymupdf")

ROOT = Path(__file__).resolve().parents[1] / "web" / "public"

# embed 하면 한글 전용은 한자가 notdef, Noto CJK 는 15MB 넘음
BUILTIN_CJK = "korea"


def build_pdf(fixture_path: Path, out_path: Path = None, fontfile=None) -> Path:
    fx = json.loads(fixture_path.read_text(encoding="utf-8"))
    out_path = out_path or (ROOT / fx.get("pdf", f"assets/{fx['id']}/searchable.pdf"))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open()

    for page_spec in fx["pages"]:
        w, h = page_spec["width"], page_spec["height"]
        page = doc.new_page(width=w, height=h)

        img_path = ROOT / page_spec["image"]
        if img_path.exists():
            page.insert_image(fitz.Rect(0, 0, w, h), filename=str(img_path))

        if fontfile:
            fontname = "ocrfont"
            page.insert_font(fontname=fontname, fontfile=str(fontfile))
        else:
            fontname = BUILTIN_CJK

        for line in page_spec["lines"]:
            text = line["text"]
            if not text.strip():
                continue
            x0, y0, x1, y1 = line["bbox"]
            box_h = max(y1 - y0, 1)
            size = box_h * 0.78
            try:
                tl = fitz.get_text_length(text, fontname=fontname, fontsize=size)
            except Exception:
                tl = len(text) * size * 0.75
            if tl > (x1 - x0) and tl > 0:
                size *= (x1 - x0) / tl
            baseline = y1 - box_h * 0.22
            page.insert_text((x0, baseline), text,
                             fontname=fontname, fontsize=size,
                             render_mode=3)          # 3 = invisible

    if fontfile and hasattr(doc, "subset_fonts"):
        try:
            doc.subset_fonts()
        except Exception:
            pass
    doc.save(str(out_path), deflate=True, garbage=3)
    doc.close()
    return out_path


def verify(pdf_path: Path, needles) -> str:
    """실제로 검색이 되는지 확인.

    공백이 폰트에 따라 NBSP 로 들어가므로 공백 없는 덩어리로,
    한 줄이 실패할 수 있으니 여러 줄 시도.
    """
    doc = fitz.open(str(pdf_path))
    try:
        for text in needles:
            for cand in [w for w in text.split() if len(w) >= 2][:3] or [text.strip()[:6]]:
                cand = cand[:8]
                if cand and any(page.search_for(cand) for page in doc):
                    return cand
    finally:
        doc.close()
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", type=Path, help="단일 fixture 경로 (없으면 전부)")
    ap.add_argument("--fontfile", type=Path,
                    help="텍스트 레이어에 embed 할 TTF/OTF (기본: 내장 CJK 폰트)")
    args = ap.parse_args()

    targets = [args.fixture] if args.fixture else sorted(
        p for p in (ROOT / "fixtures").glob("*.json") if p.name != "index.json")

    for fp in targets:
        fx = json.loads(fp.read_text(encoding="utf-8"))
        out = build_pdf(fp, fontfile=args.fontfile)
        probes = [l["text"] for l in fx["pages"][0]["lines"] if len(l["text"]) > 4][:8]
        hit = verify(out, probes) if probes else ""
        size_kb = out.stat().st_size / 1024
        print(f"  {fx['id']}: {out.relative_to(ROOT)}  {size_kb:.0f} KB  "
              f"검색 검증 {'통과 (' + hit + ')' if hit else '실패'}")


if __name__ == "__main__":
    main()
