from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from config import config 

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

from sqlalchemy.orm import Session
from database import database
import json

from github import Github, Auth

@router.post("/trigger-workflow")
async def trigger_workflow(db: Session = Depends(database.get_session)):
    if not all([config.github_app_id, config.github_private_key_path, config.github_installation_id, config.github_repo_owner, config.github_repo_name]):
        raise HTTPException(status_code=500, detail="GitHub App configuration is missing")
    
    # ... (serialization logic remains the same)
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

    try:
        with open(config.github_private_key_path, 'r') as f:
            private_key = f.read()
        
        auth = Auth.AppAuth(int(config.github_app_id), private_key).get_installation_auth(int(config.github_installation_id))
        g = Github(auth=auth)
        
        repo_name = f"{config.github_repo_owner}/{config.github_repo_name}"
        repo = g.get_repo(repo_name)
        
        repo.create_repository_dispatch(
            event_type="trigger",
            client_payload=db_dump
        )
        
    except Exception as e:
        logger.error(f"Failed to trigger workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger workflow: {str(e)}")
        
    return {"message": "Workflow triggered successfully"}
