from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
import logging
from database import database
import puremagic
import glob, zipfile, os, pathlib, shutil, traceback
from config import config
from uuid import UUID
from sqlalchemy.orm import Session

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
    p = os.path.normpath(p).replace("\\", "/")
    if p == ".":
        return ""
    return p

@router.get("/")
def get_all_games(db: Session = Depends(database.get_session)):
    return {"games": db.query(database.Game).all()}

@router.post("/")
def create_game(name: str, db: Session = Depends(database.get_session)):
    new_game = database.Game(name=name)
    db.add(new_game)
    db.commit()
    return {"game_id": new_game.id, "name": new_game.name}


def _get_latest_zip_upload(db: Session, game_id: UUID):
    return (
        db.query(database.ZipUpload)
        .filter_by(game_id=game_id)
        .order_by(database.ZipUpload.id.desc())
        .first()
    )

def _get_extracted_dir_for_zip(zip_upload):
    extracted_root = os.path.join(config.uploads_directory, 'extracted_games', zip_upload.name)
    if not os.path.exists(extracted_root):
        os.makedirs(extracted_root, exist_ok=True)
        zip_path = os.path.join(config.uploads_directory, 'uploaded_zips', zip_upload.name)
        if not os.path.exists(zip_path):
            raise HTTPException(status_code=500, detail=f"ZIP file not found: {zip_upload.name}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extracted_root)
    return extracted_root

def _find_game_root(extracted_dir: str) -> str:
    # Look for index.html directly in extracted_dir
    if os.path.exists(os.path.join(extracted_dir, "index.html")):
        return extracted_dir

    # If not, search for the first directory containing an index.html or any .html file
    for root, dirs, files in os.walk(extracted_dir):
        if "index.html" in files:
            return root
        # Alternatively, if there's any .html file in a directory, consider it a potential root
        for f in files:
            if f.endswith(".html"):
                return root # Return the directory containing the first HTML file found
    
    # If no HTML files are found, default to the extracted_dir itself, though this case should be handled by HTTPException earlier
    return extracted_dir

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

    overrides_dir = os.path.join(config.uploads_directory, 'asset_overrides', str(game_id))
    os.makedirs(overrides_dir, exist_ok=True)

    # Sanitize original_path to use as filename or subpath
    # To keep it simple and avoid path traversal, we'll replace slashes with underscores for the filename
    # but store the original_path in the database.
    safe_filename = normalized_original_path.replace("/", "_").replace("\\", "_")
    file_path = os.path.join(overrides_dir, safe_filename)

    try:
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
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

    extracted_dir = _get_extracted_dir_for_zip(zip_upload)
    game_root_dir = _find_game_root(extracted_dir)

    index_html_path = os.path.join(game_root_dir, "index.html")
    if not os.path.exists(index_html_path):
        html_files = glob.glob(os.path.join(game_root_dir, '**/*.html'), recursive=True)
        if not html_files:
            raise HTTPException(status_code=404, detail="No index.html or other HTML file found in the game package.")
        index_html_path = html_files[0]

    # Compute the file_path relative to game_root_dir
    rel_path = os.path.relpath(index_html_path, game_root_dir)
    # Use the override-aware logic by calling serve_game_file
    return serve_game_file(game_id, rel_path, db)


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

        extracted_dir = _get_extracted_dir_for_zip(zip_upload)
        game_root_dir = _find_game_root(extracted_dir)

        candidate = os.path.normpath(os.path.join(game_root_dir, normalized_file_path))
        abs_root = os.path.abspath(game_root_dir)
        abs_candidate = os.path.abspath(candidate)

        # Check for asset override
        asset_override = (
            db.query(database.Asset)
            .filter_by(game_id=game_id, original_path=normalized_file_path)
            .first()
        )
        if asset_override and os.path.exists(asset_override.path):
            logger.info(f"Serving overridden file: {normalized_file_path} -> {asset_override.path}")
            return FileResponse(asset_override.path)

        logger.info(f"Serving file: {normalized_file_path} -> {abs_candidate}")
        logger.info(f"Root: {abs_root}, Candidate: {abs_candidate}")

        # Security check: ensure the requested file is within the extracted directory
        if os.path.commonpath([abs_root, abs_candidate]) != abs_root:
            logger.error(f"Invalid file path: {normalized_file_path}")
            raise HTTPException(status_code=400, detail="Invalid file path")
        if not os.path.exists(abs_candidate) or not os.path.isfile(abs_candidate):
            logger.error(f"File not found: {abs_candidate}")
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(abs_candidate)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception serving file {file_path}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


def get_uploaded_files():
    # This function should return a list of uploaded filenames (no directory path)
    uploaded_files = []
    for filepath in glob.iglob(config.uploads_directory + '/uploaded_zips/*', recursive=True):
        filename = os.path.basename(filepath)
        logger.info(filename)
        uploaded_files.append(filename)

    return uploaded_files


