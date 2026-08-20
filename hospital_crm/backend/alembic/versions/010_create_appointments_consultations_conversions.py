"""create appointments, consultations, conversions tables

Revision ID: 010_create_appointments_consultations_conversions
Revises: 009_create_followups_table
Create Date: 2026-08-15 19:46:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '010_create_appointments_consultations_conversions'
down_revision: Union[str, None] = '009_create_followups_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'appointments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('doctor_id', sa.String(length=36), nullable=True),
        sa.Column('booked_by', sa.String(length=36), nullable=False),
        sa.Column('appointment_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('department', sa.String(length=100), nullable=False, server_default='Fertility & IVF'),
        sa.Column('service_type', sa.String(length=255), nullable=False, server_default='Initial Consultation'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='Booked'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('reminder_sent', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['booked_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_appointments_id'), 'appointments', ['id'], unique=False)
    op.create_index(op.f('ix_appointments_lead_id'), 'appointments', ['lead_id'], unique=False)
    op.create_index(op.f('ix_appointments_branch_id'), 'appointments', ['branch_id'], unique=False)
    op.create_index(op.f('ix_appointments_doctor_id'), 'appointments', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_appointments_appointment_at'), 'appointments', ['appointment_at'], unique=False)
    op.create_index(op.f('ix_appointments_status'), 'appointments', ['status'], unique=False)

    op.create_table(
        'consultation_outcomes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('appointment_id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('doctor_id', sa.String(length=36), nullable=True),
        sa.Column('outcome_status', sa.String(length=100), nullable=False),
        sa.Column('recommended_service', sa.String(length=255), nullable=True),
        sa.Column('estimated_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('clinical_summary', sa.Text(), nullable=True),
        sa.Column('recorded_by', sa.String(length=36), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('appointment_id')
    )
    op.create_index(op.f('ix_consultation_outcomes_id'), 'consultation_outcomes', ['id'], unique=False)
    op.create_index(op.f('ix_consultation_outcomes_lead_id'), 'consultation_outcomes', ['lead_id'], unique=False)

    op.create_table(
        'conversions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('appointment_id', sa.String(length=36), nullable=True),
        sa.Column('converted_service', sa.String(length=255), nullable=False),
        sa.Column('conversion_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('converted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('converted_by', sa.String(length=36), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['converted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversions_id'), 'conversions', ['id'], unique=False)
    op.create_index(op.f('ix_conversions_lead_id'), 'conversions', ['lead_id'], unique=False)


def downgrade() -> None:
    op.drop_table('conversions')
    op.drop_table('consultation_outcomes')
    op.drop_table('appointments')
