"""Offline, evidence-first timeline of successive research document versions.

This module does not make scientific judgments. It reports changes in extracted
text, keeps every revision in user-specified order, and preserves raw-file
SHA-256 fingerprints so extraction blind spots remain visible.

The optimizer is intentionally not used: repeated or superseded text must not
be folded across revisions.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from pathlib import Path
from typing import Sequence

MAX_VERSIONS = 100
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_FRAGMENTS_PER_VERSION = 12000
MAX_CHANGE_GROUPS = 30000

SCOPE_NOTICE = (
    "Text-fragment comparison only. Parsing can normalize whitespace and "
    "formatting, omit images, equations stored as images, and other non-text "
    "features. SHA-256 covers each original file; keep the originals. "
    "A changed file with identical extracted text still needs manual review. "
    "Order and revision notes are supplied by the researcher, not inferred. "
    "No claim of correctness, causality, or scientific validation is made."
)


def _load(path: str | Path, note: str) -> tuple[dict, list[tuple[str, int, str]]]:
    from parsers import parse_upload

    source_path = Path(path).expanduser()
    if not source_path.is_file():
        raise ValueError(f"Research file not found: {source_path}")
    data = source_path.read_bytes()
    if not data:
        raise ValueError(f"Research file is empty: {source_path.name}")
    sources = parse_upload(data, source_path.name, min_length=1)
    if not sources:
        raise ValueError(f"No readable text fragments: {source_path.name}")

    rows: list[tuple[str, int, str]] = []
    for source in sources:
        # A ZIP member keeps its relative member name; an ordinary document
        # uses a common key so changing revision filenames does not make every
        # paragraph look different.
        member = source.name
        prefix = source_path.name + "/"
        section = member[len(prefix):] if member.startswith(prefix) else "document"
        for index, fragment in enumerate(source.fragments, 1):
            rows.append((section, index, fragment))
            if len(rows) > MAX_FRAGMENTS_PER_VERSION:
                raise ValueError(
                    f"{source_path.name}: more than {MAX_FRAGMENTS_PER_VERSION} "
                    "text fragments. Split this project into smaller revisions."
                )

    meta = {
        "filename": source_path.name,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "fragment_count": len(rows),
        "researcher_note": note,
    }
    return meta, rows


def _evidence(row: tuple[str, int, str]) -> dict:
    section, ordinal, text = row
    return {"section": section, "fragment": ordinal, "text": text}


def _compare(
    before: list[tuple[str, int, str]], after: list[tuple[str, int, str]]
) -> tuple[list[dict], dict]:
    # Keep duplicate fragments and their relative ordering. An autojunk-enabled
    # matcher stays practical for highly repetitive logs and long manuscripts.
    left = [(section, text) for section, _, text in before]
    right = [(section, text) for section, _, text in after]
    if left == right:
        return [], {"added_fragments": 0, "removed_fragments": 0,
                    "changed_groups": 0}

    matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=True)
    changes: list[dict] = []
    added = removed = 0
    for op, first1, last1, first2, last2 in matcher.get_opcodes():
        if op == "equal":
            continue
        if len(changes) >= MAX_CHANGE_GROUPS:
            raise ValueError(
                "Comparison exceeds the change-group limit; split the project "
                "into smaller version batches."
            )
        previous = [_evidence(item) for item in before[first1:last1]]
        current = [_evidence(item) for item in after[first2:last2]]
        removed += len(previous)
        added += len(current)
        changes.append({
            "kind": {"replace": "modified", "insert": "added",
                     "delete": "removed"}[op],
            "before": previous,
            "after": current,
        })
    return changes, {"added_fragments": added, "removed_fragments": removed,
                     "changed_groups": len(changes)}


_SENTENCE_BREAK = re.compile(r"(?<=[.!?。！？])\\s+(?=\\S)")


def _sentence_segments(fragment: str) -> list[tuple[str, int, int]]:
    """Return exact extracted-text spans at *candidate* sentence boundaries.

    Do not claim linguistic segmentation accuracy: abbreviations, formulas
    and unusual punctuation can fool any punctuation-based segmenter.
    A duplicate is indexed only when all extracted characters are identical.
    """
    result: list[tuple[str, int, int]] = []
    start = 0
    edges = [m.start() for m in _SENTENCE_BREAK.finditer(fragment)]
    for end in edges + [len(fragment)]:
        raw = fragment[start:end]
        first = len(raw) - len(raw.lstrip())
        last = len(raw.rstrip())
        if last > first:
            lo, hi = start + first, start + last
            result.append((fragment[lo:hi], lo, hi))
        start = end
        while start < len(fragment) and fragment[start].isspace():
            start += 1
    return result


def _exact_sentence_candidates(
    rows_by_version: list[list[tuple[str, int, str]]],
) -> dict:
    groups: dict[str, list[dict]] = {}
    for version, rows in enumerate(rows_by_version, 1):
        for section, fragment_number, text in rows:
            for sentence, lo, hi in _sentence_segments(text):
                groups.setdefault(sentence, []).append({
                    "revision": version,
                    "section": section,
                    "fragment": fragment_number,
                    "start_char": lo,
                    "end_char": hi,
                })
    entries = [
        {"text": value, "occurrences": origins}
        for value, origins in groups.items() if len(origins) > 1
    ]
    return {
        "scope": (
            "Only identical Unicode substrings of extracted text are grouped. "
            "Punctuation-based sentence boundaries are candidates, not "
            "verified linguistic sentences. Source fragment and character "
            "offsets are retained. No scientific equivalence is inferred."
        ),
        "repeated_candidates": len(entries),
        "entries": entries,
    }


def _exact_passage_index(
    rows_by_version: list[list[tuple[str, int, str]]],
) -> dict:
    """Index identical *extracted* passages; never equate paraphrases.

    An occurrence always refers back to its original revision, member/section,
    and fragment ordinal. Count duplication only in the displayed index; the
    chronological differences and original files are untouched.
    """
    buckets: dict[str, list[dict]] = {}
    for version, rows in enumerate(rows_by_version, 1):
        for section, fragment, text in rows:
            # Exact Unicode-string equality, with no further case folding,
            # number masking, MinHash, heuristics or semantic equivalence.
            buckets.setdefault(text, []).append({
                "revision": version,
                "section": section,
                "fragment": fragment,
            })
    repeats = [
        {"text": text, "occurrences": occurrences}
        for text, occurrences in buckets.items()
        if len(occurrences) > 1
    ]
    return {
        "scope": (
            "Identical Unicode strings after document text extraction, not "
            "byte-identical original files or verified semantic equivalence. "
            "Formatting removed by parsers is not considered. Changed numbers, "
            "units, words, capitalization or punctuation are not merged."
        ),
        "unique_extracted_passages": len(buckets),
        "repeated_extracted_passages": len(repeats),
        "entries": repeats,
    }


def compare_revisions(
    paths: Sequence[str | Path], *,
    project: str = "Research project",
    notes: Sequence[str] | None = None,
) -> dict:
    """Compare 2–100 supplied files in precisely the order supplied.

    No filesystem timestamps or filenames are used to infer chronology.
    Revision notes are verbatim researcher-supplied evidence, not AI analysis.
    Input files are read but never modified. Nothing is transmitted online.
    """
    if not 2 <= len(paths) <= MAX_VERSIONS:
        raise ValueError(f"Select 2 to {MAX_VERSIONS} ordered research versions.")
    if notes is not None and len(notes) != len(paths):
        raise ValueError("Provide one note per version, or omit notes.")
    clean_notes = list(notes) if notes is not None else [""] * len(paths)
    if any(not isinstance(n, str) for n in clean_notes):
        raise ValueError("Revision notes must be text.")

    versions: list[dict] = []
    comparisons: list[dict] = []
    total_bytes = 0
    prior_rows: list[tuple[str, int, str]] | None = None
    all_rows: list[list[tuple[str, int, str]]] = []
    for index, (path, note) in enumerate(zip(paths, clean_notes), 1):
        path = Path(path).expanduser()
        if not path.is_file():
            raise ValueError(f"Research file not found: {path}")
        total_bytes += path.stat().st_size
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("Research versions exceed 50 MB combined; split into batches.")
        meta, rows = _load(path, note)
        meta["revision"] = index
        all_rows.append(rows)
        versions.append(meta)
        if prior_rows is not None:
            changes, counts = _compare(prior_rows, rows)
            prev = versions[-2]
            comparisons.append({
                "from_revision": index - 1,
                "to_revision": index,
                "from_sha256": prev["sha256"],
                "to_sha256": meta["sha256"],
                "source_bytes_changed": prev["sha256"] != meta["sha256"],
                "text_fragments_changed": bool(changes),
                "changed_source_without_text_change": (
                    prev["sha256"] != meta["sha256"] and not changes
                ),
                "researcher_note": note,
                "stats": counts,
                "changes": changes,
            })
        prior_rows = rows
    return {
        "schema": "tokenforge.research-history.v1",
        "project": str(project).strip() or "Research project",
        "comparison_scope": SCOPE_NOTICE,
        "versions": versions,
        "comparisons": comparisons,
        "exact_repetitions": _exact_passage_index(all_rows),
        "exact_sentence_candidates": _exact_sentence_candidates(all_rows),
    }


def render_history(report: dict) -> str:
    """Human-readable report; no content is hidden or abbreviated."""
    lines = [
        f"RESEARCH EVOLUTION: {report['project']}",
        f"Scope: {report['comparison_scope']}",
        "",
        "VERSIONS (oldest to newest, in the order you supplied):",
    ]
    for v in report["versions"]:
        lines.append(
            f"  {v['revision']}. {v['filename']} | {v['fragment_count']} "
            f"fragments | SHA-256 {v['sha256']}"
        )
        if v["researcher_note"]:
            lines.append(f"     Researcher note: {v['researcher_note']}")
    repetition = report["exact_repetitions"]
    lines.extend([
        "",
        "EXACT REPEATED EXTRACTED PASSAGES (shared display, original occurrences kept):",
        repetition["scope"],
        f"  {repetition['repeated_extracted_passages']} repeated passages; "
        f"{repetition['unique_extracted_passages']} distinct passages",
    ])
    for entry in repetition["entries"]:
        location = ", ".join(
            f"v{o['revision']} {o['section']} #{o['fragment']}"
            for o in entry["occurrences"]
        )
        lines.append(f"  {entry['text']}  [appears at: {location}]")
    sentences = report["exact_sentence_candidates"]
    lines.extend([
        "",
        "EXACT REPEATED SENTENCE CANDIDATES (inside extracted paragraphs):",
        sentences["scope"],
        f"  {sentences['repeated_candidates']} repeated exact segments",
    ])
    for entry in sentences["entries"]:
        positions = ", ".join(
            f"v{o['revision']} {o['section']} fragment {o['fragment']} "
            f"chars {o['start_char']}:{o['end_char']}"
            for o in entry["occurrences"]
        )
        lines.append(f"  {entry['text']}  [occurs at: {positions}]")
    for comparison in report["comparisons"]:
        st = comparison["stats"]
        lines.extend([
            "",
            f"REVISION {comparison['from_revision']} -> {comparison['to_revision']}: "
            f"{st['changed_groups']} change groups, "
            f"{st['removed_fragments']} prior fragments, "
            f"{st['added_fragments']} new fragments",
        ])
        if comparison["researcher_note"]:
            lines.append(f"  Researcher explanation: {comparison['researcher_note']}")
        if comparison["changed_source_without_text_change"]:
            lines.append("  REVIEW REQUIRED: Original bytes differ but extracted text is identical.")
        elif not comparison["source_bytes_changed"]:
            lines.append("  Original file bytes are identical.")
        for change in comparison["changes"]:
            lines.append(f"  {change['kind'].upper()}:")
            for entry in change["before"]:
                lines.append(f"    - [{entry['section']} fragment {entry['fragment']}] {entry['text']}")
            for entry in change["after"]:
                lines.append(f"    + [{entry['section']} fragment {entry['fragment']}] {entry['text']}")
    return "\n".join(lines) + "\n"
