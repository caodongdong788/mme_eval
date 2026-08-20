"""Encrypt recoverable OpenAPI Key values in place.

Revision ID: 20260820_0002
Revises: 20260820_0001
"""

from alembic import op
from sqlalchemy import text

from server.secret_codec import (
    encrypt_recoverable_secret,
    is_encrypted_recoverable_secret,
)


revision = "20260820_0002"
down_revision = "20260820_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        text(
            "SELECT id, api_key FROM open_api_access_key "
            "WHERE api_key IS NOT NULL AND api_key<>''"
        )
    ).mappings().all()
    for row in rows:
        raw_value = str(row["api_key"] or "")
        if is_encrypted_recoverable_secret(raw_value):
            continue
        connection.execute(
            text("UPDATE open_api_access_key SET api_key=:value WHERE id=:id"),
            {
                "id": row["id"],
                "value": encrypt_recoverable_secret(raw_value),
            },
        )


def downgrade() -> None:
    # 密文降级为明文会降低安全性，因此保持现状；旧版仍可依赖 key_hash 鉴权。
    pass
