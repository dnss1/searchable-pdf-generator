"""
GT vs 예측 비교.

    gt/{domain}/{page}.txt  ↔  pred/{domain}/{page}.txt

    python -m ocr_eval.evaluate --gt gt --pred pred --mode page
    python -m ocr_eval.evaluate --gt gt --pred pred --mode line
    python -m ocr_eval.evaluate --tsv pairs.tsv     # id<TAB>gt<TAB>pred

page 는 페이지 전체를 이어붙여, line 은 같은 줄 번호끼리 비교.
둘은 재는 게 다르다 (research/docs/평가지표_정의.md).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .metrics import Accumulator
from .report import markdown


def eval_dirs(gt_root: Path, pred_root: Path, mode: str, domains=None) -> dict:
    per_domain, overall = {}, Accumulator()
    dirs = sorted(d for d in gt_root.iterdir() if d.is_dir())
    if domains:
        dirs = [d for d in dirs if d.name in domains]
    if not dirs:                                   # 평평한 구조
        dirs = [gt_root]

    for gt_dir in dirs:
        dom = gt_dir.name if gt_dir != gt_root else "(all)"
        pred_dir = pred_root / dom if gt_dir != gt_root else pred_root
        acc = Accumulator()
        for gt_file in sorted(gt_dir.glob("*.txt")):
            pred_file = pred_dir / gt_file.name
            if not pred_file.exists():
                print(f"  예측 없음, 건너뜀: {pred_file}", file=sys.stderr)
                continue
            gt_raw = gt_file.read_text(encoding="utf-8")
            pr_raw = pred_file.read_text(encoding="utf-8")
            if mode == "page":
                acc.add(gt_raw, pr_raw)
            else:
                gl = [l for l in gt_raw.splitlines() if l.strip()]
                pl = [l for l in pr_raw.splitlines() if l.strip()]
                for i, g in enumerate(gl):
                    acc.add(g, pl[i] if i < len(pl) else "", classify=True)
        if acc.units:
            per_domain[dom] = acc.result()
            overall.merge(acc)
    return {"mode": mode, "per_domain": per_domain, "overall": overall.result()}


def eval_tsv(path: Path) -> dict:
    acc = Accumulator()
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) < 3:
                continue
            acc.add(row[1], row[2], classify=True)
    return {"mode": "line", "per_domain": {}, "overall": acc.result()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt", type=Path, help="정답 루트 디렉토리")
    ap.add_argument("--pred", type=Path, help="예측 루트 디렉토리")
    ap.add_argument("--tsv", type=Path, help="id<TAB>gt<TAB>pred 형식 파일")
    ap.add_argument("--mode", choices=["page", "line"], default="line")
    ap.add_argument("--domains", nargs="*", help="평가할 도메인 폴더 이름 (기본: 전부)")
    ap.add_argument("--out-json", type=Path)
    ap.add_argument("--out-md", type=Path)
    ap.add_argument("--title", default="평가 결과")
    args = ap.parse_args(argv)

    if args.tsv:
        result = eval_tsv(args.tsv)
    elif args.gt and args.pred:
        result = eval_dirs(args.gt, args.pred, args.mode, args.domains)
    else:
        ap.error("--gt/--pred 또는 --tsv 가 필요합니다.")

    md = markdown(result, args.title)
    print(md)
    if args.out_json:
        args.out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"\nJSON 저장: {args.out_json}", file=sys.stderr)
    if args.out_md:
        args.out_md.write_text(md, encoding="utf-8")
        print(f"마크다운 저장: {args.out_md}", file=sys.stderr)
    return result


if __name__ == "__main__":
    main()
