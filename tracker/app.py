import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
MONGO_DB = os.getenv("MONGO_DB")
HEARTBEAT_TTL_SECONDS = int(os.getenv("HEARTBEAT_TTL_SECONDS", "30"))

mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = mongo[MONGO_DB] if MONGO_DB else mongo.get_default_database(default="p2p_notes")
MONGO_DB = db.name
peers = db.peers
files = db.files
replicas = db.replicas

app = FastAPI(
    title="P2P Notes Tracker",
    description="Discovery and metadata service for the distributed notes sharing system.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PeerRegisterRequest(BaseModel):
    peer_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    host: str = "127.0.0.1"
    port: int = Field(gt=0, lt=65536)
    base_url: str | None = None


class HeartbeatRequest(BaseModel):
    peer_id: str = Field(min_length=1)
    load: int = Field(default=0, ge=0)


class FileAnnounceRequest(BaseModel):
    file_hash: str = Field(min_length=16)
    filename: str = Field(min_length=1)
    subject: str = ""
    semester: str = ""
    size: int = Field(ge=0)
    chunk_count: int = Field(default=1, ge=1)
    peer_id: str = Field(min_length=1)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_online(peer: dict[str, Any]) -> bool:
    last_heartbeat = as_aware(peer.get("last_heartbeat"))
    if last_heartbeat is None:
        return False
    return now_utc() - last_heartbeat <= timedelta(seconds=HEARTBEAT_TTL_SECONDS)


def public_peer(peer: dict[str, Any] | None) -> dict[str, Any] | None:
    if peer is None:
        return None
    base_url = peer.get("base_url") or f"http://{peer.get('host')}:{peer.get('port')}"
    last_heartbeat = as_aware(peer.get("last_heartbeat"))
    return {
        "peer_id": peer.get("peer_id"),
        "name": peer.get("name"),
        "host": peer.get("host"),
        "port": peer.get("port"),
        "base_url": base_url,
        "load": peer.get("load", 0),
        "status": "online" if is_online(peer) else "offline",
        "last_heartbeat": last_heartbeat.isoformat() if last_heartbeat else None,
    }


def public_file(file_doc: dict[str, Any], replica_docs: list[dict[str, Any]]) -> dict[str, Any]:
    peer_docs = {
        peer["peer_id"]: peer
        for peer in peers.find({"peer_id": {"$in": [doc["peer_id"] for doc in replica_docs]}})
    }
    return {
        "file_hash": file_doc.get("file_hash"),
        "filename": file_doc.get("filename"),
        "subject": file_doc.get("subject", ""),
        "semester": file_doc.get("semester", ""),
        "size": file_doc.get("size", 0),
        "chunk_count": file_doc.get("chunk_count", 1),
        "created_at": file_doc.get("created_at").isoformat()
        if file_doc.get("created_at")
        else None,
        "replicas": [
            public_peer(peer_docs.get(replica_doc["peer_id"]))
            for replica_doc in replica_docs
            if peer_docs.get(replica_doc["peer_id"]) is not None
        ],
    }


@app.on_event("startup")
def ensure_indexes() -> None:
    mongo.admin.command("ping")
    peers.create_index("peer_id", unique=True)
    files.create_index("file_hash", unique=True)
    files.create_index([("filename", ASCENDING), ("subject", ASCENDING), ("semester", ASCENDING)])
    replicas.create_index([("file_hash", ASCENDING), ("peer_id", ASCENDING)], unique=True)


@app.get("/health")
def health() -> dict[str, str]:
    try:
        mongo.admin.command("ping")
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {exc}") from exc
    return {"status": "ok", "database": MONGO_DB}


@app.post("/peers/register")
def register_peer(payload: PeerRegisterRequest) -> dict[str, Any]:
    base_url = payload.base_url or f"http://{payload.host}:{payload.port}"
    update = {
        "$set": {
            "peer_id": payload.peer_id,
            "name": payload.name,
            "host": payload.host,
            "port": payload.port,
            "base_url": base_url,
            "last_heartbeat": now_utc(),
            "load": 0,
        }
    }
    try:
        peers.update_one({"peer_id": payload.peer_id}, update, upsert=True)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail=f"Could not register peer: {exc}") from exc
    return {"status": "registered", "peer_id": payload.peer_id, "base_url": base_url}


@app.post("/peers/heartbeat")
def heartbeat(payload: HeartbeatRequest) -> dict[str, str]:
    result = peers.update_one(
        {"peer_id": payload.peer_id},
        {"$set": {"last_heartbeat": now_utc(), "load": payload.load}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Peer is not registered")
    return {"status": "alive", "peer_id": payload.peer_id}


@app.get("/peers")
def list_peers() -> dict[str, list[dict[str, Any]]]:
    return {"peers": [public_peer(peer) for peer in peers.find().sort("peer_id", ASCENDING)]}


@app.post("/files/announce")
def announce_file(payload: FileAnnounceRequest) -> dict[str, Any]:
    peer = peers.find_one({"peer_id": payload.peer_id})
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer must register before announcing files")

    created_at = now_utc()
    try:
        files.update_one(
            {"file_hash": payload.file_hash},
            {
                "$setOnInsert": {
                    "file_hash": payload.file_hash,
                    "filename": payload.filename,
                    "size": payload.size,
                    "chunk_count": payload.chunk_count,
                    "created_at": created_at,
                },
                "$set": {
                    "subject": payload.subject,
                    "semester": payload.semester,
                    "updated_at": created_at,
                },
            },
            upsert=True,
        )
        replicas.update_one(
            {"file_hash": payload.file_hash, "peer_id": payload.peer_id},
            {
                "$set": {
                    "file_hash": payload.file_hash,
                    "peer_id": payload.peer_id,
                    "available": True,
                    "updated_at": created_at,
                }
            },
            upsert=True,
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail=f"Could not announce file: {exc}") from exc

    return {
        "status": "announced",
        "file_hash": payload.file_hash,
        "peer_id": payload.peer_id,
    }


@app.get("/files/search")
def search_files(q: str = Query(default="", description="Filename, subject, or semester")) -> dict[str, Any]:
    query = q.strip()
    mongo_query: dict[str, Any] = {}
    if query:
        escaped = re.escape(query)
        mongo_query = {
            "$or": [
                {"filename": {"$regex": escaped, "$options": "i"}},
                {"subject": {"$regex": escaped, "$options": "i"}},
                {"semester": {"$regex": escaped, "$options": "i"}},
            ]
        }

    results = []
    for file_doc in files.find(mongo_query).sort("updated_at", -1).limit(50):
        replica_docs = list(
            replicas.find({"file_hash": file_doc["file_hash"], "available": True})
        )
        results.append(public_file(file_doc, replica_docs))
    return {"query": query, "results": results}


@app.get("/files/{file_hash}/peers")
def file_peers(file_hash: str) -> dict[str, Any]:
    file_doc = files.find_one({"file_hash": file_hash})
    if file_doc is None:
        raise HTTPException(status_code=404, detail="File not found")
    replica_docs = list(replicas.find({"file_hash": file_hash, "available": True}))
    return public_file(file_doc, replica_docs)
