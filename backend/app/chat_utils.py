"""Shared utilities for chat token handling."""
import hashlib
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import ChatSession


def hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def lookup_session(token: str, db: Session) -> ChatSession:
    hashed = hash_token(token)
    session = db.query(ChatSession).filter_by(token_hash=hashed).first()
    if not session:
        raise HTTPException(404, "Chat-sessie niet gevonden of verlopen")
    if session.expires_at and session.expires_at.replace(tzinfo=None) < datetime.utcnow():
        raise HTTPException(410, "Deze chat-link is verlopen")
    return session
