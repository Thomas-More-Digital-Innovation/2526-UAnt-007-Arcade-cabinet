"""
Game management and file serving routes.
"""
import logging
import posixpath
import traceback
from uuid import UUID

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_api_key
from database import database
from storage.uploads_storage import uploads_storage

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_virtual_path(p: str) -> str:
    """Normalize paths coming from URLs/forms so overrides match reliably."""
    if p is None:
        return ''
    p = p.replace('\\', '/').strip()
    while p.startswith('/'):
        p = p[1:]
    if p.startswith('./'):
        p = p[2:]
    p = posixpath.normpath(p)
    if p == '.':
        return ''
    return p


@router.get('/', dependencies=[Depends(get_api_key)])
def get_all_games(db: Session = Depends(database.get_session)):  # noqa: B008
    """Retrieve all games from the database."""
    return {'games': db.query(database.Game).all()}


class GameCreateRequest(BaseModel):
    """Pydantic model for game creation."""
    name: str
    description: str | None = None


@router.post('/', dependencies=[Depends(get_api_key)])
def create_game(
    request: GameCreateRequest,
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """Create a new game record."""
    new_game = database.Game(
        name=request.name,
        description=request.description
    )
    db.add(new_game)
    db.commit()
    return {
        'game': {
            'id': new_game.id,
            'name': new_game.name,
            'description': new_game.description
        }
    }


class GamePutRequest(BaseModel):
    """Pydantic model for updating a game."""
    id: UUID  # noqa: A003
    name: str
    description: str | None = None


@router.put('/{game_id}', dependencies=[Depends(get_api_key)])
def update_game(
    game_id: UUID,
    request: GamePutRequest,
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """Update an existing game record."""
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail='Game not found')
    game.name = request.name
    game.description = request.description
    db.commit()
    return {
        'game': {
            'id': game.id,
            'name': game.name,
            'description': game.description
        }
    }


@router.delete('/{game_id}', dependencies=[Depends(get_api_key)])
def delete_game(
    game_id: UUID,
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """Delete a game and all its associated assets."""
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail='Game not found')

    # Delete associated zip uploads and assets from DB and S3
    for zip_upload in game.zip_uploads:
        try:
            uploads_storage.delete_path(
                uploads_storage.uploaded_zip_uri(zip_upload.name)
            )
            uploads_storage.delete_path(
                uploads_storage.extracted_root_uri(zip_upload.name),
                recursive=True
            )
        except Exception as e:  # noqa: PLW718
            logger.error(
                'Error deleting zip %s from S3: %s',
                zip_upload.name,
                e
            )
        db.delete(zip_upload)

    for asset in game.assets:
        try:
            uploads_storage.delete_path(asset.path)
        except Exception as e:  # noqa: PLW718
            logger.error('Error deleting asset %s from S3: %s', asset.path, e)
        db.delete(asset)

    try:
        uploads_storage.delete_path(
            uploads_storage.asset_override_root_uri(str(game_id)),
            recursive=True
        )

    except Exception as e:  # noqa: PLW718
        logger.error(
            'Error deleting overrides for game %s from S3: %s',
            game_id,
            e
        )

    db.delete(game)
    db.commit()
    return {'message': 'Game deleted successfully'}


def _get_latest_zip_upload(db: Session, game_id: UUID):
    return (
        db.query(database.ZipUpload)
        .filter_by(game_id=game_id)
        .order_by(database.ZipUpload.id.desc())
        .first()
    )


def _get_extracted_dir_for_zip(zip_upload):
    return uploads_storage.extracted_root_uri(zip_upload.name)


def _find_game_root(zip_upload, db: Session) -> str:
    # Use cached URI if available
    if zip_upload.game_root_uri:
        return zip_upload.game_root_uri

    extracted_dir = _get_extracted_dir_for_zip(zip_upload)

    # Check if this ZIP had any files at all
    if not uploads_storage.prefix_has_files(extracted_dir):
        raise HTTPException(
            status_code=500,
            detail=f'Extracted files not found for ZIP: {zip_upload.name}'
        )

    # Calculation logic for legacy uploads
    root_uri = extracted_dir
    # Look for index.html directly in extracted_dir
    if uploads_storage.path_is_file(f"{extracted_dir.rstrip('/')}/index.html"):
        root_uri = extracted_dir
    else:
        # Search for the first directory containing an index.html or any .html
        files = uploads_storage.walk_files(extracted_dir)
        found = False
        for file_uri in files:
            if file_uri.endswith('/index.html'):
                root_uri = file_uri.rsplit('/', 1)[0]
                found = True
                break
        if not found:
            for file_uri in files:
                if file_uri.endswith('.html'):
                    root_uri = file_uri.rsplit('/', 1)[0]
                    break

    # Cache it in DB for next time
    zip_upload.game_root_uri = root_uri
    db.commit()
    return root_uri


def _resolve_candidate_path(
    extracted_dir: str, game_root_dir: str, normalized_file_path: str
):
    if normalized_file_path.startswith('_downloaded_assets/'):
        base_dir = extracted_dir
    else:
        base_dir = game_root_dir

    base_prefix = base_dir.rstrip('/') + '/'
    candidate = base_prefix + normalized_file_path
    return base_prefix, candidate


@router.post('/{game_id}/upload-asset', dependencies=[Depends(get_api_key)])
def upload_asset(
    game_id: UUID,
    original_path: str = Form(...),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
    db: Session = Depends(database.get_session),  # noqa: B008
):
    """Upload a manual asset override."""
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail='Game not found')

    normalized_original_path = _normalize_virtual_path(original_path)
    if not normalized_original_path:
        raise HTTPException(status_code=400, detail='Invalid original_path')

    safe_filename = normalized_original_path.replace(
        '/', '_'
    ).replace('\\', '_')
    try:
        file_path = uploads_storage.save_asset_override(
            str(game_id), safe_filename, file.file
        )
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail='Could not save file'
        ) from e
    finally:
        file.file.close()

    asset = db.query(database.Asset).filter_by(
        game_id=game_id, original_path=normalized_original_path
    ).first()
    if asset:
        asset.path = file_path
    else:
        asset = database.Asset(
            game_id=game_id,
            original_path=normalized_original_path,
            path=file_path
        )
        db.add(asset)

    db.commit()
    return {
        'message': f'Asset {normalized_original_path} uploaded',
        'asset_id': asset.id
    }


@router.delete(
    '/{game_id}/asset-override',
    dependencies=[Depends(get_api_key)]
)
def delete_asset_override(
    game_id: UUID,
    original_path: str = Query(...),  # noqa: B008
    db: Session = Depends(database.get_session),  # noqa: B008
):
    """Remove a manual asset override."""
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail='Game not found')

    normalized_original_path = _normalize_virtual_path(original_path)
    asset = db.query(database.Asset).filter_by(
        game_id=game_id, original_path=normalized_original_path
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail='Asset override not found')

    try:
        uploads_storage.delete_path(asset.path)
    except Exception as e:  # noqa: PLW718
        logger.error('Error deleting asset %s from S3: %s', asset.path, e)

    db.delete(asset)
    db.commit()
    return {
        'message': f'Asset override for {normalized_original_path} deleted'
    }


@router.get('/{game_id}/analyzed-assets', dependencies=[Depends(get_api_key)])
def get_analyzed_assets(
    game_id: UUID,
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """Get a list of media files found in the game package."""
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail='Game not found')

    zip_upload = _get_latest_zip_upload(db, game_id)
    if not zip_upload:
        return {'media_files': []}

    game_root_dir = _find_game_root(zip_upload, db)
    media_files = []

    game_root_prefix = game_root_dir.rstrip('/') + '/'
    if game_root_prefix.startswith('s3://'):
        game_root_prefix = game_root_prefix[len('s3://'):]

    for file_uri in uploads_storage.walk_files(game_root_dir):
        mime = uploads_storage.guess_content_type(file_uri)
        if not mime or not (
            mime.startswith('image/') or mime.startswith('audio/')
        ):
            continue

        if file_uri.startswith(game_root_prefix):
            relative_path = file_uri[len(game_root_prefix):]
        else:
            relative_path = file_uri

        media_files.append({
            'zip_file': zip_upload.name,
            'path': relative_path,
            'mime': mime
        })

    return {'media_files': media_files}


@router.get('/{game_id}/asset-overrides', dependencies=[Depends(get_api_key)])
def get_asset_overrides(
    game_id: UUID,
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """Get all manual asset overrides for a specific game."""
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail='Game not found')

    overrides = db.query(database.Asset).filter_by(game_id=game_id).all()
    return {
        'overrides': [
            {'original_path': asset.original_path, 'path': asset.path}
            for asset in overrides
        ]
    }


@router.get('/{game_id}/test')
def load_game_test(
    game_id: UUID,
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """Serve the main HTML file for the game preview."""
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail='Game not found')

    zip_upload = _get_latest_zip_upload(db, game_id)
    if not zip_upload:
        raise HTTPException(status_code=404, detail='No uploaded ZIP')

    game_root_dir = _find_game_root(zip_upload, db)

    index_html_path = f"{game_root_dir.rstrip('/')}/index.html"
    if not uploads_storage.path_is_file(index_html_path):
        html_files = [
            p for p in uploads_storage.walk_files(game_root_dir)
            if p.endswith('.html')
        ]
        if not html_files:
            raise HTTPException(status_code=404, detail='No HTML file found')
        index_html_path = html_files[0]

    prefix = game_root_dir.rstrip('/') + '/'
    if index_html_path.startswith(prefix):
        rel_path = index_html_path[len(prefix):]
    else:
        rel_path = index_html_path

    return serve_game_file(game_id, rel_path, db)


@router.get('/{game_id}/original/{file_path:path}')
def serve_original_game_file(
    game_id: UUID,
    file_path: str,
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """Serve an original file ignoring overrides."""
    try:
        normalized_file_path = _normalize_virtual_path(file_path)
        if not normalized_file_path:
            raise HTTPException(status_code=400, detail='Invalid file path')

        game = db.get(database.Game, game_id)
        if not game:
            logger.error('Game not found: %s', game_id)
            raise HTTPException(status_code=404, detail='Game not found')

        zip_upload = _get_latest_zip_upload(db, game_id)
        if not zip_upload:
            logger.error('No uploaded ZIP for game: %s', game_id)
            raise HTTPException(status_code=404, detail='No uploaded ZIP')

        extracted_dir = _get_extracted_dir_for_zip(zip_upload)
        game_root_dir = _find_game_root(zip_upload, db)

        abs_root, abs_candidate = _resolve_candidate_path(
            extracted_dir, game_root_dir, normalized_file_path
        )

        if not abs_candidate.startswith(abs_root):
            logger.error('Invalid path: %s', normalized_file_path)
            raise HTTPException(status_code=400, detail='Invalid file path')

        media_type = uploads_storage.guess_content_type(abs_candidate)
        try:
            return StreamingResponse(
                uploads_storage.open_binary(abs_candidate),
                media_type=media_type
            )
        except Exception as exc:
            raise HTTPException(
                status_code=404, detail='File not found'
            ) from exc

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            'Exception serving original file %s: %s\n%s',
            file_path, e, traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail=f'Error: {e}') from e


@router.get('/{game_id}/replacement/{file_path:path}')
def serve_replacement_game_file(
    game_id: UUID,
    file_path: str,
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """Serve an overridden asset file if it exists."""
    normalized_file_path = _normalize_virtual_path(file_path)
    if not normalized_file_path:
        raise HTTPException(status_code=400, detail='Invalid file path')

    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail='Game not found')

    asset_override = db.query(database.Asset).filter_by(
        game_id=game_id, original_path=normalized_file_path
    ).first()
    if not asset_override:
        raise HTTPException(status_code=404, detail='No override found')

    media_type = uploads_storage.guess_content_type(asset_override.path)
    try:
        stream = uploads_storage.open_binary(asset_override.path)
        return StreamingResponse(stream, media_type=media_type)
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail='File not found'
        ) from exc


@router.get('/{game_id}/{file_path:path}')
def serve_game_file(
    game_id: UUID,
    file_path: str,
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """Serve a game file, automatically resolving overrides."""
    try:
        normalized_file_path = _normalize_virtual_path(file_path)
        if not normalized_file_path:
            raise HTTPException(status_code=400, detail='Invalid file path')

        game = db.get(database.Game, game_id)
        if not game:
            logger.error('Game not found: %s', game_id)
            raise HTTPException(status_code=404, detail='Game not found')

        zip_upload = _get_latest_zip_upload(db, game_id)
        if not zip_upload:
            logger.error('No uploaded ZIP for game: %s', game_id)
            raise HTTPException(status_code=404, detail='No uploaded ZIP')

        extracted_dir = _get_extracted_dir_for_zip(zip_upload)
        game_root_dir = _find_game_root(zip_upload, db)

        abs_root, abs_candidate = _resolve_candidate_path(
            extracted_dir, game_root_dir, normalized_file_path
        )

        # Check for asset override
        asset_override = db.query(database.Asset).filter_by(
            game_id=game_id, original_path=normalized_file_path
        ).first()
        if asset_override:
            logger.info(
                'Serving override: %s -> %s',
                normalized_file_path,
                asset_override.path
            )

            media_type = uploads_storage.guess_content_type(
                asset_override.path
            )

            try:
                stream = uploads_storage.open_binary(asset_override.path)
                return StreamingResponse(stream, media_type=media_type)
            except Exception:  # noqa: PLW718
                pass  # Fallback to original

        if not abs_candidate.startswith(abs_root):
            logger.error('Invalid path: %s', normalized_file_path)
            raise HTTPException(status_code=400, detail='Invalid file path')

        media_type = uploads_storage.guess_content_type(abs_candidate)
        try:
            return StreamingResponse(
                uploads_storage.open_binary(abs_candidate),
                media_type=media_type
            )
        except Exception as exc:
            raise HTTPException(
                status_code=404, detail='File not found'
            ) from exc

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            'Exception serving file %s: %s\n%s',
            file_path, e, traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail=f'Error: {e}') from e


def get_uploaded_files():
    """Retrieve a list of all uploaded ZIP filenames."""
    uploaded_files = []
    # Accessing remote URI prefix for uploaded zips.
    prefix = uploads_storage.uploaded_zip_uri('').rstrip('/')
    for filepath in uploads_storage.walk_files(prefix):
        filename = filepath.rsplit('/', 1)[-1]
        logger.info(filename)
        uploaded_files.append(filename)
    return uploaded_files
