"""문서 OCR 학습용 이미지 증강."""

from .augment import (  # noqa: F401
    add_gaussian_noise, add_jpeg_compression, adjust_brightness_contrast,
    add_gaussian_blur, add_motion_blur, add_paper_texture, add_ink_bleed,
    add_skew, add_shear, add_stretch, add_underline,
    add_scratches, add_stains, add_dark_bg_patches, add_grain, add_fade,
    augment_clean, augment_light, augment_medium, augment_heavy,
    augment_empty_noise, random_augment, process_directory,
)

__version__ = "0.1.0"
__all__ = [n for n in dir() if n.startswith(("add_", "adjust_", "augment_", "random_", "process_"))]
