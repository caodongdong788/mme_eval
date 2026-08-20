"""Establish the Alembic baseline for the current MME schema.

Revision ID: 20260820_0001
Revises:
"""

from alembic import op

from server.db import Base
from server import models_db  # noqa: F401


revision = "20260820_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh databases are created from the current ORM metadata. Existing databases are
    # normalized once by init_db before being stamped at this baseline.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Baseline downgrade is intentionally non-destructive; production data must only be
    # restored through the verified pg_dump workflow.
    pass
