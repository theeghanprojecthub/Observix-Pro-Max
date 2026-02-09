from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from observix_common.settings import get_settings

_ENGINE: Optional[Engine] = None
_SESSION_FACTORY: Optional[sessionmaker] = None
_CONFIGURED_DB_URL: Optional[str] = None


def _resolve_database_url() -> str:
    """
    Resolve DB URL precedence:
      1) YAML/user override via init_engine/configure
      2) OBSERVIX_CP_DEFAULT_DATABASE_URL (operator remote default)
      3) .env/env via get_settings (DB_URL / DATABASE_URL / DB__URL)
    """
    if _CONFIGURED_DB_URL and _CONFIGURED_DB_URL.strip():
        return _CONFIGURED_DB_URL.strip()

    op_default = os.getenv("OBSERVIX_CP_DEFAULT_DATABASE_URL", "").strip()
    if op_default:
        return op_default

    s = get_settings()
    url = (s.db.url or "").strip()
    if not url:
        raise RuntimeError(
            "Database URL is required. Provide `database_url` in control-plane YAML, "
            "or set OBSERVIX_CP_DEFAULT_DATABASE_URL, or set DB_URL/DATABASE_URL."
        )
    return url


def init_engine(db_url: Optional[str] = None) -> None:
    """
    Configure and initialize the engine/session factory.

    Calling with a db_url resets the cached engine/session factory so the new URL is used.
    Calling without a db_url keeps current configuration and initializes lazily.
    """
    global _CONFIGURED_DB_URL, _ENGINE, _SESSION_FACTORY

    if db_url is not None:
        _CONFIGURED_DB_URL = db_url.strip() if db_url.strip() else None
        _ENGINE = None
        _SESSION_FACTORY = None

    _ensure_initialized()


def configure(*, db_url: Optional[str] = None) -> None:
    """
    Backwards-compatible alias for configuring the DB URL.
    """
    init_engine(db_url=db_url or "")


def _ensure_initialized() -> None:
    """
    Ensure engine + session factory exist.
    """
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None and _SESSION_FACTORY is not None:
        return

    url = _resolve_database_url()
    _ENGINE = create_engine(url, pool_pre_ping=True, future=True)
    _SESSION_FACTORY = sessionmaker(
        bind=_ENGINE, autocommit=False, autoflush=False, future=True
    )


def get_engine() -> Engine:
    """
    Return initialized engine.
    """
    _ensure_initialized()
    assert _ENGINE is not None
    return _ENGINE


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    Transactional session scope.
    """
    _ensure_initialized()
    assert _SESSION_FACTORY is not None

    session: Session = _SESSION_FACTORY()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
