from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from observix_control_plane.models import Base


def ensure_tables(engine: Engine) -> None:
    """
    Ensure all SQLAlchemy tables exist.

    This is intended for local/dev convenience (SQLite).
    In production, prefer Alembic migrations.
    """
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    # If nothing exists yet, create everything
    if not existing:
        Base.metadata.create_all(bind=engine)
        return

    # Otherwise create any missing tables (safe additive behavior)
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            table.create(bind=engine)
