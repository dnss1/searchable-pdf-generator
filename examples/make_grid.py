"""
증강 before/after 그리드. README 에 붙이는 비교 이미지용.

    python examples/make_grid.py                    # 합성 샘플
    python examples/make_grid.py --input line.png   # 내 이미지
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocr_augment import augment as A  # noqa: E402

SAMPLE_TEXT = "第3章 문화예술교육 참가의사 조사결과"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "C:/Windows/Fonts/malgun.ttf",
]

SINGLE = [
    ("gaussian_noise",   lambda im: A.add_gaussian_noise(im, 12, 22)),
    ("jpeg_compression", lambda im: A.add_jpeg_compression(im, 20, 30)),
    ("gaussian_blur",    lambda im: A.add_gaussian_blur(im, 5, 1.6)),
    ("motion_blur",      lambda im: A.add_motion_blur(im, 7)),
    ("paper_texture",    lambda im: A.add_paper_texture(im, 0.22)),
    ("ink_bleed",        lambda im: A.add_ink_bleed(im, 2, 1)),
    ("skew",             lambda im: A.add_skew(im, 1.5)),
    ("shear",            lambda im: A.add_shear(im, 0.2)),
    ("stretch",          lambda im: A.add_stretch(im, (0.88, 0.90))),
    ("underline",        lambda im: A.add_underline(im, 1.0)),
    ("fade",             lambda im: A.add_fade(im, (0.55, 0.60))),
    ("scratches  *",     lambda im: A.add_scratches(im, (3, 5))),
    ("stains  *",        lambda im: A.add_stains(im, (2, 3))),
    ("dark_bg_patches *", lambda im: A.add_dark_bg_patches(im)),
    ("grain  *",         lambda im: A.add_grain(im, 30)),
]

LEVELS = [
    ("clean        25%", A.augment_clean),
    ("light        50%", A.augment_light),
    ("medium          ", A.augment_medium),
    ("heavy        15%", A.augment_heavy),
    ("empty_noise  10%", A.augment_empty_noise),
]


def find_font(size):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def make_sample(text=SAMPLE_TEXT, height=48, pad=12):
    font = find_font(int(height * 0.62))
    probe = Image.new("RGB", (10, 10), "white")
    w = int(ImageDraw.Draw(probe).textlength(text, font=font)) + pad * 2
    img = Image.new("RGB", (w, height), "white")
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), text, font=font)
    d.text((pad, (height - (bbox[3] - bbox[1])) // 2 - bbox[1]), text, font=font, fill=(20, 20, 20))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def label_strip(width, text, height=22, font_size=14):
    img = Image.new("RGB", (width, height), (246, 246, 248))
    d = ImageDraw.Draw(img)
    f = find_font(font_size)
    d.text((8, (height - font_size) // 2 - 2), text, font=f, fill=(70, 70, 80))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def build_grid(base, items, title, cols=1, gap=8):
    width = max(im.shape[1] for _, im in items)
    rows = []
    head = label_strip(width, title, height=30, font_size=17)
    rows.append(head)
    rows.append(np.full((gap, width, 3), 255, np.uint8))
    for name, im in items:
        if im.shape[1] < width:
            im = cv2.copyMakeBorder(im, 0, 0, 0, width - im.shape[1],
                                    cv2.BORDER_CONSTANT, value=(255, 255, 255))
        rows.append(label_strip(width, name))
        rows.append(im)
        rows.append(np.full((gap, width, 3), 255, np.uint8))
    return np.vstack(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="샘플 대신 쓸 라인 이미지 경로")
    ap.add_argument("--text", default=SAMPLE_TEXT, help="합성 샘플에 쓸 문자열")
    ap.add_argument("--outdir", default=str(Path(__file__).parent), help="출력 폴더")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    A.random.seed(args.seed)
    np.random.seed(args.seed)

    base = cv2.imread(args.input) if args.input else make_sample(args.text)
    if base is None:
        raise SystemExit(f"이미지 로드 실패: {args.input}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(outdir / "00_original.png"), base)

    singles = [("original", base)] + [(n, f(base.copy())) for n, f in SINGLE]
    cv2.imwrite(str(outdir / "grid_single.png"),
                build_grid(base, singles, "개별 증강  ( * = 옛 스캔 대응으로 직접 구현 )"))

    levels = [("original", base)] + [(n, f(base.copy())) for n, f in LEVELS]
    cv2.imwrite(str(outdir / "grid_levels.png"),
                build_grid(base, levels, "레벨 프리셋  ( 학습셋 적용 비율 )"))

    print(f"저장 완료 → {outdir}/grid_single.png, {outdir}/grid_levels.png")


if __name__ == "__main__":
    main()
