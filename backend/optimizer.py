"""TokenForge optimizer engine — pure algorithm, no LLM.

Pipeline (each fragment is read once, nothing is ever discarded):
  1. TOKENIZE   count tokens of every fragment (tiktoken cl100k, multi-threaded)
  2. EXACT      collapse fragments with the same normalized key (O(n) hashing)
  3. MINHASH    vectorized MinHash signatures over kind-aware shingles (numpy)
  4. LSH        banded locality-sensitive hashing -> candidate pairs, verified
                against the signature similarity, merged with union-find (O(n))
  5. RESOLVE    per cluster:  a) TEMPLATE  same-shape fragments become one line
                with slots, e.g. "Order {1041|1042|1043} shipped" (lossless)
                b) GUARD  a near-duplicate is folded into a canonical only if
                every fact it carries (numbers, IDs, names) is already present
  6. VERIFY     rebuild the original fragment stream from the reconstruction
                map and assert it is byte-identical -> `lossless_verified`
"""
from __future__ import annotations

import itertools
import re
import time
import zlib
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

ENGINE_VERSION = "2.0"
KINDS = ("prose", "tabular", "code", "log")
MAX_TEMPLATE_ROWS = 64
MAX_SLOTS = 4

_WORD = re.compile(r"-?\d+(?:[.,:/]\d+)*%?|[^\W_]+", re.UNICODE)
_DIGITS = re.compile(r"(?<![^\W\d_])-?\d+(?:[.,:/]\d+)*%?(?![^\W\d_])")
_WS = re.compile(r"\s+")

# ----------------------------- tokens -----------------------------
try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens_batch(texts: Sequence[str]) -> List[int]:
        enc = _ENC.encode_ordinary
        return [len(enc(t)) for t in texts]
except Exception:  # pragma: no cover - offline fallback
    def count_tokens_batch(texts: Sequence[str]) -> List[int]:
        return [max(len(t.split()), len(t) // 4) for t in texts]


def count_tokens(text: str) -> int:
    return count_tokens_batch([text])[0]


# ----------------------------- normalization -----------------------------
def exact_key(text: str, kind: str) -> str:
    if kind == "code":
        return _WS.sub(" ", text).strip()
    toks = _WORD.findall(text.lower())
    return " ".join(toks) if toks else _WS.sub(" ", text).strip().lower()


def shingles(key: str, kind: str) -> List[str]:
    masked = _DIGITS.sub("0", key)
    if kind in ("code", "log") or (" " not in masked and len(masked) > 20):
        k = 5 if kind in ("code", "log") else 3
        if len(masked) <= k:
            return [masked]
        return [masked[i:i + k] for i in range(len(masked) - k + 1)]
    words = masked.split()
    if len(words) < 2:
        return words or [masked]
    return words + [f"{a} {b}" for a, b in zip(words, words[1:])]


def facts(text: str) -> frozenset:
    """Information-bearing tokens: numbers/IDs, plus capitalized names & acronyms."""
    toks = _WORD.findall(text)
    out = set()
    for i, t in enumerate(toks):
        if any(c.isdigit() for c in t) or (i > 0 and any(c.isupper() for c in t)):
            out.add(t.lower())
    return frozenset(out)


def words(text: str) -> frozenset:
    return frozenset(t.lower() for t in _WORD.findall(text))


# ----------------------------- minhash + lsh -----------------------------
_RNG = np.random.default_rng(1337)


def _perm(num_perm: int):
    rng = np.random.default_rng(num_perm)
    a = rng.integers(1, 2**63, size=num_perm, dtype=np.uint64) | np.uint64(1)
    b = rng.integers(0, 2**63, size=num_perm, dtype=np.uint64)
    return a, b


def minhash_signatures(shingle_sets: List[List[str]], num_perm: int) -> np.ndarray:
    n = len(shingle_sets)
    sig = np.empty((n, num_perm), dtype=np.uint32)
    if n == 0:
        return sig
    hashed = [[zlib.crc32(s.encode("utf-8")) for s in set(sh)] for sh in shingle_sets]
    lengths = np.fromiter((len(h) for h in hashed), dtype=np.int64, count=n)
    flat = np.fromiter(itertools.chain.from_iterable(hashed), dtype=np.uint64, count=int(lengths.sum()))
    offsets = np.concatenate([[0], np.cumsum(lengths)])
    a, b = _perm(num_perm)
    chunk = 32768
    start = 0
    while start < n:
        end = int(np.searchsorted(offsets, offsets[start] + chunk, side="right")) - 1
        end = min(max(end, start + 1), n)
        lo, hi = offsets[start], offsets[end]
        h = ((np.outer(flat[lo:hi], a) + b) >> np.uint64(32)).astype(np.uint32)
        sig[start:end] = np.minimum.reduceat(h, offsets[start:end] - lo, axis=0)
        start = end
    return sig


def lsh_params(threshold: float, num_perm: int) -> tuple[int, int]:
    """Pick (bands, rows) minimizing false positives + false negatives at threshold."""
    s = np.linspace(0, 1, 401)
    best, best_err = (num_perm, 1), float("inf")
    for r in range(1, num_perm + 1):
        b = num_perm // r
        p = 1 - (1 - s**r) ** b
        fp = p[s < threshold].sum()
        fn = (1 - p[s >= threshold]).sum()
        err = 0.5 * fp + 0.5 * fn
        if err < best_err:
            best, best_err = (b, r), err
    return best


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def lsh_cluster(sig: np.ndarray, threshold: float, active: np.ndarray, uf: UnionFind) -> UnionFind:
    num_perm = sig.shape[1]
    idx_all = np.flatnonzero(active)
    if len(idx_all) < 2:
        return uf
    bands, rows = lsh_params(threshold, num_perm)
    weights = _RNG.integers(1, 2**62, size=rows, dtype=np.uint64) | np.uint64(1)
    verify_t = threshold * 0.94
    sub = sig[idx_all].astype(np.uint64)
    for band in range(bands):
        keys = (sub[:, band * rows:(band + 1) * rows] * weights).sum(axis=1)
        order = np.argsort(keys, kind="stable")
        sk = keys[order]
        same = sk[1:] == sk[:-1]
        if not same.any():
            continue
        gid = np.cumsum(np.r_[True, ~same])
        counts = np.bincount(gid)
        keep = counts[gid] > 1
        members, mg = order[keep], gid[keep]
        cuts = np.flatnonzero(np.diff(mg)) + 1
        for grp in np.split(members, cuts):
            pending = idx_all[grp]
            rounds = 0
            while len(pending) > 1 and rounds < 8:
                lead, rest = pending[0], pending[1:]
                sim = (sig[rest] == sig[lead]).mean(axis=1)
                for j in rest[sim >= verify_t]:
                    uf.union(int(lead), int(j))
                pending = rest[sim < verify_t]
                rounds += 1
    return uf


# ----------------------------- templates -----------------------------
def _split_affix(values: List[str]) -> tuple[str, List[str], str]:
    """Move the shared prefix/suffix out of a slot, cut at a separator: 10:00:{09|11}."""
    shortest = min(len(v) for v in values)
    p = 0
    while p < shortest - 1 and len({v[p] for v in values}) == 1:
        p += 1
    while p > 0 and values[0][p - 1].isalnum():
        p -= 1
    s = 0
    while s < shortest - p - 1 and len({v[-s - 1] for v in values}) == 1:
        s += 1
    while s > 0 and values[0][-s].isalnum():
        s -= 1
    pre, suf = values[0][:p], values[0][len(values[0]) - s:] if s else ""
    return pre, [v[p:len(v) - s] for v in values], suf


def build_templates(texts: List[str]) -> Optional[List[str]]:
    """Fold same-shape texts into lossless templated lines, or None if not foldable."""
    toks = [t.split() for t in texts]
    length = len(toks[0])
    if length < 2 or any(len(t) != length for t in toks):
        return None
    vary = [p for p in range(length) if len({t[p] for t in toks}) > 1]
    if not vary:
        return None
    spans, cur = [], [vary[0], vary[0]]
    for p in vary[1:]:
        if p == cur[1] + 1:
            cur[1] = p
        else:
            spans.append(tuple(cur))
            cur = [p, p]
    spans.append(tuple(cur))
    constant = length - len(vary)
    if len(spans) > MAX_SLOTS or constant < max(2, length * 0.5):
        return None

    rows = [[" ".join(t[s:e + 1]) for s, e in spans] for t in toks]
    affixes = []
    for k in range(len(spans)):
        pre, core, suf = _split_affix([r[k] for r in rows])
        affixes.append((pre, suf))
        for r, c in zip(rows, core):
            r[k] = c

    def skeleton(slot_fill: List[str]) -> str:
        out, p, k = [], 0, 0
        while p < length:
            if k < len(spans) and p == spans[k][0]:
                pre, suf = affixes[k]
                out.append(f"{pre}{slot_fill[k]}{suf}")
                p = spans[k][1] + 1
                k += 1
            else:
                out.append(toks[0][p])
                p += 1
        return " ".join(out)

    lines = []
    for i in range(0, len(rows), MAX_TEMPLATE_ROWS):
        chunk = rows[i:i + MAX_TEMPLATE_ROWS]
        if len(spans) == 1:
            vals = list(dict.fromkeys(r[0] for r in chunk))
            lines.append(skeleton(["{" + "|".join(vals) + "}"]))
        else:
            tpl = skeleton([f"{{{k + 1}}}" for k in range(len(spans))])
            body = "; ".join("|".join(r) for r in dict.fromkeys(tuple(r) for r in chunk))
            lines.append(f"{tpl} :: {body}")
    return lines


# ----------------------------- main entry -----------------------------
def optimize(fragments: List[str], threshold: float = 0.82, kind: str = "prose", **kw) -> Dict:
    return optimize_sources([("input", fragments, kind)], threshold=threshold, **kw)


def optimize_sources(
    sources: Iterable,
    threshold: float = 0.82,
    mode: str = "auto",
    guard: str = "facts",
    order: str = "original",
    templates: bool = True,
    num_perm: int = 128,
) -> Dict:
    """sources: iterable of (name, fragments, kind) tuples or objects with those attributes."""
    t0 = time.perf_counter()
    timings: Dict[str, float] = {}

    def lap(name: str, since: float) -> float:
        now = time.perf_counter()
        timings[name] = round((now - since) * 1000, 1)
        return now

    src_meta, fragments, frag_src, frag_kind = [], [], [], []
    for s in sources:
        name, frs, k = (s.name, s.fragments, s.kind) if hasattr(s, "fragments") else s
        k = mode if mode in KINDS else (k if k in KINDS else "prose")
        src_meta.append({"name": name, "kind": k, "fragments": len(frs)})
        si = len(src_meta) - 1
        fragments.extend(frs)
        frag_src.extend([si] * len(frs))
        frag_kind.extend([k] * len(frs))
    n = len(fragments)

    # 1. tokenize
    t = time.perf_counter()
    frag_tokens = count_tokens_batch(fragments) if n else []
    tokens_before = sum(frag_tokens)
    t = lap("tokenize", t)

    # 2. exact dedup
    uniq_by_key: Dict[tuple, int] = {}
    uniq: List[dict] = []
    frag_uniq = [0] * n
    for i, (f, k) in enumerate(zip(fragments, frag_kind)):
        key = (k == "code", exact_key(f, k))
        u = uniq_by_key.get(key)
        if u is None:
            u = len(uniq)
            uniq_by_key[key] = u
            uniq.append({"text": f, "key": key[1], "kind": k, "count": 0, "originals": {}, "first": i,
                         "sources": set()})
        e = uniq[u]
        e["count"] += 1
        e["originals"].setdefault(f, len(e["originals"]))
        e["sources"].add(frag_src[i])
        frag_uniq[i] = u
    t = lap("exact", t)

    # 3-4. minhash + lsh near-dup clustering
    m = len(uniq)
    if threshold < 1.0 and m > 1:
        sig = minhash_signatures([shingles(u["key"], u["kind"]) for u in uniq], num_perm)
        t = lap("minhash", t)
        uf = UnionFind(m)
        is_code = np.array([u["kind"] == "code" for u in uniq])
        lsh_cluster(sig, threshold, ~is_code, uf)
        lsh_cluster(sig, max(threshold, 0.92), is_code, uf)
        t = lap("lsh", t)
    else:
        uf = UnionFind(m)
        timings["minhash"] = timings["lsh"] = 0.0

    # 5. resolve clusters -> records
    clusters: Dict[int, List[int]] = {}
    for i in range(m):
        clusters.setdefault(uf.find(i), []).append(i)

    records: List[dict] = []
    uniq_record = [0] * m
    n_templates = values_folded = guard_splits = near_clusters = 0

    def add_record(text: str, members: List[int], rkind: str) -> None:
        rid = len(records)
        records.append({"text": text, "members": members, "rkind": rkind})
        for u in members:
            uniq_record[u] = rid

    for members in clusters.values():
        if len(members) == 1:
            u = members[0]
            add_record(uniq[u]["text"], members, "duplicate" if uniq[u]["count"] > 1 else "unique")
            continue
        near_clusters += 1
        members.sort(key=lambda u: uniq[u]["first"])
        pool: List[int] = []
        if templates:
            by_len: Dict[int, List[int]] = {}
            for u in members:
                if uniq[u]["kind"] == "code":
                    pool.append(u)
                else:
                    by_len.setdefault(len(uniq[u]["text"].split()), []).append(u)
            for grp in by_len.values():
                lines = build_templates([uniq[u]["text"] for u in grp]) if len(grp) > 1 else None
                if not lines:
                    pool.extend(grp)
                    continue
                for ci, line in enumerate(lines):
                    add_record(line, grp[ci * MAX_TEMPLATE_ROWS:(ci + 1) * MAX_TEMPLATE_ROWS], "template")
                    n_templates += 1
                values_folded += len(grp)
        else:
            pool = list(members)

        pool.sort(key=lambda u: -len(uniq[u]["text"]))
        canon: List[tuple] = []
        for u in pool:
            info = words(uniq[u]["text"]) if guard == "strict" else facts(uniq[u]["text"])
            placed = False
            for c in canon[:32]:
                if guard == "off" or info <= c[1]:
                    c[2].append(u)
                    placed = True
                    break
            if not placed:
                if canon:
                    guard_splits += 1
                canon.append((u, info, [u]))
        for head, _, grp in canon:
            add_record(uniq[head]["text"], grp, "near_duplicate" if len(grp) > 1 else
                       ("duplicate" if uniq[head]["count"] > 1 else "unique"))
    t = lap("resolve", t)

    # finalize records (counts, originals, sources, ordering)
    for r in records:
        originals: Dict[str, int] = {}
        for u in sorted(r["members"], key=lambda x: uniq[x]["first"]):
            for o in uniq[u]["originals"]:
                originals.setdefault(o, len(originals))
        r["originals_index"] = originals
        r["count"] = sum(uniq[u]["count"] for u in r["members"])
        r["first_index"] = min(uniq[u]["first"] for u in r["members"])
        r["sources"] = sorted(set().union(*(uniq[u]["sources"] for u in r["members"])))
    rec_tokens = count_tokens_batch([r["text"] for r in records]) if records else []
    for r, tk in zip(records, rec_tokens):
        r["tokens"] = tk

    if order == "frequency":
        perm = sorted(range(len(records)), key=lambda i: (-records[i]["count"], -records[i]["tokens"]))
    else:
        perm = sorted(range(len(records)), key=lambda i: records[i]["first_index"])
    new_id = {old: new for new, old in enumerate(perm)}
    records = [records[i] for i in perm]

    # 6. reconstruction map + verification
    map_record = [new_id[uniq_record[frag_uniq[i]]] for i in range(n)]
    map_original = [records[map_record[i]]["originals_index"][fragments[i]] for i in range(n)]
    out_records = []
    for rid, r in enumerate(records):
        originals = list(r["originals_index"])
        variants = [o for o in originals if o != r["text"]]
        out_records.append({
            "id": rid,
            "text": r["text"],
            "kind": r["rkind"],
            "count": r["count"],
            "tokens": r["tokens"],
            "first_index": r["first_index"],
            "sources": r["sources"],
            "variants": variants[:25],
            "variant_count": len(variants),
            "originals": originals,
        })
    rebuilt_ok = all(out_records[map_record[i]]["originals"][map_original[i]] == fragments[i] for i in range(n))
    lap("verify", t)

    tokens_after = sum(rec_tokens)
    kinds: Dict[str, int] = {}
    for s in src_meta:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + s["fragments"]
    stats = {
        "engine": ENGINE_VERSION,
        "fragments_in": n,
        "raw_chars": sum(len(f) for f in fragments),
        "after_exact_dedup": m,
        "unique_concepts": len(out_records),
        "duplicates_removed": n - len(out_records),
        "dup_reduction_pct": round((1 - len(out_records) / n) * 100, 2) if n else 0.0,
        "tokens_before": tokens_before,
        "tokens_after": tokens_after,
        "tokens_saved": tokens_before - tokens_after,
        "token_reduction_pct": round((1 - tokens_after / tokens_before) * 100, 2) if tokens_before else 0.0,
        "exact_duplicates": n - m,
        "near_dup_clusters": near_clusters,
        "templates": n_templates,
        "values_folded": values_folded,
        "guard_splits": guard_splits,
        "cross_source_records": sum(1 for r in out_records if len(r["sources"]) > 1),
        "lossless_verified": rebuilt_ok,
        "threshold": threshold,
        "mode": mode,
        "guard": guard,
        "order": order,
        "kinds": kinds,
        "sources": src_meta,
        "timings_ms": timings,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
    return {"stats": stats, "records": out_records,
            "map": {"record": map_record, "original": map_original}}


def reconstruct(records: List[dict], map_record: List[int], map_original: List[int]) -> List[str]:
    """Rebuild the exact original fragment stream from records + reconstruction map."""
    return [records[r]["originals"][o] for r, o in zip(map_record, map_original)]


def render(records: List[dict], fmt: str = "text") -> str:
    """LLM-ready rendering: 'text' (one line per record) or 'annotated' (with ×count)."""
    if fmt == "annotated":
        return "\n".join(f"[x{r['count']}] {r['text']}" if r["count"] > 1 else r["text"] for r in records)
    return "\n".join(r["text"] for r in records)
