"""
Module for downloading and localizing internet assets referenced in game files.
"""
import hashlib
import logging
import mimetypes
import os
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_HTTP_URL_PATTERN = re.compile(r'https?://[^\s"\'<>)]+', re.IGNORECASE)


_TEXT_EXTENSIONS = {
    '.html',
    '.htm',
    '.css',
    '.js',
    '.mjs',
    '.json',
    '.xml',
    '.svg',
    '.txt',
}


def _guess_extension(url: str, content_type: str | None) -> str:
    parsed = urlparse(url)
    path_ext = os.path.splitext(parsed.path)[1]
    if path_ext and len(path_ext) <= 10:
        return path_ext

    if content_type:
        mime_type = content_type.split(';')[0].strip()
        guessed = mimetypes.guess_extension(mime_type)
        if guessed:
            return guessed

    return ''


def _download_asset(url: str, downloads_dir: str, max_bytes: int) -> str:
    request = Request(
        url,
        headers={'User-Agent': 'ArcadeCabinetAssetLocalizer/1.0'},
    )

    with urlopen(request, timeout=15) as response:
        content_type = response.headers.get('Content-Type')
        extension = _guess_extension(url, content_type)
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:24]
        filename = f'{url_hash}{extension}'
        destination = os.path.join(downloads_dir, filename)

        if os.path.exists(destination):
            return destination

        total = 0
        with open(destination, 'wb') as output:
            while True:
                chunk = response.read(1024 * 64)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    output.close()
                    os.remove(destination)
                    raise ValueError(f'Downloaded asset too large: {url}')
                output.write(chunk)

        return destination


def _get_local_asset_path(
    url: str, cache: dict, downloads_dir: str, max_size: int
) -> str | None:
    local_path = cache.get(url)
    if local_path is None:
        try:
            local_path = _download_asset(url, downloads_dir, max_size)
            cache[url] = local_path
        except Exception as exc:  # noqa: PLW718
            logger.warning('Could not localize URL %s: %s', url, exc)
            return None
    return local_path


def _calculate_rel_path(
    local_path: str, asset_url_prefix: str | None, root: str
) -> str:
    if asset_url_prefix:
        return (
            f'{asset_url_prefix.rstrip("/")}/_downloaded_assets/'
            f'{os.path.basename(local_path)}'
        )

    return os.path.relpath(local_path, root).replace('\\', '/')


def _process_file(

    file_path: str,
    downloads_dir: str,
    cache: dict,
    asset_url_prefix: str | None,
    root: str
) -> bool:
    try:
        with open(
            file_path, 'r', encoding='utf-8', errors='ignore'
        ) as source_file:
            original_text = source_file.read()
    except Exception:  # noqa: PLW718
        return False

    urls = set(_HTTP_URL_PATTERN.findall(original_text))
    if not urls:
        return False

    updated_text = original_text
    changed = False
    max_asset_size = 25 * 1024 * 1024

    for url in urls:
        local_path = _get_local_asset_path(
            url, cache, downloads_dir, max_asset_size
        )
        if not local_path:
            continue

        rel_local_path = _calculate_rel_path(
            local_path, asset_url_prefix, root
        )

        if url in updated_text:
            updated_text = updated_text.replace(url, rel_local_path)
            changed = True

    if changed and updated_text != original_text:
        with open(file_path, 'w', encoding='utf-8') as destination_file:
            destination_file.write(updated_text)
        return True
    return False


def localize_internet_assets(
    extracted_root: str,
    asset_url_prefix: str | None = None
) -> dict:
    """
    Download external http(s) assets and rewrite references to local files.
    """
    downloaded_assets_dir = os.path.join(extracted_root, '_downloaded_assets')
    os.makedirs(downloaded_assets_dir, exist_ok=True)

    cache: dict[str, str] = {}
    stats = {'rewritten_files': 0, 'downloaded_assets': 0}

    for root, _, files in os.walk(extracted_root):
        if os.path.abspath(root).startswith(
            os.path.abspath(downloaded_assets_dir)
        ):
            continue

        for name in files:
            if os.path.splitext(name)[1].lower() not in _TEXT_EXTENSIONS:
                continue

            file_path = os.path.join(root, name)
            if _process_file(
                file_path, downloaded_assets_dir, cache, asset_url_prefix, root
            ):
                stats['rewritten_files'] += 1

    stats['downloaded_assets'] = len(cache)
    return stats
