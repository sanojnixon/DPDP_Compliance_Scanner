"""
ocr_structure.py - preserves OCR line and row context for classifiers.

EasyOCR blocks may arrive as individual words or fragments. This module groups
nearby blocks into visual lines while retaining block indexes and bounding boxes.
"""

from typing import Any, Dict, List, Tuple


def _bbox_bounds(bbox: List[List[float]] | None) -> Tuple[float, float, float, float]:
    if not bbox:
        return 0.0, 0.0, 0.0, 0.0
    xs = [float(point[0]) for point in bbox]
    ys = [float(point[1]) for point in bbox]
    return min(xs), min(ys), max(xs), max(ys)


def _merge_bounds(bounds: List[Tuple[float, float, float, float]]) -> List[List[float]]:
    if not bounds:
        return []
    x1 = min(item[0] for item in bounds)
    y1 = min(item[1] for item in bounds)
    x2 = max(item[2] for item in bounds)
    y2 = max(item[3] for item in bounds)
    return [[round(x1, 1), round(y1, 1)], [round(x2, 1), round(y1, 1)], [round(x2, 1), round(y2, 1)], [round(x1, 1), round(y2, 1)]]


def _block_record(block: Dict[str, Any], index: int) -> Dict[str, Any]:
    x1, y1, x2, y2 = _bbox_bounds(block.get("bbox"))
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    return {
        "index": index,
        "text": str(block.get("text", "")),
        "confidence": float(block.get("confidence", 0) or 0),
        "bbox": block.get("bbox"),
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "cx": (x1 + x2) / 2,
        "cy": (y1 + y2) / 2,
        "width": width,
        "height": height,
    }


def _needs_direct_join(previous_text: str, current_text: str, gap: float, median_height: float) -> bool:
    previous = previous_text.strip()
    current = current_text.strip()
    if not previous or not current:
        return False

    if previous.endswith(("/", "-", ":", ".")) or current.startswith(("/", "-", ":", ".")):
        return True
    if previous in {"/", "-", ":"} or current in {"/", "-", ":"}:
        return True
    if gap <= max(6.0, median_height * 0.18):
        return True
    return False


def _compose_line_text(group: List[Dict[str, Any]], median_height: float) -> str:
    parts: List[str] = []
    previous = None
    for item in group:
        token = item["text"].strip()
        if not token:
            continue
        if not parts:
            parts.append(token)
            previous = item
            continue

        gap = max(0.0, item["x1"] - previous["x2"])
        if _needs_direct_join(parts[-1], token, gap, median_height):
            parts[-1] = parts[-1] + token
        else:
            parts.append(token)
        previous = item
    return " ".join(part for part in parts if part)


def _column_clusters(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    clusters: List[Dict[str, Any]] = []
    median_width = sorted(item["width"] for item in records)[len(records) // 2] if records else 1.0
    threshold = max(45.0, median_width * 0.85)

    for record in sorted(records, key=lambda item: item["x1"]):
        best_cluster = None
        best_distance = None
        for cluster in clusters:
            distance = abs(record["x1"] - cluster["x1"])
            if distance <= threshold and (best_distance is None or distance < best_distance):
                best_cluster = cluster
                best_distance = distance

        if best_cluster is None:
            clusters.append({
                "column_index": len(clusters),
                "x1": record["x1"],
                "x2": record["x2"],
                "cx": record["cx"],
                "_x1_sum": record["x1"],
                "_cx_sum": record["cx"],
                "block_indices": [record["index"]],
            })
            continue

        best_cluster["block_indices"].append(record["index"])
        best_cluster["_x1_sum"] += record["x1"]
        best_cluster["_cx_sum"] += record["cx"]
        best_cluster["x1"] = round(best_cluster["_x1_sum"] / len(best_cluster["block_indices"]), 2)
        best_cluster["x2"] = max(best_cluster["x2"], record["x2"])
        best_cluster["cx"] = round(best_cluster["_cx_sum"] / len(best_cluster["block_indices"]), 2)

    clusters.sort(key=lambda item: item["x1"])
    for idx, cluster in enumerate(clusters):
        cluster["column_index"] = idx
        cluster.pop("_x1_sum", None)
        cluster.pop("_cx_sum", None)
    return clusters


def _row_cells(group: List[Dict[str, Any]], column_lookup: Dict[int, int]) -> List[Dict[str, Any]]:
    cells = []
    for item in sorted(group, key=lambda record: record["x1"]):
        cells.append({
            "block_index": item["index"],
            "column_index": column_lookup.get(item["index"]),
            "text": item["text"],
            "confidence": round(item["confidence"], 4),
            "bbox": item["bbox"],
            "x1": item["x1"],
            "y1": item["y1"],
            "x2": item["x2"],
            "y2": item["y2"],
            "cx": item["cx"],
            "cy": item["cy"],
            "width": item["width"],
            "height": item["height"],
        })
    return cells


def parse_ocr_structure(ocr_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    records = [_block_record(block, idx) for idx, block in enumerate(ocr_blocks)]
    records.sort(key=lambda item: (item["cy"], item["x1"]))

    if not records:
        return {"lines": [], "rows": [], "columns": [], "full_text": "", "block_to_line": {}, "blocks": []}

    median_height = sorted(item["height"] for item in records)[len(records) // 2]
    threshold = max(10.0, median_height * 0.65)
    columns = _column_clusters(records)
    column_lookup = {
        block_index: column["column_index"]
        for column in columns
        for block_index in column.get("block_indices", [])
    }

    grouped: List[List[Dict[str, Any]]] = []
    for record in records:
        if not grouped:
            grouped.append([record])
            continue
        current = grouped[-1]
        current_cy = sum(item["cy"] for item in current) / len(current)
        if abs(record["cy"] - current_cy) <= threshold:
            current.append(record)
        else:
            grouped.append([record])

    lines = []
    rows = []
    cursor = 0
    block_to_line = {}
    for line_index, group in enumerate(grouped):
        group.sort(key=lambda item: item["x1"])
        line_text = _compose_line_text(group, median_height)
        if not line_text:
            continue
        start = cursor
        end = start + len(line_text)
        bounds = [_bbox_bounds(item.get("bbox")) for item in group]
        x1, y1, x2, y2 = _bbox_bounds(_merge_bounds(bounds))
        block_indices = [item["index"] for item in group]
        for block_index in block_indices:
            block_to_line[block_index] = len(lines)
        lines.append({
            "line_index": len(lines),
            "text": line_text,
            "start": start,
            "end": end,
            "block_indices": block_indices,
            "bbox": _merge_bounds(bounds),
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "cx": (x1 + x2) / 2,
            "cy": (y1 + y2) / 2,
            "width": max(1.0, x2 - x1),
            "height": max(1.0, y2 - y1),
            "avg_confidence": round(sum(item["confidence"] for item in group) / len(group), 4),
        })
        rows.append({
            "row_index": len(rows),
            "line_index": len(lines) - 1,
            "text": line_text,
            "block_indices": block_indices,
            "bbox": _merge_bounds(bounds),
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "cx": (x1 + x2) / 2,
            "cy": (y1 + y2) / 2,
            "avg_confidence": round(sum(item["confidence"] for item in group) / len(group), 4),
            "cells": _row_cells(group, column_lookup),
        })
        cursor = end + 1

    full_text = "\n".join(line["text"] for line in lines)
    for idx, line in enumerate(lines):
        neighbors = []
        if idx > 0:
            neighbors.append(lines[idx - 1]["text"])
        neighbors.append(line["text"])
        if idx + 1 < len(lines):
            neighbors.append(lines[idx + 1]["text"])
        line["context_text"] = "\n".join(neighbors)

    return {
        "lines": lines,
        "rows": rows,
        "columns": columns,
        "full_text": full_text,
        "block_to_line": block_to_line,
        "blocks": records,
    }


def line_context_for_span(structure: Dict[str, Any], start: int, end: int, window: int = 1) -> Dict[str, Any]:
    lines = structure.get("lines", [])
    touched = [
        idx for idx, line in enumerate(lines)
        if start < line.get("end", 0) and end > line.get("start", 0)
    ]
    if not touched:
        return {"line_indices": [], "context_text": "", "block_indices": [], "bbox": None}

    first = max(0, min(touched) - window)
    last = min(len(lines) - 1, max(touched) + window)
    selected = lines[first:last + 1]
    block_indices = []
    for line in selected:
        block_indices.extend(line.get("block_indices", []))

    primary_bounds = []
    for line_index in touched:
        bbox = lines[line_index].get("bbox")
        if bbox:
            primary_bounds.append(_bbox_bounds(bbox))

    return {
        "line_indices": touched,
        "context_text": "\n".join(line.get("text", "") for line in selected),
        "block_indices": sorted(set(block_indices)),
        "bbox": _merge_bounds(primary_bounds) if primary_bounds else None,
    }
