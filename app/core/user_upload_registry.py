"""
Persist uploaded file metadata and learning activity per user (local disk, no Mongo required).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_EXT_TO_CT = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _registry_path() -> str:
    base = os.getenv("OUTPUT_FOLDER", "data/output")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "user_uploads_registry.json")


def _load() -> Dict[str, Any]:
    path = _registry_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Could not read upload registry: %s", e)
        return {}


def _save(data: Dict[str, Any]) -> None:
    path = _registry_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _user_bucket(data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    if user_id not in data:
        data[user_id] = {"files": [], "activities": []}
    b = data[user_id]
    if "files" not in b:
        b["files"] = []
    if "activities" not in b:
        b["activities"] = []
    return b


def _rel_path(abs_path: str) -> str:
    try:
        return os.path.relpath(abs_path, os.getcwd())
    except ValueError:
        return abs_path


def _resolve_stored_path(stored: str) -> str:
    if os.path.isabs(stored):
        return stored
    return os.path.normpath(os.path.join(os.getcwd(), stored))


def record_folder_upload(
    user_id: str,
    temp_folder: str,
    exam_type: str,
    exam_date: str,
    process_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Copy each file from temp_folder into persistent storage and register for user_id."""
    if not user_id or not temp_folder or not os.path.isdir(temp_folder):
        return []

    safe_uid = user_id.replace("/", "_").replace("\\", "_")[:120]
    persist_root = os.path.join(os.getcwd(), "data", "user_uploads", safe_uid)
    os.makedirs(persist_root, exist_ok=True)

    data = _load()
    bucket = _user_bucket(data, user_id)
    added: List[Dict[str, Any]] = []

    for name in sorted(os.listdir(temp_folder)):
        fp = os.path.join(temp_folder, name)
        if not os.path.isfile(fp):
            continue
        try:
            size = os.path.getsize(fp)
        except OSError:
            continue
        ext = os.path.splitext(name)[1].lower()
        dest_name = f"{uuid.uuid4().hex[:12]}_{name}"
        dest_path = os.path.join(persist_root, dest_name)
        try:
            shutil.copy2(fp, dest_path)
        except OSError as e:
            logger.warning("Could not persist upload %s: %s", fp, e)
            continue
        try:
            size = os.path.getsize(dest_path)
        except OSError:
            continue
        rec = {
            "file_id": f"local-{uuid.uuid4().hex}",
            "filename": name,
            "content_type": _EXT_TO_CT.get(ext, "application/octet-stream"),
            "size": size,
            "upload_date": _now_iso(),
            "storage": "local",
            "path": _rel_path(os.path.abspath(dest_path)),
            "metadata": {
                "exam_type": exam_type,
                "exam_date": exam_date,
                **(process_meta or {}),
            },
        }
        bucket["files"].append(rec)
        added.append(rec)

    act = {
        "id": str(uuid.uuid4()),
        "date": _now_iso(),
        "activity": "Upload & content analysis",
        "details": f"{len(added)} file(s) for {exam_type} (exam date {exam_date})",
        "status": "Completed",
    }
    bucket["activities"].insert(0, act)
    bucket["activities"] = bucket["activities"][:200]

    _save(data)
    return added


def log_learning_activity(
    user_id: str,
    activity: str,
    details: str,
    status: str = "Completed",
) -> None:
    if not user_id:
        return
    data = _load()
    bucket = _user_bucket(data, user_id)
    bucket["activities"].insert(
        0,
        {
            "id": str(uuid.uuid4()),
            "date": _now_iso(),
            "activity": activity,
            "details": details,
            "status": status,
        },
    )
    bucket["activities"] = bucket["activities"][:200]
    _save(data)


def list_local_files(user_id: str) -> List[Dict[str, Any]]:
    data = _load()
    bucket = data.get(user_id) or {}
    files = bucket.get("files") or []
    # Drop entries whose path no longer exists
    out: List[Dict[str, Any]] = []
    for f in files:
        p = f.get("path")
        if not p:
            continue
        if os.path.isfile(_resolve_stored_path(p)):
            out.append(f)
    return sorted(out, key=lambda x: x.get("upload_date") or "", reverse=True)


def list_activities(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    data = _load()
    bucket = data.get(user_id) or {}
    acts = bucket.get("activities") or []
    return acts[:limit]


def get_local_file(user_id: str, file_id: str) -> Optional[Dict[str, Any]]:
    for f in list_local_files(user_id):
        if f.get("file_id") == file_id:
            return f
    return None


def absolute_path_for_record(rec: Dict[str, Any]) -> str:
    return _resolve_stored_path(rec.get("path") or "")


def delete_local_file(user_id: str, file_id: str) -> bool:
    if not file_id.startswith("local-"):
        return False
    data = _load()
    bucket = data.get(user_id)
    if not bucket or "files" not in bucket:
        return False

    kept: List[Dict[str, Any]] = []
    removed = False
    for f in bucket["files"]:
        if f.get("file_id") == file_id:
            p = f.get("path")
            if p:
                ap = _resolve_stored_path(p)
                try:
                    if os.path.isfile(ap):
                        os.remove(ap)
                except OSError as e:
                    logger.warning("Could not delete file %s: %s", ap, e)
            removed = True
            continue
        kept.append(f)

    if not removed:
        return False

    bucket["files"] = kept
    bucket.setdefault("activities", []).insert(
        0,
        {
            "id": str(uuid.uuid4()),
            "date": _now_iso(),
            "activity": "File removed",
            "details": f"Deleted {file_id}",
            "status": "Completed",
        },
    )
    bucket["activities"] = bucket["activities"][:200]
    data[user_id] = bucket
    _save(data)
    return True
