"""create executive_profiles table

Revision ID: 003_create_executive_profiles
Revises: 002_create_hospitals_and_branches
Create Date: 2026-08-15 19:36:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_create_executive_profiles'
down_revision: Union[str, None] = '002_create_hospitals_and_branches'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'executive_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('employee_id', sa.String(length=50), nullable=False),
        sa.Column('manager_id', sa.String(length=36), nullable=True),
        sa.Column('telephony_agent_id', sa.String(length=100), nullable=True),
        sa.Column('telephony_extension', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='Online'),
        sa.Column('last_status_change_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('max_active_leads_capacity', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('is_available_for_lead_assignment', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['manager_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_executive_profiles_id'), 'executive_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_executive_profiles_user_id'), 'executive_profiles', ['user_id'], unique=True)
    op.create_index(op.f('ix_executive_profiles_employee_id'), 'executive_profiles', ['employee_id'], unique=True)
    op.create_index(op.f('ix_executive_profiles_manager_id'), 'executive_profiles', ['manager_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_executive_profiles_manager_id'), table_name='executive_profiles')
    op.drop_index(op.f('ix_executive_profiles_employee_id'), table_name='executive_profiles')
    op.drop_index(op.f('ix_executive_profiles_user_id'), table_name='executive_profiles')
    op.drop_index(op.f('ix_executive_profiles_id'), table_name='executive_profiles')
    op.drop_table('executive_profiles')
