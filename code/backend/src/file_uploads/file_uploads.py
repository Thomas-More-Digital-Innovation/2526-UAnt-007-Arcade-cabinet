"""
Module for handling game ZIP file uploads and extraction.
"""
import logging
import pathlib
import shutil
import tempfile
import zipfile
from uuid import UUID, uuid4

import puremagic
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import database
from game.internet_assets import localize_internet_assets
from storage.uploads_storage import uploads_storage

logger = logging.getLogger(__name__)

router = APIRouter()


def _determine_game_root(extracted_root: pathlib.Path) -> pathlib.Path | None:
    """Find the directory containing the main HTML file."""
    if (extracted_root / 'index.html').is_file():
        return extracted_root

    # Look for index.html recursively
    for p in extracted_root.rglob('index.html'):
        if p.is_file():
            return p.parent

    # Fallback to any .html file
    for p in extracted_root.rglob('*.html'):
        if p.is_file():
            return p.parent

    return None


def _get_game_root_uri(
    extracted_root: pathlib.Path,
    filename: str,
    game_root_local: pathlib.Path | None
) -> str:
    """Calculate the remote URI for the game root."""
    if not game_root_local:
        return uploads_storage.extracted_root_uri(filename)

    rel_root = game_root_local.relative_to(extracted_root)
    if str(rel_root) == '.':
        return uploads_storage.extracted_root_uri(filename)

    base_uri = uploads_storage.extracted_root_uri(filename).rstrip('/')
    return f"{base_uri}/{str(rel_root).replace('\\', '/')}"


def _save_to_storage(file: UploadFile, filename: str, file_path: pathlib.Path):
    """Save the uploaded file to temporary and then remote storage."""
    try:
        with open(file_path, 'wb') as f:
            while contents := file.file.read(1024 * 1024):
                f.write(contents)
        with open(file_path, 'rb') as f:
            uploads_storage.save_uploaded_zip_from_fileobj(filename, f)
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail='Something went wrong'
        ) from e
    finally:
        file.file.close()


def _process_zip_contents(
    file_path: pathlib.Path,
    game_id: UUID,
    filename: str
) -> str:
    """Extract, localize, and upload the contents of the ZIP file."""
    temp_dir = file_path.parent
    extracted_root = temp_dir / 'extracted_games' / filename
    extracted_root.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(str(file_path), 'r') as zip_ref:
            zip_ref.extractall(extracted_root)

        localization_result = localize_internet_assets(
            str(extracted_root),
            asset_url_prefix=f'/games/{game_id}',
        )
        logger.info(
            'Localized internet assets for %s: %s',
            filename,
            localization_result,
        )

        uploads_storage.upload_tree(
            str(extracted_root),
            uploads_storage.extracted_root_uri(filename)
        )

        game_root_local = _determine_game_root(extracted_root)
        return _get_game_root_uri(extracted_root, filename, game_root_local)

    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=400,
            detail='ZIP extraction/localization failed'
        ) from e


@router.post('/upload-zip')
def upload_zip(
    game_id: UUID,
    file: UploadFile = File(...),  # noqa: B008
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """
    Upload a ZIP file containing a game, extract it, and localize assets.
    """
    generated_uuid = uuid4().hex
    filename = f'{generated_uuid}.zip'

    temp_dir = tempfile.mkdtemp(prefix='upload_zip_')
    temp_path = pathlib.Path(temp_dir)
    file_path = temp_path / filename

    try:
        _save_to_storage(file, filename, file_path)

        mime_type = puremagic.from_file(str(file_path), True)
        if mime_type != 'application/zip':
            raise HTTPException(
                status_code=400,
                detail='Only ZIP files are allowed'
            )

        game_root_uri = _process_zip_contents(file_path, game_id, filename)

        zip_upload = database.ZipUpload(
            name=filename,
            game_id=game_id,
            game_root_uri=game_root_uri
        )
        db.add(zip_upload)
        db.commit()

        return {'message': f'Successfully uploaded {file.filename}'}

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
