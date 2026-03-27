import dotenv

dotenv.load_dotenv()

from config import config
import logging

logging.basicConfig(
    level=config.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from fastapi import FastAPI
from analyze_uploads.analyze_uploads import router as analyze_uploads_router
from file_uploads.file_uploads import router as file_uploads_router
from docker_builder.docker_builder import router as docker_builder_router
from game.game import router as game_router

logger = logging.getLogger(__name__)

app = FastAPI()

app.include_router(game_router, prefix="/games")

app.include_router(analyze_uploads_router)
app.include_router(file_uploads_router, prefix="/file-uploads")
app.include_router(docker_builder_router, prefix="/docker-builder")

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Hello World"}
