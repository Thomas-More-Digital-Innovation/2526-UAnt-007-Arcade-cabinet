from fastapi import APIRouter
import puremagic
import glob, zipfile, os, pathlib, shutil
from config import config

router = APIRouter()

@router.get("/analyze-zip-uploads")
def analyze_zip_uploads():
    media_exts = {
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff',
        'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'opus'
    }
    found_media = []

    for filename in get_uploaded_files():
        uploaded_path = os.path.join(config.uploads_directory, 'uploaded_zips', filename)
        unzip_path = os.path.normpath(os.path.join(config.uploads_directory, 'extracted_games', filename))

        print(f"Unzipping {uploaded_path} to {unzip_path}")

        if os.path.exists(unzip_path):
            # remove previous extracted directory (or file) before re-processing
            if os.path.isdir(unzip_path):
                shutil.rmtree(unzip_path)
            else:
                os.remove(unzip_path)

        os.makedirs(unzip_path, exist_ok=True)

        with zipfile.ZipFile(uploaded_path, 'r') as zip_ref:
            zip_ref.extractall(unzip_path)

        for root, _, files in os.walk(unzip_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    mime = puremagic.from_file(file_path, mime=True)
                except Exception:
                    mime = None

                if not mime or not (mime.startswith('image/') or mime.startswith('audio/')):
                    continue

                relative_path = os.path.relpath(file_path, unzip_path)
                found_media.append({
                    'zip_file': filename,
                    'path': relative_path,
                    'mime': mime,
                })

    return {'media_files': found_media}


def get_uploaded_files():
    # This function should return a list of uploaded filenames (no directory path)
    
    uploaded_files = []
    for filepath in glob.iglob(config.uploads_directory + '/uploaded_zips/*', recursive=True):
        filename = os.path.basename(filepath)
        print(filename)
        uploaded_files.append(filename)

    return uploaded_files

    



