from fastapi import APIRouter
import logging
from database import database

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
def get_all_games():
    return {"games": database.session.query(database.Game).all()}

@router.post("/")
def create_game(name: str):
    new_game = database.Game(name=name)
    database.session.add(new_game)
    database.session.commit()
    return {"game_id": new_game.id, "name": new_game.name}
    