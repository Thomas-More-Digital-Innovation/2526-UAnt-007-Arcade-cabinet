from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from config import config 
import logging
import json
import time
from sqlalchemy.orm import Session
from database import database
from github import Github, Auth

logger = logging.getLogger(__name__)
router = APIRouter()

# Global cache for the GitHub client
_github_client = None
_github_client_expiry = 0

def get_github_client():
    global _github_client, _github_client_expiry
    
    # Re-use client if it's still valid (refresh every 30 mins, though tokens last 1 hr)
    if _github_client and time.time() < _github_client_expiry:
        return _github_client
        
    try:
        with open(config.github_private_key_path, 'r') as f:
            private_key = f.read()
        
        auth = Auth.AppAuth(int(config.github_app_id), private_key).get_installation_auth(int(config.github_installation_id))
        _github_client = Github(auth=auth)
        _github_client_expiry = time.time() + 1800 # 30 minutes
        return _github_client
    except Exception as e:
        logger.error(f"Failed to initialize GitHub client: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GitHub initialization failed: {str(e)}")

def serialize_game(game):
    return {
        "id": str(game.id),
        "name": game.name,
        "description": game.description,
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

@router.post("/trigger-workflow")
async def trigger_workflow(db: Session = Depends(database.get_session)):
    if not all([config.github_app_id, config.github_private_key_path, config.github_installation_id, config.github_repo_owner, config.github_repo_name]):
        raise HTTPException(status_code=500, detail="GitHub App configuration is missing")
    
    games = db.query(database.Game).all()
    zip_uploads = db.query(database.ZipUpload).all()
    assets = db.query(database.Asset).all()

    db_dump = {
        "games": [serialize_game(game) for game in games],
        "zip_uploads": [serialize_zip_upload(zu) for zu in zip_uploads],
        "assets": [serialize_asset(asset) for asset in assets]
    }

    try:
        g = get_github_client()
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

@router.get("/workflow-status")
async def get_workflow_status():
    if not all([config.github_app_id, config.github_private_key_path, config.github_installation_id, config.github_repo_owner, config.github_repo_name]):
        raise HTTPException(status_code=500, detail="GitHub App configuration is missing")
    
    try:
        g = get_github_client()
        repo_name = f"{config.github_repo_owner}/{config.github_repo_name}"
        repo = g.get_repo(repo_name)
        
        # Get the latest workflow run for repository_dispatch
        runs = repo.get_workflow_runs(event="repository_dispatch")
        
        if runs.totalCount == 0:
            return {"status": "none", "conclusion": None}
            
        latest_run = runs[0]
        
        # Fetch jobs to get step progress
        jobs = None
        try:
            if hasattr(latest_run, "get_jobs"):
                jobs = latest_run.get_jobs()
            elif hasattr(latest_run, "jobs"):
                jobs = latest_run.jobs()
            else:
                logger.error(f"WorkflowRun object has neither get_jobs nor jobs. Available: {[a for a in dir(latest_run) if not a.startswith('_')]}")
        except Exception as e:
            logger.error(f"Error calling jobs method: {str(e)}")

        total_steps = 0
        completed_steps = 0
        current_step_name = ""
        
        if jobs and jobs.totalCount > 0:
            # Usually there is only one main job for these workflows
            job = jobs[0]
            total_steps = len(job.steps)
            for step in job.steps:
                if step.status == "completed":
                    completed_steps += 1
                elif step.status == "in_progress":
                    current_step_name = step.name
            
            # If nothing is in_progress but we have completed some, the next one is current
            if not current_step_name and completed_steps < total_steps:
                current_step_name = job.steps[completed_steps].name

        return {
            "id": latest_run.id,
            "status": latest_run.status,
            "conclusion": latest_run.conclusion,
            "created_at": latest_run.created_at.isoformat() if latest_run.created_at else None,
            "updated_at": latest_run.updated_at.isoformat() if latest_run.updated_at else None,
            "progress": {
                "total_steps": total_steps,
                "completed_steps": completed_steps,
                "current_step": current_step_name
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch workflow status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch workflow status: {str(e)}")
