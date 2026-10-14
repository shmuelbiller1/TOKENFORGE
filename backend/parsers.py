"""File parsers: turn raw bytes of ANY common format into atomic text fragments.

Every parser returns a list of `Source(name, fragments, kind)` where `kind` is the
content family used to pick the best dedup strategy: prose | tabular | code | log.
Unknown extensions are sniffed from their bytes, ZIP archives are expanded.
"""
from __future__ import annotations

import csv
import email
import io
import json
import re
import zipfile
from dataclasses import dataclass
from email import policy
from typing import Callable, Dict, List

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+(?=[^\s])")
_LINE_PREFIX = re.compile(r"^\s*(?:[-*•·▪◦>]+|#{1,6}|\d+[.)]|[a-zA-Z][.)])\s+")
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
_MD_EMPH = re.compile(r"(\*\*|__|`)(.+?)\1")
_LOG_LINE = re.compile(
    r"^\s*(?:\[?\d{4}-\d{2}-\d{2}|\[?\d{2}/\w{3}/\d{4}|\w{3}\s+\d{1,2}\s\d{2}:\d{2}|\d{2}:\d{2}:\d{2}"
    r"|\[?(?:TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\b)", re.I)
_CODE_HINT = re.compile(
    r"^\s*(?:def |class |import |from \S+ import|function |const |let |var |public |private |"
    r"#include|package |func |fn |return\b|if\s*\(|for\s*\(|}\s*$|{\s*$)")

CODE_EXT = {
    "py", "js", "jsx", "ts", "tsx", "go", "rs", "java", "kt", "c", "h", "cpp", "hpp", "cc", "cs",
    "rb", "php", "swift", "scala", "sh", "bash", "zsh", "ps1", "sql", "r", "lua", "pl", "dart",
    "vue", "svelte", "css", "scss", "less", "toml", "ini", "cfg", "conf", "dockerfile", "makefile",
    "tf", "gradle", "m", "ex", "exs", "hs", "clj", "ipynb_src",
}
MAX_ZIP_MEMBERS = 2000
MAX_ZIP_UNCOMPRESSED = 200 * 1024 * 1024


@dataclass
class Source:
    name: str
    fragments: List[str]
    kind: str


# ----------------------------- text helpers -----------------------------
def _decode(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _clean(line: str) -> str:
    line = line.replace("\u00a0", " ").replace("\u200b", "")
    line = _LINE_PREFIX.sub("", line.strip())
    return re.sub(r"\s+", " ", line).strip()


def split_text(raw: str, min_length: int = 3) -> List[str]:
    """Free text -> clean fragments (lines; very long lines are split by sentence)."""
    out: List[str] = []
    for rawline in raw.splitlines():
        line = _clean(rawline)
        if not line:
            continue
        if len(line) > 240 and _SENTENCE_SPLIT.search(line):
            out.extend(s.strip() for s in _SENTENCE_SPLIT.split(line) if len(s.strip()) >= min_length)
        elif len(line) >= min_length:
            out.append(line)
    return out


def split_code(raw: str, min_length: int = 3) -> List[str]:
    """Source code -> logical blocks separated by blank lines (indentation kept)."""
    blocks, cur = [], []
    for line in raw.splitlines():
        if line.strip():
            cur.append(line.rstrip())
        elif cur:
            blocks.append("\n".join(cur))
            cur = []
    if cur:
        blocks.append("\n".join(cur))
    return [b for b in blocks if len(b.strip()) >= min_length]


def split_log(raw: str, min_length: int = 3) -> List[str]:
    out = []
    for line in raw.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) >= min_length:
            out.append(line)
    return out


# ----------------------------- structured -----------------------------
def _flatten_json(obj, prefix: str = "") -> List[str]:
    rows: List[str] = []
    if isinstance(obj, dict):
        parts, nested = [], []
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list)):
                nested.extend(_flatten_json(v, key))
            else:
                parts.append(f"{k}: {v}")
        if parts:
            rows.append((f"{prefix} | " if prefix else "") + " | ".join(parts))
        rows.extend(nested)
    elif isinstance(obj, list):
        if obj and all(not isinstance(i, (dict, list)) for i in obj):
            rows.append((f"{prefix}: " if prefix else "") + ", ".join(str(i) for i in obj))
        else:
            for item in obj:
                rows.extend(_flatten_json(item, prefix))
    elif obj is not None:
        rows.append(f"{prefix}: {obj}" if prefix else str(obj))
    return rows


def _min(rows: List[str], n: int) -> List[str]:
    return [r for r in rows if len(r) >= n]


def _parse_json(text: str, n: int) -> List[str]:
    return _min(_flatten_json(json.loads(text)), n)


def _parse_jsonl(text: str, n: int) -> List[str]:
    rows: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.extend(_flatten_json(json.loads(line)))
        except ValueError:
            rows.append(line)
    return _min(rows, n)


def _parse_yaml(text: str, n: int) -> List[str]:
    import yaml

    rows: List[str] = []
    for doc in yaml.safe_load_all(text):
        rows.extend(_flatten_json(doc))
    return _min(rows, n)


def _looks_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _table_rows(rows, n: int) -> List[str]:
    out, header = [], None
    for i, cols in enumerate(rows):
        cols = ["" if c is None else str(c).strip() for c in cols]
        if not any(cols):
            continue
        if header is None and i == 0 and any(c and not _looks_numeric(c) for c in cols):
            header = cols
            continue
        if header and len(header) >= len(cols):
            row = " | ".join((f"{h}: {c}" if c else f"{h}:") if h else c for h, c in zip(header, cols)
                             if c or h)
        else:
            row = " | ".join(c for c in cols if c)
        if len(row) >= n:
            out.append(row)
    return out


def _parse_csv(text: str, n: int, delim: str | None = None) -> List[str]:
    if delim is None:
        try:
            delim = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|").delimiter
        except csv.Error:
            delim = ","
    csv.field_size_limit(10 * 1024 * 1024)
    return _table_rows(csv.reader(io.StringIO(text), delimiter=delim), n)


def _parse_xlsx(data: bytes, n: int) -> List[str]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    out: List[str] = []
    for ws in wb.worksheets:
        rows = _table_rows(ws.iter_rows(values_only=True), n)
        out.extend(f"{ws.title} | {r}" if len(wb.worksheets) > 1 else r for r in rows)
    wb.close()
    return out


# ----------------------------- markup -----------------------------
def _html_text(data: bytes | str) -> str:
    import lxml.html

    doc = lxml.html.fromstring(data if data else "<p></p>")
    for bad in doc.xpath("//script|//style|//noscript|//svg|//head"):
        bad.drop_tree()
    for br in doc.xpath("//br|//p|//div|//li|//tr|//h1|//h2|//h3|//h4|//h5|//h6|//section|//article"):
        br.tail = "\n" + (br.tail or "")
    for cell in doc.xpath("//td|//th"):
        cell.tail = " | " + (cell.tail or "")
    return doc.text_content()


def _parse_html(data: bytes, n: int) -> List[str]:
    return _min([f.strip(" |") for f in split_text(_html_text(data), n)], n)


def _parse_xml(data: bytes, n: int) -> List[str]:
    from lxml import etree

    root = etree.fromstring(data, parser=etree.XMLParser(recover=True, huge_tree=True,
                                                          resolve_entities=False, no_network=True))
    if root is None:
        return split_text(_decode(data), n)
    out: List[str] = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        tag = etree.QName(el).localname
        parts = [f"{etree.QName(k).localname}={v}" for k, v in el.attrib.items()]
        txt = (el.text or "").strip()
        if txt:
            parts.append(re.sub(r"\s+", " ", txt))
        if parts:
            line = f"{tag}: " + " | ".join(parts)
            if len(line) >= n:
                out.append(line)
    return out


def _parse_markdown(text: str, n: int) -> List[str]:
    out: List[str] = []
    in_code, code = False, []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            if in_code and code:
                block = "\n".join(code)
                if len(block.strip()) >= n:
                    out.append(block)
            in_code, code = not in_code, []
            continue
        if in_code:
            code.append(line.rstrip())
            continue
        if re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line) and "-" in line:
            continue
        line = _MD_LINK.sub(lambda m: f"{m.group(1)} ({m.group(2)})" if m.group(1) else m.group(2), line)
        line = _MD_EMPH.sub(r"\2", line)
        out.extend(split_text(line.strip().strip("|").replace(" | ", " | "), n))
    return out


def _parse_rtf(text: str, n: int) -> List[str]:
    from striprtf.striprtf import rtf_to_text

    return split_text(rtf_to_text(text, errors="ignore"), n)


def _parse_eml(data: bytes, n: int) -> List[str]:
    msg = email.message_from_bytes(data, policy=policy.default)
    out = [f"{h}: {msg[h]}" for h in ("From", "To", "Cc", "Date", "Subject") if msg[h]]
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is not None:
        content = body.get_content()
        text = _html_text(content.encode("utf-8")) if body.get_content_type() == "text/html" else content
        out.extend(split_text(text, n))
    for part in msg.iter_attachments():
        out.append(f"Attachment: {part.get_filename() or 'unnamed'} ({part.get_content_type()})")
    return _min(out, n)


# ----------------------------- office / pdf -----------------------------
def _parse_pdf(data: bytes, n: int) -> List[str]:
    from pypdf import PdfReader

    out: List[str] = []
    for page in PdfReader(io.BytesIO(data)).pages:
        out.extend(split_text(page.extract_text() or "", n))
    return out


def _parse_docx(data: bytes, n: int) -> List[str]:
    from docx import Document

    doc = Document(io.BytesIO(data))
    out = _min([_clean(p.text) for p in doc.paragraphs], n)
    for table in doc.tables:
        out.extend(_table_rows(([c.text for c in r.cells] for r in table.rows), n))
    return out


def _parse_pptx(data: bytes, n: int) -> List[str]:
    from pptx import Presentation

    out: List[str] = []
    for shape_slide in Presentation(io.BytesIO(data)).slides:
        for shape in shape_slide.shapes:
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    t = _clean("".join(r.text for r in p.runs))
                    if len(t) >= n:
                        out.append(t)
            if getattr(shape, "has_table", False) and shape.has_table:
                out.extend(_table_rows(([c.text for c in r.cells] for r in shape.table.rows), n))
        if shape_slide.has_notes_slide:
            out.extend(split_text(shape_slide.notes_slide.notes_text_frame.text, n))
    return out


def _parse_ipynb(text: str, n: int) -> List[str]:
    nb = json.loads(text)
    out: List[str] = []
    for cell in nb.get("cells", []):
        src = "".join(cell.get("source", []))
        out.extend(split_code(src, n) if cell.get("cell_type") == "code" else _parse_markdown(src, n))
    return out


# ----------------------------- detection -----------------------------
def _ext(name: str) -> str:
    base = name.lower().rsplit("/", 1)[-1]
    if base in ("dockerfile", "makefile"):
        return base
    return base.rsplit(".", 1)[-1] if "." in base else ""


def _sniff_text_kind(text: str) -> str:
    """Return a parser key for text with no/unknown extension."""
    head = text.lstrip()[:4096]
    if head.startswith("{\\rtf"):
        return "rtf"
    if head[:1] in "{[":
        try:
            json.loads(text)
            return "json"
        except ValueError:
            lines = [ln for ln in text.splitlines()[:50] if ln.strip()]
            if lines and all(ln.strip()[:1] in "{[" for ln in lines):
                return "jsonl"
    if head.startswith("<"):
        low = head[:500].lower()
        return "html" if ("<html" in low or "<!doctype html" in low or "<body" in low or "<div" in low) else "xml"
    if re.match(r"(?im)^(from|received|return-path|message-id|mime-version):", head) and re.search(r"(?im)^subject:", head):
        return "eml"
    lines = [ln for ln in text.splitlines()[:200] if ln.strip()]
    if not lines:
        return "txt"
    if sum(bool(_LOG_LINE.match(ln)) for ln in lines) / len(lines) >= 0.5:
        return "log"
    if sum(bool(_CODE_HINT.match(ln)) for ln in lines) / len(lines) >= 0.15:
        return "code"
    if len(lines) >= 3:
        for d in (",", "\t", ";", "|"):
            counts = [ln.count(d) for ln in lines[:50]]
            if counts[0] >= 1 and len(set(counts)) == 1:
                return "csv"
    if re.search(r"(?m)^(#{1,6} |```|\* |- \[)", head):
        return "md"
    return "txt"


_TEXT_PARSERS: Dict[str, tuple[Callable[[str, int], List[str]], str]] = {
    "txt": (split_text, "prose"),
    "md": (_parse_markdown, "prose"),
    "markdown": (_parse_markdown, "prose"),
    "rst": (split_text, "prose"),
    "json": (_parse_json, "tabular"),
    "jsonl": (_parse_jsonl, "tabular"),
    "ndjson": (_parse_jsonl, "tabular"),
    "yaml": (_parse_yaml, "tabular"),
    "yml": (_parse_yaml, "tabular"),
    "csv": (_parse_csv, "tabular"),
    "tsv": (lambda t, n: _parse_csv(t, n, "\t"), "tabular"),
    "log": (split_log, "log"),
    "rtf": (_parse_rtf, "prose"),
    "ipynb": (_parse_ipynb, "code"),
    "code": (split_code, "code"),
}
_BYTE_PARSERS: Dict[str, tuple[Callable[[bytes, int], List[str]], str]] = {
    "pdf": (_parse_pdf, "prose"),
    "docx": (_parse_docx, "prose"),
    "xlsx": (_parse_xlsx, "tabular"),
    "xlsm": (_parse_xlsx, "tabular"),
    "pptx": (_parse_pptx, "prose"),
    "html": (_parse_html, "prose"),
    "htm": (_parse_html, "prose"),
    "xhtml": (_parse_html, "prose"),
    "xml": (_parse_xml, "tabular"),
    "svg": (_parse_xml, "tabular"),
    "eml": (_parse_eml, "prose"),
}

SUPPORTED_EXTENSIONS = sorted(set(_TEXT_PARSERS) - {"code"} | set(_BYTE_PARSERS) | CODE_EXT | {"zip"})


def _zip_office_type(zf: zipfile.ZipFile) -> str | None:
    names = set(zf.namelist())
    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsx"
    if "ppt/presentation.xml" in names:
        return "pptx"
    return None


def _parse_one(data: bytes, name: str, n: int, depth: int = 0) -> List[Source]:
    ext = _ext(name)
    if data[:4] == b"%PDF":
        ext = "pdf"
    elif data[:2] == b"PK" and ext not in ("docx", "xlsx", "xlsm", "pptx"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                office = _zip_office_type(zf)
                if office:
                    ext = office
                elif depth < 2:
                    return _parse_zip(zf, name, n, depth)
        except zipfile.BadZipFile:
            pass

    if ext in _BYTE_PARSERS:
        fn, kind = _BYTE_PARSERS[ext]
        return [Source(name, fn(data, n), kind)]
    if b"\x00" in data[:8192] and data[:2] not in (b"\xff\xfe", b"\xfe\xff"):
        raise ValueError(f"{name}: binary file type is not supported")

    text = _decode(data)
    if ext in CODE_EXT:
        ext = "code"
    elif ext not in _TEXT_PARSERS:
        ext = _sniff_text_kind(text)
        if ext in _BYTE_PARSERS:
            fn, kind = _BYTE_PARSERS[ext]
            return [Source(name, fn(data, n), kind)]
    fn, kind = _TEXT_PARSERS[ext]
    try:
        frags = fn(text, n)
    except Exception:
        frags, kind = split_text(text, n), "prose"
    return [Source(name, frags, kind)]


def _parse_zip(zf: zipfile.ZipFile, name: str, n: int, depth: int) -> List[Source]:
    out: List[Source] = []
    total = 0
    members = [i for i in zf.infolist() if not i.is_dir() and not i.filename.startswith(("__MACOSX/", "."))]
    for info in members[:MAX_ZIP_MEMBERS]:
        total += info.file_size
        if total > MAX_ZIP_UNCOMPRESSED:
            raise ValueError(f"{name}: archive expands beyond {MAX_ZIP_UNCOMPRESSED // 1048576} MB")
        try:
            out.extend(_parse_one(zf.read(info), f"{name}/{info.filename}", n, depth + 1))
        except ValueError:
            continue
    return out


def parse_upload(data: bytes, filename: str, min_length: int = 3) -> List[Source]:
    """Parse any supported file (or ZIP of files) into one or more Sources."""
    return [s for s in _parse_one(data, filename or "input", min_length) if s.fragments]


def parse_text(text: str, min_length: int = 3, kind: str = "auto") -> Source:
    """Parse pasted text; `kind='auto'` sniffs JSON/CSV/log/code/markdown/etc."""
    key = _sniff_text_kind(text) if kind == "auto" else {"prose": "txt", "tabular": "csv"}.get(kind, kind)
    if key in _BYTE_PARSERS:
        fn, k = _BYTE_PARSERS[key]
        return Source("text", fn(text.encode("utf-8"), min_length), k)
    fn, k = _TEXT_PARSERS.get(key, _TEXT_PARSERS["txt"])
    try:
        return Source("text", fn(text, min_length), k)
    except Exception:
        return Source("text", split_text(text, min_length), "prose")
