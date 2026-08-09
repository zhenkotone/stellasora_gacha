from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_MANIFEST_URL = (
    "https://raw.githubusercontent.com/zhenkotone/stellasora_gacha/main/resource_manifest.json"
)


def _read_url(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "StellaSoraToolkit/1.0"})
    last_error: OSError | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                return response.read()
        except OSError as error:
            last_error = error
            if attempt < 2:
                time.sleep(attempt + 1)
    raise OSError(f"resource download failed: {url}") from last_error


def _safe_asset_path(root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".png":
        raise ValueError(f"invalid resource path: {relative_path}")
    resolved = (root / path).resolve()
    if root.resolve() not in resolved.parents:
        raise ValueError(f"resource path escapes asset directory: {relative_path}")
    return resolved


def update_resources(manifest_url: str, asset_root: Path) -> tuple[list[dict], int]:
    manifest = json.loads(_read_url(manifest_url).decode("utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
        raise ValueError("resource manifest format is invalid")
    base_url = urljoin(manifest_url, str(manifest.get("base_url", "./")))
    if urlparse(base_url).scheme not in {"http", "https"}:
        raise ValueError("resource manifest base URL is invalid")

    downloaded = 0
    asset_root.mkdir(parents=True, exist_ok=True)
    archive_url = manifest.get("archive_url")
    archive_data: zipfile.ZipFile | None = None
    if archive_url:
        payload = _read_url(str(archive_url))
        expected_archive_hash = str(manifest.get("archive_sha256", "")).lower()
        if expected_archive_hash and hashlib.sha256(payload).hexdigest().lower() != expected_archive_hash:
            raise ValueError("resource archive checksum mismatch")
        archive_data = zipfile.ZipFile(io.BytesIO(payload))
    for item in manifest["items"]:
        if not isinstance(item, dict):
            continue
        relative_path = str(item.get("path", ""))
        target = _safe_asset_path(asset_root, relative_path)
        expected_hash = str(item.get("sha256", "")).lower()
        if target.exists() and expected_hash:
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if digest == expected_hash:
                continue
        payload = archive_data.read(relative_path) if archive_data else _read_url(urljoin(base_url, relative_path))
        if expected_hash and hashlib.sha256(payload).hexdigest().lower() != expected_hash:
            raise ValueError(f"resource checksum mismatch: {relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="stella-resource-", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as temp_file:
                temp_file.write(payload)
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        downloaded += 1
    return [item for item in manifest["items"] if isinstance(item, dict)], downloaded
