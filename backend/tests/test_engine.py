"""Engine + parser unit tests (no server needed):  cd backend && pytest tests/test_engine.py -q"""
import io
import json
import random
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optimizer import build_templates, optimize, optimize_sources, reconstruct  # noqa: E402
from parsers import parse_text, parse_upload  # noqa: E402


def _roundtrip(res, frags):
    assert res["stats"]["lossless_verified"] is True
    assert reconstruct(res["records"], res["map"]["record"], res["map"]["original"]) == frags


def test_exact_duplicates_collapse_and_count():
    frags = ["hello world", "Hello, world!", "hello world", "other line"]
    res = optimize(frags)
    assert len(res["records"]) == 2
    assert res["records"][0]["count"] == 3
    _roundtrip(res, frags)


def test_single_slot_template_is_lossless_in_text():
    frags = [f"Order {i} shipped to Berlin" for i in (1041, 1042, 1043)]
    res = optimize(frags)
    assert [r["text"] for r in res["records"]] == ["Order {1041|1042|1043} shipped to Berlin"]
    _roundtrip(res, frags)


def test_multi_slot_template_keeps_pairing():
    lines = build_templates(["10:01 user 5 login", "10:02 user 6 login"])
    assert lines == ["10:{1} user {2} login :: 01|5; 02|6"]


def test_template_pulls_shared_affix_out_of_slot():
    assert build_templates(["at 10:00:09 timeout", "at 10:00:11 timeout"]) == ["at 10:00:{09|11} timeout"]
    assert build_templates(["page /p/1 ok", "page /p/2 ok"]) == ["page /p/{1|2} ok"]


def test_fact_guard_never_hides_numbers():
    frags = ["The invoice total is 120 USD for March billing period",
             "The invoice total is 125 USD for the March billing period now"]
    res = optimize(frags, threshold=0.5)
    text = " ".join(r["text"] for r in res["records"])
    assert "120" in text and "125" in text
    _roundtrip(res, frags)


def test_near_duplicate_superset_folds():
    frags = ["The quick brown fox jumps over the lazy dog",
             "The quick brown fox jumps over the lazy dog today"]
    res = optimize(frags, threshold=0.7)
    assert len(res["records"]) == 1
    assert res["records"][0]["text"].endswith("today")
    _roundtrip(res, frags)


def test_unicode_is_never_dropped():
    frags = ["שלום עולם", "שלום עולם", "你好世界", "Привет мир", "---"]
    res = optimize(frags)
    texts = {r["text"] for r in res["records"]}
    assert texts == {"שלום עולם", "你好世界", "Привет мир", "---"}
    _roundtrip(res, frags)


def test_cross_source_dedup():
    res = optimize_sources([("a.txt", ["shared line here", "only a"], "prose"),
                            ("b.txt", ["shared line here", "only b"], "prose")])
    assert res["stats"]["cross_source_records"] == 1
    assert res["records"][0]["sources"] == [0, 1]


def test_code_blocks_not_templated():
    src = parse_upload(b"def a():\n    return 1\n\ndef b():\n    return 2\n", "x.py")[0]
    assert src.kind == "code"
    res = optimize_sources([src])
    assert all(r["kind"] != "template" for r in res["records"])


def test_random_fuzz_roundtrip():
    rnd = random.Random(3)
    vocab = ["alpha", "beta", "gamma", "delta", "42", "7", "Berlin", "x-1"]
    frags = [" ".join(rnd.choices(vocab, k=rnd.randint(1, 8))) for _ in range(3000)]
    for guard in ("facts", "strict", "off"):
        for order in ("original", "frequency"):
            _roundtrip(optimize_sources([("f", frags, "prose")], threshold=0.6, guard=guard, order=order), frags)


def test_parsers_detect_formats():
    assert parse_text('{"a": 1, "b": [1, 2]}').kind == "tabular"
    assert parse_text("2026-01-01 10:00:00 INFO ok\n2026-01-01 10:00:01 INFO ok").kind == "log"
    assert parse_text("<html><body><p>Hi there</p></body></html>").fragments == ["Hi there"]
    jsonl = "\n".join(json.dumps({"e": i}) for i in range(3))
    assert parse_upload(jsonl.encode(), "x.ndjson")[0].fragments == ["e: 0", "e: 1", "e: 2"]
    assert parse_upload(b"a: 1\nb: [x, y]\n", "c.yaml")[0].fragments == ["a: 1", "b: x, y"]


def test_zip_expands_members():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("one.txt", "hello there\nhello there")
        z.writestr("two.csv", "name,city\nAnn,Rome\nBob,Oslo")
    srcs = parse_upload(buf.getvalue(), "pack.zip")
    assert [s.name for s in srcs] == ["pack.zip/one.txt", "pack.zip/two.csv"]
    assert srcs[1].fragments == ["name: Ann | city: Rome", "name: Bob | city: Oslo"]


def test_binary_rejected():
    try:
        parse_upload(b"\x00\x01\x02binary", "blob.bin")
    except ValueError:
        return
    raise AssertionError("binary input should be rejected")


def test_table_folding_writes_columns_once_and_hoists_constants():
    from optimizer import render
    src = parse_upload(b"id,city,plan\n1,Berlin,pro\n2,Berlin,free\n3,Berlin,pro", "t.csv")
    res = optimize_sources(src)
    assert res["output"]["text"] == "[table id|plan; every row: city=Berlin]\n1|pro\n2|free\n3|pro"
    assert res["stats"]["tables_folded"] == 1
    assert render(res["records"], "text", fold_tables=False).startswith("id: 1 | city: Berlin")
    _roundtrip(res, src[0].fragments)


def test_token_budget_keeps_most_repeated_and_marks_partial():
    frags = ["very common line here"] * 50 + [f"rare unique line number {i} with words" for i in range(200)]
    res = optimize_sources([("f", frags, "prose")], budget=60, templates=False)
    s = res["stats"]
    assert s["tokens_after"] <= 60 and s["output_complete"] is False and s["budget_omitted_records"] > 0
    assert res["output"]["text"].startswith("very common line here")
    _roundtrip(res, frags)
