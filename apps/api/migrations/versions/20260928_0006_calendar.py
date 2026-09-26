"""Add calendar connections, their calendars and OAuth state.

Revision ID: 20260928_0006
Revises: 20260927_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0006"
down_revision: str | Sequence[str] | None = "20260927_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "calendar_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("account_email", sa.String(length=320), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=40), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "provider IN ('google', 'microsoft')",
            name=op.f("ck_calendar_connections_provider_value"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'reauth_required')",
            name=op.f("ck_calendar_connections_status_value"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_calendar_connections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_connections")),
        sa.UniqueConstraint(
            "user_id", "provider", "account_email", name="calendar_connection_account"
        ),
    )
    op.create_index(op.f("ix_calendar_connections_user_id"), "calendar_connections", ["user_id"])

    op.create_table(
        "calendar_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider_calendar_id", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("is_selected", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["calendar_connections.id"],
            name=op.f("fk_calendar_sources_connection_id_calendar_connections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_calendar_sources_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_sources")),
        sa.UniqueConstraint(
            "connection_id", "provider_calendar_id", name="calendar_source_calendar"
        ),
    )
    op.create_index(
        op.f("ix_calendar_sources_connection_id"), "calendar_sources", ["connection_id"]
    )
    op.create_index(op.f("ix_calendar_sources_user_id"), "calendar_sources", ["user_id"])

    op.create_table(
        "oauth_states",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_oauth_states_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("state_hash", name=op.f("pk_oauth_states")),
    )
    op.create_index(op.f("ix_oauth_states_user_id"), "oauth_states", ["user_id"])

    op.add_column("calendar_events", sa.Column("connection_id", sa.Uuid(), nullable=True))
    op.add_column("calendar_events", sa.Column("source_id", sa.Uuid(), nullable=True))
    op.add_column("calendar_events", sa.Column("provider_event_id", sa.Text(), nullable=True))
    op.add_column(
        "calendar_events",
        sa.Column("is_all_day", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "calendar_events", sa.Column("location_label", sa.String(length=160), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_calendar_events_connection_id_calendar_connections"),
        "calendar_events",
        "calendar_connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_calendar_events_source_id_calendar_sources"),
        "calendar_events",
        "calendar_sources",
        ["source_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_calendar_events_connection_id"), "calendar_events", ["connection_id"])
    op.create_index(op.f("ix_calendar_events_source_id"), "calendar_events", ["source_id"])
    op.create_unique_constraint(
        "calendar_event_source_event", "calendar_events", ["source_id", "provider_event_id"]
    )


def downgrade() -> None:
    op.drop_constraint("calendar_event_source_event", "calendar_events", type_="unique")
    op.drop_index(op.f("ix_calendar_events_source_id"), table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_connection_id"), table_name="calendar_events")
    op.drop_constraint(
        op.f("fk_calendar_events_source_id_calendar_sources"),
        "calendar_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_calendar_events_connection_id_calendar_connections"),
        "calendar_events",
        type_="foreignkey",
    )
    op.drop_column("calendar_events", "location_label")
    op.drop_column("calendar_events", "is_all_day")
    op.drop_column("calendar_events", "provider_event_id")
    op.drop_column("calendar_events", "source_id")
    op.drop_column("calendar_events", "connection_id")

    op.drop_index(op.f("ix_oauth_states_user_id"), table_name="oauth_states")
    op.drop_table("oauth_states")
    op.drop_index(op.f("ix_calendar_sources_user_id"), table_name="calendar_sources")
    op.drop_index(op.f("ix_calendar_sources_connection_id"), table_name="calendar_sources")
    op.drop_table("calendar_sources")
    op.drop_index(op.f("ix_calendar_connections_user_id"), table_name="calendar_connections")
    op.drop_table("calendar_connections")
