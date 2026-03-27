from typing import List
from typing import Optional
import uuid
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

class Base(DeclarativeBase):
    pass

class Game(Base):
    __tablename__ = "game"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    def __repr__(self) -> str:
        return f"Game(id={self.id!r}, name={self.name!r})"

class ZipUpload(Base):
    __tablename__ = "zip_upload"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("game.id"))
    game: Mapped["Game"] = relationship(back_populates="zip_uploads")
    def __repr__(self) -> str:
        return f"ZipUpload(id={self.id!r}, name={self.name!r})"
    
class Asset(Base):
    __tablename__ = "asset"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    gameId: Mapped[uuid.UUID] = mapped_column(String(255))
    game: Mapped["Game"] = relationship(back_populates="assets")
    original_path: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(255))
    def __repr__(self) -> str:
        return f"Asset(id={self.id!r}, name={self.name!r})"