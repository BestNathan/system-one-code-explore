#!/usr/bin/env python3
"""Full-read Claude relevance-field baseline utilities."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_WINDOW_LINES = 64
DEFAULT_STRIDE_LINES = 32
ROLES = {"core", "supporting", "context", "incidental", "irrelevant"}
CONTINUITY = {"self_contained", "requires_left", "requires_right", "requires_both"}


def numbered_source(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    source = "\n".join(f"{i}: {line}" for i, line in enumerate(lines, 1))
    return source, len(lines)


def canonical_ranges(line_count, window_lines=64, stride_lines=32):
    if line_count <= 0:
        return []
    ranges = []
    start = 1
    index = 0
    while start <= line_count:
        end = min(line_count, start + window_lines - 1)
        ranges.append({
            "id": f"r{index + 1:04d}",
            "start_line": start,
            "end_line": end,
        })
        index += 1
        if end == line_count:
            break
        start += max(1, stride_lines)
    return ranges


def build_prompt(path, query, source, line_count, ranges):
    range_json = json.dumps(ranges, indent=2, ensure_ascii=False)
    return f"""You are building a reference relevance field for code localization.

Task:
{query}

The COMPLETE target file is supplied below. Treat every line as already read.
Do not explore only individual ranges. Use the full file context before scoring.

Score every canonical range from 0 to 1 for how materially it contributes to
the task. A range may be highly relevant even if it is only a fragment of a
larger function; use continuity to record that fact.

Role: one of core, supporting, context, incidental, irrelevant.
Continuity: one of self_contained, requires_left, requires_right, requires_both.

Return ONLY JSON. Return every range exactly once and preserve its geometry.

Shape:
{{
  "schema_version": 1,
  "kind": "claude-full-read-relevance-field",
  "task": {json.dumps(query)},
  "path": {json.dumps(path)},
  "line_count": {line_count},
  "window_lines": 64,
  "stride_lines": 32,
  "full_read": true,
  "ranges": [
    {{
      "id": "r0001",
      "start_line": 1,
      "end_line": 64,
      "relevance": 0.0,
      "role": "core",
      "continuity": "self_contained",
      "reason": "brief evidence-based rationale"
    }}
  ]
}}

Canonical ranges:
{range_json}

FULL SOURCE:
--- BEGIN ---
{source}
--- END ---
"""


def extract_json(text):
    text = text.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for i, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("Claude output did not contain a JSON object")
