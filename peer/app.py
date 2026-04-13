import asyncio
import hashlib
import json
import math
import os
import re
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

load_dotenv()

TRACKER_URL = os.getenv("TRACKER_URL", "http://127.0.0.1:8000").rstrip("/")
PEER_ID = os.getenv("PEER_ID", "peer1")
PEER_NAME = os.getenv("PEER_NAME", "Peer One")
PEER_HOST = os.getenv("PEER_HOST", "127.0.0.1")
PEER_PORT = int(os.getenv("PEER_PORT", "9001"))
PEER_BASE_URL = f"http://{PEER_HOST}:{PEER_PORT}"
STORAGE_DIR = Path(os.getenv("PEER_STORAGE_DIR", "./data/peer1")).resolve()
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./downloads")).resolve()
CHUNK_SIZE_BYTES = int(os.getenv("CHUNK_SIZE_BYTES", str(1024 * 1024)))
INDEX_FILE = STORAGE_DIR / "index.json"

app = FastAPI(
    title=f"P2P Notes Peer {PEER_ID}",
    description="Peer node that stores notes locally and serves them to other peers.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

heartbeat_task: asyncio.Task | None = None


class DownloadFromPeerRequest(BaseModel):
    file_hash: str = Field(min_length=16)
    filename: str = Field(min_length=1)
    source_peer_url: str = Field(min_length=1)
    subject: str = ""
    semester: str = ""


def safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return cleaned or "note.bin"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_index() -> dict[str, Any]:
    if not INDEX_FILE.exists():
        return {}
    return json.loads(INDEX_FILE.read_text(encoding="utf-8"))


def write_index(index: dict[str, Any]) -> None:
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = INDEX_FILE.with_suffix(".tmp")
    temp_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    temp_path.replace(INDEX_FILE)


def file_path_for(file_hash: str, filename: str) -> Path:
    return STORAGE_DIR / f"{file_hash}_{safe_filename(filename)}"


def build_file_record(path: Path, filename: str, subject: str, semester: str) -> dict[str, Any]:
    size = path.stat().st_size
    file_hash = sha256_file(path)
    return {
        "file_hash": file_hash,
        "filename": filename,
        "safe_filename": safe_filename(filename),
        "subject": subject,
        "semester": semester,
        "size": size,
        "chunk_count": max(1, math.ceil(size / CHUNK_SIZE_BYTES)),
        "path": str(path),
    }


async def register_with_tracker() -> None:
    payload = {
        "peer_id": PEER_ID,
        "name": PEER_NAME,
        "host": PEER_HOST,
        "port": PEER_PORT,
        "base_url": PEER_BASE_URL,
    }
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(f"{TRACKER_URL}/peers/register", json=payload)


async def announce_file(record: dict[str, Any]) -> None:
    payload = {
        "file_hash": record["file_hash"],
        "filename": record["filename"],
        "subject": record.get("subject", ""),
        "semester": record.get("semester", ""),
        "size": record["size"],
        "chunk_count": record["chunk_count"],
        "peer_id": PEER_ID,
    }
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(f"{TRACKER_URL}/files/announce", json=payload)
        response.raise_for_status()


async def heartbeat_loop() -> None:
    while True:
        try:
            index = read_index()
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{TRACKER_URL}/peers/heartbeat",
                    json={"peer_id": PEER_ID, "load": len(index)},
                )
            if response.status_code == 404:
                await register_with_tracker()
        except Exception as exc:
            print(f"Heartbeat failed for {PEER_ID}: {exc}")
        await asyncio.sleep(10)


@app.on_event("startup")
async def startup() -> None:
    global heartbeat_task
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with suppress(Exception):
        await register_with_tracker()
    heartbeat_task = asyncio.create_task(heartbeat_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    if heartbeat_task:
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "peer_id": PEER_ID}


@app.get("/info")
def info() -> dict[str, Any]:
    return {
        "peer_id": PEER_ID,
        "name": PEER_NAME,
        "base_url": PEER_BASE_URL,
        "tracker_url": TRACKER_URL,
        "storage_dir": str(STORAGE_DIR),
        "download_dir": str(DOWNLOAD_DIR),
        "chunk_size_bytes": CHUNK_SIZE_BYTES,
        "local_file_count": len(read_index()),
    }


@app.get("/files")
def list_files() -> dict[str, list[dict[str, Any]]]:
    return {"files": list(read_index().values())}


@app.post("/upload-note")
async def upload_note(
    file: UploadFile = File(...),
    subject: str = Form(""),
    semester: str = Form(""),
) -> dict[str, Any]:
    original_name = safe_filename(file.filename or "note.bin")
    temp_path = STORAGE_DIR / f".upload_{uuid4().hex}.part"
    with temp_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            output.write(chunk)

    file_hash = sha256_file(temp_path)
    final_path = file_path_for(file_hash, original_name)
    if final_path.exists():
        temp_path.unlink()
    else:
        shutil.move(str(temp_path), final_path)

    record = build_file_record(final_path, original_name, subject, semester)
    index = read_index()
    index[file_hash] = record
    write_index(index)

    try:
        await announce_file(record)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Tracker announce failed: {exc}") from exc

    return {"status": "uploaded", "file": record}


@app.get("/search")
async def search_notes(q: str = "") -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8) as client:
        try:
            response = await client.get(f"{TRACKER_URL}/files/search", params={"q": q})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"Tracker search failed: {exc}") from exc
    return response.json()


@app.get("/download/{file_hash}")
def download(file_hash: str) -> FileResponse:
    record = read_index().get(file_hash)
    if record is None:
        raise HTTPException(status_code=404, detail="File not available on this peer")
    path = Path(record["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Local file is missing")
    return FileResponse(path, filename=record["filename"])


@app.get("/chunk/{file_hash}/{chunk_no}")
def download_chunk(file_hash: str, chunk_no: int) -> Response:
    record = read_index().get(file_hash)
    if record is None:
        raise HTTPException(status_code=404, detail="File not available on this peer")
    if chunk_no < 0 or chunk_no >= record["chunk_count"]:
        raise HTTPException(status_code=404, detail="Chunk not found")

    path = Path(record["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Local file is missing")

    with path.open("rb") as stream:
        stream.seek(chunk_no * CHUNK_SIZE_BYTES)
        data = stream.read(CHUNK_SIZE_BYTES)

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "X-Chunk-Hash": sha256_bytes(data),
            "X-Chunk-No": str(chunk_no),
            "X-Chunk-Count": str(record["chunk_count"]),
        },
    )


@app.post("/download-from-peer")
async def download_from_peer(payload: DownloadFromPeerRequest) -> dict[str, Any]:
    source_url = f"{payload.source_peer_url.rstrip('/')}/download/{payload.file_hash}"
    temp_path = DOWNLOAD_DIR / f".download_{uuid4().hex}.part"

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", source_url) as response:
                response.raise_for_status()
                with temp_path.open("wb") as output:
                    async for chunk in response.aiter_bytes():
                        output.write(chunk)
    except httpx.HTTPError as exc:
        with suppress(FileNotFoundError):
            temp_path.unlink()
        raise HTTPException(status_code=503, detail=f"Peer download failed: {exc}") from exc

    downloaded_hash = sha256_file(temp_path)
    if downloaded_hash != payload.file_hash:
        temp_path.unlink()
        raise HTTPException(status_code=409, detail="Downloaded file hash did not match tracker metadata")

    final_path = file_path_for(downloaded_hash, payload.filename)
    if final_path.exists():
        temp_path.unlink()
    else:
        shutil.move(str(temp_path), final_path)

    record = build_file_record(final_path, payload.filename, payload.subject, payload.semester)
    index = read_index()
    index[payload.file_hash] = record
    write_index(index)
    try:
        await announce_file(record)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Tracker announce failed: {exc}") from exc

    return {
        "status": "downloaded",
        "source_peer_url": payload.source_peer_url,
        "file": record,
    }
