"""Optimizer routes: jobs (multi-file), exports, reconstruction, sharing, usage, v1 API, playground."""
from __future__ import annotations

import asyncio
import csv
import gzip
import hashlib
import io
import json
import logging
import re
import secrets
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

import auth as A
from models import OptimizeTextRequest, PlaygroundRequest, ShareRequest
from optimizer import ENGINE_VERSION, KINDS, build_output, optimize_sources, reconstruct
from parsers import SUPPORTED_EXTENSIONS, parse_text, parse_upload

logger = logging.getLogger("tokenforge")

MAX_BYTES = 50 * 1024 * 1024
PLAYGROUND_MAX = 256 * 1024
MODES = ("auto",) + KINDS
GUARDS = ("facts", "strict", "off")
ORDERS = ("original", "frequency")
EXPORT_FORMATS = ("json", "txt", "annotated", "md", "jsonl", "csv", "bundle")
SHARE_PREVIEW_CHARS = 6000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _oid(v: str) -> ObjectId:
    if not ObjectId.is_valid(v):
        raise HTTPException(status_code=404, detail="Not found")
    return ObjectId(v)


def _opts(threshold: float, mode: str, guard: str, order: str, fold_tables: bool = True,
          budget: Optional[int] = None) -> dict:
    if mode not in MODES:
        raise HTTPException(status_code=400, detail=f"mode must be one of {MODES}")
    if guard not in GUARDS:
        raise HTTPException(status_code=400, detail=f"guard must be one of {GUARDS}")
    if order not in ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {ORDERS}")
    if budget is not None and budget < 50:
        raise HTTPException(status_code=400, detail="budget must be at least 50 tokens")
    return {"threshold": max(0.5, min(1.0, threshold)), "mode": mode, "guard": guard, "order": order,
            "fold_tables": fold_tables, "budget": budget or None}


def _cache_key(parts: List[bytes], opts: dict, min_length: int) -> str:
    h = hashlib.sha256(ENGINE_VERSION.encode())
    # Sequence matters: reversing files changes source indices and reconstruction map.
    for p in parts:
        h.update(len(p).to_bytes(8, "big"))
        h.update(hashlib.sha256(p).digest())
    h.update(json.dumps(opts, sort_keys=True).encode() + str(min_length).encode())
    return h.hexdigest()


class _LRU(OrderedDict):
    def __init__(self, size: int):
        super().__init__()
        self.size = size

    def get_item(self, k):
        if k in self:
            self.move_to_end(k)
            return self[k]
        return None

    def put(self, k, v):
        self[k] = v
        self.move_to_end(k)
        while len(self) > self.size:
            self.popitem(last=False)


_API_CACHE = _LRU(64)


def _public_records(records: List[dict], include_originals: bool) -> List[dict]:
    if include_originals:
        return records
    return [{k: v for k, v in r.items() if k != "originals"} for r in records]


async def _form_files(request: Request) -> List[UploadFile]:
    form = await request.form()
    return [f for k in ("files", "file") for f in form.getlist(k) if hasattr(f, "read")]


async def _read_uploads(files: List[UploadFile]) -> List[tuple]:
    blobs, total = [], 0
    for f in files:
        data = await f.read(MAX_BYTES - total + 1)
        total += len(data)
        if total > MAX_BYTES:
            raise HTTPException(status_code=413, detail="Upload exceeds 50 MB total limit")
        if data:
            blobs.append((f.filename or "input", data))
    if not blobs:
        raise HTTPException(status_code=400, detail="Empty file")
    return blobs


def _parse_all(blobs: List[tuple], min_length: int) -> tuple[list, list]:
    sources, errors = [], []
    for name, data in blobs:
        try:
            sources.extend(parse_upload(data, name, min_length))
        except Exception as e:  # noqa: BLE001 - surface parse errors per file
            errors.append(f"{name}: {e}")
    return sources, errors


def _day(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def _series(rows: List[dict], days: int) -> List[dict]:
    by_day = {r["_id"]: r for r in rows}
    out = []
    for i in range(days - 1, -1, -1):
        d = _day(i)
        r = by_day.get(d, {})
        out.append({"day": d, "requests": r.get("requests", 0), "tokens_before": r.get("tokens_before", 0),
                    "tokens_after": r.get("tokens_after", 0),
                    "tokens_saved": r.get("tokens_before", 0) - r.get("tokens_after", 0)})
    return out


_GROUP_SUMS = {"requests": {"$sum": 1}, "tokens_before": {"$sum": "$tokens_before"},
               "tokens_after": {"$sum": "$tokens_after"}}


def build_router(db) -> APIRouter:
    r = APIRouter()
    fs = AsyncIOMotorGridFSBucket(db, bucket_name="reconstruction")

    async def _owned_job(job_id: str, user: dict) -> dict:
        j = await db.jobs.find_one({"_id": _oid(job_id), "user_id": user["_id"]})
        if not j:
            raise HTTPException(status_code=404, detail="Job not found")
        return j

    async def _log_usage(user_id: str, source: str, stats: dict, key_id: Optional[str] = None,
                         cached: bool = False, nbytes: int = 0) -> None:
        await db.usage.insert_one({
            "user_id": user_id, "key_id": key_id, "source": source, "cached": cached,
            "day": _day(), "ts": _now(), "bytes": nbytes,
            "tokens_before": stats.get("tokens_before", 0), "tokens_after": stats.get("tokens_after", 0),
        })

    async def _store_result(job_id: str, result: dict) -> None:
        await db.fragments.delete_many({"job_id": job_id})
        batch = []
        for rec in result["records"]:
            doc = {k: v for k, v in rec.items() if k != "originals"}
            doc.update(job_id=job_id, order=rec["id"])
            batch.append(doc)
            if len(batch) >= 1000:
                await db.fragments.insert_many(batch)
                batch = []
        if batch:
            await db.fragments.insert_many(batch)
        blob = gzip.compress(json.dumps({
            "originals": [rec["originals"] for rec in result["records"]],
            "map": result["map"],
            "output": result["output"],
        }, ensure_ascii=False).encode("utf-8"), compresslevel=6)
        await fs.upload_from_stream(f"{job_id}.json.gz", blob, metadata={"job_id": job_id})

    async def _load_bundle(job_id: str) -> dict:
        meta = await db["reconstruction.files"].find_one({"metadata.job_id": job_id}, sort=[("uploadDate", -1)])
        if not meta:
            raise HTTPException(status_code=404, detail="Reconstruction map not available for this job")
        stream = await fs.open_download_stream(meta["_id"])
        return json.loads(gzip.decompress(await stream.read()))

    async def _delete_bundle(job_id: str) -> None:
        async for f in db["reconstruction.files"].find({"metadata.job_id": job_id}, {"_id": 1}):
            await fs.delete(f["_id"])

    async def _run_job(job_id: str, user_id: str, blobs: List[tuple], opts: dict, min_length: int):
        loop = asyncio.get_running_loop()
        try:
            sources, errors = await loop.run_in_executor(None, _parse_all, blobs, min_length)
            if not sources:
                msg = "; ".join(errors) or "No readable text fragments found"
                await db.jobs.update_one({"_id": ObjectId(job_id)}, {"$set": {
                    "status": "failed", "error": msg, "completed_at": _now()}})
                return
            result = await loop.run_in_executor(None, lambda: optimize_sources(sources, **opts))
            result["stats"]["parse_errors"] = errors
            await _store_result(job_id, result)
            await db.jobs.update_one({"_id": ObjectId(job_id)}, {"$set": {
                "status": "completed", "stats": result["stats"], "completed_at": _now()}})
            await _log_usage(user_id, "web", result["stats"], nbytes=sum(len(d) for _, d in blobs))
        except Exception as e:  # pragma: no cover
            logger.exception("job failed")
            await db.jobs.update_one({"_id": ObjectId(job_id)}, {"$set": {
                "status": "failed", "error": str(e), "completed_at": _now()}})

    def _job_out(j: dict) -> dict:
        return {
            "id": str(j["_id"]),
            "filename": j["filename"],
            "files": j.get("files", [j["filename"]]),
            "size_bytes": j.get("size_bytes", 0),
            "threshold": j.get("threshold"),
            "options": j.get("options"),
            "status": j["status"],
            "stats": j.get("stats"),
            "error": j.get("error"),
            "share_enabled": bool(j.get("share_enabled")),
            "share_token": j.get("share_token") if j.get("share_enabled") else None,
            "created_at": j["created_at"],
            "completed_at": j.get("completed_at"),
        }

    # ---------------- meta ----------------
    @r.get("/formats")
    async def formats():
        return {"extensions": SUPPORTED_EXTENSIONS, "modes": MODES, "guards": GUARDS,
                "orders": ORDERS, "export_formats": EXPORT_FORMATS, "max_bytes": MAX_BYTES}

    # ---------------- jobs ----------------
    @r.post("/jobs")
    async def create_job(
        request: Request,
        threshold: float = 0.82,
        mode: str = "auto",
        guard: str = "facts",
        order: str = "original",
        fold_tables: bool = True,
        budget: Optional[int] = None,
        min_length: int = 3,
        user: dict = Depends(A.get_current_user),
    ):
        uploads = await _form_files(request)
        if not uploads:
            raise HTTPException(status_code=400, detail="No file uploaded")
        opts = _opts(threshold, mode, guard, order, fold_tables, budget)
        min_length = max(1, min(200, min_length))
        blobs = await _read_uploads(uploads)
        names = [n for n, _ in blobs]
        label = names[0] if len(names) == 1 else f"{names[0]} +{len(names) - 1} more"
        key = _cache_key([name.encode("utf-8") + b"\x00" + data for name, data in blobs], opts, min_length)
        hit = await db.jobs.find_one({"user_id": user["_id"], "cache_key": key, "status": "completed"},
                                     sort=[("created_at", -1)])
        if hit:
            await _log_usage(user["_id"], "web", hit.get("stats") or {}, cached=True)
            return {"id": str(hit["_id"]), "status": "completed", "filename": hit["filename"],
                    "files": hit.get("files", names), "cached": True}
        doc = {
            "user_id": user["_id"], "filename": label, "files": names, "cache_key": key,
            "size_bytes": sum(len(d) for _, d in blobs), "threshold": opts["threshold"],
            "options": opts, "status": "processing", "stats": None, "error": None,
            "created_at": _now(), "completed_at": None,
        }
        res = await db.jobs.insert_one(doc)
        job_id = str(res.inserted_id)
        asyncio.create_task(_run_job(job_id, user["_id"], blobs, opts, min_length))
        return {"id": job_id, "status": "processing", "filename": label, "files": names, "cached": False}

    @r.get("/jobs")
    async def list_jobs(user: dict = Depends(A.get_current_user)):
        jobs = await db.jobs.find({"user_id": user["_id"]}).sort("created_at", -1).to_list(200)
        return [_job_out(j) for j in jobs]

    @r.get("/jobs/{job_id}")
    async def get_job(job_id: str, user: dict = Depends(A.get_current_user)):
        return _job_out(await _owned_job(job_id, user))

    @r.get("/jobs/{job_id}/fragments")
    async def job_fragments(job_id: str, page: int = 1, page_size: int = 50, search: str = "",
                            kind: str = "", user: dict = Depends(A.get_current_user)):
        await _owned_job(job_id, user)
        query: dict = {"job_id": job_id}
        if search:
            query["text"] = {"$regex": re.escape(search), "$options": "i"}
        if kind:
            query["kind"] = kind
        page, page_size = max(1, page), max(1, min(200, page_size))
        total = await db.fragments.count_documents(query)
        items = await db.fragments.find(query, {"_id": 0, "job_id": 0}).sort("order", 1) \
            .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    @r.get("/jobs/{job_id}/export")
    async def export_job(job_id: str, format: str = "json", user: dict = Depends(A.get_current_user)):
        j = await _owned_job(job_id, user)
        if format not in EXPORT_FORMATS:
            raise HTTPException(status_code=400, detail=f"format must be one of {EXPORT_FORMATS}")
        cursor = db.fragments.find({"job_id": job_id}, {"_id": 0, "job_id": 0, "order": 0}).sort("order", 1)
        base = f"optimized_{job_id}"
        needs_bundle = format in ("bundle", "txt", "annotated", "md")
        bundle = await _load_bundle(job_id) if needs_bundle else None

        async def lines():
            if format in ("json", "bundle"):
                head = {"filename": j["filename"], "files": j.get("files"), "stats": j.get("stats")}
                yield json.dumps(head, ensure_ascii=False)[:-1] + ', "records": ['
                i = 0
                async for f in cursor:
                    if bundle:
                        f["originals"] = bundle["originals"][i]
                    yield ("," if i else "") + json.dumps(f, ensure_ascii=False)
                    i += 1
                yield "]" + (', "map": ' + json.dumps(bundle["map"]) if bundle else "") + "}"
            elif format == "csv":
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(["id", "kind", "count", "tokens", "text", "variant_count", "sources"])
                async for f in cursor:
                    w.writerow([f["id"], f["kind"], f["count"], f["tokens"], f["text"], f["variant_count"],
                                ";".join(map(str, f["sources"]))])
                    yield buf.getvalue()
                    buf.seek(0)
                    buf.truncate()
            elif format == "jsonl":
                async for f in cursor:
                    yield json.dumps(f, ensure_ascii=False) + "\n"
            else:
                out = bundle.get("output")
                if not out:
                    out = build_output([f async for f in cursor])
                if format == "md":
                    s = j.get("stats") or {}
                    yield (f"# TokenForge report: {j['filename']}\n\n"
                           f"| tokens before | tokens after | saved | fragments → records | lossless |\n"
                           f"|---|---|---|---|---|\n"
                           f"| {s.get('tokens_before')} | {s.get('tokens_after')} | {s.get('token_reduction_pct')}% "
                           f"| {s.get('fragments_in')} → {s.get('unique_concepts')} | {s.get('lossless_verified')} |\n\n"
                           "```text\n" + out.get("annotated", "") + "\n```\n")
                else:
                    yield out.get("annotated" if format == "annotated" else "text", "") + "\n"

        ext = {"annotated": "txt", "bundle": "json"}.get(format, format)
        media = {"json": "application/json", "bundle": "application/json", "csv": "text/csv",
                 "jsonl": "application/x-ndjson", "md": "text/markdown"}.get(format, "text/plain")
        return StreamingResponse(lines(), media_type=f"{media}; charset=utf-8", headers={
            "Content-Disposition": f'attachment; filename="{base}{"_annotated" if format == "annotated" else ""}.{ext}"'})

    @r.get("/jobs/{job_id}/reconstruct")
    async def reconstruct_job(job_id: str, user: dict = Depends(A.get_current_user)):
        j = await _owned_job(job_id, user)
        bundle = await _load_bundle(job_id)
        recs = [{"originals": o} for o in bundle["originals"]]
        frags = reconstruct(recs, bundle["map"]["record"], bundle["map"]["original"])

        async def body():
            for i in range(0, len(frags), 2000):
                yield "\n".join(frags[i:i + 2000]) + "\n"

        verified = str((j.get("stats") or {}).get("lossless_verified", False)).lower()
        return StreamingResponse(body(), media_type="text/plain; charset=utf-8", headers={
            "Content-Disposition": f'attachment; filename="reconstructed_{job_id}.txt"',
            "X-Lossless-Verified": verified, "X-Fragment-Count": str(len(frags))})

    @r.delete("/jobs/{job_id}")
    async def delete_job(job_id: str, user: dict = Depends(A.get_current_user)):
        res = await db.jobs.delete_one({"_id": _oid(job_id), "user_id": user["_id"]})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Job not found")
        await db.fragments.delete_many({"job_id": job_id})
        await _delete_bundle(job_id)
        return {"ok": True}

    # ---------------- sharing ----------------
    @r.post("/jobs/{job_id}/share")
    async def share_job(job_id: str, body: ShareRequest, user: dict = Depends(A.get_current_user)):
        j = await _owned_job(job_id, user)
        if j["status"] != "completed":
            raise HTTPException(status_code=400, detail="Only completed jobs can be shared")
        token = j.get("share_token") or secrets.token_urlsafe(12)
        await db.jobs.update_one({"_id": j["_id"]}, {"$set": {"share_token": token, "share_enabled": body.enabled}})
        return {"enabled": body.enabled, "token": token if body.enabled else None}

    @r.get("/share/{token}")
    async def shared_report(token: str):
        j = await db.jobs.find_one({"share_token": token, "share_enabled": True})
        if not j:
            raise HTTPException(status_code=404, detail="This report is private or no longer shared")
        job_id = str(j["_id"])
        out = (await _load_bundle(job_id)).get("output") or {}
        text = out.get("text", "")
        recs = await db.fragments.find({"job_id": job_id}, {"_id": 0, "job_id": 0, "variants": 0}) \
            .sort("order", 1).limit(30).to_list(30)
        s = j.get("stats") or {}
        keep = ("tokens_before", "tokens_after", "tokens_saved", "token_reduction_pct", "fragments_in",
                "unique_concepts", "dup_reduction_pct", "templates", "tables_folded", "near_dup_clusters",
                "exact_duplicates", "lossless_verified", "elapsed_ms", "mode", "guard", "kinds", "engine")
        return {"filename": j["filename"], "file_count": len(j.get("files", [])), "created_at": j["created_at"],
                "stats": {k: s.get(k) for k in keep}, "preview_text": text[:SHARE_PREVIEW_CHARS],
                "preview_truncated": len(text) > SHARE_PREVIEW_CHARS, "preview_records": recs}

    # ---------------- usage analytics ----------------
    async def _usage(match: dict, days: int) -> dict:
        since = _day(days - 1)
        q = {**match, "day": {"$gte": since}}
        rows = await db.usage.aggregate([{"$match": q}, {"$group": {"_id": "$day", **_GROUP_SUMS}}]).to_list(400)
        series = _series(rows, days)
        totals = {k: sum(d[k] for d in series) for k in ("requests", "tokens_before", "tokens_after", "tokens_saved")}
        cached = await db.usage.count_documents({**q, "cached": True})
        return {"days": days, "series": series, "totals": {**totals, "cached_hits": cached}}

    @r.get("/usage")
    async def my_usage(days: int = 30, user: dict = Depends(A.get_current_user)):
        days = max(1, min(365, days))
        out = await _usage({"user_id": user["_id"]}, days)
        rows = await db.usage.aggregate([
            {"$match": {"user_id": user["_id"], "key_id": {"$ne": None}, "day": {"$gte": _day(days - 1)}}},
            {"$group": {"_id": "$key_id", **_GROUP_SUMS}},
        ]).to_list(500)
        out["by_key"] = {x["_id"]: {"requests": x["requests"], "tokens_saved": x["tokens_before"] - x["tokens_after"]}
                         for x in rows}
        by_source = await db.usage.aggregate([
            {"$match": {"user_id": user["_id"], "day": {"$gte": _day(days - 1)}}},
            {"$group": {"_id": "$source", **_GROUP_SUMS}},
        ]).to_list(10)
        out["by_source"] = {x["_id"]: x["requests"] for x in by_source}
        return out

    @r.get("/admin/usage")
    async def admin_usage(days: int = 30, admin: dict = Depends(A.get_current_admin)):
        days = max(1, min(365, days))
        out = await _usage({}, days)
        rows = await db.usage.aggregate([
            {"$match": {"day": {"$gte": _day(days - 1)}}},
            {"$group": {"_id": "$user_id", **_GROUP_SUMS}},
            {"$addFields": {"saved": {"$subtract": ["$tokens_before", "$tokens_after"]}}},
            {"$sort": {"saved": -1}}, {"$limit": 10},
        ]).to_list(10)
        users = {str(u["_id"]): u for u in await db.users.find(
            {"_id": {"$in": [ObjectId(x["_id"]) for x in rows if ObjectId.is_valid(x["_id"])]}},
            {"email": 1, "name": 1}).to_list(10)}
        out["top_users"] = [{"user_id": x["_id"], "email": users.get(x["_id"], {}).get("email", "deleted user"),
                             "requests": x["requests"], "tokens_saved": x["saved"]} for x in rows]
        return out

    # ---------------- public API (X-API-Key) ----------------
    def _api_payload(result: dict, include_map: bool, fmt: str) -> dict:
        out = {"stats": result["stats"],
               "optimized_text": result["output"]["annotated" if fmt == "annotated" else "text"],
               "records": _public_records(result["records"], include_map)}
        if include_map:
            out["map"] = result["map"]
        return out

    async def _cached_optimize(key: str, sources_fn, opts: dict) -> tuple[dict, bool]:
        hit = _API_CACHE.get_item(key)
        if hit:
            return hit, True
        loop = asyncio.get_running_loop()
        sources, errors = await loop.run_in_executor(None, sources_fn)
        if not sources:
            raise HTTPException(status_code=400, detail="; ".join(errors) or "No text fragments to optimize")
        result = await loop.run_in_executor(None, lambda: optimize_sources(sources, **opts))
        result["stats"]["parse_errors"] = errors
        _API_CACHE.put(key, result)
        return result, False

    def _with_cache_flag(payload: dict, cached: bool) -> dict:
        payload["stats"] = {**payload["stats"], "cached": cached}
        return payload

    @r.post("/v1/optimize")
    async def v1_optimize(body: OptimizeTextRequest, user: dict = Depends(A.get_user_by_api_key)):
        opts = _opts(body.threshold, body.mode, body.guard, body.order, body.fold_tables, body.budget)
        raw = body.text.encode("utf-8")
        key = _cache_key([user["_id"].encode(), raw, body.mode.encode()], opts, body.min_length)

        def sources():
            src = parse_text(body.text, body.min_length, body.mode)
            return ([src] if src.fragments else []), []

        result, cached = await _cached_optimize(key, sources, opts)
        await _log_usage(user["_id"], "api", result["stats"], user.get("_api_key_id"), cached, len(raw))
        return _with_cache_flag(_api_payload(result, body.include_map, body.format), cached)

    @r.post("/v1/optimize/file")
    async def v1_optimize_file(
        request: Request,
        threshold: float = 0.82, mode: str = "auto", guard: str = "facts", order: str = "original",
        fold_tables: bool = True, budget: Optional[int] = None,
        min_length: int = 3, include_map: bool = False, format: str = "text",
        user: dict = Depends(A.get_user_by_api_key),
    ):
        uploads = await _form_files(request)
        if not uploads:
            raise HTTPException(status_code=400, detail="No file uploaded")
        opts = _opts(threshold, mode, guard, order, fold_tables, budget)
        min_length = max(1, min(200, min_length))
        blobs = await _read_uploads(uploads)
        key = _cache_key([user["_id"].encode(), b"file"] +
                         [name.encode("utf-8") + b"\x00" + data for name, data in blobs],
                         opts, min_length)
        result, cached = await _cached_optimize(key, lambda: _parse_all(blobs, min_length), opts)
        await _log_usage(user["_id"], "api", result["stats"], user.get("_api_key_id"), cached,
                         sum(len(d) for _, d in blobs))
        return _with_cache_flag(_api_payload(result, include_map, format), cached)

    # ---------------- playground (no auth, small inputs) ----------------
    @r.post("/playground")
    async def playground(body: PlaygroundRequest):
        if len(body.text.encode("utf-8")) > PLAYGROUND_MAX:
            raise HTTPException(status_code=413, detail="Playground input is limited to 256 KB. Sign up for 50 MB")
        opts = _opts(body.threshold, body.mode, body.guard, body.order, body.fold_tables, body.budget)
        src = parse_text(body.text, body.min_length, body.mode)
        if not src.fragments:
            raise HTTPException(status_code=400, detail="No text fragments to optimize")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: optimize_sources([src], **opts))
        rebuilt = reconstruct(result["records"], result["map"]["record"], result["map"]["original"])
        return {
            "stats": result["stats"],
            "detected_kind": src.kind,
            "input_fragments": src.fragments[:500],
            "records": result["records"][:500],
            "optimized_text": result["output"]["text"],
            "annotated_text": result["output"]["annotated"],
            "map": {k: v[:500] for k, v in result["map"].items()},
            "reconstructed_matches": rebuilt == src.fragments,
        }

    return r


async def reap_stale_jobs(db) -> None:
    res = await db.jobs.update_many({"status": "processing"}, {"$set": {
        "status": "failed", "error": "Interrupted by a server restart. Please re-upload",
        "completed_at": _now()}})
    if res.modified_count:
        logger.info("Reaped %s stale jobs", res.modified_count)
