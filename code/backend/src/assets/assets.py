from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from config import config
import os, logging, puremagic, pathlib
from database import database
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/")
def upload_asset(game_id: UUID, original_path: str, file: UploadFile = File(...), db: Session = Depends(database.get_session)):
    # Keep behavior consistent with the game override system:
    # - store files under uploads/asset_overrides/<game_id>/
    # - upsert by (game_id, original_path)
    if original_path is None:
        raise HTTPException(status_code=400, detail="Invalid original_path")
    normalized_original_path = original_path.replace("\\", "/").strip()
    while normalized_original_path.startswith("/"):
        normalized_original_path = normalized_original_path[1:]
    if normalized_original_path.startswith("./"):
        normalized_original_path = normalized_original_path[2:]
    normalized_original_path = os.path.normpath(normalized_original_path).replace("\\", "/")
    if normalized_original_path in ("", "."):
        raise HTTPException(status_code=400, detail="Invalid original_path")

    overrides_dir = os.path.join(config.uploads_directory, 'asset_overrides', str(game_id))
    os.makedirs(overrides_dir, exist_ok=True)

    original_name = file.filename
    safe_filename = normalized_original_path.replace("/", "_")
    file_path = os.path.join(overrides_dir, safe_filename)

    try:
        logger.info(f"Saving file to {file_path}")
        with open(file_path, 'wb') as f:
            while contents := file.file.read(1024 * 1024):
                f.write(contents)
            
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail='Something went wrong')
    finally:
        file.file.close()

    asset = db.query(database.Asset).filter_by(game_id=game_id, original_path=normalized_original_path).first()
    if asset:
        asset.path = file_path
    else:
        asset = database.Asset(original_path=normalized_original_path, path=file_path, game_id=game_id)
        db.add(asset)
    db.commit()

    return {"message": f"Successfully uploaded {original_name}"}

