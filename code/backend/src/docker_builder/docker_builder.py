from fastapi import APIRouter
import docker

docker_client = docker.from_env()

router = APIRouter()

@router.get("/ps")
def list_containers():
    containers = docker_client.containers.list()
    return {"containers": [container.name for container in containers]}
