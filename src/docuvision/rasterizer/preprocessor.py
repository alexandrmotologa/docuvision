"""Image preprocessing, deskewing, and contrast normalization for scans."""

from __future__ import annotations

import io
from typing import Tuple

from PIL import Image, ImageEnhance, ImageOps


class ImagePreprocessor:
    """Preprocesses rasterized page images to improve OCR and VLM comprehension."""

    def __init__(
        self,
        contrast_factor: float = 1.25,
        sharpness_factor: float = 1.30,
        enable_autocontrast: bool = True,
    ) -> None:
        self.contrast_factor = contrast_factor
        self.sharpness_factor = sharpness_factor
        self.enable_autocontrast = enable_autocontrast

    def enhance(self, image: Image.Image) -> Image.Image:
        """Apply tone enhancement, contrast correction, and sharpening."""
        img = image.convert("RGB")

        if self.enable_autocontrast:
            img = ImageOps.autocontrast(img, cutoff=0.5)

        if self.contrast_factor != 1.0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(self.contrast_factor)

        if self.sharpness_factor != 1.0:
            sharpener = ImageEnhance.Sharpness(img)
            img = sharpener.enhance(self.sharpness_factor)

        return img

    def enhance_bytes(self, image_bytes: bytes) -> bytes:
        """Apply enhancements to raw image bytes and return optimized PNG bytes."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            enhanced = self.enhance(img)
            out_buf = io.BytesIO()
            enhanced.save(out_buf, format="PNG", optimize=True)
            return out_buf.getvalue()

    def resize_max_bound(
        self,
        image: Image.Image,
        max_dim: int = 2048,
    ) -> Tuple[Image.Image, float]:
        """Proportionally scale down image if max(width, height) exceeds max_dim.

        Returns:
            Tuple of (scaled_image, scale_factor).
        """
        w, h = image.size
        max_side = max(w, h)
        if max_side <= max_dim:
            return image, 1.0

        scale = max_dim / float(max_side)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        return resized, scale
