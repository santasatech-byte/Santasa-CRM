"""create leads table

Revision ID: 004_create_leads_table
Revises: 003_create_executive_profiles
Create Date: 2026-08-15 19:37:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_create_leads_table'
down_revision: Union[str, None] = '003_create_executive_profiles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'leads',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('patient_name', sa.String(length=255), nullable=False),
        sa.Column('primary_phone', sa.String(length=50), nullable=False),
        sa.Column('normalized_phone', sa.String(length=50), nullable=False),
        sa.Column('secondary_phone', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('gender', sa.String(length=20), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=False, server_default='Hassan'),
        sa.Column('lead_source', sa.String(length=50), nullable=False, server_default='Manual'),
        sa.Column('campaign', sa.String(length=255), nullable=True),
        sa.Column('department', sa.String(length=100), nullable=False, server_default='Fertility & IVF'),
        sa.Column('service_interested', sa.String(length=255), nullable=True),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('assigned_executive_id', sa.String(length=36), nullable=True),
        sa.Column('lead_status', sa.String(length=50), nullable=False, server_default='New'),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='Medium'),
        sa.Column('next_followup_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_contacted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('updated_by', sa.String(length=36), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_executive_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_leads_id'), 'leads', ['id'], unique=False)
    op.create_index(op.f('ix_leads_patient_name'), 'leads', ['patient_name'], unique=False)
    op.create_index(op.f('ix_leads_normalized_phone'), 'leads', ['normalized_phone'], unique=False)
    op.create_index(op.f('ix_leads_email'), 'leads', ['email'], unique=False)
    op.create_index(op.f('ix_leads_lead_source'), 'leads', ['lead_source'], unique=False)
    op.create_index(op.f('ix_leads_department'), 'leads', ['department'], unique=False)
    op.create_index(op.f('ix_leads_branch_id'), 'leads', ['branch_id'], unique=False)
    op.create_index(op.f('ix_leads_assigned_executive_id'), 'leads', ['assigned_executive_id'], unique=False)
    op.create_index(op.f('ix_leads_lead_status'), 'leads', ['lead_status'], unique=False)
    op.create_index(op.f('ix_leads_priority'), 'leads', ['priority'], unique=False)
    op.create_index(op.f('ix_leads_next_followup_at'), 'leads', ['next_followup_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_leads_next_followup_at'), table_name='leads')
    op.drop_index(op.f('ix_leads_priority'), table_name='leads')
    op.drop_index(op.f('ix_leads_lead_status'), table_name='leads')
    op.drop_index(op.f('ix_leads_assigned_executive_id'), table_name='leads')
    op.drop_index(op.f('ix_leads_branch_id'), table_name='leads')
    op.drop_index(op.f('ix_leads_department'), table_name='leads')
    op.drop_index(op.f('ix_leads_lead_source'), table_name='leads')
    op.drop_index(op.f('ix_leads_email'), table_name='leads')
    op.drop_index(op.f('ix_leads_normalized_phone'), table_name='leads')
    op.drop_index(op.f('ix_leads_patient_name'), table_name='leads')
    op.drop_index(op.f('ix_leads_id'), table_name='leads')
    op.drop_table('leads')
