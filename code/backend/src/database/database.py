"""
Database models and session management.
"""
import logging
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from config import config

engine = create_engine(
    config.db_string,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600
)

level = getattr(logging, config.db_log_level.upper(), logging.INFO)
logging.getLogger('sqlalchemy.engine').setLevel(level)

SESSION_LOCAL = sessionmaker(
    bind=engine, autoflush=False, autocommit=False
)


def get_session():
    """Dependency for getting a database session."""
    db = SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):  # noqa: PLR903
    """Base class for SQLAlchemy models."""


class Game(Base):  # noqa: PLR903
    """Model representing a game."""
    __tablename__ = 'game'
    id: Mapped[UUID] = mapped_column(  # noqa: A003
        primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(
        String(2000), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    zip_uploads: Mapped[list['ZipUpload']] = relationship(
        back_populates='game'
    )
    assets: Mapped[list['Asset']] = relationship(back_populates='game')

    def __repr__(self) -> str:
        return (
            f'Game(id={self.id!r}, name={self.name!r}, '
            f'description={self.description!r})'
        )


class ZipUpload(Base):  # noqa: PLR903
    """Model representing a ZIP file upload."""
    __tablename__ = 'zip_upload'
    id: Mapped[UUID] = mapped_column(  # noqa: A003
        primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    game_id: Mapped[UUID] = mapped_column(ForeignKey('game.id'))
    game: Mapped['Game'] = relationship(back_populates='zip_uploads')
    # Pre-calculated S3 URI where index.html (or main entry) is located.
    # This avoids expensive S3 listings on every asset request.
    game_root_uri: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f'ZipUpload(id={self.id!r}, name={self.name!r}, '
            f'root={self.game_root_uri!r})'
        )


class Asset(Base):  # noqa: PLR903
    """Model representing a manual asset override."""
    __tablename__ = 'asset'
    id: Mapped[UUID] = mapped_column(  # noqa: A003
        primary_key=True, default=uuid4
    )
    game_id: Mapped[UUID] = mapped_column(ForeignKey('game.id'))
    game: Mapped['Game'] = relationship(back_populates='assets')
    original_path: Mapped[str] = mapped_column(String(1024))
    path: Mapped[str] = mapped_column(String(1024))

    def __repr__(self) -> str:
        return (
            f'Asset(id={self.id!r}, game_id={self.game_id!r}, '
            f'original_path={self.original_path!r})'
        )


Base.metadata.create_all(engine)
