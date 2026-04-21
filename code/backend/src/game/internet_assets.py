import hashlib
import logging
import mimetypes
import os
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_HTTP_URL_PATTERN = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)
_TEXT_EXTENSIONS = {
    ".html",
    ".htm",
    ".css",
    ".js",
    ".mjs",
    ".json",
    ".xml",
    ".svg",
    ".txt",
}


def _guess_extension(url: str, content_type: str | None) -> str:
    parsed = urlparse(url)
    path_ext = os.path.splitext(parsed.path)[1]
    if path_ext and len(path_ext) <= 10:
        return path_ext

    if content_type:
        mime_type = content_type.split(";")[0].strip()
        guessed = mimetypes.guess_extension(mime_type)
        if guessed:
            return guessed

    return ""


def _download_asset(url: str, downloads_dir: str, max_bytes: int) -> str:
    request = Request(
        url,
        headers={"User-Agent": "ArcadeCabinetAssetLocalizer/1.0"},
    )

    with urlopen(request, timeout=15) as response:
        content_type = response.headers.get("Content-Type")
        extension = _guess_extension(url, content_type)
        filename = f"{hashlib.sha256(url.encode('utf-8')).hexdigest()[:24]}{extension}"
        destination = os.path.join(downloads_dir, filename)

        if os.path.exists(destination):
            return destination

        total = 0
        with open(destination, "wb") as output:
            while True:
                chunk = response.read(1024 * 64)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    output.close()
                    os.remove(destination)
                    raise ValueError(f"Downloaded asset too large: {url}")
                output.write(chunk)

        return destination


def localize_internet_assets(extracted_root: str, asset_url_prefix: str | None = None) -> dict:
    """Download external http(s) assets and rewrite references to local files."""
    downloaded_assets_dir = os.path.join(extracted_root, "_downloaded_assets")
    os.makedirs(downloaded_assets_dir, exist_ok=True)

    max_asset_size = 25 * 1024 * 1024
    cache: dict[str, str] = {}

    rewritten_files = 0
    downloaded_count = 0
    failed_urls = 0

    for root, _, files in os.walk(extracted_root):
        if os.path.abspath(root).startswith(os.path.abspath(downloaded_assets_dir)):
            continue

        for name in files:
            if os.path.splitext(name)[1].lower() not in _TEXT_EXTENSIONS:
                continue

            file_path = os.path.join(root, name)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as source_file:
                    original_text = source_file.read()
            except Exception:
                continue

            urls = set(_HTTP_URL_PATTERN.findall(original_text))
            if not urls:
                continue

            updated_text = original_text
            changed = False

            for url in urls:
                local_path = cache.get(url)
                if local_path is None:
                    try:
                        local_path = _download_asset(url, downloaded_assets_dir, max_asset_size)
                        cache[url] = local_path
                        downloaded_count += 1
                    except Exception as exc:
                        failed_urls += 1
                        logger.warning("Could not localize URL %s: %s", url, exc)
                        continue

                if asset_url_prefix:
                    rel_local_path = f"{asset_url_prefix.rstrip('/')}/_downloaded_assets/{os.path.basename(local_path)}"
                else:
                    rel_local_path = os.path.relpath(local_path, root).replace("\\", "/")
                if url in updated_text:
                    updated_text = updated_text.replace(url, rel_local_path)
                    changed = True

            if changed and updated_text != original_text:
                with open(file_path, "w", encoding="utf-8") as destination_file:
                    destination_file.write(updated_text)
                rewritten_files += 1

    return {
        "rewritten_files": rewritten_files,
        "downloaded_assets": downloaded_count,
        "failed_urls": failed_urls,
    }
