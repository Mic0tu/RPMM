"""add event-driven and gRPC infrastructure tables

Revision ID: a61c3f4b82d1
Revises: 5e9646f686d9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a61c3f4b82d1"
down_revision: Union[str, Sequence[str], None] = "5e9646f686d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "kitchen_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index(op.f("ix_kitchen_orders_id"), "kitchen_orders", ["id"])
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("routing_key", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_index(op.f("ix_kitchen_orders_id"), table_name="kitchen_orders")
    op.drop_table("kitchen_orders")
    op.drop_table("processed_events")
