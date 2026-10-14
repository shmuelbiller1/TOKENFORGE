"""R&D timeline regression tests: no history is folded away or invented."""
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_history import compare_revisions, render_history


def test_three_version_timeline_keeps_changed_numbers_and_review_notes(tmp_path):
    a = tmp_path / "revision_1.txt"
    b = tmp_path / "revision_2.txt"
    c = tmp_path / "revision_3.txt"
    a.write_text("Current: 4 MA\nHold time: 150 microseconds\n", encoding="utf-8")
    b.write_text("Current: 6 MA\nHold time: 30 microseconds\n", encoding="utf-8")
    c.write_text("Current: 8 MA\nHold time: 10 microseconds\n", encoding="utf-8")
    report = compare_revisions(
        [a, b, c], project="R&D feasibility", notes=[
            "Initial hypothesis", "Revised model, pending validation",
            "Later proposal, not experimentally established"
        ]
    )
    assert [v["revision"] for v in report["versions"]] == [1, 2, 3]
    assert [v["researcher_note"] for v in report["versions"]] == [
        "Initial hypothesis", "Revised model, pending validation",
        "Later proposal, not experimentally established"
    ]
    assert len(report["comparisons"]) == 2
    earlier = str(report["comparisons"][0]["changes"])
    later = str(report["comparisons"][1]["changes"])
    assert "4 MA" in earlier and "6 MA" in earlier
    assert "6 MA" in later and "8 MA" in later
    assert "150 microseconds" in earlier and "30 microseconds" in earlier
    assert "30 microseconds" in later and "10 microseconds" in later
    assert report["versions"][0]["sha256"] == hashlib.sha256(a.read_bytes()).hexdigest()
    text = render_history(report)
    assert "pending validation" in text and "10 microseconds" in text
    assert "Scope:" in text


def test_same_extracted_content_different_original_bytes_requires_review(tmp_path):
    # Markdown heading markers disappear during parsing, but source SHA differs.
    a = tmp_path / "v1.md"
    b = tmp_path / "v2.md"
    a.write_text("# Same claim\n", encoding="utf-8")
    b.write_text("Same claim\n", encoding="utf-8")
    pair = compare_revisions([a, b])["comparisons"][0]
    assert pair["changes"] == []
    assert pair["source_bytes_changed"] is True
    assert pair["text_fragments_changed"] is False
    assert pair["changed_source_without_text_change"] is True
    assert "REVIEW REQUIRED" in render_history(compare_revisions([a, b]))


def test_repeated_text_is_not_deduplicated_across_versions(tmp_path):
    a = tmp_path / "one.txt"
    b = tmp_path / "two.txt"
    a.write_text("Repeat paragraph\nRepeat paragraph\nOld assumption 100\n")
    b.write_text("Repeat paragraph\nRepeat paragraph\nNew assumption 101\n")
    r = compare_revisions([a, b])
    assert r["versions"][0]["fragment_count"] == 3
    assert r["versions"][1]["fragment_count"] == 3
    changes = r["comparisons"][0]["changes"]
    assert any("Old assumption 100" in str(c) for c in changes)
    assert any("New assumption 101" in str(c) for c in changes)


def test_same_file_bytes_stay_identical_even_under_distinct_names(tmp_path):
    a = tmp_path / "old.txt"
    b = tmp_path / "new.txt"
    a.write_text("The same calculation and result\n")
    b.write_bytes(a.read_bytes())
    r = compare_revisions([a, b])
    pair = r["comparisons"][0]
    assert not pair["source_bytes_changed"] and not pair["text_fragments_changed"]
    assert pair["changes"] == []


def test_order_is_explicit_not_inferred_from_names_or_timestamps(tmp_path):
    later_named = tmp_path / "2026.txt"
    earlier_named = tmp_path / "2020.txt"
    later_named.write_text("Result changed to 88\n")
    earlier_named.write_text("Earlier estimate 44\n")
    r = compare_revisions([later_named, earlier_named])
    assert [x["filename"] for x in r["versions"]] == ["2026.txt", "2020.txt"]
    assert "Earlier estimate 44" in str(r["comparisons"][0]["changes"])


def test_unicode_and_filename_provenance(tmp_path):
    a = tmp_path / "earlier.txt"
    b = tmp_path / "updated.txt"
    a.write_text("מדידה א: 12\n", encoding="utf-8")
    b.write_text("מדידה א: 15\n", encoding="utf-8")
    r = compare_revisions([a, b])
    assert "15" in render_history(r)
    assert r["comparisons"][0]["changes"][0]["before"][0]["fragment"] == 1


def test_rejects_invalid_inputs_and_does_not_modify_files(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("Initial hypothesis\n")
    b.write_text("Updated hypothesis\n")
    before = [a.read_bytes(), b.read_bytes()]
    with pytest.raises(ValueError, match="2 to"):
        compare_revisions([a])
    with pytest.raises(ValueError, match="note per version"):
        compare_revisions([a, b], notes=["missing"])
    with pytest.raises(ValueError, match="not found"):
        compare_revisions([a, tmp_path / "absent.txt"])
    with pytest.raises(ValueError, match="50 MB"):
        from unittest.mock import patch
        with patch("research_history.MAX_TOTAL_BYTES", 4):
            compare_revisions([a, b])
    compare_revisions([a, b])
    assert [a.read_bytes(), b.read_bytes()] == before


def test_empty_and_unreadable_files_fail_clearly(tmp_path):
    empty = tmp_path / "empty.txt"
    valid = tmp_path / "valid.txt"
    empty.write_bytes(b"")
    valid.write_text("Valid entry\n")
    with pytest.raises(ValueError, match="empty"):
        compare_revisions([valid, empty])
    unknown = tmp_path / "image.bin"
    unknown.write_bytes(b"\x00\x01\x02some binary content")
    with pytest.raises(ValueError, match="not supported"):
        compare_revisions([valid, unknown])
