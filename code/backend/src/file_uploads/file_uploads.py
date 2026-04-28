from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from config import config
import logging, puremagic, pathlib, zipfile
import shutil
import tempfile
from database import database
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from game.internet_assets import localize_internet_assets
from storage.uploads_storage import uploads_storage

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post('/upload-zip')
def upload_zip(game_id: UUID, file: UploadFile = File(...), db: Session = Depends(database.get_session)):
    original_name = file.filename
    generated_uuid = uuid4().hex
    filename = f'{generated_uuid}.zip'
    zip_remote_uri = uploads_storage.uploaded_zip_uri(filename)

    temp_dir = tempfile.mkdtemp(prefix='upload_zip_')
    temp_path = pathlib.Path(temp_dir)
    file_path = temp_path / filename

    try:
        logger.info(f'Saving file to {zip_remote_uri}')
        with open(file_path, 'wb') as f:
            while contents := file.file.read(1024 * 1024):
                f.write(contents)
        with open(file_path, 'rb') as f:
            uploads_storage.save_uploaded_zip_from_fileobj(filename, f)
            
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail='Something went wrong')
    finally:
        file.file.close()
    
    mime_type = puremagic.from_file(str(file_path), True)
    if mime_type != 'application/zip':
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail='Only ZIP files are allowed')

    extracted_root = temp_path / 'extracted_games' / filename
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

        uploads_storage.upload_tree(str(extracted_root), uploads_storage.extracted_root_uri(filename))
        
        # Determine game root URI (s3 path containing the index.html)
        # We do this calculation locally where it is fast.
        game_root_local = None
        if (extracted_root / 'index.html').is_file():
            game_root_local = extracted_root
        else:
            # Look for index.html recursively
            for p in extracted_root.rglob('index.html'):
                if p.is_file():
                    game_root_local = p.parent
                    break
            if not game_root_local:
                # Fallback to any .html file
                for p in extracted_root.rglob('*.html'):
                    if p.is_file():
                        game_root_local = p.parent
                        break
        
        game_root_uri = None
        if game_root_local:
            rel_root = game_root_local.relative_to(extracted_root)
            if str(rel_root) == '.':
                game_root_uri = uploads_storage.extracted_root_uri(filename)
            else:
                game_root_uri = uploads_storage.extracted_root_uri(filename).rstrip('/') + '/' + str(rel_root).replace('\\', '/')
        else:
            # Fallback to extracted root if no HTML found
            game_root_uri = uploads_storage.extracted_root_uri(filename)

    except Exception as e:
        logger.exception(e)
        file_path.unlink(missing_ok=True)
        if extracted_root.is_dir():
            shutil.rmtree(extracted_root, ignore_errors=True)
        raise HTTPException(status_code=400, detail='ZIP extraction/localization failed')
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    zip_upload = database.ZipUpload(name=filename, game_id=game_id, game_root_uri=game_root_uri)
    db.add(zip_upload)
    db.commit()

    return {'message': f'Successfully uploaded {original_name}'}

