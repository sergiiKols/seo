#!/usr/bin/env python3
"""
AI-pattern remover. Rewrites filler / AI-typical phrasings into
direct prose. Deterministic 1:1 swap.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_REPLACEMENTS: tuple[tuple[str, str, str], ...] = (
    (r"\bdelve\s+deeper\s+into\b", "explore", "delve-deeper-into"),
    (r"\bdelve\s+into\b", "explore", "delve-into"),
    (r"\bin\s+the\s+ever-evolving\s+landscape\s+of\b", "in", "ever-evolving-landscape"),
    (r"\bin\s+the\s+ever-evolving\s+world\s+of\b", "in", "ever-evolving-world"),
    (r"\bever-evolving\b", "changing", "ever-evolving"),
    (r"\bever-changing\b", "changing", "ever-changing"),
    (r"\bnavigating\s+the\s+complexities\s+of\b", "handling", "navigating-complexities"),
    (r"\btapestry\s+of\b", "range of", "tapestry-of"),
    (r"\b(rich|intricate|complex)\s+tapestry\b", "range", "rich-tapestry"),
    (r"\bembark\s+on\s+a\s+journey\b", "begin", "embark-journey"),
    (r"\ba\s+testament\s+to\b", "evidence of", "testament-to"),
    (r"\ba\s+beacon\s+of\b", "a leader in", "beacon-of"),
    (r"\b(the\s+|a\s+)?cornerstone\s+of\b", "central to", "cornerstone-of"),
    (r"\bat\s+the\s+heart\s+of\b", "central to", "at-the-heart-of"),
    (r"\bin\s+essence,\s*", "", "in-essence"),
    (r"\bin\s+conclusion,\s*", "", "in-conclusion"),
    (r"\bultimately,\s*", "", "ultimately-comma"),
    (r"\bmoreover,\s*", "", "moreover-comma"),
    (r"\bfurthermore,\s*", "", "furthermore-comma"),
    (r"\bhowever,\s+it'?s\s+worth\s+noting\s+that\b", "however,", "worth-noting-clause"),
    (r"\bit'?s\s+worth\s+noting\s+that\b", "note:", "worth-noting"),
    (r"\bby\s+leveraging\b", "by using", "by-leveraging"),
    (r"\bleverage\s+the\s+power\s+of\b", "use", "leverage-power"),
    (r"\bleveraging\s+the\s+power\s+of\b", "using", "leveraging-power"),
    (r"\bharness\s+the\s+power\s+of\b", "use", "harness-power"),
    (r"\bunlock\s+(?:the\s+(?:full\s+)?)?potential\b", "use", "unlock-potential"),
    (r"\bopen\s+up\s+a\s+world\s+of\b", "enable", "open-world"),
    (r"\ba\s+world\s+of\s+possibilities\b", "options", "world-possibilities"),
    (r"\belevate\s+your\b", "improve your", "elevate-your"),
    (r"\btransform\s+your\b", "improve your", "transform-your"),
    (r"\brevolutionize\s+the\s+way\b", "change how", "revolutionize-the-way"),
    (r"\bgame-?changer\b", "important", "game-changer"),
    (r"\bcutting-?edge\b", "modern", "cutting-edge"),
    (r"\bstate-of-the-art\b", "modern", "state-of-the-art"),
    (r"\bin\s+summary,\s*", "", "in-summary"),
    (r"\bto\s+summarize,\s*", "", "to-summarize"),
    (r"\bto\s+put\s+it\s+simply,\s*", "", "to-put-simply"),
    (r"\bin\s+a\s+nutshell,\s*", "", "in-nutshell"),
    (r"\bit'?s\s+important\s+to\s+note\s+that\b", "note:", "important-note"),
    (r"\bin\s+today'?s\s+(fast-paced|digital|competitive)\s+(world|age|landscape)\b", "today", "today-cliche"),
    (r"\bneedless\s+to\s+say,?\s*", "", "needless-to-say"),
    (r"\bat\s+the\s+end\s+of\s+the\s+day\b", "ultimately", "end-of-the-day"),
    (r"\bwhen\s+it\s+comes\s+to\b", "for", "when-it-comes-to"),
    (r"\bfirst\s+and\s+foremost,?\s*", "first,", "first-and-foremost"),
    (r"\blast\s+but\s+not\s+least,?\s*", "finally,", "last-but-not-least"),
    (r"\blet'?s\s+dive\s+(in|into)\b", "starting with", "let-us-dive"),
    (r"\blet'?s\s+take\s+a\s+(closer|deeper)\s+look\b", "look at", "let-us-take-look"),
)

_PATTERNS = [(re.compile(p, re.IGNORECASE), repl, label) for p, repl, label in _REPLACEMENTS]

def _preserve_case(match_text: str, replacement: str) -> str:
    if not replacement: return ""
    if match_text and match_text[0].isupper() and not replacement[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement

def humanize(text: str) -> dict:
    changes = []
    cleaned = text
    for pattern, replacement, label in _PATTERNS:
        def _repl(match):
            original = match.group(0)
            new = _preserve_case(original, replacement)
            changes.append({"label": label, "from": original, "to": new})
            return new
        cleaned = pattern.sub(_repl, cleaned)
    cleaned = re.sub(r"  +", " ", cleaned)
    cleaned = re.sub(r" ([,.;:!?])", r"\1", cleaned)
    return {"cleaned": cleaned, "changes": changes, "change_count": len(changes)}

def main():
    parser = argparse.ArgumentParser(description="AI-pattern remover.")
    parser.add_argument("source", nargs="?", default="-")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    text = sys.stdin.read() if args.source == "-" else Path(args.source).read_text(encoding="utf-8")
    result = humanize(text)
    if args.json:
        json.dump(result, sys.stdout, indent=2)
    else:
        sys.stdout.write(result["cleaned"])

if __name__ == "__main__":
    main()
