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

from fastapi import FastAPI, HTTPException, Security, Depends, Response, Cookie, Query, Request
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from analyze_uploads.analyze_uploads import router as analyze_uploads_router
from file_uploads.file_uploads import router as file_uploads_router
from game.game import router as game_router
from trigger_build.trigger_build import router as trigger_build_router
# from assets.assets import router as assets_router

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(
    request: Request,
    response: Response,
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Query(None, alias="api_key"),
    api_key_cookie: str = Cookie(None, alias="api_key")
):
    if not config.api_key:
        return None # Dev mode or not configured
    
    # Primary check: direct credentials
    key = api_key_header or api_key_query or api_key_cookie
    
    # Fallback check: Referer header (helpful for sub-resources in iframes where cookies are blocked)
    if not key:
        referer = request.headers.get("referer")
        if referer and f"api_key={config.api_key}" in referer:
            key = config.api_key

    if key == config.api_key:
        if not api_key_cookie:
            is_https = request.url.scheme == "https"
            response.set_cookie(
                key="api_key",
                value=key,
                httponly=True,
                samesite="none" if is_https else "lax",
                secure=is_https,
                path="/"
            )
        return key
        
    raise HTTPException(
        status_code=403,
        detail="Could not validate credentials",
    )

app = FastAPI(dependencies=[Depends(get_api_key)])

origins = [
    "http://localhost:9000",
    'https://ua-manage-arcade.digitalinnovation.be'
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