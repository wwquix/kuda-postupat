"""Reproduce the exact pre-Alembic legacy schema for a fresh database.

Existing legacy databases must be verified and stamped at this revision; its
upgrade must never be run over existing legacy tables. Downgrade is a no-op so
an operator cannot remove production history with a single command.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_legacy_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE specialties (
            id INTEGER NOT NULL,
            normalized_name VARCHAR(300) NOT NULL,
            display_name VARCHAR(300) NOT NULL,
            study_form VARCHAR(100) NOT NULL,
            funding_type VARCHAR(50) NOT NULL,
            source_url VARCHAR(1000) NOT NULL,
            active BOOLEAN NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_specialty UNIQUE (normalized_name, study_form, funding_type)
        )
        """
    )
    op.create_index("ix_specialties_normalized_name", "specialties", ["normalized_name"], unique=False)
    op.execute(
        """
        CREATE TABLE admission_snapshots (
            id INTEGER NOT NULL,
            specialty_id INTEGER NOT NULL,
            fetched_at DATETIME NOT NULL,
            source_updated_at DATETIME,
            admission_plan INTEGER NOT NULL,
            applications_total INTEGER NOT NULL,
            competition FLOAT NOT NULL,
            estimated_cutoff_min INTEGER,
            estimated_cutoff_max INTEGER,
            user_score INTEGER NOT NULL,
            estimated_user_position INTEGER,
            user_status VARCHAR(100) NOT NULL,
            distribution_json TEXT NOT NULL,
            raw_data_hash VARCHAR(64) NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(specialty_id) REFERENCES specialties (id)
        )
        """
    )
    op.create_index(
        "ix_admission_snapshots_specialty_id", "admission_snapshots", ["specialty_id"], unique=False
    )
    op.create_index("ix_admission_snapshots_fetched_at", "admission_snapshots", ["fetched_at"], unique=False)
    op.create_index(
        "ix_admission_snapshots_raw_data_hash", "admission_snapshots", ["raw_data_hash"], unique=False
    )
    op.execute(
        """
        CREATE TABLE scraper_runs (
            id INTEGER NOT NULL,
            started_at DATETIME NOT NULL,
            finished_at DATETIME,
            status VARCHAR(30) NOT NULL,
            http_status INTEGER,
            error_type VARCHAR(100),
            error_message TEXT,
            rows_found INTEGER NOT NULL,
            content_hash VARCHAR(64),
            PRIMARY KEY (id)
        )
        """
    )
    op.create_index("ix_scraper_runs_started_at", "scraper_runs", ["started_at"], unique=False)
    op.create_index("ix_scraper_runs_status", "scraper_runs", ["status"], unique=False)
    op.execute(
        """
        CREATE TABLE notification_logs (
            id INTEGER NOT NULL,
            fingerprint VARCHAR(64) NOT NULL,
            sent_at DATETIME NOT NULL,
            message TEXT NOT NULL,
            PRIMARY KEY (id)
        )
        """
    )
    op.create_index("ix_notification_logs_fingerprint", "notification_logs", ["fingerprint"], unique=True)
    op.execute(
        """
        CREATE TABLE http_cache_state (
            url VARCHAR(1000) NOT NULL,
            etag VARCHAR(500),
            last_modified VARCHAR(500),
            checked_at DATETIME,
            PRIMARY KEY (url)
        )
        """
    )


def downgrade() -> None:
    pass
