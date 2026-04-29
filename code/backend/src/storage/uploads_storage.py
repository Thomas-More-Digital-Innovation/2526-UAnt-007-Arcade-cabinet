"""Module for managing file uploads."""
import mimetypes
from typing import BinaryIO

import s3fs  # type: ignore

from config import config


class UploadStorage:
    """
    Class for managing file uploads to the remote storage.

    Attributes:
        backend (str): The backend to use for file uploads.
        remote_root (str): The root directory for file uploads.
        _s3fs: The S3FileSystem instance.
    """
    def __init__(self):
        self.backend = (config.uploads_backend or '').lower()
        self.remote_root = (config.uploads_remote_root or '').rstrip('/')
        self._s3fs = None

    def _s3(self):
        if self.backend != 's3':
            raise RuntimeError(
                'Only S3 backend is supported.'
                ' Set UPLOADS_BACKEND=s3.'
            )
        if not self.remote_root.startswith('s3://'):
            raise RuntimeError('UPLOADS_REMOTE_ROOT must be an s3:// URI')
        if self._s3fs is not None:
            return self._s3fs

        endpoint_url = (
            config.s3_endpoint_url.strip()
            if config.s3_endpoint_url else None
        )
        key = (
            config.s3_access_key_id.strip()
            if config.s3_access_key_id else None
        )
        secret = (
            config.s3_secret_access_key.strip()
            if config.s3_secret_access_key else None
        )
        token = (
            config.s3_session_token.strip()
            if config.s3_session_token else None
        )

        client_kwargs = {}
        if endpoint_url:
            client_kwargs['endpoint_url'] = endpoint_url

        self._s3fs = s3fs.S3FileSystem(
            key=key,
            secret=secret,
            token=token,
            client_kwargs=client_kwargs,
            default_fill_cache=True,
            anon=False,
        )
        return self._s3fs

    def _remote_uri(self, *parts: str) -> str:
        clean_parts = [p.strip('/') for p in parts if p]
        if not clean_parts:
            return self.remote_root
        return f'{self.remote_root}/' + '/'.join(clean_parts)

    def uploaded_zips_root_uri(self) -> str:
        """
            Returns the remote URI for the uploaded zips directory.
        """
        return self._remote_uri('uploaded_zips')

    def uploaded_zip_uri(self, filename: str) -> str:
        """
            Returns the remote URI for an uploaded zip file.
        """
        return self._remote_uri('uploaded_zips', filename)

    def extracted_root_uri(self, filename: str) -> str:
        """
            Returns the remote URI for an extracted game root directory.
        """
        return self._remote_uri('extracted_games', filename)

    def asset_override_root_uri(self, game_id: str) -> str:
        """
            Returns the remote URI for a game's asset overrides directory.
        """
        return self._remote_uri('asset_overrides', game_id)

    def original_asset_uri(self, zip_filename: str, relative_path: str) -> str:
        """
            Returns the remote URI for an original asset file.
        """
        return self._remote_uri('extracted_games', zip_filename, relative_path)

    def save_uploaded_zip_from_fileobj(
        self,
        filename: str,
        input_file: BinaryIO
    ) -> str:
        """
            Saves an uploaded zip file to the remote storage.
        """
        remote_uri = self.uploaded_zip_uri(filename)
        with self._s3().open(remote_uri, 'wb') as out:
            while True:
                chunk = input_file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)  # type: ignore[reportArgumentType]
        return remote_uri

    def save_asset_override(
        self, game_id: str,
        safe_filename: str,
        input_file: BinaryIO
    ) -> str:
        """
            Saves an asset override file to the remote storage.
        """
        remote_uri = self._remote_uri(
            self.asset_override_root_uri(game_id),
            safe_filename
        )

        with self._s3().open(remote_uri, 'wb') as out:
            while True:
                chunk = input_file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)  # type: ignore[reportArgumentType]
        return remote_uri

    def exists_path(self, path: str) -> bool:
        """
            Checks if the given path exists.
        """
        return self._s3().exists(path)

    def open_binary(self, path: str):
        """
            Opens the given path in binary mode.
        """
        return self._s3().open(path, 'rb')

    def path_is_file(self, path: str) -> bool:
        """
            Checks if the given path is a file.
        """
        try:
            info = self._s3().info(path)
            return info.get('type') == 'file'
        except FileNotFoundError:
            return False

    def prefix_has_files(self, prefix_uri: str) -> bool:
        """
            Checks if the given prefix_uri has any files.
        """
        try:
            items = self._s3().ls(prefix_uri)
            return len(items) > 0
        except FileNotFoundError:
            return False

    def upload_tree(self, local_dir: str, remote_prefix_uri: str) -> None:
        """
            Uploads the given directory to the remote prefix_uri.
        """
        # s3fs put() supports recursive=True
        # and is highly optimized for directory uploads
        self._s3().put(local_dir, remote_prefix_uri, recursive=True)

    def walk_files(self, prefix_uri: str) -> list[str]:
        """
            Walks the given prefix_uri and returns a list of all file paths.
        """
        return list(self._s3().find(prefix_uri, withdirs=False))

    def guess_content_type(self, path: str) -> str | None:
        """
            Guesses the content type of a file based on its extension.
        """
        guessed, _ = mimetypes.guess_type(path)
        return guessed

    def delete_path(self, path: str, recursive: bool = False) -> None:
        """
            Deletes the given path. If recursive is True,
            deletes the path and all its contents.
        """
        try:
            if self._s3().exists(path):
                self._s3().rm(path, recursive=recursive)
        except Exception:  # noqa: PLW718
            # Optionally log,
            # or allow failure if bucket doesn't actually have the file
            pass


uploads_storage = UploadStorage()
