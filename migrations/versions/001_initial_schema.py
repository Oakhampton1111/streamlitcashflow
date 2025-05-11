"""Initial database schema.

Revision ID: 001
Revises: None
Create Date: 2023-01-01

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '001'
down_revision = None

def upgrade():
    """Create initial tables."""
    # Create suppliers table
    op.create_table(
        'suppliers',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('type', sa.Enum('core', 'flex', name='supplier_type'), nullable=False),
        sa.Column('max_delay_days', sa.Integer, nullable=False),
    )
    
    # Create creditors table
    op.create_table(
        'creditors',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('supplier_id', sa.Integer, sa.ForeignKey('suppliers.id'), nullable=False, index=True),
        sa.Column('invoice_date', sa.Date, nullable=False),
        sa.Column('due_date', sa.Date, nullable=False),
        sa.Column('amount', sa.Numeric, nullable=False),
        sa.Column('aging_days', sa.Integer, nullable=False),
        sa.Column('status', sa.String, nullable=False),
    )
    
    # Create rule_changes table
    op.create_table(
        'rule_changes',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('nl_text', sa.Text, nullable=False),
        sa.Column('applied', sa.Boolean, default=False, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    
    # Create payment_plans table
    op.create_table(
        'payment_plans',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('creditor_id', sa.Integer, sa.ForeignKey('creditors.id'), nullable=False, index=True),
        sa.Column('scheduled_date', sa.Date, nullable=False),
        sa.Column('amount', sa.Numeric, nullable=False),
        sa.Column('note', sa.Text),
    )
    
    # Create forecasts table
    op.create_table(
        'forecasts',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('run_date', sa.DateTime, nullable=False),
        sa.Column('horizon_days', sa.Integer, nullable=False),
        sa.Column('forecast_json', sa.JSON, nullable=False),
    )


def downgrade():
    """Drop all tables."""
    op.drop_table('forecasts')
    op.drop_table('payment_plans')
    op.drop_table('rule_changes')
    op.drop_table('creditors')
    op.drop_table('suppliers')
    op.execute('DROP TYPE IF EXISTS supplier_type')
