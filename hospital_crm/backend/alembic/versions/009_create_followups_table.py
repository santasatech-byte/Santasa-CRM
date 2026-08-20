"""create followups table

Revision ID: 009_create_followups_table
Revises: 008_create_calls_table
Create Date: 2026-08-15 19:44:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '009_create_followups_table'
down_revision: Union[str, None] = '008_create_calls_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'followups',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('executive_id', sa.String(length=36), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False, server_default='Call'),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='Medium'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='Scheduled'),
        sa.Column('reminder_offset_minutes', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('reminder_processed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completion_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['executive_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_followups_id'), 'followups', ['id'], unique=False)
    op.create_index(op.f('ix_followups_lead_id'), 'followups', ['lead_id'], unique=False)
    op.create_index(op.f('ix_followups_executive_id'), 'followups', ['executive_id'], unique=False)
    op.create_index(op.f('ix_followups_scheduled_at'), 'followups', ['scheduled_at'], unique=False)
    op.create_index(op.f('ix_followups_status'), 'followups', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_followups_status'), table_name='followups')
    op.drop_index(op.f('ix_followups_scheduled_at'), table_name='followups')
    op.drop_index(op.f('ix_followups_executive_id'), table_name='followups')
    op.drop_index(op.f('ix_followups_lead_id'), table_name='followups')
    op.drop_index(op.f('ix_followups_id'), table_name='followups')
    op.drop_table('followups')
