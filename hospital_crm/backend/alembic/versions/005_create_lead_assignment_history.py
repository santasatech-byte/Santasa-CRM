"""create lead_assignment_history table

Revision ID: 005_create_lead_assignment_history
Revises: 004_create_leads_table
Create Date: 2026-08-15 19:39:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '005_create_lead_assignment_history'
down_revision: Union[str, None] = '004_create_leads_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lead_assignment_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('previous_executive_id', sa.String(length=36), nullable=True),
        sa.Column('new_executive_id', sa.String(length=36), nullable=False),
        sa.Column('assigned_by', sa.String(length=36), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('strategy', sa.String(length=50), nullable=False, server_default='Manual'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['previous_executive_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['new_executive_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lead_assignment_history_id'), 'lead_assignment_history', ['id'], unique=False)
    op.create_index(op.f('ix_lead_assignment_history_lead_id'), 'lead_assignment_history', ['lead_id'], unique=False)
    op.create_index(op.f('ix_lead_assignment_history_previous_executive_id'), 'lead_assignment_history', ['previous_executive_id'], unique=False)
    op.create_index(op.f('ix_lead_assignment_history_new_executive_id'), 'lead_assignment_history', ['new_executive_id'], unique=False)
    op.create_index(op.f('ix_lead_assignment_history_assigned_by'), 'lead_assignment_history', ['assigned_by'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lead_assignment_history_assigned_by'), table_name='lead_assignment_history')
    op.drop_index(op.f('ix_lead_assignment_history_new_executive_id'), table_name='lead_assignment_history')
    op.drop_index(op.f('ix_lead_assignment_history_previous_executive_id'), table_name='lead_assignment_history')
    op.drop_index(op.f('ix_lead_assignment_history_lead_id'), table_name='lead_assignment_history')
    op.drop_index(op.f('ix_lead_assignment_history_id'), table_name='lead_assignment_history')
    op.drop_table('lead_assignment_history')
