#!/usr/bin/env python3
"""TokenForge CLI — run the optimizer locally, no server or database needed.

  python cli.py optimize data.csv logs.zip -f annotated -o optimized.txt
  python cli.py optimize notes.md -f bundle -o bundle.json      # lossless bundle
  python cli.py reconstruct bundle.json -o original.txt         # rebuild originals
  python cli.py optimize export.csv -b 4000                     # fit into a 4k-token budget
  cat file.txt | python cli.py optimize -                       # stdin
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from optimizer import KINDS, optimize_sources, reconstruct
from parsers import parse_text, parse_upload


def _write(text: str, out: str | None) -> None:
    if out:
        Path(out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text + ("" if text.endswith("\n") else "\n"))


def cmd_optimize(a: argparse.Namespace) -> int:
    sources = []
    for p in a.inputs:
        if p == "-":
            sources.append(parse_text(sys.stdin.read(), a.min_length, a.mode))
        else:
            sources.extend(parse_upload(Path(p).read_bytes(), Path(p).name, a.min_length))
    sources = [s for s in sources if s.fragments]
    if not sources:
        print("error: no readable text fragments found", file=sys.stderr)
        return 1
    res = optimize_sources(sources, threshold=a.threshold, mode=a.mode, guard=a.guard, order=a.order,
                           fold_tables=not a.no_fold, budget=a.budget)
    s = res["stats"]
    print(f"[tokenforge] {s['fragments_in']:,} fragments -> {s['unique_concepts']:,} records | "
          f"tokens {s['tokens_before']:,} -> {s['tokens_after']:,} (-{s['token_reduction_pct']}%) | "
          f"templates {s['templates']} | tables {s['tables_folded']} | lossless {s['lossless_verified']} | {s['elapsed_ms']} ms",
          file=sys.stderr)
    if a.format in ("text", "annotated"):
        _write(res["output"]["annotated" if a.format == "annotated" else "text"], a.out)
    else:
        payload = {"stats": s, "records": res["records"] if a.format == "bundle" else
                   [{k: v for k, v in r.items() if k != "originals"} for r in res["records"]]}
        if a.format == "bundle":
            payload["map"] = res["map"]
        _write(json.dumps(payload, ensure_ascii=False, indent=1), a.out)
    return 0


def cmd_reconstruct(a: argparse.Namespace) -> int:
    b = json.loads(Path(a.bundle).read_text(encoding="utf-8"))
    if "map" not in b:
        print("error: not a bundle (export with -f bundle / format=bundle)", file=sys.stderr)
        return 1
    _write("\n".join(reconstruct(b["records"], b["map"]["record"], b["map"]["original"])), a.out)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="tokenforge", description="Pure-algorithm LLM token optimizer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("optimize", help="dedup + compress files")
    o.add_argument("inputs", nargs="+", help="files, ZIP archives, or - for stdin")
    o.add_argument("-t", "--threshold", type=float, default=0.82, help="near-dup similarity 0.5-1.0")
    o.add_argument("-m", "--mode", default="auto", choices=("auto",) + KINDS)
    o.add_argument("-g", "--guard", default="facts", choices=("facts", "strict", "off"))
    o.add_argument("--order", default="original", choices=("original", "frequency"))
    o.add_argument("--min-length", type=int, default=3)
    o.add_argument("-b", "--budget", type=int, help="fit output into N tokens (keeps most repeated first)")
    o.add_argument("--no-fold", action="store_true", help="disable table folding")
    o.add_argument("-f", "--format", default="text", choices=("text", "annotated", "json", "bundle"))
    o.add_argument("-o", "--out")
    o.set_defaults(fn=cmd_optimize)
    r = sub.add_parser("reconstruct", help="rebuild the original fragments from a bundle")
    r.add_argument("bundle")
    r.add_argument("-o", "--out")
    r.set_defaults(fn=cmd_reconstruct)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
