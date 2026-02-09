"""Social signal crawler integration.

Revision ID: 140
Revises: 139
Create Date: 2025-02-02
"""

from alembic import op
import sqlalchemy as sa

revision = "140"
down_revision = "139"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Social crawl run log
    op.create_table(
        "social_crawl_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("platform", sa.String(20), nullable=False, index=True),
        sa.Column("post_count", sa.Integer, nullable=False),
        sa.Column("tickers_found_json", sa.Text),
        sa.Column("errors_json", sa.Text),
        sa.Column("crawl_duration_ms", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Social post archive
    op.create_table(
        "social_posts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("platform", sa.String(20), nullable=False, index=True),
        sa.Column("author", sa.String(100)),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("tickers_json", sa.Text),
        sa.Column("sentiment", sa.Float),
        sa.Column("upvotes", sa.Integer, server_default="0"),
        sa.Column("comments", sa.Integer, server_default="0"),
        sa.Column("url", sa.Text),
        sa.Column("post_timestamp", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_social_posts_sentiment", "social_posts", ["sentiment"])


def downgrade() -> None:
    op.drop_index("ix_social_posts_sentiment", "social_posts")
    op.drop_table("social_posts")
    op.drop_table("social_crawl_runs")
