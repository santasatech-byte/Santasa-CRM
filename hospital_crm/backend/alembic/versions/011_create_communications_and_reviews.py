"""create communication_logs and review_requests tables

Revision ID: 011_create_communications_and_reviews
Revises: 010_create_appointments_consultations_conversions
Create Date: 2026-08-15 19:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '011_create_communications_and_reviews'
down_revision: Union[str, None] = '010_create_appointments_consultations_conversions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'communication_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False, server_default='WhatsApp'),
        sa.Column('template_name', sa.String(length=100), nullable=True),
        sa.Column('recipient_phone', sa.String(length=50), nullable=False),
        sa.Column('message_body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='Sent'),
        sa.Column('external_message_id', sa.String(length=100), nullable=True),
        sa.Column('sent_by', sa.String(length=36), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sent_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_communication_logs_id'), 'communication_logs', ['id'], unique=False)
    op.create_index(op.f('ix_communication_logs_lead_id'), 'communication_logs', ['lead_id'], unique=False)
    op.create_index(op.f('ix_communication_logs_channel'), 'communication_logs', ['channel'], unique=False)
    op.create_index(op.f('ix_communication_logs_status'), 'communication_logs', ['status'], unique=False)
    op.create_index(op.f('ix_communication_logs_external_message_id'), 'communication_logs', ['external_message_id'], unique=False)

    op.create_table(
        'review_requests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('appointment_id', sa.String(length=36), nullable=True),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('google_review_url', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='Requested'),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('requested_by', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_requests_id'), 'review_requests', ['id'], unique=False)
    op.create_index(op.f('ix_review_requests_lead_id'), 'review_requests', ['lead_id'], unique=False)


def downgrade() -> None:
    op.drop_table('review_requests')
    op.drop_table('communication_logs')
