import dotenv
from pathlib import Path

# Load env files deterministically so credentials in src/.env are always picked up.
_app_dir = Path(__file__).resolve().parent
_src_dir = _app_dir.parent
_backend_dir = _src_dir.parent

dotenv.load_dotenv(_backend_dir / ".env")
dotenv.load_dotenv(_src_dir / ".env")

from config import config
import logging

logging.basicConfig(
    level=config.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from analyze_uploads.analyze_uploads import router as analyze_uploads_router
from file_uploads.file_uploads import router as file_uploads_router
from game.game import router as game_router
from trigger_build.trigger_build import router as trigger_build_router
# from assets.assets import router as assets_router

logger = logging.getLogger(__name__)

app = FastAPI()

origins = [
    "http://localhost:9000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(game_router, prefix="/games", tags=["games"])
# app.include_router(assets_router, prefix="/assets", tags=["assets"])

app.include_router(analyze_uploads_router)
app.include_router(file_uploads_router, prefix="/file-uploads", tags=["assets"])
app.include_router(trigger_build_router, prefix="/trigger-build", tags=["trigger-build"])

@app.get("/")
async def root():   
    logger.info("Root endpoint accessed")
    return {"message": "Hello World"}