from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AdminUser(Base):
    __tablename__ = "admin_users"
    __table_args__ = (
        CheckConstraint("length(username) BETWEEN 1 AND 64", name="ck_admin_username_length"),
        CheckConstraint("failed_login_count >= 0", name="ck_admin_failed_login_count"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    failed_login_count: Mapped[int] = mapped_column(server_default=text("0"))
    login_locked_until: Mapped[int | None]
    created_at: Mapped[int]


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="ck_session_token_hash"),
        CheckConstraint("expires_at > created_at", name="ck_session_expiry"),
        Index("ix_admin_sessions_admin_id", "admin_id"),
        Index("ix_admin_sessions_expiry", "expires_at"),
    )

    token_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"))
    created_at: Mapped[int]
    expires_at: Mapped[int]


class AdminItem(Base):
    __tablename__ = "admin_items"
    __table_args__ = (
        CheckConstraint(
            "length(name) BETWEEN 1 AND 100 AND length(trim(name)) > 0 AND instr(name, char(0)) = 0",
            name="ck_admin_item_name",
        ),
        CheckConstraint(
            "length(description) <= 500 AND instr(description, char(0)) = 0",
            name="ck_admin_item_description",
        ),
        CheckConstraint("updated_at >= created_at", name="ck_admin_item_timestamps"),
        Index("ix_admin_items_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[int]
    updated_at: Mapped[int]


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("admin_id", "idempotency_key", name="uq_idempotency_admin_key"),
        CheckConstraint("length(idempotency_key) BETWEEN 1 AND 128", name="ck_idempotency_key"),
        CheckConstraint("length(request_hash) = 64", name="ck_idempotency_request_hash"),
        CheckConstraint(
            "CASE WHEN json_valid(response_json) THEN json_type(response_json) = 'object' ELSE 0 END",
            name="ck_idempotency_response_object",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="RESTRICT"))
    item_id: Mapped[int] = mapped_column(ForeignKey("admin_items.id", ondelete="RESTRICT"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(Text)
    request_hash: Mapped[str] = mapped_column(Text)
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int]


class QARun(Base):
    __tablename__ = "qa_runs"
    __table_args__ = (
        CheckConstraint(
            "CASE WHEN json_valid(selected_scenarios) THEN json_type(selected_scenarios) = 'array' "
            "AND json_array_length(selected_scenarios) BETWEEN 1 AND 6 ELSE 0 END",
            name="ck_qa_run_selected_scenarios",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')", name="ck_qa_run_status"
        ),
        CheckConstraint("(status = 'PENDING') = (started_at IS NULL)", name="ck_qa_run_start"),
        CheckConstraint(
            "(status = 'RUNNING' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND heartbeat_at IS NOT NULL AND lease_expires_at >= heartbeat_at) OR "
            "(status <> 'RUNNING' AND lease_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_qa_run_lease",
        ),
        CheckConstraint(
            "(status IN ('COMPLETED', 'FAILED')) = (finished_at IS NOT NULL)", name="ck_qa_run_finish"
        ),
        CheckConstraint("(status = 'FAILED') = (error_code IS NOT NULL)", name="ck_qa_run_error"),
        CheckConstraint(
            "(started_at IS NULL OR started_at >= requested_at) AND "
            "(heartbeat_at IS NULL OR (started_at IS NOT NULL AND heartbeat_at >= started_at)) AND "
            "(finished_at IS NULL OR finished_at >= coalesce(heartbeat_at, started_at))",
            name="ck_qa_run_timestamps",
        ),
        Index("ix_qa_runs_status_id", "status", "id"),
        Index("ix_qa_runs_status_lease", "status", "lease_expires_at"),
        Index("ix_qa_runs_requested_by", "requested_by"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="RESTRICT"))
    selected_scenarios: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="PENDING")
    requested_at: Mapped[int]
    started_at: Mapped[int | None]
    heartbeat_at: Mapped[int | None]
    lease_token: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[int | None]
    finished_at: Mapped[int | None]
    error_code: Mapped[str | None] = mapped_column(Text)
    log_path: Mapped[str | None] = mapped_column(Text)


class QAResult(Base):
    __tablename__ = "qa_results"
    __table_args__ = (
        UniqueConstraint("run_id", "scenario_id", name="uq_qa_result_run_scenario"),
        CheckConstraint(
            "scenario_id IN ('TC-N-01', 'TC-N-02', 'TC-N-03', 'TC-EX-01', 'TC-EX-02', 'TC-EX-03')",
            name="ck_qa_result_scenario",
        ),
        CheckConstraint("status IN ('PASS', 'FAIL', 'ERROR', 'SKIPPED')", name="ck_qa_result_status"),
        CheckConstraint("duration_ms >= 0", name="ck_qa_result_duration"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("qa_runs.id", ondelete="CASCADE"))
    scenario_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[int]
    detail: Mapped[str | None] = mapped_column(Text)
    screenshot_path: Mapped[str | None] = mapped_column(Text)
