"""
TRDG 이미지 증강 파이프라인
실문서 도메인(스캔/인쇄/노이즈) 대응을 위한 후처리

증강 비율:
  25% - 클린 (디지털 PDF 대응)
  50% - 경미한 열화
  15% - 심한 열화 (scan-old 대응)
  10% - 빈 배경 + 노이즈 (det 오검출 대응, 레이블 "")

각 증강은 학습 데이터에만 적용, val 에는 적용 안 함.
"""

import os
import sys
import random
import argparse
from pathlib import Path
import numpy as np
import cv2

random.seed(42)


# ============================================================
# 개별 증강 함수
# ============================================================

def add_gaussian_noise(img, sigma_min=5, sigma_max=15):
    sigma = random.uniform(sigma_min, sigma_max)
    noise = np.random.normal(0, sigma, img.shape).astype(np.int16)
    out = img.astype(np.int16) + noise
    return np.clip(out, 0, 255).astype(np.uint8)


def add_jpeg_compression(img, q_min=70, q_max=90):
    q = random.randint(q_min, q_max)
    _, enc = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR)


def adjust_brightness_contrast(img, brightness_pct=10, contrast_pct=10):
    b = random.uniform(-brightness_pct, brightness_pct) / 100.0
    c = 1 + random.uniform(-contrast_pct, contrast_pct) / 100.0
    out = img.astype(np.float32) * c + b * 255
    return np.clip(out, 0, 255).astype(np.uint8)


def add_gaussian_blur(img, kernel_max=3, sigma_max=1.5):
    k = random.choice([3, 5]) if kernel_max >= 5 else 3
    sigma = random.uniform(0.5, sigma_max)
    return cv2.GaussianBlur(img, (k, k), sigma)


def add_motion_blur(img, kernel_size=5):
    k = random.choice([3, 5, 7])
    angle = random.uniform(-30, 30)
    kernel = np.zeros((k, k))
    kernel[k // 2, :] = 1
    kernel /= k
    M = cv2.getRotationMatrix2D((k / 2, k / 2), angle, 1)
    kernel = cv2.warpAffine(kernel, M, (k, k))
    kernel /= kernel.sum()
    return cv2.filter2D(img, -1, kernel)


def add_paper_texture(img, intensity=0.15):
    """종이 질감 효과 (옅은 노란 tint + 미세 노이즈)"""
    out = img.astype(np.float32)
    # 옅은 노란/베이지 tint
    tint = np.array([random.uniform(-5, 5), random.uniform(-5, 5),
                      random.uniform(0, 15)])  # B, G, R 순 (BGR)
    out += tint
    # 미세 노이즈
    noise = np.random.normal(0, intensity * 50, img.shape)
    out += noise
    return np.clip(out, 0, 255).astype(np.uint8)


def add_ink_bleed(img, kernel_size=2, iterations=1):
    """잉크 번짐 시뮬레이션: erosion (검은색 텍스트 두꺼워짐)"""
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.erode(img, kernel, iterations=iterations)


def add_skew(img, angle_max=1.0):
    """회전 후 캔버스를 확장해 텍스트 잘림 방지 (wide-aspect OCR 이미지 대응).
    예: 1533×53 이미지 1° 회전 시 원래 코너가 24px 밀려 원본 캔버스 밖으로 나감 → 확장."""
    h, w = img.shape[:2]
    angle = random.uniform(-angle_max, angle_max)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
    # 회전된 bounding box 크기 계산 → 캔버스 확장
    cos_a = abs(M[0, 0]); sin_a = abs(M[0, 1])
    new_w = int(w * cos_a + h * sin_a + 0.5)
    new_h = int(w * sin_a + h * cos_a + 0.5)
    # 중심 이동 보정
    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2
    return cv2.warpAffine(img, M, (new_w, new_h), borderValue=(255, 255, 255))


def add_shear(img, shear_max=0.2):
    """이탈릭 시뮬레이션 — 수평 기울기 (A3 참고문헌 저널명 대응)"""
    h, w = img.shape[:2]
    s = random.uniform(-shear_max, shear_max)
    M = np.float32([[1, s, 0], [0, 1, 0]])
    new_w = int(w + abs(s) * h)
    return cv2.warpAffine(img, M, (new_w, h), borderValue=(255, 255, 255))


def add_stretch(img, factor_range=(0.92, 1.08)):
    """수평 폭 변화 — 폰트 metric variance 학습"""
    h, w = img.shape[:2]
    f = random.uniform(*factor_range)
    new_w = max(1, int(w * f))
    return cv2.resize(img, (new_w, h), interpolation=cv2.INTER_LANCZOS4)


def add_underline(img, prob=1.0):
    """5% 확률 밑줄 — 학술 강조 표기"""
    h, w = img.shape[:2]
    thickness = random.choice([1, 2])
    y = h - random.randint(2, 5)
    color = (random.randint(0, 60),) * 3
    out = img.copy()
    cv2.line(out, (2, y), (w - 2, y), color, thickness)
    return out


def add_scratches(img, count_range=(1, 4)):
    """무작위 스크래치 선 — 옛 스캔/복사본 긁힘 시뮬 (논문 Jeon 2025 강한 노이즈)"""
    h, w = img.shape[:2]
    out = img.copy()
    for _ in range(random.randint(*count_range)):
        x1 = random.randint(0, w); y1 = random.randint(0, h)
        length = random.randint(20, max(21, w // 2))
        angle = random.uniform(0, 3.14159)
        x2 = int(x1 + length * np.cos(angle))
        y2 = int(y1 + length * np.sin(angle))
        color = random.randint(80, 180)
        thickness = random.choice([1, 1, 2])
        cv2.line(out, (x1, y1), (x2, y2), (color, color, color), thickness)
    return out


def add_stains(img, count_range=(1, 3)):
    """무작위 어두운 얼룩/점 — 잉크 번짐·먼지 자국 (논문 강한 노이즈)"""
    h, w = img.shape[:2]
    out = img.copy()
    for _ in range(random.randint(*count_range)):
        cx = random.randint(0, w); cy = random.randint(0, h)
        r = random.randint(3, 12)
        color = random.randint(120, 200)
        overlay = out.copy()
        cv2.circle(overlay, (cx, cy), r, (color, color, color), -1)
        alpha = random.uniform(0.4, 0.8)
        out = cv2.addWeighted(out, 1-alpha, overlay, alpha, 0)
    return out


def add_dark_bg_patches(img):
    """부분 어두운 배경 (옛 스캔 음영) — 논문 '강한 노이즈 배경제거 실패'"""
    h, w = img.shape[:2]
    side = random.choice(['left', 'right', 'top', 'bottom', 'corner'])
    decrease = random.uniform(0.55, 0.85)
    grad = np.ones((h, w), dtype=np.float32)
    if side == 'left':
        grad = np.tile(np.linspace(decrease, 1.0, w), (h, 1))
    elif side == 'right':
        grad = np.tile(np.linspace(1.0, decrease, w), (h, 1))
    elif side == 'top':
        grad = np.tile(np.linspace(decrease, 1.0, h)[:, None], (1, w))
    elif side == 'bottom':
        grad = np.tile(np.linspace(1.0, decrease, h)[:, None], (1, w))
    else:  # corner
        gx = np.linspace(decrease, 1.0, w)
        gy = np.linspace(decrease, 1.0, h)[:, None]
        grad = gx * gy
    out = img.astype(np.float32) * grad[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def add_grain(img, intensity=25):
    """입자감 배경 (복사본/옛 신문 느낌) — 논문 '경미한 그레인 배경'"""
    h, w = img.shape[:2]
    grain = np.random.normal(0, intensity, (h, w)).astype(np.int16)
    grain = np.stack([grain, grain, grain], axis=-1)
    out = img.astype(np.int16) + grain
    return np.clip(out, 0, 255).astype(np.uint8)


def add_fade(img, alpha_range=(0.55, 0.85)):
    """저대비 페이드 — 낮은 잉크 농도 스캔 대응"""
    alpha = random.uniform(*alpha_range)
    white = np.full_like(img, 255)
    return cv2.addWeighted(img, alpha, white, 1 - alpha, 0)


# ============================================================
# 증강 정책 (확률 기반)
# ============================================================

def augment_clean(img):
    """30% - 원본 유지"""
    return img


def augment_light(img):
    """경미한 열화 (50%) + 논문 표4 '경미한 노이즈' 반영"""
    if random.random() < 0.7:
        img = add_gaussian_noise(img, 3, 10)
    if random.random() < 0.5:
        img = add_jpeg_compression(img, 75, 92)
    if random.random() < 0.5:
        img = adjust_brightness_contrast(img, 8, 8)
    if random.random() < 0.3:
        img = add_skew(img, 0.5)
    if random.random() < 0.3:          # 이탈릭 시뮬 (A3)
        img = add_shear(img, 0.1)
    if random.random() < 0.4:          # 폰트 metric variance
        img = add_stretch(img, (0.95, 1.05))
    if random.random() < 0.25:         # 입자감 배경 (논문 '그레인 배경')
        img = add_grain(img, intensity=15)
    if random.random() < 0.15:         # 소량 스크래치
        img = add_scratches(img, (1, 2))
    return img


def augment_medium(img):
    """25% - 중간 열화"""
    if random.random() < 0.8:
        img = add_gaussian_noise(img, 8, 20)
    if random.random() < 0.6:
        img = add_gaussian_blur(img, 3, 1.0)
    if random.random() < 0.7:
        img = add_jpeg_compression(img, 50, 75)
    if random.random() < 0.5:
        img = adjust_brightness_contrast(img, 15, 15)
    if random.random() < 0.4:
        img = add_paper_texture(img, 0.10)
    if random.random() < 0.4:
        img = add_skew(img, 1.0)
    if random.random() < 0.35:          # 이탈릭 더 강하게
        img = add_shear(img, 0.15)
    if random.random() < 0.4:
        img = add_stretch(img, (0.92, 1.08))
    if random.random() < 0.25:          # 페이드 (저대비 스캔)
        img = add_fade(img, (0.70, 0.90))
    if random.random() < 0.05:          # 밑줄 (드물게)
        img = add_underline(img)
    return img


def augment_heavy(img):
    """심한 열화 (15%) + 논문 표4 '강한 노이즈' (스크래치·얼룩·배경제거 실패) 반영"""
    if random.random() < 0.9:
        img = add_gaussian_noise(img, 15, 30)
    if random.random() < 0.7:
        img = add_gaussian_blur(img, 5, 1.8)
    if random.random() < 0.5:
        img = add_motion_blur(img, 5)
    if random.random() < 0.8:
        img = add_jpeg_compression(img, 25, 55)
    if random.random() < 0.7:
        img = adjust_brightness_contrast(img, 25, 20)
    if random.random() < 0.6:
        img = add_paper_texture(img, 0.20)
    if random.random() < 0.4:
        img = add_ink_bleed(img, 2, 1)
    if random.random() < 0.5:
        img = add_skew(img, 1.5)
    if random.random() < 0.4:
        img = add_shear(img, 0.2)
    if random.random() < 0.45:
        img = add_stretch(img, (0.88, 1.12))
    if random.random() < 0.4:
        img = add_fade(img, (0.55, 0.80))
    if random.random() < 0.08:
        img = add_underline(img)
    # 논문 반영 추가 노이즈
    if random.random() < 0.45:         # 스크래치 (옛 스캔 긁힘)
        img = add_scratches(img, (2, 5))
    if random.random() < 0.35:         # 얼룩 (잉크 번짐·먼지)
        img = add_stains(img, (1, 3))
    if random.random() < 0.4:          # 배경 음영 (scanner shading, 배경제거 실패)
        img = add_dark_bg_patches(img)
    if random.random() < 0.35:         # 강한 입자
        img = add_grain(img, intensity=25)
    return img


def augment_empty_noise(img):
    """빈 배경 + 노이즈 (10%) — 논문 Jeon et al. (2025) 방식.
    det 오검출 (여백, 선, 그림) 대응. 레이블은 "" (별도 처리).
    다양한 노이즈 조합으로 학습 다양성 확보.
    """
    h, w = img.shape[:2]
    # 배경 색 — 흰색이 주이지만 일부 밝은 회색/베이지도
    bg_type = random.random()
    if bg_type < 0.7:
        blank = np.full((h, w, 3), 255, dtype=np.uint8)
    elif bg_type < 0.9:
        base = random.randint(220, 250)
        blank = np.full((h, w, 3), base, dtype=np.uint8)
    else:
        # 베이지/크림 톤
        blank = np.full((h, w, 3), [225, 230, 240], dtype=np.uint8)

    if random.random() < 0.9:
        blank = add_gaussian_noise(blank, 15, 35)
    if random.random() < 0.6:
        blank = add_paper_texture(blank, 0.25)
    if random.random() < 0.5:
        blank = add_jpeg_compression(blank, 25, 55)
    if random.random() < 0.3:
        blank = add_gaussian_blur(blank, 3, 1.2)
    # 논문의 "텍스트 없음 + 복합 노이즈"
    if random.random() < 0.4:
        blank = add_grain(blank, intensity=30)
    if random.random() < 0.35:
        blank = add_scratches(blank, (1, 4))   # 의미없는 선
    if random.random() < 0.3:
        blank = add_stains(blank, (1, 3))      # 먼지/얼룩
    if random.random() < 0.35:
        blank = add_dark_bg_patches(blank)     # 음영
    return blank


def random_augment(img):
    """확률 기반 증강 선택 — Stage 6 (논문 분포):
       클린 25% / 경미 50% / 강 15% / 빈배경 10%
    """
    r = random.random()
    if r < 0.25:
        return augment_clean(img), 'clean'
    elif r < 0.75:
        return augment_light(img), 'light'
    elif r < 0.90:
        return augment_heavy(img), 'heavy'
    else:
        return augment_empty_noise(img), 'empty_noise'


# ============================================================
# 디렉토리 단위 처리
# ============================================================

def process_directory(input_dir, output_dir=None, in_place=False, max_width=1280):
    """input_dir의 모든 이미지에 증강 적용 + max_width 초과 필터링.
    labels.txt도 함께 재작성한다 (필터링된 항목 제외)."""
    input_path = Path(input_dir)
    if in_place:
        output_path = input_path
    else:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

    # labels.txt 로드 (있는 경우): "filename.png <text>"
    labels_map = {}
    labels_file = input_path / 'labels.txt'
    if labels_file.exists():
        with open(labels_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if ' ' in line:
                    fname, text = line.split(' ', 1)
                    labels_map[fname] = text

    img_files = sorted(list(input_path.glob('*.png')) + list(input_path.glob('*.jpg')))

    stats = {'clean': 0, 'light': 0, 'heavy': 0, 'empty_noise': 0,
             'over_width_skipped': 0, 'load_failed': 0}
    new_labels = []

    for i, img_path in enumerate(img_files):
        img = cv2.imread(str(img_path))
        if img is None:
            stats['load_failed'] += 1
            if in_place:
                try: img_path.unlink()
                except: pass
            continue

        h, w = img.shape[:2]
        if w > max_width:
            stats['over_width_skipped'] += 1
            if in_place:
                try: img_path.unlink()
                except: pass
            continue

        augmented, level = random_augment(img)
        stats[level] += 1

        if in_place:
            cv2.imwrite(str(img_path), augmented)
        else:
            out_path = output_path / img_path.name
            cv2.imwrite(str(out_path), augmented)

        fname = img_path.name
        if fname in labels_map:
            # 빈배경 처리된 이미지는 레이블을 빈 문자열로 교체
            # (논문 Jeon 2025: 텍스트 없음 샘플의 레이블 = "" → CTC blank-only 학습)
            label_text = '' if level == 'empty_noise' else labels_map[fname]
            new_labels.append(f"{fname} {label_text}")

        if (i + 1) % 5000 == 0:
            print(f"  {i+1:,}/{len(img_files):,} 처리 (drop: {stats['over_width_skipped']})")

    # labels.txt 재작성
    if new_labels:
        out_labels = output_path / 'labels.txt'
        with open(out_labels, 'w', encoding='utf-8') as f:
            for line in new_labels:
                f.write(line + '\n')

    return stats


# ============================================================
# 단일 이미지 데모
# ============================================================

def demo_augmentations(input_image, output_dir):
    """한 이미지에 모든 증강 적용해서 비교"""
    img = cv2.imread(input_image)
    if img is None:
        print(f"이미지 로드 실패: {input_image}")
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(out / "00_original.png"), img)
    cv2.imwrite(str(out / "01_clean.png"), augment_clean(img.copy()))
    cv2.imwrite(str(out / "02_light.png"), augment_light(img.copy()))
    cv2.imwrite(str(out / "03_medium.png"), augment_medium(img.copy()))
    cv2.imwrite(str(out / "04_heavy.png"), augment_heavy(img.copy()))

    print(f"데모 이미지 저장: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='입력 디렉토리 또는 이미지 파일')
    parser.add_argument('--output', help='출력 디렉토리 (없으면 in-place)')
    parser.add_argument('--demo', action='store_true', help='단일 이미지 데모 모드')
    parser.add_argument('--max_width', type=int, default=1280, help='이 값보다 넓은 이미지는 필터링 (기본 1280)')
    args = parser.parse_args()

    if args.demo:
        demo_augmentations(args.input, args.output or '/tmp/aug_demo')
    else:
        if not args.output:
            print("--output 또는 --demo 필요")
            sys.exit(1)
        in_place = (args.input == args.output)
        stats = process_directory(args.input, args.output, in_place, max_width=args.max_width)
        print(f"\n증강 분포:")
        for k, v in stats.items():
            print(f"  {k}: {v:,}")
