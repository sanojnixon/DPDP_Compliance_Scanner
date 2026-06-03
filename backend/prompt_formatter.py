"""
prompt_formatter.py - compact prompt payload formatting utilities.

Internal services keep Python dict/list objects. This module only formats the
final LLM evidence payload, preferring YAML for lower prompt overhead and
falling back to JSON if conversion fails.
"""

import json
import logging
import math
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict

logger = logging.getLogger(__name__)

_PLAIN_SAFE = re.compile(r"^[A-Za-z][A-Za-z0-9 _./()%-]*$")
_NUMERIC_LIKE = re.compile(r"^[+-]?\d+([.,]\d+)*$")
_RESERVED_WORDS = {"true", "false", "null", "none", "yes", "no", "on", "off"}


def _coerce_json_compatible(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _coerce_json_compatible(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_coerce_json_compatible(v) for v in value]
    return str(value)


def _quote_string(value: str) -> str:
    if value == "":
        return '""'
    lower_value = value.lower()
    needs_quote = (
        value != value.strip()
        or "\n" in value
        or lower_value in _RESERVED_WORDS
        or _NUMERIC_LIKE.match(value)
        or not _PLAIN_SAFE.match(value)
        or ":" in value
        or "#" in value
    )
    if not needs_quote:
        return value
    return json.dumps(value, ensure_ascii=False)


def _scalar_to_yaml(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return "null"
        return str(value)
    return _quote_string(str(value))


def _render_multiline(value: str, indent: int) -> str:
    padding = " " * (indent + 2)
    if value == "":
        return '""'
    return "|\n" + "\n".join(f"{padding}{line}" for line in value.splitlines())


def _to_yaml_lines(value: Any, indent: int = 0) -> list[str]:
    pad = " " * indent

    if isinstance(value, dict):
        if not value:
            return [pad + "{}"]
        lines: list[str] = []
        for key, item in value.items():
            key_text = _quote_string(str(key))
            if isinstance(item, str) and "\n" in item:
                lines.append(f"{pad}{key_text}: {_render_multiline(item, indent)}")
            elif isinstance(item, (dict, list)):
                lines.append(f"{pad}{key_text}:")
                lines.extend(_to_yaml_lines(item, indent + 2))
            else:
                lines.append(f"{pad}{key_text}: {_scalar_to_yaml(item)}")
        return lines

    if isinstance(value, list):
        if not value:
            return [pad + "[]"]
        lines = []
        for item in value:
            if isinstance(item, dict):
                if not item:
                    lines.append(f"{pad}- {{}}")
                    continue
                first = True
                for key, child in item.items():
                    prefix = f"{pad}- " if first else f"{pad}  "
                    key_text = _quote_string(str(key))
                    if isinstance(child, str) and "\n" in child:
                        lines.append(f"{prefix}{key_text}: {_render_multiline(child, indent + 2)}")
                    elif isinstance(child, (dict, list)):
                        lines.append(f"{prefix}{key_text}:")
                        lines.extend(_to_yaml_lines(child, indent + 4))
                    else:
                        lines.append(f"{prefix}{key_text}: {_scalar_to_yaml(child)}")
                    first = False
            elif isinstance(item, list):
                lines.append(f"{pad}-")
                lines.extend(_to_yaml_lines(item, indent + 2))
            else:
                lines.append(f"{pad}- {_scalar_to_yaml(item)}")
        return lines

    return [pad + _scalar_to_yaml(value)]


def to_compact_yaml(payload: Dict[str, Any]) -> str:
    compatible = _coerce_json_compatible(payload)
    return "\n".join(_to_yaml_lines(compatible)).strip() + "\n"


def estimate_tokens(text: str) -> int:
    # Practical approximation for logs only; avoids tokenizer dependency.
    return max(1, math.ceil(len(text) / 4))


def prepare_prompt_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    compatible = _coerce_json_compatible(payload)
    json_payload = json.dumps(compatible, ensure_ascii=False, separators=(",", ":"))
    json_chars = len(json_payload)
    json_tokens = estimate_tokens(json_payload)

    try:
        yaml_payload = to_compact_yaml(compatible)
        yaml_chars = len(yaml_payload)
        yaml_tokens = estimate_tokens(yaml_payload)
        reduction = round((1 - (yaml_chars / json_chars)) * 100, 2) if json_chars else 0
        logger.debug(
            "LLM payload formatting: json_chars=%s yaml_chars=%s json_tokens_est=%s "
            "yaml_tokens_est=%s reduction_pct=%s",
            json_chars,
            yaml_chars,
            json_tokens,
            yaml_tokens,
            reduction,
        )
        return {
            "format": "yaml",
            "text": yaml_payload,
            "json_chars": json_chars,
            "formatted_chars": yaml_chars,
            "json_tokens_est": json_tokens,
            "formatted_tokens_est": yaml_tokens,
            "reduction_pct": reduction,
        }
    except Exception as exc:
        logger.warning("YAML prompt formatting failed; falling back to compact JSON: %s", exc)
        return {
            "format": "json",
            "text": json.dumps(compatible, ensure_ascii=False, indent=2),
            "json_chars": json_chars,
            "formatted_chars": json_chars,
            "json_tokens_est": json_tokens,
            "formatted_tokens_est": json_tokens,
            "reduction_pct": 0,
        }
