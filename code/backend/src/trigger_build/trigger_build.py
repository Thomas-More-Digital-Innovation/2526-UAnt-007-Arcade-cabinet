from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from config import config 

import httpx, logging

logger = logging.getLogger(__name__)

router = APIRouter()

from sqlalchemy.orm import Session
from database import database
import json

@router.post("/trigger-workflow")
async def trigger_workflow(db: Session = Depends(database.get_session)):
    if not config.github_repo_url or not config.github_token:
        raise HTTPException(status_code=500, detail="GitHub configuration is missing")
    
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {config.github_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # Fetch all game ids from the database
    # Full DB dump (all tables as JSON)
    def serialize_game(game):
        return {
            "id": str(game.id),
            "name": game.name,
            "zip_uploads": [
                {
                    "id": str(zu.id),
                    "name": zu.name,
                    "game_id": str(zu.game_id)
                } for zu in game.zip_uploads
            ],
            "assets": [
                {
                    "id": str(asset.id),
                    "game_id": str(asset.game_id),
                    "original_path": asset.original_path,
                    "path": asset.path
                } for asset in game.assets
            ]
        }

    def serialize_zip_upload(zu):
        return {
            "id": str(zu.id),
            "name": zu.name,
            "game_id": str(zu.game_id)
        }

    def serialize_asset(asset):
        return {
            "id": str(asset.id),
            "game_id": str(asset.game_id),
            "original_path": asset.original_path,
            "path": asset.path
        }

    games = db.query(database.Game).all()
    zip_uploads = db.query(database.ZipUpload).all()
    assets = db.query(database.Asset).all()

    db_dump = {
        "games": [serialize_game(game) for game in games],
        "zip_uploads": [serialize_zip_upload(zu) for zu in zip_uploads],
        "assets": [serialize_asset(asset) for asset in assets]
    }

    payload = {
        "event_type": "trigger",
        "client_payload": db_dump
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.github_repo_url,
            headers=headers,
            json=payload
        )
        
    if response.status_code not in (200, 204):
        logger.error(f"Failed to trigger workflow: {response.text}")
        raise HTTPException(status_code=response.status_code, detail="Failed to trigger workflow")
        
    return {"message": "Workflow triggered successfully"}
