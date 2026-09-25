"""Local password gate for the v1 Streamlit UI. Not DRM."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

AUTH_NAME = "auth.json"


def auth_path(settings_dir: Path) -> Path:
    return Path(settings_dir) / AUTH_NAME


def hash_password(password: str, *, salt: bytes | None = None) -> dict[str, str]:
    if not password:
        raise ValueError("password is empty")
    salt = salt or os.urandom(16)
    hashed = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return {"kdf": "scrypt", "salt": salt.hex(), "hash": hashed.hex()}


def verify_password(password: str, record: dict[str, Any]) -> bool:
    try:
        salt = bytes.fromhex(str(record["salt"]))
        expected = bytes.fromhex(str(record["hash"]))
    except (KeyError, ValueError):
        return False
    hashed = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return secrets.compare_digest(hashed, expected)


def load_auth(settings_dir: Path) -> dict[str, Any] | None:
    path = auth_path(settings_dir)
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        return None
    return data


def write_auth(
    settings_dir: Path,
    password: str,
    *,
    language: str = "en",
    threads: int = 4,
    lab_name: str = "",
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(existing or {})
    payload.update(hash_password(password))
    payload["language"] = language
    payload["threads"] = int(threads)
    payload["lab_name"] = lab_name
    path = auth_path(settings_dir)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def update_settings(
    settings_dir: Path,
    *,
    language: str | None = None,
    threads: int | None = None,
    lab_name: str | None = None,
) -> dict[str, Any]:
    data = load_auth(settings_dir)
    if data is None:
        raise FileNotFoundError(auth_path(settings_dir))
    if language is not None:
        data["language"] = language
    if threads is not None:
        data["threads"] = int(threads)
    if lab_name is not None:
        data["lab_name"] = lab_name
    auth_path(settings_dir).write_text(json.dumps(data, indent=2) + "\n")
    return data


def change_password(settings_dir: Path, new_password: str) -> dict[str, Any]:
    data = load_auth(settings_dir)
    if data is None:
        raise FileNotFoundError(auth_path(settings_dir))
    return write_auth(
        settings_dir,
        new_password,
        language=str(data.get("language") or "en"),
        threads=int(data.get("threads") or 4),
        lab_name=str(data.get("lab_name") or ""),
        existing=data,
    )
