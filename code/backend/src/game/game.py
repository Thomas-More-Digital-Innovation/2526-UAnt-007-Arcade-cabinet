from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
import logging
from database import database
import puremagic
import glob, zipfile, os, pathlib, shutil, traceback
from config import config
from uuid import UUID

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
def get_all_games():
    return {"games": database.session.query(database.Game).all()}

@router.post("/")
def create_game(name: str):
    new_game = database.Game(name=name)
    database.session.add(new_game)
    database.session.commit()
    return {"game_id": new_game.id, "name": new_game.name}


def _get_latest_zip_upload(game_id: UUID):
    return (
        database.session.query(database.ZipUpload)
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

# @router.get("/{game_id}/assets")
# def get_game_assets(game_id: UUID):
#     game = database.session.get(database.Game, game_id)
#     if not game:
#         raise HTTPException(status_code=404, detail="Game not found")

#     zip_upload = _get_latest_zip_upload(game_id)
#     if not zip_upload:
#         raise HTTPException(status_code=404, detail="No uploaded ZIP for this game")

#     extracted_dir = _get_extracted_dir_for_zip(zip_upload)

#     game_root = _find_game_root(extracted_dir)

#     media_exts = {
#         'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff',
#         'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'opus'
#     }

#     found_media = []
#     for root, _, files in os.walk(game_root):
#         for filename in files:
#             file_path = os.path.join(root, filename)
#             _, ext = os.path.splitext(filename)
#             ext = ext.lstrip('.').lower()
#             if ext not in media_exts:
#                 continue

#             mime = None
#             try:
#                 mime = puremagic.from_file(file_path, mime=True)
#             except Exception:
#                 pass

#             relative_path = os.path.relpath(file_path, game_root)
#             found_media.append({
#                 'path': relative_path,
#                 'mime': mime,
#             })

#     return {'media_files': found_media}

# @router.get("/{game_id}/assets/{file_path:path}")
# def serve_game_asset(game_id: UUID, file_path: str):
#     game = database.session.get(database.Game, game_id)
#     if not game:
#         raise HTTPException(status_code=404, detail="Game not found")

#     zip_upload = _get_latest_zip_upload(game_id)
#     if not zip_upload:
#         raise HTTPException(status_code=404, detail="No uploaded ZIP for this game")

#     extracted_dir = _get_extracted_dir_for_zip(zip_upload)
#     game_root = _find_game_root(extracted_dir)

#     candidate = os.path.normpath(os.path.join(game_root, file_path))
#     abs_root = os.path.abspath(game_root)
#     abs_candidate = os.path.abspath(candidate)
#     if os.path.commonpath([abs_root, abs_candidate]) != abs_root:
#         raise HTTPException(status_code=400, detail="Invalid path")

#     if os.path.exists(abs_candidate):
#         return FileResponse(abs_candidate)

#     # If not found, search recursively for a file with the same name
#     filename = os.path.basename(file_path)
#     found_files = []
#     for root, _, files in os.walk(game_root):
#         for f in files:
#             found_files.append(os.path.join(root, f))
#             if f == filename:
#                 logger.info(f"Found {filename} at {os.path.join(root, f)}")
#                 return FileResponse(os.path.join(root, f))
#     logger.error(f"Could not find {filename}. Files seen: {found_files}")
#     raise HTTPException(status_code=404, detail="File not found")


@router.post("/{game_id}/upload-asset")
def upload_asset(game_id: UUID, original_path: str = Form(...), file: UploadFile = File(...)):
    game = database.session.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    overrides_dir = os.path.join(config.uploads_directory, 'asset_overrides', str(game_id))
    os.makedirs(overrides_dir, exist_ok=True)

    # Sanitize original_path to use as filename or subpath
    # To keep it simple and avoid path traversal, we'll replace slashes with underscores for the filename
    # but store the original_path in the database.
    safe_filename = original_path.replace("/", "_").replace("\\", "_")
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
    asset = database.session.query(database.Asset).filter_by(gameId=game_id, original_path=original_path).first()
    if asset:
        asset.path = file_path
    else:
        asset = database.Asset(gameId=game_id, original_path=original_path, path=file_path)
        database.session.add(asset)
    
    database.session.commit()

    return {"message": f"Asset {original_path} uploaded successfully", "asset_id": asset.id}


@router.get("/{game_id}/test")
def load_game_test(game_id: UUID):
    game = database.session.get(database.Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    zip_upload = _get_latest_zip_upload(game_id)
    if not zip_upload:
        raise HTTPException(status_code=404, detail="No uploaded ZIP for this game")

    extracted_dir = _get_extracted_dir_for_zip(zip_upload)
    game_root_dir = _find_game_root(extracted_dir)
    
    index_html_path = os.path.join(game_root_dir, "index.html")
    if not os.path.exists(index_html_path):
        # Look for the first html file if index.html is not found.
        html_files = glob.glob(os.path.join(game_root_dir, '**/*.html'), recursive=True)
        if not html_files:
            raise HTTPException(status_code=404, detail="No index.html or other HTML file found in the game package.")
        index_html_path = html_files[0]
    return FileResponse(index_html_path)


@router.get("/{game_id}/{file_path:path}")
def serve_game_file(game_id: UUID, file_path: str):
    try:
        game = database.session.get(database.Game, game_id)
        if not game:
            logger.error(f"Game not found: {game_id}")
            raise HTTPException(status_code=404, detail="Game not found")

        zip_upload = _get_latest_zip_upload(game_id)
        if not zip_upload:
            logger.error(f"No uploaded ZIP for game: {game_id}")
            raise HTTPException(status_code=404, detail="No uploaded ZIP for this game")

        extracted_dir = _get_extracted_dir_for_zip(zip_upload)
        game_root_dir = _find_game_root(extracted_dir)

        candidate = os.path.normpath(os.path.join(game_root_dir, file_path))
        abs_root = os.path.abspath(game_root_dir)
        abs_candidate = os.path.abspath(candidate)

        # Check for asset override
        asset_override = database.session.query(database.Asset).filter_by(gameId=game_id, original_path=file_path).first()
        if asset_override and os.path.exists(asset_override.path):
            logger.info(f"Serving overridden file: {file_path} -> {asset_override.path}")
            return FileResponse(asset_override.path)

        logger.info(f"Serving file: {file_path} -> {abs_candidate}")
        logger.info(f"Root: {abs_root}, Candidate: {abs_candidate}")

        # Security check: ensure the requested file is within the extracted directory
        if os.path.commonpath([abs_root, abs_candidate]) != abs_root:
            logger.error(f"Invalid file path: {file_path}")
            raise HTTPException(status_code=400, detail="Invalid file path")
        if not os.path.exists(abs_candidate) or not os.path.isfile(abs_candidate):
            logger.error(f"File not found: {abs_candidate}")
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(abs_candidate)
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


