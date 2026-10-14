from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import logging
import os
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

import auth as A
from optimizer import ENGINE_VERSION
from engine_routes import build_router, reap_stale_jobs
from models import CreateKeyRequest, LoginRequest, RegisterRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("tokenforge")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="TokenForge - LLM Token Ingestion Optimizer")
app.state.db = db
api = APIRouter(prefix="/api")


def public_user(u: dict) -> dict:
    return {
        "id": str(u.get("_id", u.get("id"))),
        "email": u["email"],
        "name": u.get("name", ""),
        "role": u.get("role", "user"),
        "active": u.get("active", True),
        "created_at": u.get("created_at", ""),
    }


# ============================ AUTH ============================
@api.post("/auth/register")
async def register(body: RegisterRequest, response: Response):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "email": email,
        "password_hash": A.hash_password(body.password),
        "name": body.name.strip(),
        "role": "user",
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    access = A.create_access_token(uid, email)
    refresh = A.create_refresh_token(uid)
    A.set_auth_cookies(response, access, refresh)
    doc["_id"] = uid
    return public_user(doc)


@api.post("/auth/login")
async def login(body: LoginRequest, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not A.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")
    uid = str(user["_id"])
    access = A.create_access_token(uid, email)
    refresh = A.create_refresh_token(uid)
    A.set_auth_cookies(response, access, refresh)
    return public_user(user)


@api.post("/auth/logout")
async def logout(response: Response):
    A.clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(A.get_current_user)):
    return public_user(user)


@api.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    import jwt as _jwt

    try:
        payload = _jwt.decode(token, A.get_jwt_secret(), algorithms=[A.JWT_ALGORITHM])
    except _jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    access = A.create_access_token(str(user["_id"]), user["email"])
    response.set_cookie("access_token", access, httponly=True, secure=True,
                        samesite="none", max_age=3600, path="/")
    return {"ok": True}


# ============================ API KEYS ============================
@api.get("/keys")
async def list_keys(user: dict = Depends(A.get_current_user)):
    keys = await db.api_keys.find({"user_id": user["_id"]}).sort("created_at", -1).to_list(200)
    return [{
        "id": str(k["_id"]),
        "name": k["name"],
        "prefix": k["prefix"],
        "revoked": k.get("revoked", False),
        "usage_count": k.get("usage_count", 0),
        "last_used": k.get("last_used"),
        "created_at": k["created_at"],
    } for k in keys]


@api.post("/keys")
async def create_key(body: CreateKeyRequest, user: dict = Depends(A.get_current_user)):
    full, prefix, key_hash = A.generate_api_key()
    doc = {
        "user_id": user["_id"],
        "name": body.name.strip(),
        "prefix": prefix,
        "key_hash": key_hash,
        "revoked": False,
        "usage_count": 0,
        "last_used": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.api_keys.insert_one(doc)
    return {
        "id": str(res.inserted_id),
        "name": doc["name"],
        "prefix": prefix,
        "api_key": full,  # shown ONCE
        "created_at": doc["created_at"],
    }


@api.delete("/keys/{key_id}")
async def revoke_key(key_id: str, user: dict = Depends(A.get_current_user)):
    res = await db.api_keys.update_one(
        {"_id": ObjectId(key_id), "user_id": user["_id"]},
        {"$set": {"revoked": True}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"ok": True}


# ============================ ADMIN ============================
@api.get("/admin/stats")
async def admin_stats(admin: dict = Depends(A.get_current_admin)):
    total_users = await db.users.count_documents({})
    active_users = await db.users.count_documents({"active": True})
    total_jobs = await db.jobs.count_documents({})
    total_keys = await db.api_keys.count_documents({"revoked": False})
    agg = await db.jobs.aggregate([
        {"$match": {"status": "completed"}},
        {"$group": {"_id": None,
                    "tokens_saved": {"$sum": "$stats.tokens_saved"},
                    "tokens_before": {"$sum": "$stats.tokens_before"}}},
    ]).to_list(1)
    saved = agg[0]["tokens_saved"] if agg else 0
    before = agg[0]["tokens_before"] if agg else 0
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_jobs": total_jobs,
        "active_keys": total_keys,
        "total_tokens_saved": saved,
        "total_tokens_processed": before,
    }


@api.get("/admin/users")
async def admin_users(admin: dict = Depends(A.get_current_admin)):
    users = await db.users.find({}).sort("created_at", -1).to_list(1000)
    out = []
    for u in users:
        uid = str(u["_id"])
        jobs = await db.jobs.count_documents({"user_id": uid})
        keys = await db.api_keys.count_documents({"user_id": uid, "revoked": False})
        item = public_user(u)
        item["job_count"] = jobs
        item["key_count"] = keys
        out.append(item)
    return out


@api.patch("/admin/users/{user_id}")
async def admin_toggle_user(user_id: str, request: Request,
                            admin: dict = Depends(A.get_current_admin)):
    body = await request.json()
    active = bool(body.get("active", True))
    if user_id == admin["_id"]:
        raise HTTPException(status_code=400, detail="Cannot modify your own account")
    res = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"active": active}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "active": active}


@api.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, admin: dict = Depends(A.get_current_admin)):
    if user_id == admin["_id"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.get("role") == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete an admin account")
    await db.users.delete_one({"_id": ObjectId(user_id)})
    job_ids = [str(j["_id"]) async for j in db.jobs.find({"user_id": user_id}, {"_id": 1})]
    await db.jobs.delete_many({"user_id": user_id})
    await db.api_keys.delete_many({"user_id": user_id})
    if job_ids:
        await db.fragments.delete_many({"job_id": {"$in": job_ids}})
    return {"ok": True}


@api.get("/")
async def root():
    return {"service": "TokenForge", "status": "ok", "engine": ENGINE_VERSION}


api.include_router(build_router(db))
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.api_keys.create_index("key_hash", unique=True)
    await db.api_keys.create_index("user_id")
    await db.jobs.create_index("user_id")
    await db.fragments.create_index([("job_id", 1), ("order", 1)])
    await db.usage.create_index([("user_id", 1), ("day", 1)])
    await db.usage.create_index("day")
    await db.jobs.create_index("share_token", sparse=True)
    await db.jobs.create_index([("user_id", 1), ("cache_key", 1)])
    await reap_stale_jobs(db)
    # seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": A.hash_password(admin_password),
            "name": "Owner",
            "role": "admin",
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Seeded admin %s", admin_email)
    elif not A.verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email},
            {"$set": {"password_hash": A.hash_password(admin_password), "role": "admin", "active": True}})


@app.on_event("shutdown")
async def shutdown():
    client.close()
