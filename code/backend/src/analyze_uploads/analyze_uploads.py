from fastapi import APIRouter
from storage.uploads_storage import uploads_storage

router = APIRouter()

@router.get('/analyze-zip-uploads')
def analyze_zip_uploads():
    found_media = []

    for filename in get_uploaded_files():
        extracted_dir = uploads_storage.extracted_root_uri(filename)
        prefix = extracted_dir.rstrip('/') + '/'

        if not uploads_storage.prefix_has_files(extracted_dir):
            continue

        for file_uri in uploads_storage.walk_files(extracted_dir):
            mime = uploads_storage.guess_content_type(file_uri)
            if not mime or not (mime.startswith('image/') or mime.startswith('audio/')):
                continue

            relative_path = file_uri[len(prefix):] if file_uri.startswith(prefix) else file_uri
            found_media.append({
                'zip_file': filename,
                'path': relative_path,
                'mime': mime,
            })

    return {'media_files': found_media}


def get_uploaded_files():
    uploaded_files = []
    for file_uri in uploads_storage.walk_files(uploads_storage._remote_uri('uploaded_zips')):
        filename = file_uri.rsplit('/', 1)[-1]
        print(filename)
        uploaded_files.append(filename)

    return uploaded_files

    



