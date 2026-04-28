import dotenv
from pathlib import Path

# Load env files deterministically so credentials in src/.env are always picked up.
_app_dir = Path(__file__).resolve().parent
_src_dir = _app_dir.parent
_backend_dir = _src_dir.parent

dotenv.load_dotenv(_backend_dir / '.env')
dotenv.load_dotenv(_src_dir / '.env')

from config import config
import logging

logging.basicConfig(
    level=config.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from analyze_uploads.analyze_uploads import router as analyze_uploads_router
from file_uploads.file_uploads import router as file_uploads_router
from game.game import router as game_router
from trigger_build.trigger_build import router as trigger_build_router
from app.auth import get_api_key

logger = logging.getLogger(__name__)

app = FastAPI()

origins = [
    'http://localhost:9000',
    'https://ua-manage-arcade.digitalinnovation.be'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Individual endpoint protection (API key required)
protected_dependency = [Depends(get_api_key)]

# Routers
# Note: game_router has internal granular auth (see game.py)
app.include_router(game_router, prefix='/games', tags=['games'])

app.include_router(analyze_uploads_router, dependencies=protected_dependency)
app.include_router(file_uploads_router, prefix='/file-uploads', tags=['assets'], dependencies=protected_dependency)
app.include_router(trigger_build_router, prefix='/trigger-build', tags=['trigger-build'], dependencies=protected_dependency)

@app.get('/')
async def root():   
    logger.info('Root endpoint accessed')
    return {'message': 'Hello World'}