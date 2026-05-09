from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field


APP_NAME = "Jazz Jarvis"
PORT = int(os.getenv("JARVIS_PORT", "43432"))
CORE_API = os.getenv("JARVIS_CORE_API", "http://127.0.0.1:8000").rstrip("/")
WORKSPACE_ROOT = Path(os.getenv("JARVIS_WORKSPACE", "/root/jazzai/jarvis_workspace")).resolve()
MAX_UPLOAD_BYTES = int(os.getenv("JARVIS_MAX_UPLOAD_BYTES", str(250 * 1024 * 1024)))
MAX_TEXT_BYTES = int(os.getenv("JARVIS_MAX_TEXT_BYTES", str(2 * 1024 * 1024)))
MAX_DIR_ITEMS = 500

WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=APP_NAME, version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.jazzai.online",
        "https://jazzai.online",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://45.79.124.28:43432",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=200_000)
    model_id: str = "kimi-k2.6-nvidia"
    session_id: Optional[str] = None
    speak: bool = True
    file_context: str = ""


class FileWriteRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    content: str = Field("", max_length=5_000_000)
    encoding: str = Field("text", pattern="^(text|base64)$")
    overwrite: bool = True


class FileMoveRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=500)
    target: str = Field(..., min_length=1, max_length=500)
    overwrite: bool = False


class MkdirRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)


class FileActionRequest(BaseModel):
    op: str = Field(..., pattern="^(list|read|write|append|delete|mkdir|move|copy)$")
    path: str = Field("", max_length=500)
    target: str = Field("", max_length=500)
    content: str = Field("", max_length=5_000_000)
    encoding: str = Field("text", pattern="^(text|base64)$")
    overwrite: bool = False


def _auth_headers(authorization: Optional[str]) -> Dict[str, str]:
    return {"Authorization": authorization} if authorization else {}


def _auth_from_query(authorization: Optional[str], token: Optional[str]) -> Optional[str]:
    if authorization:
        return authorization
    if token:
        return "Bearer " + token
    return None


async def _require_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(401, "Not authenticated")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{CORE_API}/auth/me", headers=_auth_headers(authorization))
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, "Jazz session is not valid")
    return resp.json()


def _clean_rel(raw: str) -> Path:
    raw = (raw or "").strip().replace("\\", "/")
    if raw in {"", ".", "/"}:
        return Path("")
    if "\x00" in raw:
        raise HTTPException(400, "Invalid path")
    rel = Path(raw.lstrip("/"))
    if any(part in {"..", ""} for part in rel.parts):
        raise HTTPException(400, "Path must stay inside Jarvis workspace")
    return rel


def _safe_path(raw: str) -> Path:
    target = (WORKSPACE_ROOT / _clean_rel(raw)).resolve()
    try:
        target.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise HTTPException(403, "Path escapes Jarvis workspace")
    return target


def _rel(p: Path) -> str:
    return str(p.resolve().relative_to(WORKSPACE_ROOT)).replace("\\", "/")


def _file_info(p: Path) -> Dict[str, Any]:
    st = p.stat()
    is_dir = p.is_dir()
    mime = "inode/directory" if is_dir else (mimetypes.guess_type(p.name)[0] or "application/octet-stream")
    return {
        "name": p.name,
        "path": _rel(p),
        "type": "directory" if is_dir else "file",
        "mime": mime,
        "size": 0 if is_dir else st.st_size,
        "modified": int(st.st_mtime),
    }


def _read_file(path: str) -> Dict[str, Any]:
    p = _safe_path(path)
    if not p.exists():
        raise HTTPException(404, "File not found")
    if p.is_dir():
        return {"entry": _file_info(p), "children": _list_dir(path)["items"]}
    data = p.read_bytes()
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    is_text = mime.startswith("text/") or p.suffix.lower() in {
        ".txt", ".md", ".csv", ".json", ".xml", ".html", ".css", ".js", ".ts",
        ".tsx", ".jsx", ".py", ".java", ".c", ".cpp", ".cs", ".go", ".rs",
        ".php", ".rb", ".yml", ".yaml", ".toml", ".ini", ".log", ".tex",
    }
    payload: Dict[str, Any] = {"entry": _file_info(p), "mime": mime, "truncated": False}
    if is_text:
        clipped = data[:MAX_TEXT_BYTES]
        payload["content"] = clipped.decode("utf-8", errors="replace")
        payload["encoding"] = "text"
        payload["truncated"] = len(data) > len(clipped)
    else:
        clipped = data[:MAX_TEXT_BYTES]
        payload["content"] = base64.b64encode(clipped).decode("ascii")
        payload["encoding"] = "base64"
        payload["truncated"] = len(data) > len(clipped)
    return payload


def _list_dir(path: str = "") -> Dict[str, Any]:
    root = _safe_path(path)
    if not root.exists():
        raise HTTPException(404, "Folder not found")
    if not root.is_dir():
        raise HTTPException(400, "Path is not a folder")
    items = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:MAX_DIR_ITEMS]
    return {"root": str(WORKSPACE_ROOT), "path": _rel(root) if root != WORKSPACE_ROOT else "", "items": [_file_info(p) for p in items]}


def _write_file(req: FileWriteRequest, append: bool = False) -> Dict[str, Any]:
    p = _safe_path(req.path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and p.is_dir():
        raise HTTPException(400, "Cannot write over a directory")
    if p.exists() and not req.overwrite and not append:
        raise HTTPException(409, "File already exists")
    data = base64.b64decode(req.content) if req.encoding == "base64" else req.content.encode("utf-8")
    mode = "ab" if append else "wb"
    with p.open(mode) as f:
        f.write(data)
    return {"ok": True, "entry": _file_info(p)}


def _delete_path(path: str) -> Dict[str, Any]:
    p = _safe_path(path)
    if not p.exists():
        raise HTTPException(404, "Path not found")
    if p == WORKSPACE_ROOT:
        raise HTTPException(400, "Cannot delete workspace root")
    info = _file_info(p)
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return {"ok": True, "deleted": info}


async def _proxy_sse_to_core(req: ChatRequest, authorization: str):
    jarvis_preamble = (
        "You are Jazz Jarvis, a fast realtime AI operator with concise spoken responses. "
        "Sound like a polished futuristic assistant: calm, witty, precise, and action-oriented. "
        "Do not claim you changed files unless a file operation result is included. "
        "If the user asks for file changes, explain the exact operation needed or use the provided file context. "
        "Keep voice replies short unless the user asks for detail.\n\n"
    )
    file_context = f"\n\n[Jarvis visible files/context]\n{req.file_context[:12000]}" if req.file_context else ""
    payload = {
        "message": jarvis_preamble + req.message + file_context,
        "model_id": req.model_id,
        "session_id": req.session_id,
        "use_rag": True,
        "web_search": False,
        "plan_mode": False,
        "tools": {"rag": True, "web_search": False, "plan_mode": False},
    }
    headers = {"Authorization": authorization, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", f"{CORE_API}/chat/stream", headers=headers, json=payload) as resp:
            if resp.status_code >= 400:
                detail = await resp.aread()
                yield f"data: {json.dumps({'type':'error','message':detail.decode('utf-8', 'ignore')[:500]})}\n\n"
                return
            async for chunk in resp.aiter_bytes():
                if chunk:
                    yield chunk


@app.get("/health")
async def health():
    return {"ok": True, "service": APP_NAME, "port": PORT, "workspace": str(WORKSPACE_ROOT), "core_api": CORE_API}


@app.get("/", response_class=HTMLResponse)
async def landing():
    return """
<!doctype html><meta charset="utf-8">
<title>Jazz Jarvis Backend</title>
<body style="font-family:system-ui;background:#05070d;color:#dbeafe;padding:32px">
<h1>Jazz Jarvis backend online</h1>
<p>Use the Jazz AI Jarvis page at <a style="color:#7df9ff" href="https://www.jazzai.online/jarvis">www.jazzai.online/jarvis</a>.</p>
</body>
"""


@app.get("/models")
async def models(authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{CORE_API}/model-info", headers=_auth_headers(authorization))
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, "Could not load Jazz models")
    return resp.json()


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    return StreamingResponse(_proxy_sse_to_core(req, authorization or ""), media_type="text/event-stream")


@app.get("/files")
async def files(path: str = "", authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    return _list_dir(path)


@app.get("/files/read")
async def read_file(path: str = Query(...), authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    return _read_file(path)


@app.post("/files/write")
async def write_file(req: FileWriteRequest, authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    return _write_file(req)


@app.post("/files/append")
async def append_file(req: FileWriteRequest, authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    return _write_file(req, append=True)


@app.post("/files/mkdir")
async def mkdir(req: MkdirRequest, authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    p = _safe_path(req.path)
    p.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "entry": _file_info(p)}


@app.patch("/files/move")
async def move_file(req: FileMoveRequest, authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    src = _safe_path(req.source)
    dst = _safe_path(req.target)
    if not src.exists():
        raise HTTPException(404, "Source not found")
    if dst.exists() and not req.overwrite:
        raise HTTPException(409, "Target already exists")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    shutil.move(str(src), str(dst))
    return {"ok": True, "entry": _file_info(dst)}


@app.delete("/files")
async def delete_file(path: str = Query(...), authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    return _delete_path(path)


@app.post("/files/upload")
async def upload_file(path: str = "", file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    folder = _safe_path(path)
    folder.mkdir(parents=True, exist_ok=True)
    name = Path(file.filename or f"upload-{int(time.time())}").name
    target = (folder / name).resolve()
    try:
        target.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise HTTPException(403, "Invalid upload path")
    total = 0
    with target.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                f.close()
                target.unlink(missing_ok=True)
                raise HTTPException(413, "Upload too large")
            f.write(chunk)
    return {"ok": True, "entry": _file_info(target)}


@app.get("/files/download")
async def download_file(path: str = Query(...), token: Optional[str] = None, authorization: Optional[str] = Header(None)):
    await _require_user(_auth_from_query(authorization, token))
    p = _safe_path(path)
    if not p.exists() or p.is_dir():
        raise HTTPException(404, "File not found")
    return FileResponse(p, filename=p.name, media_type=mimetypes.guess_type(p.name)[0] or "application/octet-stream")


@app.get("/files/zip")
async def zip_path(path: str = "", token: Optional[str] = None, authorization: Optional[str] = Header(None)):
    await _require_user(_auth_from_query(authorization, token))
    src = _safe_path(path)
    if not src.exists():
        raise HTTPException(404, "Path not found")
    zip_name = f"jarvis-{src.name or 'workspace'}-{int(time.time())}.zip"
    out = WORKSPACE_ROOT / ".exports" / zip_name
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        if src.is_file():
            z.write(src, arcname=src.name)
        else:
            for p in src.rglob("*"):
                if p.is_file() and ".exports" not in p.parts:
                    z.write(p, arcname=str(p.relative_to(src)))
    return FileResponse(out, filename=zip_name, media_type="application/zip")


@app.post("/files/action")
async def file_action(req: FileActionRequest, authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    if req.op == "list":
        return _list_dir(req.path)
    if req.op == "read":
        return _read_file(req.path)
    if req.op == "write":
        return _write_file(FileWriteRequest(path=req.path, content=req.content, encoding=req.encoding, overwrite=req.overwrite))
    if req.op == "append":
        return _write_file(FileWriteRequest(path=req.path, content=req.content, encoding=req.encoding, overwrite=True), append=True)
    if req.op == "delete":
        return _delete_path(req.path)
    if req.op == "mkdir":
        p = _safe_path(req.path); p.mkdir(parents=True, exist_ok=True); return {"ok": True, "entry": _file_info(p)}
    if req.op in {"move", "copy"}:
        src = _safe_path(req.path); dst = _safe_path(req.target)
        if not src.exists():
            raise HTTPException(404, "Source not found")
        if dst.exists() and not req.overwrite:
            raise HTTPException(409, "Target already exists")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if req.op == "copy":
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        else:
            if dst.exists():
                shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
            shutil.move(str(src), str(dst))
        return {"ok": True, "entry": _file_info(dst)}
    raise HTTPException(400, "Unsupported operation")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("jarvis_server:app", host="0.0.0.0", port=PORT, reload=False)
