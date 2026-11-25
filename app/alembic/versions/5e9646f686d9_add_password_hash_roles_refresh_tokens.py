"""add password_hash, roles, refresh_tokens

Revision ID: 5e9646f686d9
Revises: 9ae98d9fb1b7
Create Date: 2026-10-20 18:55:52.198116

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5e9646f686d9"
down_revision: Union[str, Sequence[str], None] = "9ae98d9fb1b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    op.add_column("users", sa.Column("role_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_users_role", "users", "roles", ["role_id"], ["id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )

    op.execute(
        "INSERT INTO roles (name) VALUES ('student'), ('cook'), ('courier'), ('admin')"
    )
    op.execute(
        "UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'student')"
    )
    # Временный placeholder-хеш для уже существующих пользователей
    # (bcrypt-хеш строки "changeme" — пользователь должен сменить пароль)
    op.execute(
        "UPDATE users SET password_hash = "
        "'$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.G2oQ.placeholder' "
        "WHERE password_hash IS NULL"
    )
    op.alter_column("users", "role_id", nullable=False)
    op.alter_column("users", "password_hash", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_users_role", "users", type_="foreignkey")
    op.drop_column("users", "role_id")
    op.drop_column("users", "password_hash")
    op.drop_table("refresh_tokens")
    op.drop_table("roles")
