from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from config import config 

import httpx


from typing import List

router = APIRouter()

@router.post("/trigger-workflow")
async def trigger_workflow(game_ids: List[str]):
    if not config.github_repo_url or not config.github_token:
        raise HTTPException(status_code=500, detail="GitHub configuration is missing")
    
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {config.github_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    payload = {
        "event_type": "trigger",
        "client_payload": {
            "game_ids": game_ids
        }
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
