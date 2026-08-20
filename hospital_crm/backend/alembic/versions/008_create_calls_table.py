"""create calls table

Revision ID: 008_create_calls_table
Revises: 007_create_lead_activities
Create Date: 2026-08-15 19:43:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '008_create_calls_table'
down_revision: Union[str, None] = '007_create_lead_activities'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'calls',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('external_call_id', sa.String(length=100), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=True),
        sa.Column('phone_number', sa.String(length=50), nullable=False),
        sa.Column('normalized_phone', sa.String(length=50), nullable=False),
        sa.Column('direction', sa.String(length=20), nullable=False, server_default='Incoming'),
        sa.Column('executive_id', sa.String(length=36), nullable=True),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='Initiated'),
        sa.Column('recording_status', sa.String(length=50), nullable=False, server_default='Unavailable'),
        sa.Column('recording_url', sa.String(length=500), nullable=True),
        sa.Column('recording_duration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='mock'),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['executive_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_calls_id'), 'calls', ['id'], unique=False)
    op.create_index(op.f('ix_calls_external_call_id'), 'calls', ['external_call_id'], unique=False)
    op.create_index(op.f('ix_calls_lead_id'), 'calls', ['lead_id'], unique=False)
    op.create_index(op.f('ix_calls_normalized_phone'), 'calls', ['normalized_phone'], unique=False)
    op.create_index(op.f('ix_calls_direction'), 'calls', ['direction'], unique=False)
    op.create_index(op.f('ix_calls_executive_id'), 'calls', ['executive_id'], unique=False)
    op.create_index(op.f('ix_calls_branch_id'), 'calls', ['branch_id'], unique=False)
    op.create_index(op.f('ix_calls_status'), 'calls', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_calls_status'), table_name='calls')
    op.drop_index(op.f('ix_calls_branch_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_executive_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_direction'), table_name='calls')
    op.drop_index(op.f('ix_calls_normalized_phone'), table_name='calls')
    op.drop_index(op.f('ix_calls_lead_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_external_call_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_id'), table_name='calls')
    op.drop_table('calls')
