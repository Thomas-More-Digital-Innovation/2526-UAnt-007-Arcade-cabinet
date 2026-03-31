from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from config import config
import os, logging, puremagic, pathlib
from database import database
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload-zip")
def upload_zip(game_id: UUID, file: UploadFile = File(...), db: Session = Depends(database.get_session)):
    uploads_dir = os.path.join(config.uploads_directory, 'uploaded_zips')
    os.makedirs(uploads_dir, exist_ok=True)

    original_name = file.filename
    generated_uuid = uuid4().hex
    filename = f"{generated_uuid}.zip"
    file_path = os.path.join(uploads_dir, filename)

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
    
    mime_type = puremagic.from_file(file_path, True)
    if mime_type != 'application/zip':
        pathlib.Path(file_path).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail='Only ZIP files are allowed')

    zip_upload = database.ZipUpload(name=filename, game_id=game_id)
    db.add(zip_upload)
    db.commit()

    return {"message": f"Successfully uploaded {original_name}"}

# @router.get("/list-zip-files")
# def list_zip_files():
#     logger.info("Listing uploaded ZIP files")
#     uploads_dir = os.path.join(os.path.dirname(__file__), config.uploads_directory)
#     if not os.path.exists(uploads_dir):
#         return {"files": []}
#     files = os.listdir(uploads_dir)
#     return {"files": files}