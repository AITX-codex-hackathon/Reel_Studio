"""SQLite via SQLAlchemy. One DB per install, simple and synchronous."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Generator

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    price = Column(String, nullable=True)
    beds = Column(Integer, nullable=True)
    baths = Column(Float, nullable=True)
    sqft = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    template_id = Column(String, nullable=True)
    storyboard_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    uploads = relationship("UploadRow", back_populates="project", cascade="all, delete-orphan")
    renders = relationship("RenderRow", back_populates="project", cascade="all, delete-orphan")


class UploadRow(Base):
    __tablename__ = "uploads"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    path = Column(String, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    sha256 = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("ProjectRow", back_populates="uploads")
    analysis = relationship("AnalysisRow", uselist=False, back_populates="upload", cascade="all, delete-orphan")


class AnalysisRow(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True)
    upload_id = Column(String, ForeignKey("uploads.id"), nullable=False, unique=True, index=True)
    room_type = Column(String, nullable=False)
    quality_score = Column(Float, nullable=False)
    framing = Column(String, nullable=False)
    lighting = Column(String, nullable=False)
    dominant_colors = Column(JSON, nullable=False, default=list)
    suggested_motion = Column(String, nullable=False)
    notes = Column(Text, nullable=False, default="")
    raw = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    upload = relationship("UploadRow", back_populates="analysis")


class StoryboardRow(Base):
    __tablename__ = "storyboards"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    template_id = Column(String, nullable=False)
    json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RenderRow(Base):
    __tablename__ = "renders"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    storyboard_id = Column(String, nullable=False)
    pass_type = Column(String, nullable=False)  # 'draft' | 'final'
    status = Column(String, nullable=False, default="pending")
    progress = Column(Float, nullable=False, default=0.0)
    output_path = Column(String, nullable=True)
    duration_sec = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    project = relationship("ProjectRow", back_populates="renders")


_engine = None
SessionLocal: sessionmaker | None = None


def init_db() -> None:
    global _engine, SessionLocal
    db_url = os.getenv("DATABASE_URL", "sqlite:///./storage_data/realstate.db")
    _engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
    )
    Base.metadata.create_all(_engine)
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def get_sessionmaker() -> sessionmaker:
    if SessionLocal is None:
        init_db()
    assert SessionLocal is not None
    return SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
