"""initial schema

Revision: 0001
Parent: none
"""

import sqlalchemy as sa
from alembic import op


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'admin_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('failed_login_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('login_locked_until', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.CheckConstraint('failed_login_count >= 0', name='ck_admin_failed_login_count'),
        sa.CheckConstraint('length(username) BETWEEN 1 AND 64', name='ck_admin_username_length'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_table(
        'admin_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), server_default='', nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.CheckConstraint('length(description) <= 500 AND instr(description, char(0)) = 0', name='ck_admin_item_description'),
        sa.CheckConstraint('length(name) BETWEEN 1 AND 100 AND length(trim(name)) > 0 AND instr(name, char(0)) = 0', name='ck_admin_item_name'),
        sa.CheckConstraint('updated_at >= created_at', name='ck_admin_item_timestamps'),
        sa.ForeignKeyConstraint(['created_by'], ['admin_users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_admin_items_created_by', 'admin_items', ['created_by'], unique=False)

    op.create_table(
        'admin_sessions',
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.Integer(), nullable=False),
        sa.CheckConstraint('expires_at > created_at', name='ck_session_expiry'),
        sa.CheckConstraint('length(token_hash) = 64', name='ck_session_token_hash'),
        sa.ForeignKeyConstraint(['admin_id'], ['admin_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('token_hash'),
    )
    op.create_index('ix_admin_sessions_admin_id', 'admin_sessions', ['admin_id'], unique=False)
    op.create_index('ix_admin_sessions_expiry', 'admin_sessions', ['expires_at'], unique=False)

    op.create_table(
        'qa_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('requested_by', sa.Integer(), nullable=False),
        sa.Column('selected_scenarios', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), server_default='PENDING', nullable=False),
        sa.Column('requested_at', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.Integer(), nullable=True),
        sa.Column('heartbeat_at', sa.Integer(), nullable=True),
        sa.Column('lease_token', sa.Text(), nullable=True),
        sa.Column('lease_expires_at', sa.Integer(), nullable=True),
        sa.Column('finished_at', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.Text(), nullable=True),
        sa.Column('log_path', sa.Text(), nullable=True),
        sa.CheckConstraint("(status = 'FAILED') = (error_code IS NOT NULL)", name='ck_qa_run_error'),
        sa.CheckConstraint("(status = 'PENDING') = (started_at IS NULL)", name='ck_qa_run_start'),
        sa.CheckConstraint("(status = 'RUNNING' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL AND lease_expires_at >= heartbeat_at) OR (status <> 'RUNNING' AND lease_token IS NULL AND lease_expires_at IS NULL)", name='ck_qa_run_lease'),
        sa.CheckConstraint("(status IN ('COMPLETED', 'FAILED')) = (finished_at IS NOT NULL)", name='ck_qa_run_finish'),
        sa.CheckConstraint("CASE WHEN json_valid(selected_scenarios) THEN json_type(selected_scenarios) = 'array' AND json_array_length(selected_scenarios) BETWEEN 1 AND 6 ELSE 0 END", name='ck_qa_run_selected_scenarios'),
        sa.CheckConstraint("status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')", name='ck_qa_run_status'),
        sa.CheckConstraint('(started_at IS NULL OR started_at >= requested_at) AND (heartbeat_at IS NULL OR (started_at IS NOT NULL AND heartbeat_at >= started_at)) AND (finished_at IS NULL OR finished_at >= coalesce(heartbeat_at, started_at))', name='ck_qa_run_timestamps'),
        sa.ForeignKeyConstraint(['requested_by'], ['admin_users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_qa_runs_requested_by', 'qa_runs', ['requested_by'], unique=False)
    op.create_index('ix_qa_runs_status_id', 'qa_runs', ['status', 'id'], unique=False)
    op.create_index('ix_qa_runs_status_lease', 'qa_runs', ['status', 'lease_expires_at'], unique=False)

    op.create_table(
        'idempotency_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('idempotency_key', sa.Text(), nullable=False),
        sa.Column('request_hash', sa.Text(), nullable=False),
        sa.Column('response_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.CheckConstraint("CASE WHEN json_valid(response_json) THEN json_type(response_json) = 'object' ELSE 0 END", name='ck_idempotency_response_object'),
        sa.CheckConstraint('length(idempotency_key) BETWEEN 1 AND 128', name='ck_idempotency_key'),
        sa.CheckConstraint('length(request_hash) = 64', name='ck_idempotency_request_hash'),
        sa.ForeignKeyConstraint(['admin_id'], ['admin_users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['item_id'], ['admin_items.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('admin_id', 'idempotency_key', name='uq_idempotency_admin_key'),
        sa.UniqueConstraint('item_id'),
    )
    op.create_table(
        'qa_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('scenario_id', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('screenshot_path', sa.Text(), nullable=True),
        sa.CheckConstraint("scenario_id IN ('TC-N-01', 'TC-N-02', 'TC-N-03', 'TC-EX-01', 'TC-EX-02', 'TC-EX-03')", name='ck_qa_result_scenario'),
        sa.CheckConstraint("status IN ('PASS', 'FAIL', 'ERROR', 'SKIPPED')", name='ck_qa_result_status'),
        sa.CheckConstraint('duration_ms >= 0', name='ck_qa_result_duration'),
        sa.ForeignKeyConstraint(['run_id'], ['qa_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id', 'scenario_id', name='uq_qa_result_run_scenario'),
    )


def downgrade() -> None:
    op.drop_table('qa_results')
    op.drop_table('idempotency_records')
    op.drop_table('qa_runs')
    op.drop_table('admin_sessions')
    op.drop_table('admin_items')
    op.drop_table('admin_users')
