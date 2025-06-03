"""
Module: toc_utils.py
Purpose: Robust, modular Table of Contents (ToC) generation logic for Marknote.

Import flow:
- toc_utils.py is standalone and does not import from ai.py or other app modules.
- UI and main application modules should import toc_utils.py for ToC features.

Usage:
- Use extract_headings(markdown_text, max_depth) to get headings.
- Use format_toc(headings) to get a markdown ToC string.
- Anchor generation matches GitHub/standard markdown (lowercase, hyphens, strip punctuation).
"""

import re
from typing import List, Dict

def extract_headings(markdown_text: str, max_depth: int = 3) -> List[Dict]:
    """
    Extract headings from markdown text up to max_depth.
    Returns a list of dicts: {level, text, anchor}
    Defensive: skips empty/invalid lines.
    """
    headings = []
    for line in markdown_text.splitlines():
        match = re.match(r'^(#{1,%d})\s+(.+)' % max_depth, line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            if not text:
                continue
            anchor = generate_anchor(text)
            headings.append({'level': level, 'text': text, 'anchor': anchor})
    return headings

def generate_anchor(text: str) -> str:
    """
    Generate a GitHub-style anchor from heading text.
    Lowercase, replace spaces with hyphens, strip most punctuation.
    """
    anchor = text.strip().lower()
    anchor = re.sub(r'[\s]+', '-', anchor)  # spaces to hyphens
    anchor = re.sub(r'[^a-z0-9\-]', '', anchor)  # remove non-alphanum except hyphen
    return anchor

def format_toc(headings: List[Dict], style: str = 'default') -> str:
    """
    Format headings as a markdown ToC. Default: bulleted, with links.
    Defensive: returns empty string if no headings.
    """
    if not headings:
        return ''
    lines = []
    for h in headings:
        indent = '  ' * (h['level'] - 1)
        lines.append(f"{indent}- [{h['text']}](#{h['anchor']})")
    return '\n'.join(lines)