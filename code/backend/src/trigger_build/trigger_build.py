"""Module for triggering and monitoring GitHub workflows."""
import logging
import time

from fastapi import APIRouter, HTTPException, Depends
from github import Github, Auth, GithubException
from sqlalchemy.orm import Session

from config import config
from database import database

logger = logging.getLogger(__name__)
router = APIRouter()

# Global cache for the GitHub client
GITHUB_CLIENT = None
GITHUB_CLIENT_EXPIRY = 0


def get_github_client():
    """
    Returns a GitHub client, using a cached one if it's still valid.
    """
    global GITHUB_CLIENT, GITHUB_CLIENT_EXPIRY  # noqa: PLW603

    # Re-use client if it's still valid (refresh every 30 mins)
    if GITHUB_CLIENT and time.time() < GITHUB_CLIENT_EXPIRY:
        return GITHUB_CLIENT

    try:
        with open(config.github_private_key_path, 'r', encoding='utf-8') as f:
            private_key = f.read()

        auth = Auth.AppAuth(
            int(config.github_app_id),
            private_key
        ).get_installation_auth(int(config.github_installation_id))

        GITHUB_CLIENT = Github(auth=auth)
        GITHUB_CLIENT_EXPIRY = time.time() + 1800  # 30 minutes
        return GITHUB_CLIENT
    except Exception as e:
        logger.error('Failed to initialize GitHub client: %s', str(e))
        raise HTTPException(
            status_code=500,
            detail=f'GitHub initialization failed: {str(e)}'
        ) from e


def serialize_game(game):
    """
    Serializes a Game object to a dictionary.
    """
    return {
        'id': str(game.id),
        'name': game.name,
        'description': game.description,
        'is_active': game.is_active,
        'zip_uploads': [
            {
                'id': str(zu.id),
                'name': zu.name,
                'game_id': str(zu.game_id)
            } for zu in game.zip_uploads
        ],
        'assets': [
            {
                'id': str(asset.id),
                'game_id': str(asset.game_id),
                'original_path': asset.original_path,
                'path': asset.path
            } for asset in game.assets
        ]
    }


def serialize_zip_upload(zu):
    """
    Serializes a ZipUpload object to a dictionary.
    """
    return {
        'id': str(zu.id),
        'name': zu.name,
        'game_id': str(zu.game_id)
    }


def serialize_asset(asset):
    """
    Serializes an Asset object to a dictionary.
    """
    return {
        'id': str(asset.id),
        'game_id': str(asset.game_id),
        'original_path': asset.original_path,
        'path': asset.path
    }


@router.post('/trigger-workflow')
async def trigger_workflow(
    db: Session = Depends(database.get_session)  # noqa: B008
):
    """
    Triggers the GitHub workflow.
    """
    if not all(
        [
            config.github_app_id,
            config.github_private_key_path,
            config.github_installation_id,
            config.github_repo_owner,
            config.github_repo_name
        ]
    ):
        raise HTTPException(
            status_code=500,
            detail='GitHub App configuration is missing'
        )

    games = db.query(database.Game).filter(database.Game.is_active == True).all()
    zip_uploads = db.query(database.ZipUpload).all()
    assets = db.query(database.Asset).all()

    db_dump = {
        'games': [serialize_game(game) for game in games],
        'zip_uploads': [serialize_zip_upload(zu) for zu in zip_uploads],
        'assets': [serialize_asset(asset) for asset in assets]
    }

    try:
        g = get_github_client()
        repo_name = f'{config.github_repo_owner}/{config.github_repo_name}'
        repo = g.get_repo(repo_name)

        repo.create_repository_dispatch(
            event_type='trigger',
            client_payload=db_dump
        )

    except Exception as e:
        logger.error('Failed to trigger workflow: %s', str(e))
        raise HTTPException(
            status_code=500,
            detail=f'Failed to trigger workflow: {str(e)}'
        ) from e

    return {'message': 'Workflow triggered successfully'}


@router.get('/workflow-status')
async def get_workflow_status():
    """
    Returns the status of the latest GitHub workflow run.
    """
    if not all([
        config.github_app_id,
        config.github_private_key_path,
        config.github_installation_id,
        config.github_repo_owner,
        config.github_repo_name
    ]):
        raise HTTPException(
            status_code=500,
            detail='GitHub App configuration is missing'
        )

    try:
        g = get_github_client()
        repo_name = f'{config.github_repo_owner}/{config.github_repo_name}'
        repo = g.get_repo(repo_name)

        # Get the latest workflow run for repository_dispatch
        runs = repo.get_workflow_runs(event='repository_dispatch')

        if runs.totalCount == 0:
            return {'status': 'none', 'conclusion': None}

        latest_run = runs[0]

        # Fetch jobs to get step progress
        jobs = None
        try:
            if hasattr(latest_run, 'get_jobs'):
                jobs = latest_run.get_jobs()  # type: ignore
            elif hasattr(latest_run, 'jobs'):
                jobs = latest_run.jobs()
            else:
                logger.error(
                    'WorkflowRun object has neither get_jobs nor jobs. '
                    'Available: %s',
                    [a for a in dir(latest_run) if not a.startswith('_')]
                )
        except (GithubException, AttributeError) as e:
            logger.error('Error calling jobs method: %s', e)

        total_steps = 0
        completed_steps = 0
        current_step_name = ''

        if jobs and jobs.totalCount > 0:
            # Usually there is only one main job for these workflows
            job = jobs[0]
            total_steps = len(job.steps)
            for step in job.steps:
                if step.status == 'completed':
                    completed_steps += 1
                elif step.status == 'in_progress':
                    current_step_name = step.name

            # If nothing is in_progress but we have completed some,
            # the next one is current
            if not current_step_name and completed_steps < total_steps:
                current_step_name = job.steps[completed_steps].name

        return {
            'id': latest_run.id,
            'status': latest_run.status,
            'conclusion': latest_run.conclusion,
            'created_at': (
                latest_run.created_at.isoformat()
                if latest_run.created_at else None
            ),
            'updated_at': (
                latest_run.updated_at.isoformat()
                if latest_run.updated_at else None
            ),
            'progress': {
                'total_steps': total_steps,
                'completed_steps': completed_steps,
                'current_step': current_step_name
            }
        }

    except Exception as e:
        logger.error('Failed to fetch workflow status: %s', e)
        raise HTTPException(
            status_code=500,
            detail=f'Failed to fetch workflow status: {str(e)}'
        ) from e
