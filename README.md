# TokenForge

**Cut LLM token costs without losing information.** TokenForge is an open-source, pure-algorithm (no LLM) ingestion optimizer. It reads almost any file, keeps each piece of data once, folds repeating patterns into lossless templates, and outputs a token-minimized dataset that is ready to paste into a prompt, a RAG index or a fine-tuning set.

Each job also checks that the full original input can be rebuilt from the output.

```text
INPUT  9 log lines · 193 tokens
2026-06-01 10:00:01 INFO user 17 logged in from 10.0.0.17
2026-06-01 10:00:02 INFO user 18 logged in from 10.0.0.18
2026-06-01 10:00:05 WARN cache miss for key session:17
2026-06-01 10:00:07 INFO user 21 logged in from 10.0.0.21
2026-06-01 10:00:09 ERROR payment gateway timeout after 30s
2026-06-01 10:00:11 ERROR payment gateway timeout after 30s
2026-06-01 10:00:12 WARN cache miss for key session:21
2026-06-01 10:00:15 INFO healthcheck ok
2026-06-01 10:00:20 INFO healthcheck ok

OUTPUT  4 records · 125 tokens (-35%) · lossless_verified: true
2026-06-01 10:00:{1} INFO user {2} logged in from 10.0.0.{3} :: 01|17|17; 02|18|18; 07|21|21
2026-06-01 10:00:{1} WARN cache miss for key session:{2} :: 05|17; 12|21
2026-06-01 10:00:{09|11} ERROR payment gateway timeout after 30s
2026-06-01 10:00:{15|20} INFO healthcheck ok
```
Every timestamp, user ID and IP is still in the output, and on real logs and exports the savings grow with size (typically 50–95 %).

---

**To run TokenForge without programming:** Download the correct application archive from [GitHub Releases](https://github.com/shmuelbiller1/TOKENFORGE/releases), **not** the automatically generated Source code ZIP/tar.gz. See the [offline installation guide](docs/OFFLINE_DESKTOP.md).

**Offline desktop:** see [download/build instructions](docs/OFFLINE_DESKTOP.md). The desktop app requires no account, database, or cloud connection. Security review: [public release checklist](docs/PUBLIC_RELEASE_CHECKLIST.md).

## Table of contents
- [Why](#why)
- [Features](#features)
- [How it works](#how-it-works)
- [Guarantees (and what “lossless” means exactly)](#guarantees)
- [Supported formats](#supported-formats)
- [Quick start](#quick-start)
- [CLI (no server needed)](#cli)
- [REST API](#rest-api)
- [Settings](#settings)
- [Export formats](#export-formats)
- [Performance](#performance)
- [Architecture](#architecture)
- [Tests](#tests)
- [Self-hosting & security checklist](#self-hosting--security-checklist)
- [Roadmap](#roadmap)
- [License](#license)

---

## Why
Real data repeats itself: logs print the same line with a new timestamp, exports repeat rows, documents get copied and lightly edited, catalogs differ only by SKU and price. You pay for every one of those tokens.

Common fixes don't hold up:
- **Exact dedup** misses near-duplicates.
- **Summarizing with an LLM** costs money, is not deterministic, and can silently drop facts.
- **Plain fuzzy matching** is O(n²) and merges lines that differ in the one number that matters.

TokenForge is linear-time, deterministic and audit-friendly. It never hides a value unless you tell it to.

## Features
| | |
|---|---|
| **Exact dedup** | Unicode-aware normalization (case, punctuation, spacing) with numbers kept intact, using O(n) hashing |
| **Near-dup detection** | Vectorized 128-permutation MinHash + banded LSH tuned to your threshold. Every candidate pair is verified, then merged with union-find |
| **Lossless templates** | Same-shape lines become `Order {1041\|1042\|1043} shipped`. Multi-slot templates keep the values of each row together: `10:{1} user {2} login :: 01\|5; 02\|6` |
| **Table folding** | CSV/XLSX/JSON/JSONL/YAML rows are written as a table with the column names once, and columns that never change are moved into the header (`[table id\|plan; every row: city=Berlin]`). This is the biggest token saver on structured data (often 80–95 %) |
| **Token budget** | `budget=4000` fits the output into N tokens. The most repeated records are kept first and the cut is stated in the output, while the map still holds everything |
| **Instant cache** | Re-uploading identical content with the same settings returns the earlier result in ~0 ms (per user for jobs, in-memory LRU for the API) |
| **Fact Guard** | A near-duplicate is folded only if every number/ID/name it holds is already in the kept line (`facts`), or every word (`strict`) |
| **Content-aware modes** | Word shingles for prose and tables, character 5-grams for logs and code. Code blocks are never templated and need ≥ 0.92 similarity |
| **Multi-file & ZIP** | Files in one job are deduplicated against each other, and each record lists the files it came from |
| **Reconstruction map** | Stores (record, original) for every input fragment. You can rebuild the input via the UI, API or CLI |
| **Round-trip verification** | Each run rebuilds its input and sets `lossless_verified` |
| **Accounts, API keys, admin** | Email/password (JWT httpOnly cookies, bcrypt), per-user hashed API keys, owner console |
| **Shareable reports** | Public link with stats and an output preview. The owner can turn it off at any time, and originals and the map are never exposed |
| **Usage analytics** | Tokens saved and runs per day for each user and each API key, plus an owner-wide chart and top savers |
| **Keyboard shortcuts** | `?` shows the list; `g d/k/h/a` navigate, `u` upload, `Enter` start, `/` search, `c` copy, `e` export, `r` rebuild, `s` share, `⌘/Ctrl+Enter` run the playground |
| **Playground** | `/how-it-works` lets anyone paste text and watch the engine run, no signup needed |
| **CLI** | `backend/cli.py` runs the same engine offline |

## How it works
```
 files ─► PARSE ─► TOKENIZE ─► EXACT ─► MINHASH ─► LSH+VERIFY ─► RESOLVE ─────────────► VERIFY ─► records + map
          (any     (cl100k)    (hash)   (numpy)    (bands,       ├─ TEMPLATE same shape   (rebuild
          format)                                   union-find)   └─ FACT GUARD the rest   == input?)
```
1. **Parse**: each file becomes atomic *fragments*: lines/sentences (prose), one fragment per row (`col: value | col: value`) for CSV/XLSX/JSON/YAML/XML, one per entry for logs, blank-line-separated blocks for code. Unknown extensions are detected from their bytes, and ZIPs are expanded.
2. **Tokenize**: every fragment is counted with `tiktoken` `cl100k_base`, so savings are in real tokens.
3. **Exact dedup**: the normalized key collapses `Hello, world!` and `hello world`. Every distinct spelling is kept as an *original*.
4. **MinHash**: kind-aware shingles. Standalone numbers are masked, so `user 17 logged in` and `user 18 logged in` look identical to the hasher. Signatures are computed in vectorized numpy chunks.
5. **LSH + verify**: bands × rows are chosen to minimize false positives and negatives at your threshold. Only fragments that share a bucket get compared, and each pair is checked against signature similarity before merging.
6. **Resolve** each cluster:
   - **Template**: members with the same token length and at most 4 varying spans (≥ 50 % constant tokens) become one line. All values are written into it, up to 64 rows per template line.
   - **Fact Guard**: everything else folds into the longest member, but only if its facts are a subset of that member's. Otherwise it stays a separate record.
7. **Verify**: rebuild `originals[map]` and compare it to the input stream.
8. **Render**: tabular records with the same columns are folded into one table, constant columns are hoisted, and the optional token budget is applied. `tokens_after` is measured on this final text.

### Design decisions (why this approach)
The goal is the fewest tokens an LLM must read while it can still answer any question the raw data could answer. That rules some things out and points to others:

| Option | Verdict |
|---|---|
| LLM summarization | ✗ Costs tokens to save tokens, isn't deterministic, and can invent or drop facts |
| Embedding/semantic dedup | ✗ as default: needs a model, and "semantically similar" lines can still hold different facts. Possible later as an opt-in |
| gzip/base64 or other byte compression | ✗ LLMs can't read it, and it often *raises* token counts |
| Exact + MinHash/LSH dedup | ✓ Linear time, and handles the most common waste (repeated lines) |
| **Structure-aware rewriting** (templates, table folding, constant hoisting) | ✓ The biggest win: it removes repeated *structure* rather than repeated lines, while every value stays readable |
| Reconstruction map + verification | ✓ Makes "no data loss" testable instead of a promise |

Order of savings on typical data: **table folding > templates > exact dedup > near-dup folding**.

## Guarantees
- **Nothing is dropped.** Every input fragment maps to exactly one record and one stored original (`/reconstruct`, `format=bundle`, `cli.py reconstruct`).
- **Values stay visible.** Templates write every distinct value into the optimized text. Under the default guard, no number, ID or name disappears from the LLM-facing text.
- **Deterministic.** The same input and settings always give the same output.

**What “lossless” covers, exactly:** the stream of fragments *after parsing*, not the original file bytes. Parsing trims leading and trailing whitespace, list bullets and markup (HTML tags, Markdown emphasis). It extracts the text of PDF/Office files (not images or styling) and skips fragments shorter than `min_length` (default 3). With `guard=off`, near-duplicate variants appear only in the map, not in the optimized text.

## Supported formats
| Family | Formats |
|---|---|
| Documents | `.txt` `.md` `.rst` `.rtf` `.pdf` `.docx` `.pptx` `.html` `.htm` `.eml` |
| Data | `.csv` `.tsv` (delimiter sniffed) `.xlsx` `.xlsm` `.json` `.jsonl` `.ndjson` `.yaml` `.yml` `.xml` `.svg` |
| Logs | `.log`, or any text where ≥ 50 % of lines start with a timestamp or level |
| Code | `py js jsx ts tsx go rs java kt c h cpp cs rb php swift scala sh sql r lua dart vue svelte css scss toml ini …` + `.ipynb` |
| Archives | `.zip` (nested up to 2 levels, 2,000 members, 200 MB uncompressed) |
| Unknown | Sniffed: PDF/Office signatures, JSON, JSONL, HTML/XML, e-mail, CSV, logs, code, Markdown, plain text |

Encodings: UTF-8 (with or without BOM), UTF-16, and a CP-1252 fallback.

## Quick start

### Docker (one command)
```bash
git clone https://github.com/shmuelbiller1/TOKENFORGE.git && cd TOKENFORGE
cp .env.docker.example .env        # REQUIRED: replace secrets with unique values
docker compose up -d --build       # → http://localhost:8080
```
Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`. nginx serves the UI and proxies `/api` to the backend, and MongoDB data lives in the `mongo-data` volume. Cookies are `Secure`, which browsers allow on `http://localhost`. On any other host, put HTTPS in front (Caddy, Traefik or a cloud load balancer).

### Manual
Requirements: Python 3.11+, Node 18+ with Yarn, MongoDB 6+.

```bash
git clone https://github.com/shmuelbiller1/TOKENFORGE.git && cd TOKENFORGE

# backend
cd backend
cp .env.example .env            # then edit the secrets
pip install -r requirements-core.txt
uvicorn server:app --host 0.0.0.0 --port 8001

# frontend (new terminal)
cd frontend
cp .env.example .env            # REACT_APP_BACKEND_URL=http://localhost:8001
yarn install && yarn start      # http://localhost:3000
```
The owner account from `ADMIN_EMAIL` / `ADMIN_PASSWORD` is created on first start. All API routes live under `/api`.

## CLI
Same engine, no server, no database:
```bash
cd backend
python cli.py optimize data.csv logs.zip notes.md -f annotated -o optimized.txt
python cli.py optimize export.json -m tabular -g strict -t 0.9 -f json -o records.json
python cli.py optimize big.log -f bundle -o bundle.json          # lossless bundle
python cli.py optimize export.csv -b 4000                         # fit into a 4k-token budget
python cli.py optimize export.csv --no-fold                       # keep "col: value" rows
python cli.py reconstruct bundle.json -o original.txt             # rebuild every fragment
cat anything.txt | python cli.py optimize -                       # stdin
```
A summary line goes to stderr: `[tokenforge] 540 fragments -> 8 records | tokens 9,026 -> 4,826 (-46.53%) | templates 7 | lossless True | 20.5 ms`

## REST API
Programmatic endpoints use `X-API-Key` (create keys in the dashboard). Dashboard endpoints use the session cookie.

### `POST /api/v1/optimize`: text
```bash
curl -X POST https://your-host/api/v1/optimize \
  -H "X-API-Key: tio_..." -H "Content-Type: application/json" \
  -d '{"text":"Order 1 shipped\nOrder 2 shipped\nhello\nhello","mode":"auto","guard":"facts",
       "threshold":0.82,"order":"original","format":"text","include_map":true}'
```
```json
{
  "stats": {"fragments_in": 4, "unique_concepts": 2, "tokens_before": 10, "tokens_after": 8,
            "token_reduction_pct": 20.0, "templates": 1, "lossless_verified": true,
            "timings_ms": {"tokenize": 0.1, "exact": 0.0, "minhash": 0.6, "lsh": 9.8, "resolve": 0.0, "verify": 0.0}, "...": "..."},
  "optimized_text": "Order {1|2} shipped\nhello",
  "records": [{"id": 0, "text": "Order {1|2} shipped", "kind": "template", "count": 2, "tokens": 7,
               "sources": [0], "originals": ["Order 1 shipped", "Order 2 shipped"], "...": "..."}],
  "map": {"record": [0, 0, 1, 1], "original": [0, 1, 0, 0]}
}
```
To rebuild fragment *i*: `records[map.record[i]].originals[map.original[i]]`.

### `POST /api/v1/optimize/file`: files (multipart)
```bash
curl -X POST "https://your-host/api/v1/optimize/file?mode=auto&format=annotated" \
  -H "X-API-Key: tio_..." -F files=@logs.zip -F files=@customers.csv
```
Query params: `threshold, mode, guard, order, fold_tables, budget, min_length, include_map, format (text|annotated)`. The JSON endpoint accepts the same fields in the body. Repeating an identical request returns `stats.cached: true` instantly. The limit is 50 MB total.

### Other endpoints
| Method & path | Auth | Purpose |
|---|---|---|
| `POST /api/playground` | none | Optimize ≤ 256 KB of text (used by the How-it-works page) |
| `GET /api/formats` | none | Supported extensions, modes, guards, export formats |
| `POST /api/jobs` | cookie | Multipart `files` (one or many) → background job |
| `GET /api/jobs` · `GET /api/jobs/{id}` | cookie | List / poll jobs |
| `GET /api/jobs/{id}/fragments?page&page_size&search&kind` | cookie | Paginated records |
| `GET /api/jobs/{id}/export?format=` | cookie | Streamed export (see below) |
| `GET /api/jobs/{id}/reconstruct` | cookie | Every original fragment, in input order (`X-Lossless-Verified` header) |
| `DELETE /api/jobs/{id}` | cookie | Delete job, records and map |
| `POST /api/jobs/{id}/share` `{"enabled": true}` | cookie | Turn the public report link on or off |
| `GET /api/share/{token}` | none | Public report: stats and an output preview |
| `GET /api/usage?days=30` | cookie | Your daily usage, per-key totals |
| `GET /api/admin/usage?days=30` | admin | All users' daily usage and top savers |
| `POST /api/auth/register · login · logout · refresh`, `GET /api/auth/me` | — | Accounts |
| `GET/POST/DELETE /api/keys` | cookie | API keys (shown once, stored as SHA-256) |
| `GET /api/admin/stats · users`, `PATCH/DELETE /api/admin/users/{id}` | admin | Owner console |

## Settings
| Setting | Values | Default | Effect |
|---|---|---|---|
| `threshold` | 0.5 – 1.0 | 0.82 | Jaccard similarity needed for a near-duplicate. `1.0` = exact only |
| `mode` | `auto` `prose` `tabular` `log` `code` | `auto` | Shingling and normalization strategy (auto = per file) |
| `guard` | `facts` `strict` `off` | `facts` | What a near-duplicate must share with the kept line before it folds |
| `order` | `original` `frequency` | `original` | Keep reading order, or put the most repeated first |
| `fold_tables` | true / false | true | Fold rows with the same columns into a compact table |
| `budget` | ≥ 50 tokens | none | Fit the output into N tokens (most repeated records first) |
| `min_length` | 1 – 200 | 3 | Shorter fragments are skipped while parsing |

## Export formats
`txt` (LLM-ready) · `annotated` (`[x12] line`) · `md` (report) · `json` · `jsonl` · `csv` · `bundle` (records + originals + map, for rebuilding offline with `cli.py reconstruct`).

## Performance
Single process, measured on a commodity container:

| Input | Fragments | Time |
|---|---|---|
| 2.6 MB synthetic, high-entropy | 40,000 | ≈ 2.7 s |
| 26 MB synthetic, high-entropy | 400,000 | ≈ 30 s |
| Real logs / CSV exports | — | usually much faster, with 50–95 % token reduction |

Main costs: MinHash (numpy, chunked to bound memory), tokenization, and the verification pass. Jobs run in a thread executor, so the API stays responsive.

## Architecture
```
backend/
  optimizer.py      engine: tokenize, exact, MinHash, LSH, templates, guard, verify, render
  parsers.py        30+ formats → Source(name, fragments, kind); sniffing, ZIP expansion
  engine_routes.py  jobs, exports (streamed), reconstruct, v1 API, playground
  server.py         FastAPI app, auth, API keys, admin, startup (indexes, admin seed, stale-job reaper)
  auth.py           JWT cookies, bcrypt, API-key hashing
  cli.py            offline CLI
  tests/            engine tests + API tests
frontend/src/
  pages/            Landing, HowItWorks (+ playground), Dashboard, JobResult, ApiKeys, Admin, Login, Register
  pages/SharedReport.jsx  public /r/:token report
  components/       AppShell, PublicHeader, EngineOptions, Playground, UploadReview, ShareDialog, UsageChart, Shortcuts
  lib/hotkeys.js    keyboard shortcut hook
samples/            example files for every format family
```
Storage (MongoDB): `users`, `api_keys`, `jobs`, `fragments` (records), `usage` (one event per run), and GridFS bucket `reconstruction` (gzip of originals + map, which keeps large jobs under the 16 MB document limit).

## Tests
```bash
cd backend
pytest tests/test_engine.py -q          # engine + parsers, no server needed
REACT_APP_BACKEND_URL=http://localhost:8001 pytest tests/backend_test.py -q   # API (server running)
```
The engine tests include a fuzz round-trip across every guard and order combination.

## Self-hosting & security checklist
- [ ] Set a long random `JWT_SECRET` and a strong `ADMIN_PASSWORD`
- [ ] **Never commit `.env` files.** Only `.env.example` belongs in git
- [ ] Set `FRONTEND_URL` to your real origin (CORS with credentials) and serve over HTTPS (cookies are `Secure; SameSite=None`)
- [ ] Put a reverse proxy request-size limit of slightly above 50 MB in front of `/api/jobs`
- [ ] Back up MongoDB, including the `reconstruction.*` GridFS collections

## Roadmap
- Streaming parser for files larger than RAM
- Per-key quotas
- Optional phrase legend (short codes for long phrases that repeat across lines)
- Semantic (embedding) dedup as an optional add-on

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License
[MIT](LICENSE)
