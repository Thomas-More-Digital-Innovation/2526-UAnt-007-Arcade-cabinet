from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import logging
from database import database
import puremagic
import posixpath
import traceback
from uuid import UUID
from sqlalchemy.orm import Session
from storage.uploads_storage import uploads_storage

logger = logging.getLogger(__name__)

router = APIRouter()

def _normalize_virtual_path(p: str) -> str:
    # Normalize paths coming from URLs/forms so overrides match reliably.
    # Examples -> "assets/death.mp3":
    # - "/assets/death.mp3"
    # - "./assets/death.mp3"
    # - "assets\\death.mp3"
    if p is None:
        return ""
    p = p.replace("\\", "/").strip()
    while p.startswith("/"):
        p = p[1:]
    if p.startswith("./"):
        p = p[2:]
    # Collapse things like "a/../b" or "a//b"
    p = posixpath.normpath(p)
    if p == ".":
        return ""
    return p

@router.get("/")
def get_all_games(db: Session = Depends(database.get_session)):
    return {"games": db.query(database.Game).all()}


# Pydantic model for game creation
class GameCreateRequest(BaseModel):
    name: str
    description: str | None = None

@router.post("/")
def create_game(request: GameCreateRequest, db: Session = Depends(database.get_session)):
    new_game = database.Game(name=request.name, description=request.description)
    db.add(new_game)
    db.commit()
    return {"game": {"id": new_game.id, "name": new_game.name, "description": new_game.description}}

class GamePutRequest(BaseModel):
    id: UUID
    name: str
    description: str | None = None

@router.put("/{game_id}")
def update_game(game_id: UUID, request: GamePutRequest, db: Session = Depends(database.get_session)):
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    game.name = request.name
    game.description = request.description
    db.commit()
    return {"game": {"id": game.id, "name": game.name, "description": game.description}}

@router.delete("/{game_id}")
def delete_game(game_id: UUID, db: Session = Depends(database.get_session)):
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Delete associated zip uploads and assets from DB and S3
    for zip_upload in game.zip_uploads:
        try:
            uploads_storage.delete_path(uploads_storage.uploaded_zip_uri(zip_upload.name))
            uploads_storage.delete_path(uploads_storage.extracted_root_uri(zip_upload.name), recursive=True)
        except Exception as e:
            logger.error(f"Error deleting zip {zip_upload.name} from S3: {e}")
        db.delete(zip_upload)
        
    for asset in game.assets:
        try:
            uploads_storage.delete_path(asset.path)
        except Exception as e:
            logger.error(f"Error deleting asset {asset.path} from S3: {e}")
        db.delete(asset)

    try:
        uploads_storage.delete_path(uploads_storage._remote_uri("asset_overrides", str(game_id)), recursive=True)
    except Exception as e:
        logger.error(f"Error deleting asset overrides for game {game_id} from S3: {e}")

    db.delete(game)
    db.commit()
    return {"message": "Game deleted successfully"}

def _get_latest_zip_upload(db: Session, game_id: UUID):
    return (
        db.query(database.ZipUpload)
        .filter_by(game_id=game_id)
        .order_by(database.ZipUpload.id.desc())
        .first()
    )

def _get_extracted_dir_for_zip(zip_upload, game_id: UUID):
    extracted_root = uploads_storage.extracted_root_uri(zip_upload.name)
    if not uploads_storage.prefix_has_files(extracted_root):
        raise HTTPException(status_code=500, detail=f"Extracted files not found in S3 for ZIP: {zip_upload.name}")
    return extracted_root

def _find_game_root(extracted_dir: str) -> str:
    # Look for index.html directly in extracted_dir
    if uploads_storage.path_is_file(f"{extracted_dir.rstrip('/')}/index.html"):
        return extracted_dir

    # If not, search for the first directory containing an index.html or any .html file
    files = uploads_storage.walk_files(extracted_dir)
    for file_uri in files:
        if file_uri.endswith("/index.html"):
            return file_uri.rsplit("/", 1)[0]
    for file_uri in files:
        if file_uri.endswith(".html"):
            return file_uri.rsplit("/", 1)[0]
    
    # If no HTML files are found, default to the extracted_dir itself, though this case should be handled by HTTPException earlier
    return extracted_dir


def _resolve_candidate_path(extracted_dir: str, game_root_dir: str, normalized_file_path: str):
    # Downloaded external assets are stored at extracted_root/_downloaded_assets.
    if normalized_file_path.startswith("_downloaded_assets/"):
        base_dir = extracted_dir
    else:
        base_dir = game_root_dir

    base_prefix = base_dir.rstrip("/") + "/"
    candidate = base_prefix + normalized_file_path
    return base_prefix, candidate

@router.post("/{game_id}/upload-asset")
def upload_asset(
    game_id: UUID,
    original_path: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(database.get_session),
):
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    normalized_original_path = _normalize_virtual_path(original_path)
    if not normalized_original_path:
        raise HTTPException(status_code=400, detail="Invalid original_path")

    # Sanitize original_path to use as filename or subpath
    # To keep it simple and avoid path traversal, we'll replace slashes with underscores for the filename
    # but store the original_path in the database.
    safe_filename = normalized_original_path.replace("/", "_").replace("\\", "_")
    file_path = ""

    try:
        file_path = uploads_storage.save_asset_override(str(game_id), safe_filename, file.file)
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail="Could not save file")
    finally:
        file.file.close()

    # Update or create Asset record
    asset = db.query(database.Asset).filter_by(game_id=game_id, original_path=normalized_original_path).first()
    if asset:
        asset.path = file_path
    else:
        asset = database.Asset(game_id=game_id, original_path=normalized_original_path, path=file_path)
        db.add(asset)
    
    db.commit()

    return {"message": f"Asset {normalized_original_path} uploaded successfully", "asset_id": asset.id}


@router.delete("/{game_id}/asset-override")
def delete_asset_override(
    game_id: UUID,
    original_path: str = Query(...),
    db: Session = Depends(database.get_session),
):
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    normalized_original_path = _normalize_virtual_path(original_path)
    asset = db.query(database.Asset).filter_by(game_id=game_id, original_path=normalized_original_path).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset override not found")

    try:
        uploads_storage.delete_path(asset.path)
    except Exception as e:
        logger.error(f"Error deleting asset {asset.path} from S3: {e}")
    
    db.delete(asset)
    db.commit()

    return {"message": f"Asset override for {normalized_original_path} deleted successfully"}


@router.get("/{game_id}/analyzed-assets")
def get_analyzed_assets(game_id: UUID, db: Session = Depends(database.get_session)):
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    zip_upload = _get_latest_zip_upload(db, game_id)
    if not zip_upload:
        return {"media_files": []}

    extracted_dir = _get_extracted_dir_for_zip(zip_upload, game_id)
    game_root_dir = _find_game_root(extracted_dir)
    media_files = []

    game_root_prefix = game_root_dir.rstrip("/") + "/"
    for file_uri in uploads_storage.walk_files(game_root_dir):
        mime = uploads_storage.guess_content_type(file_uri)
        if not mime or not (mime.startswith("image/") or mime.startswith("audio/")):
            continue

        relative_path = file_uri[len(game_root_prefix):] if file_uri.startswith(game_root_prefix) else file_uri
        media_files.append(
            {
                "zip_file": zip_upload.name,
                "path": relative_path,
                "mime": mime,
            }
        )

    return {"media_files": media_files}


@router.get("/{game_id}/asset-overrides")
def get_asset_overrides(game_id: UUID, db: Session = Depends(database.get_session)):
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    overrides = db.query(database.Asset).filter_by(game_id=game_id).all()
    return {
        "overrides": [
            {
                "original_path": asset.original_path,
                "path": asset.path,
            }
            for asset in overrides
        ]
    }


@router.get("/{game_id}/test")
def load_game_test(game_id: UUID, db: Session = Depends(database.get_session)):
    """
    Serve the main HTML file for the game preview, using the override-aware logic.
    """
    # Find the main HTML file path as before
    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    zip_upload = _get_latest_zip_upload(db, game_id)
    if not zip_upload:
        raise HTTPException(status_code=404, detail="No uploaded ZIP for this game")

    extracted_dir = _get_extracted_dir_for_zip(zip_upload, game_id)
    game_root_dir = _find_game_root(extracted_dir)

    index_html_path = f"{game_root_dir.rstrip('/')}/index.html"
    if not uploads_storage.path_is_file(index_html_path):
        html_files = [p for p in uploads_storage.walk_files(game_root_dir) if p.endswith(".html")]
        if not html_files:
            raise HTTPException(status_code=404, detail="No index.html or other HTML file found in the game package.")
        index_html_path = html_files[0]

    # Compute the file_path relative to game_root_dir
    rel_path = index_html_path[len(game_root_dir.rstrip('/') + '/'):] if index_html_path.startswith(game_root_dir.rstrip('/') + '/') else index_html_path
    # Use the override-aware logic by calling serve_game_file
    return serve_game_file(game_id, rel_path, db)


@router.get("/{game_id}/original/{file_path:path}")
def serve_original_game_file(game_id: UUID, file_path: str, db: Session = Depends(database.get_session)):
    try:
        normalized_file_path = _normalize_virtual_path(file_path)
        if not normalized_file_path:
            raise HTTPException(status_code=400, detail="Invalid file path")

        game = db.get(database.Game, game_id)
        if not game:
            logger.error(f"Game not found: {game_id}")
            raise HTTPException(status_code=404, detail="Game not found")

        zip_upload = _get_latest_zip_upload(db, game_id)
        if not zip_upload:
            logger.error(f"No uploaded ZIP for game: {game_id}")
            raise HTTPException(status_code=404, detail="No uploaded ZIP for this game")

        extracted_dir = _get_extracted_dir_for_zip(zip_upload, game_id)
        game_root_dir = _find_game_root(extracted_dir)

        abs_root, abs_candidate = _resolve_candidate_path(extracted_dir, game_root_dir, normalized_file_path)

        # Security check: ensure the requested file is within the extracted directory
        if not abs_candidate.startswith(abs_root):
            logger.error(f"Invalid file path: {normalized_file_path}")
            raise HTTPException(status_code=400, detail="Invalid file path")
        if not uploads_storage.exists_path(abs_candidate) or not uploads_storage.path_is_file(abs_candidate):
            logger.error(f"Original file not found: {abs_candidate}")
            raise HTTPException(status_code=404, detail="Original file not found")

        media_type = uploads_storage.guess_content_type(abs_candidate)
        return StreamingResponse(uploads_storage.open_binary(abs_candidate), media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception serving original file {file_path}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/{game_id}/replacement/{file_path:path}")
def serve_replacement_game_file(game_id: UUID, file_path: str, db: Session = Depends(database.get_session)):
    normalized_file_path = _normalize_virtual_path(file_path)
    if not normalized_file_path:
        raise HTTPException(status_code=400, detail="Invalid file path")

    game = db.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    asset_override = (
        db.query(database.Asset)
        .filter_by(game_id=game_id, original_path=normalized_file_path)
        .first()
    )
    if not asset_override or not uploads_storage.exists_path(asset_override.path):
        raise HTTPException(status_code=404, detail="Replacement file not found")

    media_type = uploads_storage.guess_content_type(asset_override.path)
    stream = uploads_storage.open_binary(asset_override.path)
    return StreamingResponse(stream, media_type=media_type)


@router.get("/{game_id}/{file_path:path}")
def serve_game_file(game_id: UUID, file_path: str, db: Session = Depends(database.get_session)):
    try:
        normalized_file_path = _normalize_virtual_path(file_path)
        if not normalized_file_path:
            raise HTTPException(status_code=400, detail="Invalid file path")

        game = db.get(database.Game, game_id)
        if not game:
            logger.error(f"Game not found: {game_id}")
            raise HTTPException(status_code=404, detail="Game not found")

        zip_upload = _get_latest_zip_upload(db, game_id)
        if not zip_upload:
            logger.error(f"No uploaded ZIP for game: {game_id}")
            raise HTTPException(status_code=404, detail="No uploaded ZIP for this game")

        extracted_dir = _get_extracted_dir_for_zip(zip_upload, game_id)
        game_root_dir = _find_game_root(extracted_dir)

        abs_root, abs_candidate = _resolve_candidate_path(extracted_dir, game_root_dir, normalized_file_path)

        # Check for asset override
        asset_override = (
            db.query(database.Asset)
            .filter_by(game_id=game_id, original_path=normalized_file_path)
            .first()
        )
        if asset_override and uploads_storage.exists_path(asset_override.path):
            logger.info(f"Serving overridden file: {normalized_file_path} -> {asset_override.path}")
            media_type = uploads_storage.guess_content_type(asset_override.path)
            stream = uploads_storage.open_binary(asset_override.path)
            return StreamingResponse(stream, media_type=media_type)

        logger.info(f"Serving file: {normalized_file_path} -> {abs_candidate}")
        logger.info(f"Root: {abs_root}, Candidate: {abs_candidate}")

        # Security check: ensure the requested file is within the extracted directory
        if not abs_candidate.startswith(abs_root):
            logger.error(f"Invalid file path: {normalized_file_path}")
            raise HTTPException(status_code=400, detail="Invalid file path")
        if not uploads_storage.exists_path(abs_candidate) or not uploads_storage.path_is_file(abs_candidate):
            logger.error(f"File not found: {abs_candidate}")
            raise HTTPException(status_code=404, detail="File not found")

        media_type = uploads_storage.guess_content_type(abs_candidate)
        return StreamingResponse(uploads_storage.open_binary(abs_candidate), media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception serving file {file_path}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


def get_uploaded_files():
    # This function should return a list of uploaded filenames (no directory path)
    uploaded_files = []
    for filepath in uploads_storage.walk_files(uploads_storage._remote_uri('uploaded_zips')):
        filename = filepath.rsplit('/', 1)[-1]
        logger.info(filename)
        uploaded_files.append(filename)

    return uploaded_files


