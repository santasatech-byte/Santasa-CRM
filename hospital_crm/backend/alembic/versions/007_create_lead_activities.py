"""create lead_activities table

Revision ID: 007_create_lead_activities
Revises: 006_create_lead_status_history
Create Date: 2026-08-15 19:41:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '007_create_lead_activities'
down_revision: Union[str, None] = '006_create_lead_status_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lead_activities',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('activity_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('activity_metadata', sa.JSON(), nullable=True),
        sa.Column('performed_by', sa.String(length=36), nullable=True),
        sa.Column('performed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['performed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lead_activities_id'), 'lead_activities', ['id'], unique=False)
    op.create_index(op.f('ix_lead_activities_lead_id'), 'lead_activities', ['lead_id'], unique=False)
    op.create_index(op.f('ix_lead_activities_activity_type'), 'lead_activities', ['activity_type'], unique=False)
    op.create_index(op.f('ix_lead_activities_performed_by'), 'lead_activities', ['performed_by'], unique=False)
    op.create_index(op.f('ix_lead_activities_performed_at'), 'lead_activities', ['performed_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lead_activities_performed_at'), table_name='lead_activities')
    op.drop_index(op.f('ix_lead_activities_performed_by'), table_name='lead_activities')
    op.drop_index(op.f('ix_lead_activities_activity_type'), table_name='lead_activities')
    op.drop_index(op.f('ix_lead_activities_lead_id'), table_name='lead_activities')
    op.drop_index(op.f('ix_lead_activities_id'), table_name='lead_activities')
    op.drop_table('lead_activities')
