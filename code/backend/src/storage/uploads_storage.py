import mimetypes
from pathlib import Path
from typing import BinaryIO

from config import config

try:
    import s3fs
except Exception:  # pragma: no cover
    s3fs = None


class UploadStorage:
    def __init__(self):
        self.backend = (config.uploads_backend or "").lower()
        self.remote_root = (config.uploads_remote_root or "").rstrip("/")
        self._s3fs = None

    def _s3(self):
        if self.backend != "s3":
            raise RuntimeError("Only S3 backend is supported. Set UPLOADS_BACKEND=s3.")
        if s3fs is None:
            raise RuntimeError("s3fs is not installed")
        if not self.remote_root.startswith("s3://"):
            raise RuntimeError("UPLOADS_REMOTE_ROOT must be an s3:// URI")
        if self._s3fs is not None:
            return self._s3fs

        endpoint_url = config.s3_endpoint_url.strip() if config.s3_endpoint_url else None
        key = config.s3_access_key_id.strip() if config.s3_access_key_id else None
        secret = config.s3_secret_access_key.strip() if config.s3_secret_access_key else None
        token = config.s3_session_token.strip() if config.s3_session_token else None

        client_kwargs = {}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url

        self._s3fs = s3fs.S3FileSystem(
            key=key,
            secret=secret,
            token=token,
            client_kwargs=client_kwargs,
            default_fill_cache=False,
            anon=False,
        )
        return self._s3fs

    def _remote_uri(self, *parts: str) -> str:
        clean_parts = [p.strip("/") for p in parts if p]
        if not clean_parts:
            return self.remote_root
        return f"{self.remote_root}/" + "/".join(clean_parts)

    def uploaded_zip_uri(self, filename: str) -> str:
        return self._remote_uri("uploaded_zips", filename)

    def extracted_root_uri(self, filename: str) -> str:
        return self._remote_uri("extracted_games", filename)

    def original_asset_uri(self, zip_filename: str, relative_path: str) -> str:
        return self._remote_uri("extracted_games", zip_filename, relative_path)

    def save_uploaded_zip_from_fileobj(self, filename: str, input_file: BinaryIO) -> str:
        remote_uri = self.uploaded_zip_uri(filename)
        with self._s3().open(remote_uri, "wb") as out:
            while True:
                chunk = input_file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        return remote_uri

    def save_asset_override(self, game_id: str, safe_filename: str, input_file: BinaryIO) -> str:
        remote_uri = self._remote_uri("asset_overrides", game_id, safe_filename)
        with self._s3().open(remote_uri, "wb") as out:
            while True:
                chunk = input_file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        return remote_uri

    def exists_path(self, path: str) -> bool:
        return self._s3().exists(path)

    def open_binary(self, path: str):
        return self._s3().open(path, "rb")

    def path_is_file(self, path: str) -> bool:
        try:
            info = self._s3().info(path)
            return info.get("type") == "file"
        except FileNotFoundError:
            return False

    def prefix_has_files(self, prefix_uri: str) -> bool:
        try:
            items = self._s3().ls(prefix_uri)
            return len(items) > 0
        except FileNotFoundError:
            return False

    def upload_tree(self, local_dir: str, remote_prefix_uri: str) -> None:
        remote_prefix_uri = remote_prefix_uri.rstrip("/")
        local_root = Path(local_dir)
        for local_path in local_root.rglob("*"):
            if not local_path.is_file():
                continue
            rel = local_path.relative_to(local_root).as_posix()
            remote_path = f"{remote_prefix_uri}/{rel}"
            self._s3().put(str(local_path), remote_path)

    def walk_files(self, prefix_uri: str) -> list[str]:
        return [p for p in self._s3().find(prefix_uri, withdirs=False)]

    def guess_content_type(self, path: str) -> str | None:
        guessed, _ = mimetypes.guess_type(path)
        return guessed


uploads_storage = UploadStorage()
