import os, dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from config import config

dotenv.load_dotenv()

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/upload")
def upload(file: UploadFile = File(...)):
    uploads_dir = os.path.join(os.path.dirname(__file__), config.uploads_directory)
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, file.filename)
    try:
        with open(file_path, 'wb') as f:
            while contents := file.file.read(1024 * 1024):
                f.write(contents)
    except Exception:
        raise HTTPException(status_code=500, detail='Something went wrong')
    finally:
        file.file.close()

    return {"message": f"Successfully uploaded {file.filename}"}

@app.get("/files")
def list_files():
    uploads_dir = os.path.join(os.path.dirname(__file__), config.uploads_directory)
    if not os.path.exists(uploads_dir):
        return {"files": []}
    files = os.listdir(uploads_dir)
    return {"files": files}