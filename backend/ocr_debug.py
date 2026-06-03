"""
ocr_debug.py - visual/debug helpers for OCR and layout mapping inspection.
"""

import base64
import io
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont


def _bbox_bounds(bbox: List[List[float]] | None) -> Tuple[float, float, float, float]:
    if not bbox:
        return 0.0, 0.0, 0.0, 0.0
    xs = [float(point[0]) for point in bbox]
    ys = [float(point[1]) for point in bbox]
    return min(xs), min(ys), max(xs), max(ys)


def _center(bbox: List[List[float]] | None) -> Tuple[float, float]:
    x1, y1, x2, y2 = _bbox_bounds(bbox)
    return (x1 + x2) / 2, (y1 + y2) / 2


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _draw_label(draw: ImageDraw.ImageDraw, xy: Tuple[float, float], text: str, fill: str, bg: str) -> None:
    x, y = xy
    font = _font(13)
    bbox = draw.textbbox((x, y), text, font=font)
    padding = 3
    draw.rectangle(
        [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding],
        fill=bg,
        outline=fill,
    )
    draw.text((x, y), text, fill=fill, font=font)


def _draw_arrow(draw: ImageDraw.ImageDraw, start: Tuple[float, float], end: Tuple[float, float], fill: str) -> None:
    draw.line([start, end], fill=fill, width=3)
    ex, ey = end
    sx, sy = start
    dx = ex - sx
    dy = ey - sy
    length = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux = dx / length
    uy = dy / length
    left = (ex - ux * 12 - uy * 6, ey - uy * 12 + ux * 6)
    right = (ex - ux * 12 + uy * 6, ey - uy * 12 - ux * 6)
    draw.polygon([end, left, right], fill=fill)


def render_ocr_debug_overlay(
    image_bytes: bytes,
    *,
    blocks: List[Dict[str, Any]],
    structure: Dict[str, Any],
    entities: List[Dict[str, Any]],
    layout_debug: Dict[str, Any],
) -> str:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Raw OCR blocks: blue boxes with stable block indexes.
    for idx, block in enumerate(blocks):
        x1, y1, x2, y2 = _bbox_bounds(block.get("bbox"))
        draw.rectangle([x1, y1, x2, y2], outline=(37, 99, 235, 220), width=2)
        label = f"B{idx} {block.get('confidence', 0):.2f}"
        _draw_label(draw, (x1, max(0, y1 - 18)), label, "#1d4ed8", "#eff6ff")

    # Row grouping: subtle green row frames.
    for row in structure.get("rows", []):
        x1, y1, x2, y2 = _bbox_bounds(row.get("bbox"))
        draw.rectangle([x1, y1, x2, y2], outline=(22, 163, 74, 150), width=1)
        _draw_label(draw, (x2 + 4, y1), f"R{row.get('row_index')}", "#15803d", "#f0fdf4")

    # Detected labels: amber.
    for label in layout_debug.get("labels", []):
        x1, y1, x2, y2 = _bbox_bounds(label.get("bbox"))
        draw.rectangle([x1, y1, x2, y2], outline=(217, 119, 6, 255), width=3)
        _draw_label(draw, (x1, y2 + 4), f"L:{label.get('entity_type')}", "#92400e", "#fffbeb")

    # Selected values and label -> value association arrows.
    for mapping in layout_debug.get("selected_mappings", []):
        label_bbox = mapping.get("label_bbox")
        value_bbox = mapping.get("value_bbox")
        x1, y1, x2, y2 = _bbox_bounds(value_bbox)
        draw.rectangle([x1, y1, x2, y2], outline=(220, 38, 38, 255), width=3)
        _draw_label(
            draw,
            (x1, y2 + 4),
            f"V:{mapping.get('entity_type')} {mapping.get('confidence', 0):.2f}",
            "#991b1b",
            "#fef2f2",
        )
        _draw_arrow(draw, _center(label_bbox), _center(value_bbox), (220, 38, 38, 255))

    # Final entity classifications: purple labels near selected values.
    for entity in entities:
        bbox = entity.get("bbox")
        if not bbox:
            continue
        x1, y1, _, _ = _bbox_bounds(bbox)
        _draw_label(
            draw,
            (x1, max(0, y1 - 36)),
            f"E:{entity.get('raw_type')} {entity.get('confidence', 0):.2f}",
            "#6d28d9",
            "#f5f3ff",
        )

    annotated = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    output = io.BytesIO()
    annotated.save(output, format="JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
