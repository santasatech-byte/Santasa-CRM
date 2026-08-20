"""create lead_status_history table

Revision ID: 006_create_lead_status_history
Revises: 005_create_lead_assignment_history
Create Date: 2026-08-15 19:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '006_create_lead_status_history'
down_revision: Union[str, None] = '005_create_lead_assignment_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lead_status_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('old_status', sa.String(length=50), nullable=True),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('changed_by', sa.String(length=36), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('competitor_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lead_status_history_id'), 'lead_status_history', ['id'], unique=False)
    op.create_index(op.f('ix_lead_status_history_lead_id'), 'lead_status_history', ['lead_id'], unique=False)
    op.create_index(op.f('ix_lead_status_history_new_status'), 'lead_status_history', ['new_status'], unique=False)
    op.create_index(op.f('ix_lead_status_history_changed_by'), 'lead_status_history', ['changed_by'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lead_status_history_changed_by'), table_name='lead_status_history')
    op.drop_index(op.f('ix_lead_status_history_new_status'), table_name='lead_status_history')
    op.drop_index(op.f('ix_lead_status_history_lead_id'), table_name='lead_status_history')
    op.drop_index(op.f('ix_lead_status_history_id'), table_name='lead_status_history')
    op.drop_table('lead_status_history')
