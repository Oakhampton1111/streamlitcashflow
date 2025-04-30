"""Initial migration

Revision ID: 0001_initial
Revises:
Create Date: 2025-04-29 11:15:00
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "type", sa.Enum("core", "flex", name="supplier_type"), nullable=False
        ),
        sa.Column("max_delay_days", sa.Integer(), nullable=False),
    )
    op.create_table(
        "creditors",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "supplier_id",
            sa.Integer(),
            sa.ForeignKey("suppliers.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("aging_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
    )
    op.create_table(
        "rule_changes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("nl_text", sa.Text(), nullable=False),
        sa.Column(
            "applied", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "payment_plans",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "creditor_id",
            sa.Integer(),
            sa.ForeignKey("creditors.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("note", sa.Text()),
    )
    op.create_table(
        "forecasts",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("run_date", sa.DateTime(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("forecast_json", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("forecasts")
    op.drop_table("payment_plans")
    op.drop_table("rule_changes")
    op.drop_table("creditors")
    op.drop_table("suppliers")
    # Drop enum type for Postgres
    op.execute("DROP TYPE IF EXISTS supplier_type;")
