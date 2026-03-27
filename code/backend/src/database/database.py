from typing import List
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from sqlalchemy import create_engine, func
engine = create_engine("sqlite:///database.db", echo=True)

session = Session(engine)

class Base(DeclarativeBase):
    pass

class Game(Base):
    __tablename__ = "game"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    zip_uploads: Mapped[List["ZipUpload"]] = relationship(back_populates="game")
    assets: Mapped[List["Asset"]] = relationship(back_populates="game")
    def __repr__(self) -> str:
        return f"Game(id={self.id!r}, name={self.name!r})"

class ZipUpload(Base):
    __tablename__ = "zip_upload"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    game_id: Mapped[UUID] = mapped_column(ForeignKey("game.id"))
    game: Mapped["Game"] = relationship(back_populates="zip_uploads")
    def __repr__(self) -> str:
        return f"ZipUpload(id={self.id!r}, name={self.name!r})"
    
class Asset(Base):
    __tablename__ = "asset"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    gameId: Mapped[UUID] = mapped_column(ForeignKey("game.id"))
    game: Mapped["Game"] = relationship(back_populates="assets")
    original_path: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(255))
    def __repr__(self) -> str:
        return f"Asset(id={self.id!r}, gameId={self.gameId!r}, original_path={self.original_path!r})"
    
Base.metadata.create_all(engine)
