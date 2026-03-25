from fastapi import APIRouter, UploadFile, File, HTTPException
from config import config
import os, logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload")
def upload(file: UploadFile = File(...)):
    uploads_dir = config.uploads_directory
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, file.filename)
    try:
        logger.info(f"Saving file to {file_path}")
        with open(file_path, 'wb') as f:
            while contents := file.file.read(1024 * 1024):
                f.write(contents)
    except Exception:
        raise HTTPException(status_code=500, detail='Something went wrong')
    finally:
        file.file.close()

    return {"message": f"Successfully uploaded {file.filename}"}

@router.get("/list")
def list_files():
    logger.info("Listing uploaded files")
    uploads_dir = os.path.join(os.path.dirname(__file__), config.uploads_directory)
    if not os.path.exists(uploads_dir):
        return {"files": []}
    files = os.listdir(uploads_dir)
    return {"files": files}