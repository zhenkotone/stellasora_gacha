from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


UPDATE_SOURCE = os.environ.get("STELLASORA_UPDATE_SOURCE", "gitee").lower()
UPDATE_MANIFEST_URLS = {
    "github": "https://raw.githubusercontent.com/zhenkotone/stellasora_gacha/main/app_update_github.json",
    "gitee": "https://gitee.com/zhen-z/stellasora_gacha/raw/master/app_update_gitee.json",
}
UPDATE_MANIFEST_URL = UPDATE_MANIFEST_URLS.get(UPDATE_SOURCE, UPDATE_MANIFEST_URLS["gitee"])
ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class AppUpdate:
    version: str
    url: str
    sha256: str
    notes: str


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = value.strip().lower().removeprefix("v").split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError(f"invalid version: {value}")
    return tuple(int(part) for part in parts)


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_parts = _version_tuple(candidate)
    current_parts = _version_tuple(current)
    length = max(len(candidate_parts), len(current_parts))
    return candidate_parts + (0,) * (length - len(candidate_parts)) > current_parts + (0,) * (length - len(current_parts))


def check_for_update(manifest_url: str, current_version: str) -> AppUpdate | None:
    request = Request(manifest_url, headers={"User-Agent": "StellaSoraToolkit/1.0"})
    with urlopen(request, timeout=12) as response:
        manifest = json.loads(response.read().decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("app update manifest format is invalid")
    update = AppUpdate(
        version=str(manifest["version"]),
        url=str(manifest["url"]),
        sha256=str(manifest["sha256"]).lower(),
        notes=str(manifest.get("notes", "")),
    )
    if urlparse(update.url).scheme != "https" or len(update.sha256) != 64:
        raise ValueError("app update manifest is invalid")
    return update if is_newer_version(update.version, current_version) else None


def download_update(update: AppUpdate, target_dir: Path, progress: ProgressCallback | None = None) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="stellasora-update-", suffix=".exe", dir=target_dir)
    digest = hashlib.sha256()
    try:
        request = Request(update.url, headers={"User-Agent": "StellaSoraToolkit/1.0"})
        with os.fdopen(fd, "wb") as output, urlopen(request, timeout=30) as response:
            total = int(response.headers.get("Content-Length", 0))
            received = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if progress and total:
                    progress(f"正在下载软件更新 {received * 100 // total}%")
        if digest.hexdigest().lower() != update.sha256:
            raise ValueError("software update checksum mismatch")
        return Path(temp_name)
    except Exception:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise
